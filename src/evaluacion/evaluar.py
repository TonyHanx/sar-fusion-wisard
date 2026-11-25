"""Fase 6: evaluación por nivel de oclusión, con intervalos por bootstrap de episodios y McNemar.

Para cada modelo (best.pt de su corrida, el criterio de Ultralytics), predice sobre una partición con el validador de
Ultralytics y `save_json`, con la misma lectura de imágenes que en la validación del entrenamiento. La evaluación COCO de
Ultralytics (faster-coco-eval) se salta. Luego calcula con pycocotools, a IoU 0.5:
- recall, precisión y F2 con las predicciones de confianza >= 0.5, y mAP@0.5 con todas;
- por subconjunto: en la prueba, los 928 fotogramas, los 310 anotados y cada nivel sobre los 310. Al evaluar un nivel,
  las personas de los otros niveles y las sin nivel van como iscrowd=1;
- con y sin las cajas dudosas de configs/cajas_dudosas.yaml ("sin ellas" = iscrowd=1; las etiquetas no se tocan);
- intervalos percentil por bootstrap de episodios (bloques y regla en CLAUDE.md), para cada modelo y para las
  diferencias entre modelos, con los mismos remuestreos;
- McNemar exacta entre cada par de modelos sobre si cada persona fue detectada (emparejada a IoU >= 0.5 por una
  predicción con confianza >= 0.5), con Bonferroni dentro de cada nivel.

Escribe las salidas de la partición (resultados, mcnemar y el gráfico de recall, en configs/fase6.yaml) y una fila por
modelo en la bitácora. En la prueba corre una sola vez: si ya existe alguna salida, no evalúa.

Con --rgb-cero (fase 7), los modelos de 4 canales (la fusión) reciben la RGB en 0: los 3 canales de color de cada imagen
se ponen en 0 al leerla (scripts/modalidad.py, p = 1), y la térmica queda igual. Los modelos de 3 canales no cambian.
Sirve para ver cuánto depende la fusión de la RGB. Las predicciones van a <modelo>_rgb0/ y las salidas llevan el sufijo
_rgb0, así que no se mezclan con las de siempre ni cuentan para "una sola vez".

Uso:
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion prueba
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion prueba --solo-verificar
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion validacion \
      --modelos fusion fusion_last
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion prueba \
      --modelos fusion --rgb-cero --solo-predecir
"""
import argparse
import contextlib
import io
import json
import time
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pycocotools.coco import COCO  # noqa: E402
from pycocotools.cocoeval import COCOeval  # noqa: E402
from statsmodels.stats.contingency_tables import mcnemar  # noqa: E402

from src.comun import (RAIZ, agregar_a_bitacora, fijar_semilla, leer_rutas, leer_yaml, pares_anotados,  # noqa: E402
                       ruta_del_dataset)

METRICAS = ["recall", "precision", "f2", "map50"]
SUFIJO_RGB_CERO = "_rgb0"  # carpeta de predicciones y sufijo de las salidas con --rgb-cero


@contextlib.contextmanager
def silencio():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def ruta(p):
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def rel(p):
    p = Path(p)
    return str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else str(p)


def lineas(txt):
    return [x.strip() for x in Path(txt).read_text().splitlines() if x.strip()]


# --------------------------------------------------------------------------------------------- datos de la partición

def bloques_por_episodio(pos, con_persona, excluidas, excluidos_cortan):
    """Bloque (episodio, desde 0) de cada fotograma de un vuelo, en orden de posición.

    Episodio = tramo seguido de fotogramas con persona. Un fotograma sin persona lo corta; un par excluido, solo si
    `excluidos_cortan`. Cada fotograma sin persona va al episodio más cercano por posición en el vídeo; el del medio
    exacto, al anterior; los del inicio o del final, al único vecino."""
    excluidas_ordenadas = np.asarray(sorted(excluidas))
    tramos = []  # [primer índice, último índice, con persona]
    for i in range(len(pos)):
        corta = (i > 0 and excluidos_cortan and len(excluidas_ordenadas)
                 and bool(((excluidas_ordenadas > pos[i - 1]) & (excluidas_ordenadas < pos[i])).any()))
        if tramos and tramos[-1][2] == con_persona[i] and not corta:
            tramos[-1][1] = i
        else:
            tramos.append([i, i, bool(con_persona[i])])
    bloque = np.full(len(pos), -1)
    episodios = []  # (posición inicial, posición final)
    for ini, fin, tiene_persona in tramos:
        if tiene_persona:
            bloque[ini:fin + 1] = len(episodios)
            episodios.append((pos[ini], pos[fin]))
    if not episodios:
        return np.zeros(len(pos), dtype=int), 1
    for i in np.where(bloque < 0)[0]:
        posicion = pos[i]
        anteriores = [k for k, (a, b) in enumerate(episodios) if b < posicion]
        siguientes = [k for k, (a, b) in enumerate(episodios) if a > posicion]
        a = anteriores[-1] if anteriores else None
        siguiente = siguientes[0] if siguientes else None
        if siguiente is None or (a is not None and posicion - episodios[a][1] <= episodios[siguiente][0] - posicion):
            bloque[i] = a
        else:
            bloque[i] = siguiente
    return bloque, len(episodios)


