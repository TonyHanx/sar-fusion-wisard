r"""Fase 8: evaluación en la prueba (FHL 0405), con las reglas confirmadas en configs/fase8.yaml.

Usa las funciones de scripts/evaluar.py (fase 6) sin cambiar sus reglas: predicciones con el validador de Ultralytics
(confianza >= 0.001, save_json), pycocotools a IoU 0.5 y maxDets 100.

Partes (cada una se detiene y espera al usuario):
- umbrales (paso 2): fija el umbral de confianza de cada modelo y peso en la validación (FHL 0134 y MtErie 0007), sin
  leer la prueba.
  - Regla: el umbral con el mayor F2, con todas las personas de WiSARD y todos los fotogramas, en la rejilla ampliada
    (`umbral.rejilla_baja` y luego `umbral.rejilla`); si hay empate, el más alto.
  - Las variantes con la RGB en 0 usan el umbral del mismo modelo y peso con la RGB real.
  - Además, el umbral de la rejilla anterior (solo `umbral.rejilla`), para la sensibilidad descriptiva de la prueba.
  - Reutiliza las predicciones de validación que ya existen (`umbral.validacion`) y hace las que faltan (rgb_base).
  - Escribe `umbral.umbrales` (una fila por modelo y peso, con el sha256 de los pesos y de las predicciones) y
    `umbral.rejilla_completa`, y una fila por modelo y peso en la bitácora. Si `umbral.umbrales` ya existe, no hace
    nada: los umbrales se fijan una sola vez.

Uso:
  .venv\Scripts\python.exe scripts\fase8_evaluar.py --config configs\fase8.yaml --rutas configs\rutas.yaml --parte umbrales
"""
import argparse
import copy
import hashlib
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import evaluar as e6
from comun import agregar_a_bitacora, fijar_semilla, leer_rutas, leer_yaml

VALIDACION = "validacion"


def ruta(p):
    return e6.ruta(p)


