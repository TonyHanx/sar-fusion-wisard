"""Fase 5: entrena YOLO26s desde yolo26s.pt con una corrida de configs/fase5.yaml y la registra en la bitácora.

Antes de entrenar comprueba que la laptop esté enchufada y con el plan de energía de la configuración, y que el límite
de potencia aplicado bajo carga (enforced.power.limit) llegue al mínimo. Si no, se detiene sin entrenar.

Con `inicio_cuarto_canal: promedio`, el cuarto canal de la primera capa arranca con el promedio de los pesos de los 3
canales de color. Con `azar`, queda como lo deja Ultralytics: los 3 de color con los pesos preentrenados y el cuarto al
azar.

Guarda en la carpeta de la corrida, además de lo de Ultralytics:
- monitor.csv: nvidia-smi (consumo, límite aplicado, memoria dedicada, temperatura, uso) y la RAM, cada `intervalo_s`;
- epocas.csv: por época, el lote, si hubo mosaico, el tiempo de entrenamiento y de validación y la memoria máxima de
  PyTorch;
- resumen.json: potencia, optimizador y tasa de aprendizaje que eligió Ultralytics, primera capa, memoria, tiempos y
  métricas de validación.

Uso: python scripts/entrenar.py --config configs/fase5.yaml --rutas configs/rutas.yaml --corrida fusion_lote16_2ep
"""
import argparse
import copy
import json
import math
import statistics
import subprocess
import threading
import time
import traceback
from pathlib import Path

import pandas as pd
import psutil
import torch
from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionTrainer

from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from fase0_entorno import plan_de_energia, potencia_bajo_carga

PRIMERA_CAPA = "model.0.conv.weight"
CAMPOS_GPU = ["power.draw", "enforced.power.limit", "memory.used", "memory.total", "temperature.gpu",
              "utilization.gpu", "clocks.sm"]
MIB = 2 ** 20


class Entrenador(DetectionTrainer):
    """DetectionTrainer de Ultralytics que, con inicio 'promedio', cambia el cuarto canal de la primera capa."""
    inicio_cuarto_canal = "azar"

    def get_model(self, cfg=None, weights=None, verbose=True):
        model = super().get_model(cfg=cfg, weights=weights, verbose=verbose)
        if self.inicio_cuarto_canal == "promedio":
            w = model.state_dict()[PRIMERA_CAPA]  # comparte memoria con la capa
            if w.shape[1] != 4:
                raise SystemExit(f"inicio_cuarto_canal: promedio pide 4 canales y la primera capa tiene {w.shape[1]}")
            with torch.no_grad():
                w[:, 3] = w[:, :3].mean(1)
        elif self.inicio_cuarto_canal != "azar":
            raise SystemExit(f"inicio_cuarto_canal desconocido: {self.inicio_cuarto_canal}")
        return model


def mezclar(base, cambios):
    """Copia de `base` con `cambios` encima; los diccionarios se mezclan por clave."""
    out = copy.deepcopy(base)
    for k, v in (cambios or {}).items():
        out[k] = mezclar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def numero(x):
    try:
        return float(x)
    except ValueError:
        return None