def preparar(cfg, rutas, nombre_part, modelos):
    """Fotogramas, personas (con nivel y si son dudosas) y bloques del bootstrap de la partición."""
    part = cfg["particiones"][nombre_part]
    ev = cfg["evaluacion"]
    W, H = ev["tam_imagen"]
    stems, txt = None, {}
    for m, info in modelos.items():
        d = ruta_del_dataset(leer_yaml(ruta(info["datos"]))) / "labels" / part["split"]
        stems_modelo = sorted(p.stem for p in d.glob("*.txt"))
        if stems is None:
            stems = stems_modelo
            txt = {st: lineas(d / f"{st}.txt") for st in stems_modelo}
        elif stems_modelo != stems or any(lineas(d / f"{st}.txt") != txt[st] for st in stems_modelo):
            raise SystemExit(f"Las etiquetas de {m} ({d}) no son las mismas que las del primer modelo.")

    fot = pd.DataFrame([{"img_id": k, "stem": st, "vuelo": st.rsplit("_", 1)[0], "posicion": int(st.rsplit("_", 1)[1])}
                        for k, st in enumerate(stems, start=1)])
    if set(fot.vuelo) != set(part["vuelos"]):
        raise SystemExit(f"Vuelos de la partición: {sorted(set(fot.vuelo))}; se esperaban {part['vuelos']}.")
    paso = part.get("paso_anotados")
    fot["anotado"] = (fot.posicion % paso == 0) if paso else True

    filas = []
    for f in fot.itertuples():
        for i, linea in enumerate(txt[f.stem]):
            c, cx, cy, w, h = linea.split()
            if int(c) != 0:
                raise SystemExit(f"Clase {c} en {f.stem}: solo hay personas (0).")
            cx, cy, w, h = float(cx) * W, float(cy) * H, float(w) * W, float(h) * H
            filas.append({"gt_id": len(filas) + 1, "img_id": f.img_id, "stem": f.stem, "vuelo": f.vuelo,
                          "posicion": f.posicion, "indice_caja": i, "linea": linea, "x": cx - w / 2, "y": cy - h / 2,
                          "w": w, "h": h, "anotado": f.anotado})
    per = pd.DataFrame(filas)
    per["nivel"] = None
    per["dudosa"] = False

    if "niveles" in part:
        niveles = pd.read_csv(ruta(part["niveles"]))
        niveles = niveles.set_index(["vuelo", "posicion", "indice_caja"])
        anotadas = per[per.anotado].set_index(["vuelo", "posicion", "indice_caja"])
        if set(anotadas.index) != set(niveles.index):
            raise SystemExit(f"{part['niveles']} no tiene las mismas personas que los fotogramas anotados: "
                             f"{len(set(anotadas.index) - set(niveles.index))} faltan y {len(set(niveles.index) - set(anotadas.index))} sobran.")
        niveles = niveles.loc[anotadas.index]
        diferencia_px = np.abs(np.c_[anotadas.x - niveles.ter_x0, anotadas.y - niveles.ter_y0, anotadas.x + anotadas.w - niveles.ter_x1, anotadas.y + anotadas.h - niveles.ter_y1]).max()
        if diferencia_px > 1.0:
            raise SystemExit(f"Las cajas de {part['niveles']} no coinciden con las etiquetas (hasta {diferencia_px:.2f} px).")
        per.loc[per.anotado, "nivel"] = [v if isinstance(v, str) else "sin_nivel" for v in niveles.nivel]

    if "cajas_dudosas" in part:
        d = leer_yaml(ruta(part["cajas_dudosas"]))
        fila_de_caja = dict(zip(zip(per.stem, per.indice_caja), per.index))
        for c in d["cajas"] + d["seguidas"]:
            k = (Path(c["etiqueta"]).stem, c["indice_caja"])
            if k not in fila_de_caja or per.at[fila_de_caja[k], "linea"].split() != c["linea"].split():
                raise SystemExit(f"Caja dudosa sin su línea en las etiquetas: {k}")
            per.at[fila_de_caja[k], "dudosa"] = True
        if per.dudosa.sum() != d["resumen"]["total"]:
            raise SystemExit(f"Cajas dudosas: {per.dudosa.sum()}; el yaml dice {d['resumen']['total']}.")
        personas_anotadas = per[per.anotado]
        if ((personas_anotadas.nivel == "sin_nivel") != personas_anotadas.dudosa).any():
            raise SystemExit("En los fotogramas anotados, las dudosas tienen que ser justo las sin nivel.")

    # bloques del bootstrap, vuelo por vuelo
    cajas_por_imagen = per.groupby("img_id").size()
    fot["con_persona"] = fot.img_id.map(cajas_por_imagen).fillna(0).to_numpy() > 0
    pares = pares_anotados(rutas["data"] / ev["pares"])
    fot["bloque"] = -1
    n_bloques = 0
    for vuelo in part["vuelos"]:
        f = fot[fot.vuelo == vuelo].sort_values("posicion")
        todas = set(pares[pares.vuelo == vuelo].posicion)
        if not set(f.posicion) <= todas:
            raise SystemExit(f"{vuelo}: hay fotogramas que no están en {ev['pares']}.")
        bloques_vuelo, k = bloques_por_episodio(f.posicion.to_numpy(), f.con_persona.to_numpy(), todas - set(f.posicion),
                                    cfg["bootstrap"]["excluidos_cortan"])
        fot.loc[f.index, "bloque"] = bloques_vuelo + n_bloques
        n_bloques += k
    return {"fot": fot, "per": per, "nb": n_bloques, "part": part, "W": W, "H": H}