def rel(p):
    return e6.rel(p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leer_config(args):
    cfg = leer_yaml(args.config)
    if cfg.get("estado") != "confirmada":
        raise SystemExit(f"{args.config}: estado '{cfg.get('estado')}'; las reglas tienen que estar confirmadas.")
    base = copy.deepcopy(leer_yaml(ruta(cfg["base"])))
    val, prueba = base["particiones"][VALIDACION], base["particiones"]["prueba"]
    if set(val["vuelos"]) & set(prueba["vuelos"]):
        raise SystemExit(f"La validación incluye un vuelo de la prueba: {val['vuelos']}")
    return cfg, base


def rejillas(u):
    r = u["rejilla"]
    anterior = [float(x) for x in np.round(np.arange(r["desde"], r["hasta"] + r["paso"] / 2, r["paso"]), 2)]
    baja = [float(x) for x in u["rejilla_baja"]]
    if not baja or max(baja) >= min(anterior) or baja != sorted(baja):
        raise SystemExit("umbral.rejilla_baja tiene que ir en orden y por debajo de umbral.rejilla.")
    return baja + anterior, anterior


def armar_modelos(cfg):
    """Un modelo por nombre y peso (más las variantes con la RGB en 0), con dónde están sus predicciones de validación."""
    modelos = {}
    val = cfg["umbral"]["validacion"]
    for m, info in cfg["modelos"].items():
        if m not in val:
            raise SystemExit(f"umbral.validacion no dice dónde están las predicciones de validación de {m}.")
        for peso, archivo in cfg["pesos"]["archivos"].items():
            k = f"{m}_{peso}"
            base = {"modelo": m, "corrida": info["corrida"], "corridas": info["corridas"], "pesos": archivo,
                    "peso": peso, "fase": info["fase"], "principal": cfg["pesos"]["principal"][info["fase"]] == peso,
                    "modalidad": info["modalidad"], "datos": val[m]["datos"], "carpeta": val[m]["carpeta"],
                    "pred": val[m].get("nombres", {}).get(peso, k), "rgb0": False}
            modelos[k] = base
            if m in cfg["rgb_cero"]:
                modelos[f"{k}_rgb0"] = {**base, "rgb0": True, "umbral_de": k}
    return modelos


def umbrales(cfg, base, rutas):
    u = cfg["umbral"]
    destino, completa = ruta(u["umbrales"]), ruta(u["rejilla_completa"])
    if destino.exists():
        raise SystemExit(f"{rel(destino)} ya existe: los umbrales se fijan una sola vez.")
    rejilla, anterior = rejillas(u)
    modelos = armar_modelos(cfg)
    reales = {k: i for k, i in modelos.items() if not i["rgb0"]}
    part = base["particiones"][VALIDACION]
    print(f"Validación: {', '.join(part['vuelos'])}. La prueba no se lee en esta parte.")
    print(f"Rejilla ({len(rejilla)} umbrales): {', '.join(f'{t:g}' for t in rejilla)}")

    datos = e6.preparar(base, rutas, VALIDACION, reales)
    e6.verificar(datos, VALIDACION)
    ev = base["evaluacion"]
    gt = e6.coco_gt(datos, np.zeros(len(datos["per"]), bool))  # todas las personas de WiSARD

    filas, resumen, t0 = [], [], time.time()
    for k, info in reales.items():
        cfg_pred = {**base, "carpeta": info["carpeta"], "corridas": info["corridas"]}
        carpeta = rutas["runs"] / info["carpeta"] / VALIDACION / info["pred"]
        hecha = not (carpeta / "predictions.json").exists()
        preds, ultra = e6.predecir(info["pred"], info, cfg_pred, rutas, VALIDACION, part)
        pesos = rutas["runs"] / info["corridas"] / info["corrida"] / info["pesos"]
        if Path(ultra["pesos"]) != Path(rel(pesos)):
            raise SystemExit(f"{k}: las predicciones de {rel(carpeta)} son de {ultra['pesos']}, no de {rel(pesos)}.")
        dt = e6.coco_dt(gt, preds, datos, ev["max_dets"])
        r0 = None
        for t in rejilla:
            r = e6.evaluar(gt, dt, datos["fot"].img_id, datos, {**ev, "conf": t})
            p = r["punto"]
            filas.append({"modelo": k, "umbral": t, "en_rejilla_anterior": t in anterior, "f2": p["f2"],
                          "recall": p["recall"], "precision": p["precision"], "tp": r["tp_conf"], "fp": r["fp_conf"]})
            r0 = r0 or r
        resumen.append({"k": k, "info": info, "preds": preds, "ultra": ultra, "hecha": hecha, "pesos": pesos,
                        "pj": carpeta / "predictions.json", "map50": r0["punto"]["map50"],
                        "n_personas": r0["n_personas"], "n_fotogramas": r0["n_fotogramas"]})
        print(f"{k}: {len(preds)} predicciones ({'hechas ahora' if hecha else 'reutilizadas'}, {rel(carpeta)}); "
              f"mAP@0.5 propio {r0['punto']['map50']:.4f}", flush=True)
    tabla = pd.DataFrame(filas)

    def mejor(d):
        """La de mayor F2 (redondeado a 12 decimales); si hay empate, la de umbral más alto."""
        f2 = d.f2.fillna(-1.0).round(12)
        return d[f2 == f2.max()].sort_values("umbral").iloc[-1]

    elegido, elegido_ant = {}, {}
    for k in reales:
        d = tabla[tabla.modelo == k]
        elegido[k], elegido_ant[k] = mejor(d), mejor(d[d.en_rejilla_anterior])
    tabla["elegido"] = [elegido[m].umbral == t for m, t in zip(tabla.modelo, tabla.umbral)]
    tabla["elegido_rejilla_anterior"] = [elegido_ant[m].umbral == t for m, t in zip(tabla.modelo, tabla.umbral)]

    fijado = datetime.now().isoformat(timespec="seconds")
    salida = []
    for k, info in modelos.items():
        kr = info.get("umbral_de", k)
        e, ea = elegido[kr], elegido_ant[kr]
        s = next(x for x in resumen if x["k"] == kr)
        salida.append({
            "modelo": k, "nombre": info["modelo"], "corrida": info["corrida"], "fase": info["fase"],
            "peso": info["peso"], "principal": info["principal"], "modalidad": info["modalidad"],
            "rgb_cero": info["rgb0"], "umbral_de": kr if info["rgb0"] else "",
            "umbral": e.umbral, "en_el_piso": e.umbral == rejilla[0], "en_el_techo": e.umbral == rejilla[-1],
            "f2": e.f2, "recall": e.recall, "precision": e.precision, "tp": int(e.tp), "fp": int(e.fp),
            "umbral_rejilla_anterior": ea.umbral, "f2_rejilla_anterior": ea.f2, "recall_rejilla_anterior": ea.recall,
            "precision_rejilla_anterior": ea.precision,
            "map50_validacion": s["map50"], "n_personas": s["n_personas"], "n_fotogramas": s["n_fotogramas"],
            "pesos": rel(s["pesos"]), "pesos_sha256": sha256(s["pesos"]),
            "predicciones_validacion": rel(s["pj"]), "predicciones_sha256": sha256(s["pj"]),
            "n_predicciones": len(s["preds"]), "fijado": fijado})
    out = pd.DataFrame(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(completa, index=False)
    out.to_csv(destino, index=False)

    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.precision", 3):
        print(out[["modelo", "umbral", "en_el_piso", "f2", "recall", "precision", "umbral_rejilla_anterior",
                   "f2_rejilla_anterior", "recall_rejilla_anterior", "map50_validacion"]].to_string(index=False))
    print(f"Escrito {rel(destino)} y {rel(completa)} ({time.time() - t0:.0f} s). La prueba no se ha leído.")

    for s in resumen:
        k, info, e, ea = s["k"], s["info"], elegido[s["k"]], elegido_ant[s["k"]]
        variantes = [v for v, i in modelos.items() if i.get("umbral_de") == k]
        agregar_a_bitacora(
            rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {k}",
            f"Fase 8, paso 2: umbral en validación ({', '.join(part['vuelos'])}); pesos {rel(s['pesos'])}; "
            f"predicciones {rel(s['pj'])} ({'hechas en este paso' if s['hecha'] else 'reutilizadas'}, confianza >= "
            f"{base['prediccion']['conf']}); mayor F2 (beta {ev['beta']}) con las {s['n_personas']} personas, IoU "
            f"{ev['iou']}, maxDets {ev['max_dets']}, rejilla {rejilla[0]:g} a {rejilla[-1]:g} ({len(rejilla)} "
            f"umbrales), empate al más alto",
            f"umbral {e.umbral:g}{' (el piso de la rejilla)' if e.umbral == rejilla[0] else ''}: F2 {e.f2:.3f}, "
            f"recall {e.recall:.3f}, P {e.precision:.3f}; rejilla anterior (0.05 a 0.95): {ea.umbral:g}, F2 "
            f"{ea.f2:.3f}, recall {ea.recall:.3f}; mAP50 propio {s['map50']:.3f}"
            + (f"; también para {', '.join(variantes)}" if variantes else "")
            + f"; en {rel(destino)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["umbrales"])
    args = ap.parse_args()
    cfg, base = leer_config(args)
    rutas = leer_rutas(args.rutas)
    fijar_semilla(base["bootstrap"]["seed"])
    if args.parte == "umbrales":
        umbrales(cfg, base, rutas)


if __name__ == "__main__":
    main()
