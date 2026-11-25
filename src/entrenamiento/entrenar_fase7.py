"""Fase 7, C2 y C3: entrena YOLO26s con la receta de la fase 7 (sección `c3` de configs/fase7.yaml).

Reutiliza de src/entrenamiento/entrenar.py, sin cambiarlo, las comprobaciones previas (aplicaciones cerradas, enchufe,
plan de
energía y potencia; los valores son los de `c3.comprobaciones`), el monitor de nvidia-smi y la RAM, el registro por
época y el inicio del cuarto canal. Lo nuevo de la receta (C2):
- **Criterio de la mejor época:** best.pt y la parada temprana (`patience`; con 0 no hay) van por el mAP@0.5 de
  validación (`c2.fitness`), no por el fitness de Ultralytics (el mAP@0.5:0.95). last.pt queda con la última época.
  resumen.json y la bitácora llevan la última época, el promedio de las `c3.ultimas_epocas` últimas (la cifra
  principal en C4) y best.pt (secundaria).
- **Dropout de modalidad:** en la fusión, cada imagen de entrenamiento pierde la RGB (los 3 canales de color en 0) con
  probabilidad `p_sin_rgb` (src/entrenamiento/dropout_modalidad.py). Nunca en la validación. Con p = 0, el dataset es el
  de Ultralytics.

Antes de entrenar comprueba que la carpeta de la corrida no exista y que ni el entrenamiento ni la validación tengan
imágenes de FHL 0405/0406 (la prueba). Guarda lo mismo que src/entrenamiento/entrenar.py (monitor.csv, epocas.csv,
resumen.json); monitor.csv y epocas.csv, además, al final de cada época, por si el proceso se corta, y en resumen.json además la época elegida, la última, el promedio de las últimas y si paró antes.

Con --verificar no entrena: comprueba el criterio (con un validador simulado) y el dropout con `c2.verificacion.imagenes`
imágenes, y escribe runs/<carpeta>/c2/verificacion_*.csv.

Uso:
  .venv\\Scripts\\python.exe -m src.entrenamiento.entrenar_fase7 --config configs\\fase7.yaml --rutas configs\\rutas.yaml --verificar
  .venv\\Scripts\\python.exe -m src.entrenamiento.entrenar_fase7 --config configs\\fase7.yaml --rutas configs\\rutas.yaml --corrida termico_base
"""
import argparse
import json
import os
import random
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import psutil
import tifffile
import torch
from ultralytics import YOLO
from ultralytics.data.dataset import YOLODataset

import src.entrenamiento.entrenar as entrenar_fase5
from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, ruta_del_dataset
from src.entrenamiento.dropout_modalidad import DatasetSinRGB, quitar_rgb

CLAVES = ["metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)"]


def ruta(p):
    """Ruta absoluta: si es relativa, desde la raíz del repositorio."""
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


class EntrenadorFase7(entrenar_fase5.Entrenador):
    """El Entrenador de la fase 5 (cuarto canal) con la mejor época por `clave_fitness` y el dropout de modalidad."""
    clave_fitness = "metrics/mAP50(B)"
    p_sin_rgb = 0.0

    def validate(self):
        """Como BaseTrainer.validate, pero el fitness (best.pt, best_fitness y parada temprana) es `clave_fitness`."""
        if self.world_size > 1:
            raise RuntimeError("La receta de la fase 7 es para una sola GPU")
        metrics = self.validator(self)
        if metrics is None:
            return None, None
        metrics.pop("fitness", None)
        fitness = metrics[self.clave_fitness]
        if self.best_fitness is None or self.best_fitness < fitness:
            self.best_fitness = fitness
        return metrics, fitness

    def build_dataset(self, img_path, mode="train", batch=None):
        """Arma el dataset como Ultralytics y, solo en el entrenamiento, le aplica el dropout de modalidad (quita la RGB
        con probabilidad `p_sin_rgb`)."""
        ds = super().build_dataset(img_path, mode, batch)
        return quitar_rgb(ds, self.p_sin_rgb) if mode == "train" else ds


COLUMNAS_MONITOR = ["s", *[c.replace(".", "_") for c in entrenar_fase5.CAMPOS_GPU], "ram_usada_mib", "ram_pct"]  # las de en.Monitor