def verificar(datos, nombre_part):
    fot, per, part = datos["fot"], datos["per"], datos["part"]
    hay = {"fotogramas": len(fot), "anotados": int(fot.anotado.sum()), "personas": len(per),
           "dudosas": int(per.dudosa.sum()), "bloques": datos["nb"]}
    for nivel in ("baja", "severa", "sin_nivel"):
        hay[nivel] = int((per.nivel == nivel).sum())
    print(f"Partición {nombre_part}: " + ", ".join(f"{k} {v}" for k, v in hay.items()))
    tam = fot.groupby("bloque").agg(fotogramas=("img_id", "size"), anotados=("anotado", "sum"),
                                    con_persona=("con_persona", "sum"), desde=("posicion", "min"),
                                    hasta=("posicion", "max"), vuelo=("vuelo", "first"))
    print("Bloques del bootstrap:\n" + tam.to_string())
    malos = {k: (hay[k], v) for k, v in part.get("comprobar", {}).items() if hay[k] != v}
    if malos:
        raise SystemExit("No coincide con lo esperado (hay, esperado): " + str(malos))
    print("Coincide con lo esperado en configs.")


# ------------------------------------------------------------------------------------------------------- predicción

def predecir(clave, info, cfg, rutas, nombre_part, part, sin_metricas=False, rgb_cero=False):
    """predictions.json del validador de Ultralytics (se reutiliza si ya existe). Con `sin_metricas`, el validador
    solo guarda las predicciones: no calcula ni imprime ninguna métrica (tampoco su P y R con umbral). Con `rgb_cero`,
    cada imagen llega con la RGB en 0 (solo 4 canales) y las predicciones van a <clave>_rgb0/."""
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionValidator

    class Validador(DetectionValidator):
        def build_dataset(self, img_path, mode="val", batch=None):
            ds = super().build_dataset(img_path, mode, batch)
            if rgb_cero:
                from src.entrenamiento.dropout_modalidad import quitar_rgb

                ds = quitar_rgb(ds, 1.0)
            return ds

        def eval_json(self, stats):  # sin faster-coco-eval: la evaluación se hace aquí con pycocotools
            return stats

        def get_stats(self):
            return {} if sin_metricas else super().get_stats()

        def print_results(self):
            if not sin_metricas:
                super().print_results()

    carpeta = rutas["runs"] / cfg["carpeta"] / nombre_part / (clave + (SUFIJO_RGB_CERO if rgb_cero else ""))
    ruta_predicciones = carpeta / "predictions.json"
    pesos = rutas["runs"] / cfg["corridas"] / info["corrida"] / info.get("pesos", cfg["pesos"])
    if ruta_predicciones.exists():
        print(f"{clave}: se reutilizan las predicciones de {ruta_predicciones}")
        ultra = json.loads((carpeta / "ultralytics.json").read_text(encoding="utf-8"))
    else:
        if not pesos.exists():
            raise SystemExit(f"No existen los pesos {pesos}")
        modelo = YOLO(str(pesos))
        t_inicio = time.time()
        metricas_ultra = modelo.val(validator=Validador, data=str(ruta(info["datos"])), split=part["split"], save_json=True,
                         project=str(carpeta.parent), name=carpeta.name, exist_ok=True, **cfg["prediccion"])
        ultra = {"pesos": rel(pesos), "segundos": round(time.time() - t_inicio, 1), "sin_metricas": sin_metricas,
                 "rgb_cero": rgb_cero}
        if not sin_metricas:
            ultra.update({"map50": float(metricas_ultra.box.map50), "map50_95": float(metricas_ultra.box.map),
                          "precision": float(metricas_ultra.box.mp), "recall": float(metricas_ultra.box.mr)})
        carpeta.mkdir(parents=True, exist_ok=True)
        if not ruta_predicciones.exists():  # sin ninguna predicción, Ultralytics no escribe el archivo
            ruta_predicciones.write_text("[]", encoding="utf-8")
        (carpeta / "ultralytics.json").write_text(json.dumps(ultra, indent=2), encoding="utf-8")
    if ultra.get("rgb_cero", False) != rgb_cero:
        raise SystemExit(f"{ruta_predicciones}: rgb_cero={ultra.get('rgb_cero', False)}, se pidió {rgb_cero}")
    return json.loads(ruta_predicciones.read_text(encoding="utf-8")), ultra