class Monitor(threading.Thread):
    """Lee nvidia-smi y la RAM cada `intervalo` segundos hasta que se le pide parar."""

    def __init__(self, intervalo):
        super().__init__(daemon=True)
        self.intervalo, self.parar, self.filas = intervalo, threading.Event(), []

    def run(self):
        t0 = time.time()
        while not self.parar.is_set():
            try:
                salida = subprocess.run(["nvidia-smi", f"--query-gpu={','.join(CAMPOS_GPU)}",
                                         "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                        timeout=10).stdout
                gpu = [numero(v.strip()) for v in salida.strip().split(",")]
            except (subprocess.SubprocessError, OSError):
                gpu = [None] * len(CAMPOS_GPU)
            vm = psutil.virtual_memory()
            self.filas.append([round(time.time() - t0, 1), *gpu, round(vm.used / MIB), vm.percent])
            self.parar.wait(self.intervalo)

    def detener(self, ruta):
        self.parar.set()
        self.join()
        df = pd.DataFrame(self.filas, columns=["s", *[c.replace(".", "_") for c in CAMPOS_GPU], "ram_usada_mib",
                                               "ram_pct"])
        df.to_csv(ruta, index=False)
        return df


class Registro:
    """Callbacks de Ultralytics: tiempo y memoria por época, optimizador elegido y primera capa."""

    def __init__(self, primera_preentrenada):
        self.pre = primera_preentrenada
        self.epocas, self.info = [], {}
        self.t_inicio = self.t_epoca = self.t_fin_entreno = self.t_fin_ultima = None
        self.mem_entreno = (0, 0)

    @staticmethod
    def _ahora():
        torch.cuda.synchronize()
        return time.perf_counter()

    def inicio(self, tr):
        self.t_inicio = time.perf_counter()

    def preparado(self, tr):
        """on_pretrain_routine_end: el modelo, la EMA y el optimizador ya existen."""
        opt = tr.optimizer
        grupos = [{"lr_inicial": g.get("initial_lr", g["lr"]), "momentum": g.get("momentum"),
                   "betas": list(g["betas"]) if "betas" in g else None, "weight_decay": g.get("weight_decay"),
                   "parametros": len(g["params"])} for g in opt.param_groups]
        n_img = len(tr.train_loader.dataset)
        iteraciones = math.ceil(n_img / max(tr.batch_size, tr.args.nbs)) * tr.epochs
        it_100 = math.ceil(n_img / max(tr.batch_size, tr.args.nbs)) * 100
        w = tr.model.state_dict()[PRIMERA_CAPA].detach().float().cpu()
        w_ema = tr.ema.ema.state_dict()[PRIMERA_CAPA].detach().float().cpu() if tr.ema else None
        capa = {"forma": list(w.shape), "forma_preentrenada": list(self.pre.shape),
                "color_igual_a_preentrenada": bool(torch.equal(w[:, :3], self.pre[:, :3])),
                "ema_igual_al_modelo": bool(w_ema is not None and torch.equal(w, w_ema)),
                "desv_color": float(w[:, :3].std())}
        if w.shape[1] == 4:
            capa |= {"desv_cuarto": float(w[:, 3].std()),
                     "max_dif_cuarto_vs_promedio_color": float((w[:, 3] - w[:, :3].mean(1)).abs().max())}
        self.info = {
            "optimizador": type(opt).__name__, "lr0": tr.args.lr0, "momentum_args": tr.args.momentum,
            "optimizer_args": tr.args.optimizer, "grupos": grupos, "acumula_lotes": tr.accumulate, "nbs": tr.args.nbs,
            "imagenes_entrenamiento": n_img, "imagenes_validacion": len(tr.test_loader.dataset),
            "lotes_por_epoca": len(tr.train_loader), "iteraciones_para_auto": iteraciones,
            "iteraciones_para_auto_100_epocas": it_100,
            "auto_con_100_epocas": "MuSGD" if it_100 > 10000 else "AdamW",
            "amp": bool(tr.amp), "lote_inicial": tr.batch_size, "trabajadores": tr.train_loader.num_workers,
            "primera_capa": capa,
        }
        print(f"[entrenar] optimizador {self.info['optimizador']} lr0={self.info['lr0']}, lote {tr.batch_size}, "
              f"AMP {self.info['amp']}; primera capa: {capa}", flush=True)

    def inicio_epoca(self, tr):
        torch.cuda.reset_peak_memory_stats()
        self.t_epoca = self._ahora()

    def fin_entreno_epoca(self, tr):
        self.t_fin_entreno = self._ahora()
        self.mem_entreno = (torch.cuda.max_memory_allocated() / MIB, torch.cuda.max_memory_reserved() / MIB)

    def fin_epoca(self, tr):
        if tr.epoch >= tr.epochs:  # final_eval de Ultralytics con best.pt: no es una época
            return
        t = self._ahora()
        cm = tr.args.close_mosaic
        self.epocas.append({
            "epoca": tr.epoch + 1, "lote": tr.batch_size,
            "mosaico": not (cm and tr.epoch >= tr.epochs - cm),
            "s_entrenamiento": round(self.t_fin_entreno - self.t_epoca, 2),
            "s_validacion_y_guardado": round(t - self.t_fin_entreno, 2),
            "s_total": round(t - self.t_epoca, 2),
            "torch_max_asignada_entreno_mib": round(self.mem_entreno[0]),
            "torch_max_reservada_entreno_mib": round(self.mem_entreno[1]),
            "torch_max_asignada_mib": round(torch.cuda.max_memory_allocated() / MIB),
            "torch_max_reservada_mib": round(torch.cuda.max_memory_reserved() / MIB),
        })
        self.t_fin_ultima = t

    def fin(self, tr):
        self.info["s_final_eval_y_graficos"] = round(time.perf_counter() - self.t_fin_ultima, 2) \
            if self.t_fin_ultima else None
        self.info["s_total_corrida"] = round(time.perf_counter() - self.t_inicio, 2)


def comprobar_potencia(cfg):
    bateria = psutil.sensors_battery()
    enchufada = bateria is None or bateria.power_plugged
    plan = plan_de_energia()
    limite, consumo = potencia_bajo_carga(cfg["segundos_carga"])
    torch.cuda.empty_cache()
    r = {"enchufada": enchufada, "plan": plan, "armoury_crate_declarado": cfg["armoury_crate"],
         "limite_mediana_w": round(statistics.median(limite), 1), "limite_min_w": round(min(limite), 1),
         "limite_max_w": round(max(limite), 1), "consumo_mediana_w": round(statistics.median(consumo), 1),
         "segundos_carga": cfg["segundos_carga"]}
    problemas = []
    if not enchufada:
        problemas.append("la laptop no está enchufada")
    if plan != cfg["plan"]:
        problemas.append(f"el plan de energía es {plan}, no {cfg['plan']}")
    if r["limite_mediana_w"] < cfg["minimo_w"]:
        problemas.append(f"el límite aplicado bajo carga es {r['limite_mediana_w']} W, menos de {cfg['minimo_w']} W")
    return r, problemas


def procesos_abiertos(nombres):
    """Los de `nombres` (sin .exe, sin distinguir mayúsculas) que están corriendo."""
    buscados = {n.lower() for n in nombres}
    abiertos = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower().removesuffix(".exe")
        if n in buscados:
            abiertos.add(n)
    return sorted(abiertos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--corrida", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.corrida not in cfg["corridas"]:
        raise SystemExit(f"No existe la corrida {args.corrida}. Hay: {', '.join(cfg['corridas'])}")
    c = mezclar(cfg["base"], cfg["corridas"][args.corrida])
    ultra = c["ultralytics"]
    datos = RAIZ / c["datos"]
    canales = leer_yaml(datos).get("channels", 3)
    if c["inicio_cuarto_canal"] == "promedio" and canales != 4:
        raise SystemExit("inicio_cuarto_canal: promedio solo tiene sentido con 4 canales")

    abiertos = procesos_abiertos(cfg.get("cerrar_antes", []))
    if abiertos:
        raise SystemExit(f"No se entrena: cierra antes {', '.join(abiertos)} (cerrar_antes en {args.config}).")
    potencia, problemas = comprobar_potencia(cfg["potencia"])
    print(f"Potencia: {potencia}")
    if problemas:
        raise SystemExit("No se entrena: " + "; ".join(problemas) + ". Revisa la laptop y vuelve a correr.")
    potencia["ram_antes_mib"] = round(psutil.virtual_memory().used / 2 ** 20)
    potencia["cerradas"] = cfg.get("cerrar_antes", [])

    modelo = YOLO(str(RAIZ / c["pesos"]))
    pre = modelo.model.state_dict()[PRIMERA_CAPA].detach().float().cpu().clone()
    reg = Registro(pre)
    for evento, fn in [("on_pretrain_routine_start", reg.inicio), ("on_pretrain_routine_end", reg.preparado),
                       ("on_train_epoch_start", reg.inicio_epoca), ("on_train_epoch_end", reg.fin_entreno_epoca),
                       ("on_fit_epoch_end", reg.fin_epoca), ("on_train_end", reg.fin)]:
        modelo.add_callback(evento, fn)
    Entrenador.inicio_cuarto_canal = c["inicio_cuarto_canal"]

    monitor = Monitor(cfg["monitor"]["intervalo_s"])
    monitor.start()
    error = None
    try:
        modelo.train(trainer=Entrenador, data=str(datos), project=str(rutas["runs"] / c["carpeta"]), name=args.corrida,
                     exist_ok=False, **ultra)
    except Exception as e:  # se registra en la bitácora y se vuelve a lanzar
        error = e
        traceback.print_exc()
    tr = modelo.trainer
    carpeta = Path(tr.save_dir) if tr is not None else rutas["runs"] / c["carpeta"] / args.corrida
    carpeta.mkdir(parents=True, exist_ok=True)
    mon = monitor.detener(carpeta / "monitor.csv")
    pd.DataFrame(reg.epocas).to_csv(carpeta / "epocas.csv", index=False)

    total_mib = mon["memory_total"].dropna().max()
    pico_mib = mon["memory_used"].dropna().max()
    lote_pedido = ultra["batch"]
    lote_final = tr.batch_size if tr is not None else None
    entra = (error is None and lote_final == lote_pedido
             and pico_mib <= cfg["memoria"]["fraccion_maxima"] * total_mib)
    bajo_carga = mon[mon["utilization_gpu"] >= 50]
    resumen = {
        "corrida": args.corrida, "configuracion": c, "canales": canales, "carpeta": str(carpeta),
        "potencia_antes": potencia, **reg.info, "lote_pedido": lote_pedido, "lote_final": lote_final,
        "entra": bool(entra), "error": repr(error) if error else None,
        "gpu_pico_memoria_mib": pico_mib, "gpu_memoria_total_mib": total_mib,
        "gpu_limite_aplicado_mediana_w": float(bajo_carga["enforced_power_limit"].median()) if len(bajo_carga) else None,
        "gpu_consumo_mediana_w": float(bajo_carga["power_draw"].median()) if len(bajo_carga) else None,
        "gpu_temperatura_max": mon["temperature_gpu"].max(),
        "ram_pico_mib": int(mon["ram_usada_mib"].max()), "ram_pico_pct": float(mon["ram_pct"].max()),
        "epocas": reg.epocas,
    }
    if error is None:
        res = pd.read_csv(carpeta / "results.csv")
        res.columns = [k.strip() for k in res.columns]
        ultima = res.iloc[-1]
        mejor = res.loc[res["metrics/mAP50(B)"].idxmax()]
        claves = ["metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)"]
        resumen["val_ultima_epoca"] = {k: float(ultima[k]) for k in claves} | {"epoca": int(ultima["epoch"])}
        resumen["val_mejor_epoca_map50"] = {k: float(mejor[k]) for k in claves} | {"epoca": int(mejor["epoch"])}
        resumen["val_best_pt"] = {k: float(v) for k, v in tr.metrics.items() if k in claves}
        args_yaml = leer_yaml(carpeta / "args.yaml")
        resumen["args_yaml"] = {k: args_yaml.get(k) for k in ["optimizer", "lr0", "momentum", "lrf", "weight_decay",
                                                              "warmup_epochs", "close_mosaic", "batch", "seed"]}
        ckpt = torch.load(carpeta / "weights" / "last.pt", map_location="cpu", weights_only=False)
        ta = ckpt.get("train_args", {})
        resumen["train_args_last_pt"] = {k: ta.get(k) for k in ["optimizer", "lr0", "momentum", "batch"]}
    with open(carpeta / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    # Bitácora
    tiempos = [e["s_total"] for e in reg.epocas]
    config_txt = (f"corrida {args.corrida}; {c['datos']} ({canales} canales); pesos {c['pesos']}; "
                  + ", ".join(f"{k}={v}" for k, v in ultra.items())
                  + (f"; cuarto canal: {c['inicio_cuarto_canal']}" if canales == 4 else "")
                  + (f"; optimizador {reg.info['optimizador']} lr0={reg.info['lr0']} (auto)" if reg.info else "")
                  + f"; potencia bajo carga {potencia['limite_mediana_w']} W; {carpeta.relative_to(RAIZ).as_posix()}")
    if error is None:
        v = resumen["val_ultima_epoca"]
        res_txt = (f"{'entra' if entra else 'no entra'} (lote {lote_final}); pico de memoria GPU {pico_mib:.0f} de "
                   f"{total_mib:.0f} MiB; tiempo por época {', '.join(f'{t:.0f}' for t in tiempos)} s; "
                   f"val época {v['epoca']}: mAP50 {v['metrics/mAP50(B)']:.4f}, mAP50-95 {v['metrics/mAP50-95(B)']:.4f}, "
                   f"P {v['metrics/precision(B)']:.3f}, R {v['metrics/recall(B)']:.3f}")
    else:
        res_txt = f"error: {repr(error)[:300]}; pico de memoria GPU {pico_mib:.0f} de {total_mib:.0f} MiB"
    lim = resumen["gpu_limite_aplicado_mediana_w"]
    res_txt += (f"; límite aplicado de la GPU al entrenar (mediana) {lim:.1f} W" if lim else "")         + f"; pico de RAM {resumen['ram_pico_pct']:.1f} %"
    agregar_a_bitacora(rutas["bitacora"], c["fase"], f"YOLO26s {Path(c['datos']).stem}", config_txt, res_txt)
    print(json.dumps({k: resumen[k] for k in ["entra", "lote_final", "gpu_pico_memoria_mib", "optimizador", "lr0"]
                      if k in resumen}, ensure_ascii=False))
    print(f"Resumen en {carpeta / 'resumen.json'}")
    if error is not None:
        raise error


if __name__ == "__main__":
    main()