def escribir_csv(df, ruta):
    """Escribe en un temporal y lo cambia de nombre: si el proceso se corta, queda el archivo anterior entero."""
    tmp = Path(ruta).with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, ruta)


class MonitorFase7(entrenar_fase5.Monitor):
    """El monitor de la fase 5, que además puede guardar lo leído hasta ahora sin pararse."""

    def guardar(self, ruta):
        """Guarda las lecturas hasta ahora en monitor.csv, sin parar el hilo."""
        escribir_csv(pd.DataFrame(list(self.filas), columns=COLUMNAS_MONITOR), ruta)


class RegistroFase7(entrenar_fase5.Registro):
    """El registro de la fase 5, sin la fila de más de la validación final de best.pt cuando la corrida para antes,
    y que al final de cada época guarda epocas.csv y monitor.csv (si tiene `monitor`) en la carpeta de la corrida. Así,
    si el proceso se corta, quedan hasta la última época terminada. Solo escribe archivos: no cambia el entrenamiento,
    y lo hace después de medir el tiempo de la época."""
    monitor = None

    def inicio_epoca(self, tr):
        """Como en la fase 5, y además recuerda qué época está en curso."""
        super().inicio_epoca(tr)
        self.epoca_en_curso = tr.epoch

    def fin_epoca(self, tr):
        """Como en la fase 5, pero ignora la evaluación final de best.pt y guarda epocas.csv y monitor.csv al final de
        cada época, por si el proceso se corta."""
        if tr.epoch != getattr(self, "epoca_en_curso", None):  # final_eval sube tr.epoch en 1 para registrar best.pt
            return
        super().fin_epoca(tr)
        carpeta = Path(tr.save_dir)
        escribir_csv(pd.DataFrame(self.epocas), carpeta / "epocas.csv")
        if self.monitor is not None:
            self.monitor.guardar(carpeta / "monitor.csv")


def prohibidos(cfg):
    """Prefijos de imagen que no pueden estar en ningún entrenamiento ni validación: los vuelos de la prueba."""
    part = leer_yaml(ruta(cfg["c1"]["particion"]))
    return set(cfg["prohibidas"]) | set(part["prueba"])


def comprobar_datos(datos_yaml, cfg):
    """Lee el yaml del dataset y se detiene si el entrenamiento o la validación tienen alguna imagen de los vuelos de la
    prueba. Devuelve el contenido del yaml."""
    datos = leer_yaml(datos_yaml)
    prefijos_prohibidos = prohibidos(cfg)
    malos = []
    for split in ("train", "val"):
        for imagen in (ruta_del_dataset(datos) / datos[split]).iterdir():
            if any(x in imagen.stem for x in prefijos_prohibidos):
                malos.append(f"{split}/{imagen.name}")
    if malos:
        raise SystemExit(f"{datos_yaml}: {len(malos)} imágenes de la prueba, por ejemplo {malos[:3]}. No se entrena.")
    return datos


# ------------------------------------------------------------------------------------------------------- verificación