# ------------------------------------------------------------------------------------------------------- evaluación

def coco_gt(datos, ignorar):
    W, H = datos["W"], datos["H"]
    per = datos["per"]
    dataset_coco = {"images": [{"id": int(i), "width": W, "height": H} for i in datos["fot"].img_id],
          "annotations": [{"id": int(persona.gt_id), "image_id": int(persona.img_id), "category_id": 1,
                           "bbox": [float(persona.x), float(persona.y), float(persona.w), float(persona.h)], "area": float(persona.w * persona.h),
                           "iscrowd": int(ignorada)} for persona, ignorada in zip(per.itertuples(), ignorar)],
          "categories": [{"id": 1, "name": "persona"}]}
    gt = COCO()
    gt.dataset = dataset_coco
    with silencio():
        gt.createIndex()
    return gt


def coco_dt(gt, preds, datos, max_dets):
    """Predicciones de Ultralytics (image_id = nombre del archivo) como resultados de COCO, hasta max_dets por imagen."""
    ids = dict(zip(datos["fot"].stem, datos["fot"].img_id))
    por_img = {}
    for pred in preds:
        por_img.setdefault(pred["image_id"], []).append(pred)
    anotaciones = []
    for stem, preds_imagen in por_img.items():
        if stem not in ids:
            raise SystemExit(f"Predicción de una imagen que no es de la partición: {stem}")
        for pred in sorted(preds_imagen, key=lambda q: -q["score"])[:max_dets]:
            anotaciones.append({"image_id": int(ids[stem]), "category_id": 1, "bbox": pred["bbox"], "score": pred["score"]})
    if not anotaciones:
        dt = COCO()
        dt.dataset = {"images": gt.dataset["images"], "annotations": [], "categories": gt.dataset["categories"]}
        with silencio():
            dt.createIndex()
        return dt
    with silencio():
        return gt.loadRes(anotaciones)


def ap_coco(tp, fp, npig, rec_thrs):
    """AP de COCO (101 puntos) a un IoU, con las predicciones ya ordenadas por confianza (sin las ignoradas)."""
    if npig == 0:
        return np.nan
    if len(tp) == 0:
        return 0.0
    tp_acumulados = np.cumsum(tp, dtype=float)
    fp_acumulados = np.cumsum(fp, dtype=float)
    recall_acum = tp_acumulados / npig
    precision_acum = tp_acumulados / (tp_acumulados + fp_acumulados + np.spacing(1))
    precision_acum = np.maximum.accumulate(precision_acum[::-1])[::-1]
    indices = np.searchsorted(recall_acum, rec_thrs, side="left")
    precision_en_umbral = np.where(indices < len(precision_acum), precision_acum[np.minimum(indices, len(precision_acum) - 1)], 0.0)
    return float(precision_en_umbral.mean())