def verificar(cfg, rutas):
    """Sin entrenar, comprueba el criterio de la mejor época con un validador simulado y el dropout de modalidad con
    unas imágenes, y escribe las tablas de verificación."""
    cfg_verif = cfg["c2"]["verificacion"]
    c3 = cfg["c3"]
    carpeta_salida = rutas["runs"] / cfg["carpeta"] / cfg_verif["carpeta"]
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    datos = ruta(cfg_verif["datos"])
    comprobar_datos(datos, cfg)
    EntrenadorFase7.clave_fitness = cfg["c2"]["fitness"]
    ultra = dict(c3["base"]["ultralytics"])
    entrenador = EntrenadorFase7(overrides={**ultra, "model": str(ruta(c3["pesos"])), "data": str(datos),
                                    "project": str(carpeta_salida), "name": "entrenador", "exist_ok": True})
    entrenador.model = SimpleNamespace(stride=torch.tensor([8.0, 16.0, 32.0]))  # build_dataset solo usa el paso del modelo

    # 1. criterio: un validador simulado con dos épocas en que el mAP@0.5 y el mAP@0.5:0.95 eligen distinto
    simuladas = [{"metrics/mAP50(B)": 0.30, "metrics/mAP50-95(B)": 0.10, "fitness": 0.10},
           {"metrics/mAP50(B)": 0.25, "metrics/mAP50-95(B)": 0.12, "fitness": 0.12}]
    entrenador.best_fitness = None
    filas_f = []
    for k, m in enumerate(simuladas, 1):
        entrenador.validator = lambda trainer, m=m: dict(m)
        metrics, fit = entrenador.validate()
        filas_f.append({"epoca": k, "map50": m["metrics/mAP50(B)"], "map50_95": m["metrics/mAP50-95(B)"],
                        "fitness_ultralytics": m["fitness"], "fitness_fase7": fit, "best_fitness": entrenador.best_fitness,
                        "fitness_en_metricas": "fitness" in metrics})
    from ultralytics.utils.torch_utils import EarlyStopping

    # parada temprana con la `patience` de la receta: la época 1 es la mejor y las demás no mejoran. Con patience = 0,
    # Ultralytics no para nunca (EarlyStopping usa `patience or inf`); se prueba con todas las épocas de la receta.
    parada = EarlyStopping(patience=ultra["patience"])
    largo = ultra["patience"] + 1 if ultra["patience"] else ultra["epochs"]
    serie = [0.30] + [0.25] * largo
    para = next((e for e, f in enumerate(serie, 1) if parada(e, f)), None)
    esperada = ultra["patience"] + 1 if ultra["patience"] else None
    fit = pd.DataFrame(filas_f)
    fit["patience"] = ultra["patience"]
    fit["epocas_probadas"] = len(serie)
    fit["parada_temprana_en_epoca"] = para
    fit.to_csv(carpeta_salida / "verificacion_fitness.csv", index=False)
    if not (fit.fitness_fase7.tolist() == [0.30, 0.25] and fit.best_fitness.tolist() == [0.30, 0.30]
            and not fit.fitness_en_metricas.any() and para == esperada):
        raise SystemExit(f"El criterio no hace lo esperado:\n{fit}")

    # 2. dropout: los datasets como los arma el entrenador, con las mismas imágenes y la misma semilla
    def armar(split, modo, p):
        """Arma el dataset de `split` con la probabilidad de quitar la RGB `p`."""
        entrenador.p_sin_rgb = p
        return entrenador.build_dataset(entrenador.data[split], mode=modo, batch=ultra["batch"])

    p = cfg_verif["p"]
    base_tr = armar("train", "train", 0.0)
    rng = np.random.default_rng(cfg_verif["seed"])
    idx = sorted(int(i) for i in rng.choice(len(base_tr), cfg_verif["imagenes"], replace=False))
    filas = []

    def fila(prueba, ds, i, img, ref_tiff, esperado_sin_rgb):
        """img: H, W, C (load_image) o C, H, W (tensor del modelo), los dos en R, G, B, T (con 4 canales Ultralytics no
        invierte el orden); ref_tiff: el TIFF leído con tifffile, en el orden del archivo (B, G, R, T)."""
        ref = ref_tiff[..., [2, 1, 0, 3]]
        if img.shape[0] == 4:  # tensor del modelo: se recorta el centro del LetterBox
            th, tw = ref.shape[:2]
            y0, x0 = (img.shape[1] - th) // 2, (img.shape[2] - tw) // 2
            t = img[:, y0:y0 + th, x0:x0 + tw].transpose(1, 2, 0)
        else:
            t = img
        sin_rgb = int(t[..., :3].max()) == 0  # dentro de la imagen, sin el relleno gris del LetterBox
        if esperado_sin_rgb is None:  # no se sabe de antemano (la lectura gasta otros números al azar)
            esperado_sin_rgb = sin_rgb
        ok_t = np.array_equal(t[..., 3], ref[..., 3])
        ok_rgb = sin_rgb if esperado_sin_rgb else np.array_equal(t[..., :3], ref[..., :3])
        filas.append({"prueba": prueba, "clase": type(ds).__name__, "p": getattr(ds, "p_sin_rgb", 0.0),
                      "indice": i, "imagen": Path(ds.im_files[i]).name, "forma": tuple(img.shape),
                      "rgb_en_0": sin_rgb, "termica_igual": ok_t, "rgb_como_se_espera": ok_rgb})

    tiff = {i: tifffile.imread(base_tr.im_files[i]) for i in idx}

    # 2a. entrenamiento con p: imagen leída (donde actúa el dropout), contra la del dataset sin dropout
    # (la lectura solo gasta el número al azar del dropout: se sabe de antemano qué imágenes pierden la RGB)
    ds = armar("train", "train", p)
    random.seed(cfg_verif["seed"])
    esperado = [random.random() < p for _ in idx]
    random.seed(cfg_verif["seed"])
    for i, e in zip(idx, esperado):
        fila(f"entrenamiento, p = {p}, imagen leída", ds, i, ds.load_image(i)[0], tiff[i], e)
    # 2b. entrenamiento con p = 1 y todas las transformaciones (mosaico incluido), contra el mismo dataset sin dropout
    # con las mismas semillas (p = 1 no gasta números al azar, así que los aumentos son los mismos). Ultralytics
    # rellena con gris (`relleno`) en los 4 canales lo que queda fuera de las imágenes, así que la RGB que llega al
    # modelo tiene que ser gris (R = G = B) y no más clara que el relleno, y la térmica, la misma.
    gris = cfg_verif["relleno"]
    ds1, ds0 = armar("train", "train", 1.0), armar("train", "train", 0.0)
    for i in idx:
        t = {}
        for k, dataset_k in ((1, ds1), (0, ds0)):
            random.seed(cfg_verif["seed"] + i)
            np.random.seed(cfg_verif["seed"] + i)
            torch.manual_seed(cfg_verif["seed"] + i)
            t[k] = dataset_k[i]["img"].numpy()
        rgb = t[1][:3]
        es_gris = bool((rgb[0] == rgb[1]).all() and (rgb[1] == rgb[2]).all())
        filas.append({"prueba": "entrenamiento, p = 1, tensor con mosaico", "clase": type(ds1).__name__, "p": 1.0,
                      "indice": i, "imagen": Path(ds1.im_files[i]).name, "forma": tuple(t[1].shape),
                      "rgb_en_0": es_gris and int(rgb.max()) <= gris,
                      "termica_igual": bool(np.array_equal(t[1][3], t[0][3])),
                      "rgb_como_se_espera": es_gris and int(rgb.max()) <= gris,
                      "sin_dropout_rgb_gris": bool((t[0][0] == t[0][1]).all() and (t[0][1] == t[0][2]).all()),
                      "pixeles_rgb_no_0": round(float((rgb.max(0) > 0).mean()), 4),
                      "pixeles_relleno_sin_dropout": round(float((t[0] == gris).all(0).mean()), 4)})
    # 2c. entrenamiento con p = 0: el entrenador deja el dataset de Ultralytics
    ds = armar("train", "train", 0.0)
    filas.append({"prueba": "entrenamiento, p = 0", "clase": type(ds).__name__, "p": 0.0, "indice": None,
                  "imagen": None, "forma": None, "rgb_en_0": None, "termica_igual": None,
                  "rgb_como_se_espera": type(ds) is YOLODataset})
    # 2d. el tensor tal como entra al modelo, sin aumentos (la lectura de la validación), con p
    ds = quitar_rgb(armar("train", "val", 0.0), p)
    random.seed(cfg_verif["seed"])
    for i in idx:
        fila(f"tensor del modelo sin aumentos, p = {p}", ds, i, ds[i]["img"].numpy(), tiff[i], None)
    # 2e. validación armada por el entrenador con p: nunca hay dropout
    ds = armar("val", "val", p)
    rng_v = np.random.default_rng(cfg_verif["seed"])
    for i in sorted(int(j) for j in rng_v.choice(len(ds), cfg_verif["imagenes"], replace=False)):
        t = ds[i]["img"].numpy()
        fila(f"validación del entrenamiento, p = {p}", ds, i, t, tifffile.imread(ds.im_files[i]), False)
    # 2f. la evaluación con la RGB en 0 (evaluar.py --rgb-cero): p = 1 en la lectura de la validación
    ds = quitar_rgb(armar("val", "val", 0.0), 1.0)
    for i in sorted(int(j) for j in np.random.default_rng(cfg_verif["seed"]).choice(len(ds), cfg_verif["imagenes"], replace=False)):
        t = ds[i]["img"].numpy()
        fila("evaluación con la RGB en 0 (p = 1)", ds, i, t, tifffile.imread(ds.im_files[i]), True)

    tabla_verificacion = pd.DataFrame(filas)
    tabla_verificacion.to_csv(carpeta_salida / "verificacion_dropout.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 60):
        print(fit.to_string(index=False))
        print(tabla_verificacion.to_string(index=False))
    res = tabla_verificacion.groupby("prueba", sort=False).agg(imagenes=("indice", "count"), rgb_en_0=("rgb_en_0", "sum"),
                                                bien=("rgb_como_se_espera", "all"))
    print(res.to_string())
    malas = tabla_verificacion[(tabla_verificacion.rgb_como_se_espera == False) | (tabla_verificacion.termica_igual == False)]  # noqa: E712
    entreno = tabla_verificacion[tabla_verificacion.prueba.str.startswith("entrenamiento, p = 0.")]
    if len(malas) or not (tabla_verificacion.clase[tabla_verificacion.prueba.str.startswith("validación")] == "YOLODataset").all():
        raise SystemExit(f"El dropout no hace lo esperado:\n{malas}")
    print(f"Bien: criterio por mAP@0.5 y dropout. Con p = {p}, {int(entreno.rgb_en_0.sum())} de {len(entreno)} "
          f"imágenes de entrenamiento quedaron sin RGB. Salidas en {carpeta_salida}")


# ------------------------------------------------------------------------------------------------------- entrenamiento

def entrenar(cfg, rutas, nombre):
    """Entrena una corrida de la fase 7: hace las comprobaciones previas, entrena con la receta de C2 y escribe
    resumen.json, epocas.csv, monitor.csv y la fila de la bitácora."""
    c3 = cfg["c3"]
    comprobaciones = leer_yaml(ruta(c3["comprobaciones"]))
    codigos = comprobaciones["codigos_salida"]

    def salir(mensaje, codigo):
        """Escribe el motivo en la salida de errores y termina con el código dado (`codigos_salida` de las
        comprobaciones)."""
        print(mensaje, file=sys.stderr, flush=True)
        sys.exit(codigo)

    if nombre not in c3["corridas"]:
        salir(f"No existe la corrida {nombre}. Hay: {', '.join(c3['corridas'])}", codigos["otro"])
    corrida_cfg = entrenar_fase5.mezclar(c3["base"], c3["corridas"][nombre])
    ultra = corrida_cfg["ultralytics"]
    datos = ruta(corrida_cfg["datos"])
    datos_cfg = comprobar_datos(datos, cfg)
    canales = datos_cfg.get("channels", 3)
    if corrida_cfg["inicio_cuarto_canal"] == "promedio" and canales != 4:
        salir("inicio_cuarto_canal: promedio solo tiene sentido con 4 canales", codigos["otro"])
    if corrida_cfg["p_sin_rgb"] and canales != 4:
        salir("El dropout de modalidad (p_sin_rgb) pide 4 canales", codigos["otro"])
    carpeta_corrida = rutas["runs"] / c3["carpeta"] / nombre
    if carpeta_corrida.exists():
        salir(f"No se entrena: ya existe {carpeta_corrida} (Ultralytics la renombraría). Muévela antes.",
              codigos["carpeta_existe"])
    abiertos = entrenar_fase5.procesos_abiertos(comprobaciones.get("cerrar_antes", []))
    if abiertos:
        salir(f"No se entrena: cierra antes {', '.join(abiertos)} (cerrar_antes en {c3['comprobaciones']}).",
              codigos["aplicaciones"])
    potencia, problemas = entrenar_fase5.comprobar_potencia(comprobaciones["potencia"])
    print(f"Potencia: {potencia}", flush=True)
    if problemas:
        salir("No se entrena: " + "; ".join(problemas) + ". Revisa la laptop y vuelve a correr.", codigos["potencia"])
    potencia["ram_antes_mib"] = round(psutil.virtual_memory().used / 2 ** 20)
    potencia["cerradas"] = comprobaciones.get("cerrar_antes", [])

    modelo = YOLO(str(ruta(c3["pesos"])))
    primera_capa_pre = modelo.model.state_dict()[entrenar_fase5.PRIMERA_CAPA].detach().float().cpu().clone()
    registro = RegistroFase7(primera_capa_pre)
    for evento, funcion in [("on_pretrain_routine_start", registro.inicio), ("on_pretrain_routine_end", registro.preparado),
                       ("on_train_epoch_start", registro.inicio_epoca), ("on_train_epoch_end", registro.fin_entreno_epoca),
                       ("on_fit_epoch_end", registro.fin_epoca), ("on_train_end", registro.fin)]:
        modelo.add_callback(evento, funcion)
    EntrenadorFase7.inicio_cuarto_canal = corrida_cfg["inicio_cuarto_canal"]
    EntrenadorFase7.clave_fitness = cfg["c2"]["fitness"]
    EntrenadorFase7.p_sin_rgb = float(corrida_cfg["p_sin_rgb"])

    monitor = MonitorFase7(comprobaciones["monitor"]["intervalo_s"])
    registro.monitor = monitor  # epocas.csv y monitor.csv se guardan al final de cada época
    monitor.start()
    error = None
    try:
        modelo.train(trainer=EntrenadorFase7, data=str(datos), project=str(rutas["runs"] / c3["carpeta"]), name=nombre,
                     exist_ok=False, **ultra)
    except Exception as e:  # se registra en la bitácora y se vuelve a lanzar
        error = e
        traceback.print_exc()
    entrenador = modelo.trainer
    carpeta = Path(entrenador.save_dir) if entrenador is not None else carpeta_corrida
    carpeta.mkdir(parents=True, exist_ok=True)
    lecturas = monitor.detener(carpeta / "monitor.csv")
    pd.DataFrame(registro.epocas).to_csv(carpeta / "epocas.csv", index=False)

    total_mib = lecturas["memory_total"].dropna().max()
    pico_mib = lecturas["memory_used"].dropna().max()
    lote_final = entrenador.batch_size if entrenador is not None else None
    entra = (error is None and lote_final == ultra["batch"]
             and pico_mib <= comprobaciones["memoria"]["fraccion_maxima"] * total_mib)
    # Lecturas con la GPU al 50 % o más: las del entrenamiento, sin el arranque ni las pausas entre épocas. De ellas
    # sale el límite aplicado real (mediana) que se registra en cada corrida (CLAUDE.md, "Potencia").
    bajo_carga = lecturas[lecturas["utilization_gpu"] >= 50]
    resumen = {
        "corrida": nombre, "configuracion": corrida_cfg, "canales": canales, "carpeta": str(carpeta),
        "fitness": EntrenadorFase7.clave_fitness, "p_sin_rgb": EntrenadorFase7.p_sin_rgb,
        "potencia_antes": potencia, **registro.info, "lote_pedido": ultra["batch"], "lote_final": lote_final,
        "entra": bool(entra), "error": repr(error) if error else None,
        "gpu_pico_memoria_mib": pico_mib, "gpu_memoria_total_mib": total_mib,
        "gpu_limite_aplicado_mediana_w": float(bajo_carga["enforced_power_limit"].median()) if len(bajo_carga) else None,
        "gpu_consumo_mediana_w": float(bajo_carga["power_draw"].median()) if len(bajo_carga) else None,
        "gpu_temperatura_max": lecturas["temperature_gpu"].max(),
        "ram_pico_mib": int(lecturas["ram_usada_mib"].max()), "ram_pico_pct": float(lecturas["ram_pct"].max()),
        "epocas": registro.epocas,
    }
    if error is None:
        resultados = pd.read_csv(carpeta / "results.csv")
        resultados.columns = [k.strip() for k in resultados.columns]
        ultima = resultados.iloc[-1]
        elegida = resultados.loc[resultados[EntrenadorFase7.clave_fitness].idxmax()]  # la primera, si hay empate (como best.pt)
        resumen["val_elegida"] = {k: float(elegida[k]) for k in CLAVES} | {"epoca": int(elegida["epoch"])}
        resumen["val_ultima_epoca"] = {k: float(ultima[k]) for k in CLAVES} | {"epoca": int(ultima["epoch"])}
        n_ultimas = c3["ultimas_epocas"]
        ultimas = resultados.tail(n_ultimas)
        resumen["val_promedio_ultimas"] = {k: float(ultimas[k].mean()) for k in CLAVES} | {
            "epocas": [int(e) for e in ultimas["epoch"]]}
        resumen["epocas_corridas"] = len(resultados)
        resumen["paro_antes"] = len(resultados) < ultra["epochs"]
        resumen["val_best_pt_final_eval"] = {k: float(v) for k, v in entrenador.metrics.items() if k in CLAVES}
        best = torch.load(carpeta / "weights" / "best.pt", map_location="cpu", weights_only=False)
        metricas_best = best.get("train_metrics", {})
        resumen["best_pt_train_metrics"] = {k: metricas_best.get(k) for k in CLAVES + ["fitness"]}
        resumen["best_pt_es_la_elegida"] = bool(np.isclose(metricas_best.get("fitness", np.nan),
                                                           elegida[EntrenadorFase7.clave_fitness], atol=1e-5))
        args_yaml = leer_yaml(carpeta / "args.yaml")
        resumen["args_yaml"] = {k: args_yaml.get(k) for k in ["optimizer", "lr0", "momentum", "lrf", "weight_decay",
                                                              "warmup_epochs", "warmup_bias_lr", "close_mosaic",
                                                              "batch", "seed", "patience", "epochs"]}
    with open(carpeta / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    tiempos = [e["s_total"] for e in registro.epocas]
    config_txt = (f"corrida {nombre}; {corrida_cfg['datos']} ({canales} canales); pesos {c3['pesos']}; "
                  + ", ".join(f"{k}={v}" for k, v in ultra.items())
                  + f"; mejor época por {EntrenadorFase7.clave_fitness}"
                  + (f"; cuarto canal: {corrida_cfg['inicio_cuarto_canal']}; dropout de modalidad p={corrida_cfg['p_sin_rgb']}"
                     if canales == 4 else "")
                  + (f"; optimizador {registro.info['optimizador']} lr0={registro.info['lr0']}" if registro.info else "")
                  + f"; potencia bajo carga {potencia['limite_mediana_w']} W; {carpeta.relative_to(RAIZ).as_posix()}")
    if error is None:
        e, ultima_val, promedio_ultimas = resumen["val_elegida"], resumen["val_ultima_epoca"], resumen["val_promedio_ultimas"]
        res_txt = (f"{'entra' if entra else 'no entra'} (lote {lote_final}); {resumen['epocas_corridas']} épocas"
                   f"{' (paró antes, patience)' if resumen['paro_antes'] else ''}; pico de memoria GPU {pico_mib:.0f} de "
                   f"{total_mib:.0f} MiB; mediana por época {np.median(tiempos):.0f} s; "
                   f"val última época {ultima_val['epoca']}: mAP50 {ultima_val['metrics/mAP50(B)']:.4f}, mAP50-95 "
                   f"{ultima_val['metrics/mAP50-95(B)']:.4f}, P {ultima_val['metrics/precision(B)']:.3f}, R {ultima_val['metrics/recall(B)']:.3f}; "
                   f"promedio de las épocas {promedio_ultimas['epocas'][0]}-{promedio_ultimas['epocas'][-1]}: mAP50 {promedio_ultimas['metrics/mAP50(B)']:.4f}, "
                   f"mAP50-95 {promedio_ultimas['metrics/mAP50-95(B)']:.4f}; best.pt (época {e['epoca']}): mAP50 "
                   f"{e['metrics/mAP50(B)']:.4f}, mAP50-95 {e['metrics/mAP50-95(B)']:.4f}; best.pt es la elegida: "
                   f"{'sí' if resumen['best_pt_es_la_elegida'] else 'NO'}")
    else:
        res_txt = f"error: {repr(error)[:300]}; pico de memoria GPU {pico_mib:.0f} de {total_mib:.0f} MiB"
    limite_w = resumen["gpu_limite_aplicado_mediana_w"]
    res_txt += (f"; límite aplicado de la GPU al entrenar (mediana) {limite_w:.1f} W" if limite_w else "") \
        + f"; pico de RAM {resumen['ram_pico_pct']:.1f} %"
    agregar_a_bitacora(rutas["bitacora"], corrida_cfg["fase"], f"YOLO26s {nombre}", config_txt, res_txt)
    print(res_txt)
    print(f"Resumen en {carpeta / 'resumen.json'}")
    if error is not None:
        raise error


def main():
    """Corre la verificación (--verificar) o entrena la corrida pedida (--corrida)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--corrida")
    g.add_argument("--verificar", action="store_true", help="criterio y dropout con unas imágenes; no entrena")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.verificar:
        verificar(cfg, rutas)
    else:
        entrenar(cfg, rutas, args.corrida)


if __name__ == "__main__":
    main()