def evaluar(gt, dt, img_ids, datos, ev):
    """Evalúa con COCOeval y deja lo necesario para el bootstrap por bloques."""
    evaluador = COCOeval(gt, dt, "bbox")
    parametros = evaluador.params
    parametros.imgIds = sorted(int(i) for i in img_ids)
    parametros.catIds = [1]
    parametros.iouThrs = np.array([ev["iou"]])
    parametros.maxDets = [ev["max_dets"]]
    parametros.areaRng = [[0, 1e10]]
    parametros.areaRngLbl = ["all"]
    with silencio():
        evaluador.evaluate()
        evaluador.accumulate()
    precisiones = evaluador.eval["precision"][0, :, 0, 0, 0]
    ap_pyc = float(precisiones[precisiones > -1].mean()) if (precisiones > -1).any() else np.nan

    bloque_de_imagen = dict(zip(datos["fot"].img_id, datos["fot"].bloque))
    n_bloques = datos["nb"]
    personas_b, aciertos_conf_b, fallos_conf_b = np.zeros(n_bloques), np.zeros(n_bloques), np.zeros(n_bloques)
    confianzas_todas, aciertos, fallos, bloques_pred = [], [], [], []
    detectada = {}
    for eval_img in evaluador.evalImgs:
        if eval_img is None:
            continue
        bloque = bloque_de_imagen[eval_img["image_id"]]
        confianzas = np.asarray(eval_img["dtScores"], dtype=float)
        emparejada = np.asarray(eval_img["dtMatches"][0])
        ignorada = np.asarray(eval_img["dtIgnore"][0]).astype(bool)
        acierto, fallo = (emparejada > 0) & ~ignorada, (emparejada == 0) & ~ignorada
        cuenta = acierto | fallo
        confianzas_todas.append(confianzas[cuenta])
        aciertos.append(acierto[cuenta])
        fallos.append(fallo[cuenta])
        bloques_pred.append(np.full(int(cuenta.sum()), bloque))
        gt_ignorada = np.asarray(eval_img["gtIgnore"]).astype(bool)
        personas_b[bloque] += (~gt_ignorada).sum()
        sobre_umbral = confianzas >= ev["conf"]
        aciertos_conf_b[bloque] += (acierto & sobre_umbral).sum()
        fallos_conf_b[bloque] += (fallo & sobre_umbral).sum()
        confianza_de = dict(zip(eval_img["dtIds"], confianzas))
        for id_gt, id_pred, ignorada_gt in zip(eval_img["gtIds"], eval_img["gtMatches"][0], gt_ignorada):
            if not ignorada_gt:
                detectada[int(id_gt)] = bool(id_pred > 0 and confianza_de[id_pred] >= ev["conf"])
    confianzas_todas = np.concatenate(confianzas_todas) if confianzas_todas else np.zeros(0)
    orden = np.argsort(-confianzas_todas, kind="mergesort")
    resultado = {"tp": np.concatenate(aciertos)[orden] if aciertos else np.zeros(0, bool),
         "fp": np.concatenate(fallos)[orden] if fallos else np.zeros(0, bool),
         "bl": np.concatenate(bloques_pred)[orden] if bloques_pred else np.zeros(0, int),
         "npig_b": personas_b, "tpc_b": aciertos_conf_b, "fpc_b": fallos_conf_b, "detectada": detectada,
         "rec_thrs": parametros.recThrs, "beta": ev["beta"]}
    unos = np.ones(n_bloques, dtype=int)
    resultado["punto"] = metricas(resultado, unos)
    if not (np.isnan(ap_pyc) and np.isnan(resultado["punto"]["map50"])) and abs(resultado["punto"]["map50"] - ap_pyc) > 1e-9:
        raise SystemExit(f"El mAP@0.5 propio ({resultado['punto']['map50']}) no coincide con el de pycocotools ({ap_pyc}).")
    resultado["n_fotogramas"] = len(img_ids)
    resultado["n_personas"] = int(personas_b.sum())
    resultado["tp_conf"], resultado["fp_conf"] = int(aciertos_conf_b.sum()), int(fallos_conf_b.sum())
    return resultado


def metricas(r, cuentas):
    """Métricas con cada bloque repetido `cuentas` veces (todo 1 = la muestra original)."""
    personas = cuentas @ r["npig_b"]
    tp, fp = cuentas @ r["tpc_b"], cuentas @ r["fpc_b"]
    recall = tp / personas if personas else np.nan
    precision = tp / (tp + fp) if (tp + fp) else np.nan  # sin predicciones >= conf, la precisión no está definida
    beta2 = r["beta"] ** 2
    denominador = (1 + beta2) * tp + beta2 * (personas - tp) + fp  # F-beta con conteos: igual a la de P y R, y 0 si no hay aciertos
    f2 = (1 + beta2) * tp / denominador if denominador else np.nan
    repeticiones = cuentas[r["bl"]]
    ap = ap_coco(np.repeat(r["tp"], repeticiones), np.repeat(r["fp"], repeticiones), personas, r["rec_thrs"])
    return {"recall": recall, "precision": precision, "f2": f2, "map50": ap}


def bootstrap(r, cuentas_b):
    return {k: np.array(v) for k, v in pd.DataFrame([metricas(r, c) for c in cuentas_b]).items()}


def intervalo(valores, confianza):
    validos = valores[~np.isnan(valores)]
    if not len(validos):
        return np.nan, np.nan
    cola = (1 - confianza) / 2 * 100
    inferior, superior = np.percentile(validos, [cola, 100 - cola])
    return float(inferior), float(superior)


# ----------------------------------------------------------------------------------------------------------- salidas

def grafico(res, cfg, part, modelos, ruta_png, dudosas, n_remuestreos):
    estilo = cfg["figura"]
    subconjuntos = [s for s in part["subconjuntos"] if s.get("grafico")]
    nombres = [s["nombre"] for s in subconjuntos]
    fig, ax = plt.subplots(figsize=(5.6, 4.0), facecolor=estilo["fondo"])
    ax.set_facecolor(estilo["fondo"])
    x = np.arange(len(nombres))
    for k, (m, info) in enumerate(modelos.items()):
        filas_modelo = res[(res.tipo == "modelo") & (res.modelo == m) & (res.dudosas == dudosas)].set_index("subconjunto")
        filas_modelo = filas_modelo.loc[nombres]
        y = filas_modelo.recall.to_numpy(dtype=float)
        err = np.vstack([y - filas_modelo.recall_ic_inf.to_numpy(dtype=float), filas_modelo.recall_ic_sup.to_numpy(dtype=float) - y])
        desplazamiento = (k - (len(modelos) - 1) / 2) * 0.07
        ax.errorbar(x + desplazamiento, y, yerr=err, color=info["color"], marker="o", markersize=7, linewidth=2, capsize=3,
                    elinewidth=1, label=info["nombre"], markeredgecolor=estilo["fondo"], markeredgewidth=1.5, zorder=3)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(estilo["rejilla"])
    ax.grid(axis="y", color=estilo["rejilla"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xticks(x, [s.get("rotulo", s["nombre"]) for s in subconjuntos])
    ax.set_xlim(-0.5, len(nombres) - 0.5)
    ax.set_ylim(0, 1)
    ax.set_ylabel(f"Recall (confianza ≥ {cfg['evaluacion']['conf']})", fontsize=9, color=estilo["texto_secundario"])
    ax.tick_params(colors=estilo["texto_secundario"], labelsize=8)
    fig.suptitle(part["titulo"], x=0.01, y=0.99, ha="left", va="top", fontsize=10, color=estilo["texto"])
    elementos, rotulos = ax.get_legend_handles_labels()
    fig.legend(elementos, rotulos, loc="upper left", bbox_to_anchor=(0.005, 0.94), ncol=len(rotulos), frameon=False, fontsize=8,
               labelcolor=estilo["texto"])
    fig.text(0.01, 0.01, f"Barras: IC del {int(cfg['bootstrap']['confianza'] * 100)} % por bootstrap de episodios "
             f"({n_remuestreos:,} remuestreos).".replace(",", " "), fontsize=7, color=estilo["texto_secundario"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.88))
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_png, dpi=estilo["dpi"], facecolor=estilo["fondo"])
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--particion", required=True)
    ap.add_argument("--modelos", nargs="+", help="por omisión, los de `modelos`")
    ap.add_argument("--solo-verificar", action="store_true", help="etiquetas, niveles, dudosas y bloques; sin predecir")
    ap.add_argument("--solo-predecir", action="store_true",
                    help="solo guarda las predicciones crudas (conf de `prediccion`); no calcula ninguna métrica")
    ap.add_argument("--rgb-cero", action="store_true",
                    help="los modelos de 4 canales reciben la RGB en 0 (la térmica igual); salidas con sufijo _rgb0")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    fijar_semilla(cfg["bootstrap"]["seed"])
    part = cfg["particiones"][args.particion]
    todos = {**cfg["modelos"], **cfg.get("modelos_solo_validacion", {})}
    claves = args.modelos or list(cfg["modelos"])
    if args.particion == "prueba" and set(claves) - set(cfg["modelos"]):
        raise SystemExit("En la prueba solo se evalúan los modelos de `modelos`.")
    modelos = {k: todos[k] for k in claves}
    salidas = {k: ruta(v) for k, v in part["salidas"].items()}
    rgb0 = {k: args.rgb_cero and leer_yaml(ruta(info["datos"])).get("channels", 3) == 4 for k, info in modelos.items()}
    if args.rgb_cero:
        if not any(rgb0.values()):
            raise SystemExit("--rgb-cero: ninguno de los modelos tiene 4 canales.")
        modelos = {k: {**info, "nombre": f"{info['nombre']} (RGB en 0)"} if rgb0[k] else info
                   for k, info in modelos.items()}
        salidas = {k: v.with_name(v.stem + SUFIJO_RGB_CERO + v.suffix) for k, v in salidas.items()}
        print("RGB en 0: " + ", ".join(k for k in modelos if rgb0[k]) + "; salidas: "
              + ", ".join(rel(v) for v in salidas.values()))

    datos = preparar(cfg, rutas, args.particion, modelos)
    verificar(datos, args.particion)
    if args.solo_verificar:
        return
    if args.solo_predecir:
        for k, info in modelos.items():
            p, info_ultra = predecir(k, info, cfg, rutas, args.particion, part, sin_metricas=True, rgb_cero=rgb0[k])
            destino = (rutas["runs"] / cfg["carpeta"] / args.particion / (k + (SUFIJO_RGB_CERO if rgb0[k] else ""))
                       / "predictions.json")
            print(f"{k}: {len(p)} predicciones (confianza >= {cfg['prediccion']['conf']}) en {rel(destino)}")
            agregar_a_bitacora(rutas["bitacora"], part["fase_bitacora"], f"YOLO26s {k}",
                               f"partición {args.particion} (split {part['split']}); pesos {info_ultra['pesos']}; solo "
                               f"predicciones crudas (confianza >= {cfg['prediccion']['conf']}, validador de "
                               f"Ultralytics con save_json)"
                               + ("; RGB en 0 (los 3 canales de color)" if rgb0[k] else ""),
                               f"{len(p)} predicciones en {rel(destino)}; no se calculó ninguna métrica")
        return
    if args.particion == "prueba":  # hasta implementar la regla del 3 de noviembre de 2026 (CLAUDE.md, "Métricas")
        raise SystemExit("La evaluación de la prueba espera los umbrales por modelo fijados en validación (F2). "
                         "Por ahora solo --solo-predecir o --solo-verificar.")
    if part.get("una_sola_vez") and any(p.exists() for p in salidas.values()):
        raise SystemExit("La partición ya se evaluó (existen " + ", ".join(rel(p) for p in
                                                                           salidas.values() if p.exists())
                         + "). Se evalúa una sola vez.")

    t0 = time.time()
    ev = cfg["evaluacion"]
    dudosas = ["con", "sin"] if "cajas_dudosas" in part else ["con"]
    n_remuestreos = cfg["bootstrap"]["remuestreos"]
    rng = np.random.default_rng(cfg["bootstrap"]["seed"])
    n_bloques = datos["nb"]
    cuentas_b = np.stack([np.bincount(rng.integers(0, n_bloques, n_bloques), minlength=n_bloques) for _ in range(n_remuestreos)])
    conf_ic = cfg["bootstrap"]["confianza"]

    preds, ultra = {}, {}
    for k, info in modelos.items():
        preds[k], ultra[k] = predecir(k, info, cfg, rutas, args.particion, part, rgb_cero=rgb0[k])
        print(f"{k}: {len(preds[k])} predicciones; Ultralytics: mAP@0.5 {ultra[k].get('map50', float('nan')):.4f}")

    per = datos["per"]
    filas, filas_mc, evals = [], [], {}
    for subconjunto in part["subconjuntos"]:
        imgs = datos["fot"] if subconjunto["fotogramas"] == "todos" else datos["fot"][datos["fot"].anotado]
        for dudosas_modo in dudosas:
            cuenta = pd.Series(True, index=per.index) if subconjunto["personas"] == "todas" else (per.nivel == subconjunto["personas"])
            if dudosas_modo == "sin":
                cuenta &= ~per.dudosa
            gt = coco_gt(datos, ~cuenta.to_numpy())
            boot = {}
            for k in modelos:
                dt = coco_dt(gt, preds[k], datos, ev["max_dets"])
                resultado = evaluar(gt, dt, imgs.img_id, datos, ev)
                evals[(subconjunto["nombre"], dudosas_modo, k)] = resultado
                t = time.time()
                boot[k] = bootstrap(resultado, cuentas_b)
                fila = {"particion": args.particion, "subconjunto": subconjunto["nombre"], "dudosas": dudosas_modo, "tipo": "modelo",
                        "modelo": k, "nombre": modelos[k]["nombre"], "n_fotogramas": resultado["n_fotogramas"],
                        "n_personas": resultado["n_personas"], "tp": resultado["tp_conf"], "fp": resultado["fp_conf"],
                        "fn": resultado["n_personas"] - resultado["tp_conf"]}
                for metrica in METRICAS:
                    fila[metrica] = resultado["punto"][metrica]
                    fila[f"{metrica}_ic_inf"], fila[f"{metrica}_ic_sup"] = intervalo(boot[k][metrica], conf_ic)
                fila["remuestreos"] = n_remuestreos
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[k][metrica]).sum() for metrica in METRICAS))
                filas.append(fila)
                print(f"{subconjunto['nombre']:>13} {dudosas_modo} {k:>11}: recall {fila['recall']:.3f} "
                      f"[{fila['recall_ic_inf']:.3f}, {fila['recall_ic_sup']:.3f}], precisión {fila['precision']:.3f}, "
                      f"F2 {fila['f2']:.3f}, mAP@0.5 {fila['map50']:.3f}  ({time.time() - t:.0f} s de bootstrap)",
                      flush=True)
            for modelo_a, modelo_b in combinations(modelos, 2):
                fila = {"particion": args.particion, "subconjunto": subconjunto["nombre"], "dudosas": dudosas_modo,
                        "tipo": "diferencia", "modelo": f"{modelo_a} - {modelo_b}",
                        "nombre": f"{modelos[modelo_a]['nombre']} − {modelos[modelo_b]['nombre']}",
                        "n_fotogramas": evals[(subconjunto["nombre"], dudosas_modo, modelo_a)]["n_fotogramas"],
                        "n_personas": evals[(subconjunto["nombre"], dudosas_modo, modelo_a)]["n_personas"]}
                for metrica in METRICAS:
                    fila[metrica] = evals[(subconjunto["nombre"], dudosas_modo, modelo_a)]["punto"][metrica] - evals[(subconjunto["nombre"], dudosas_modo, modelo_b)]["punto"][metrica]
                    fila[f"{metrica}_ic_inf"], fila[f"{metrica}_ic_sup"] = intervalo(boot[modelo_a][metrica] - boot[modelo_b][metrica], conf_ic)
                fila["remuestreos"] = n_remuestreos
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[modelo_a][metrica] - boot[modelo_b][metrica]).sum() for metrica in METRICAS))
                filas.append(fila)

        if subconjunto.get("mcnemar") and len(modelos) > 1:
            dudosas_modo = cfg["mcnemar"]["dudosas"] if cfg["mcnemar"]["dudosas"] in dudosas else dudosas[0]
            pares = list(combinations(modelos, 2))
            for modelo_a, modelo_b in pares:
                detectadas_a, detectadas_b = evals[(subconjunto["nombre"], dudosas_modo, modelo_a)]["detectada"], evals[(subconjunto["nombre"], dudosas_modo, modelo_b)]["detectada"]
                if set(detectadas_a) != set(detectadas_b):
                    raise SystemExit(f"McNemar: no son las mismas personas en {modelo_a} y {modelo_b} ({subconjunto['nombre']}).")
                ids = sorted(detectadas_a)
                det_a = np.array([detectadas_a[i] for i in ids])
                det_b = np.array([detectadas_b[i] for i in ids])
                tabla = [[int((det_a & det_b).sum()), int((det_a & ~det_b).sum())], [int((~det_a & det_b).sum()), int((~det_a & ~det_b).sum())]]
                res = mcnemar(tabla, exact=cfg["mcnemar"]["exacta"])
                p_bonferroni = min(1.0, float(res.pvalue) * len(pares))
                filas_mc.append({"particion": args.particion, "subconjunto": subconjunto["nombre"], "dudosas": dudosas_modo,
                                 "modelo_a": modelo_a, "modelo_b": modelo_b, "n_personas": len(ids), "ambos": tabla[0][0],
                                 "solo_a": tabla[0][1], "solo_b": tabla[1][0], "ninguno": tabla[1][1],
                                 "recall_a": float(det_a.mean()), "recall_b": float(det_b.mean()),
                                 "estadistico": float(res.statistic), "p": float(res.pvalue),
                                 "comparaciones": len(pares), "p_bonferroni": p_bonferroni, "alfa": cfg["mcnemar"]["alfa"],
                                 "significativo": p_bonferroni < cfg["mcnemar"]["alfa"]})

    res = pd.DataFrame(filas)
    for p in salidas.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(salidas["resultados"], index=False)
    tabla_mcnemar = pd.DataFrame(filas_mc)
    tabla_mcnemar.to_csv(salidas["mcnemar"], index=False)
    dudosas_grafico = cfg["mcnemar"]["dudosas"] if cfg["mcnemar"]["dudosas"] in dudosas else dudosas[0]
    grafico(res, cfg, part, modelos, salidas["grafico"], dudosas_grafico, n_remuestreos)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.precision", 3):
        print(res[["subconjunto", "dudosas", "modelo", "n_personas", "recall", "recall_ic_inf", "recall_ic_sup",
                   "precision", "f2", "map50"]].to_string(index=False))
        if len(tabla_mcnemar):
            print(tabla_mcnemar[["subconjunto", "modelo_a", "modelo_b", "n_personas", "solo_a", "solo_b", "p", "p_bonferroni",
                      "significativo"]].to_string(index=False))
    print(f"Salidas: {', '.join(rel(p) for p in salidas.values())} ({time.time() - t0:.0f} s)")

    for k, info in modelos.items():
        resumen = []
        for subconjunto in part["subconjuntos"]:
            fila_resumen = res[(res.tipo == "modelo") & (res.modelo == k) & (res.subconjunto == subconjunto["nombre"])
                    & (res.dudosas == dudosas[0])].iloc[0]
            resumen.append(f"{subconjunto['nombre']} ({dudosas[0]} dudosas): recall {fila_resumen.recall:.3f} "
                           f"[{fila_resumen.recall_ic_inf:.3f}, {fila_resumen.recall_ic_sup:.3f}], P {fila_resumen.precision:.3f}, F2 {fila_resumen.f2:.3f}, "
                           f"mAP50 {fila_resumen.map50:.3f}")
        config = (f"partición {args.particion} (split {part['split']}); pesos {ultra[k]['pesos']}; "
                  + ("RGB en 0 (los 3 canales de color); " if rgb0[k] else "") + f"conf {ev['conf']} "
                  f"e IoU {ev['iou']} (mAP@0.5 con conf {cfg['prediccion']['conf']}), maxDets {ev['max_dets']}; "
                  f"bootstrap {n_remuestreos} remuestreos de {n_bloques} bloques (episodios), seed={cfg['bootstrap']['seed']}; "
                  f"salidas {', '.join(rel(p) for p in salidas.values())}")
        agregar_a_bitacora(rutas["bitacora"], part["fase_bitacora"], f"YOLO26s {k}", config,
                           "; ".join(resumen) + f"; Ultralytics (su AP) mAP50 {ultra[k].get('map50', float('nan')):.4f}")


if __name__ == "__main__":
    main()
