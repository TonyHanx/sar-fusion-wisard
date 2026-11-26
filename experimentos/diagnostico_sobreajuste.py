"""Diagnóstico del sobreajuste de la primera versión, sin entrenar ni predecir (configs/diagnostico_sobreajuste.yaml).

Lee los results.csv y los best.pt de runs/, las predicciones de validación que ya existen y las etiquetas de
entrenamiento y validación. La partición de prueba (FHL 0405) no se usa.

Escribe en reports/<salida>/:
- curvas_<corrida>.png: pérdidas de entrenamiento y validación (box, cls, l1) y mAP@0.5, recall y precisión de
  validación por época;
- map50_corridas.png: el mAP@0.5 de validación de todas las corridas, con su media móvil;
- corridas.csv: por corrida, dónde deja de mejorar la validación, la brecha con el entrenamiento y la época del best.pt;
- ruido.csv y ruido_por_vuelo.csv: error típico del mAP@0.5 de validación por remuestreo y mAP@0.5 por vuelo;
- tamanos.csv y vuelos.csv: tamaño de las personas y balance entre vuelos, en entrenamiento y validación.

Uso: .venv\\Scripts\\python.exe -m experimentos.diagnostico_sobreajuste --config configs\\diagnostico_sobreajuste.yaml
     --rutas configs\\rutas.yaml
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from src.comun import RAIZ, leer_cajas_yolo, leer_rutas, leer_yaml  # noqa: E402

# Paleta de referencia (skill dataviz, modo claro): series 1 a 3 en orden fijo, tintas de texto y rejilla
AZUL, NARANJA, AQUA = "#257de0", "#f47230", "#00b894"
TINTA, TINTA2, REJILLA = "#191919", "#666666", "#e6e6e6"
PERDIDAS = ["box", "cls", "l1"]
METRICAS = [("metrics/mAP50(B)", "mAP@0.5", AZUL), ("metrics/recall(B)", "Recall", NARANJA),
            ("metrics/precision(B)", "Precisión", AQUA)]


def vuelo_y_posicion(stem):
    """'210417_MtErie_Enterprise_0007_0005' -> ('210417_MtErie_Enterprise_0007', 5)."""
    v, p = stem.rsplit("_", 1)
    return v, int(p)


def estilo(ax, titulo):
    """Ejes recesivos: rejilla horizontal clara, sin marco arriba ni a la derecha, textos en tinta secundaria."""
    ax.set_title(titulo, loc="left", fontsize=10, color=TINTA)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA2)
    ax.tick_params(colors=TINTA2, labelsize=8)
    ax.set_xlabel("Época", color=TINTA2, fontsize=8)


def marcas(ax, epoca_best, inicio_sin_mosaico):
    """Línea de la época del best.pt y sombra de las épocas sin mosaico."""
    if inicio_sin_mosaico is not None:
        ax.axvspan(inicio_sin_mosaico - 0.5, ax.get_xlim()[1], color="#f2f2f2", zorder=0, lw=0)
    ax.axvline(epoca_best, color=TINTA2, lw=1, ls=(0, (3, 3)), zorder=1)


# ------------------------------------------------------------------------------------------------------------ curvas

def analizar_corrida(clave, info, cfg, rutas):
    """Métricas de una corrida a partir de su results.csv y su best.pt."""
    carpeta = rutas["runs"] / info["carpeta"]
    res = pd.read_csv(carpeta / "results.csv")
    res.columns = [c.strip() for c in res.columns]
    ep = res["epoch"].to_numpy()
    m50 = res["metrics/mAP50(B)"].to_numpy()
    suave = pd.Series(m50).rolling(cfg["suavizado"], center=True, min_periods=1).mean().to_numpy()
    # El best.pt final de Ultralytics guarda epoch = -1, pero conserva sus métricas de validación (train_metrics): la
    # época es la fila de results.csv con el mismo mAP@0.5 y mAP@0.5:0.95 (redondeados a 5 decimales, como en el csv).
    ckpt = torch.load(carpeta / "weights" / "best.pt", map_location="cpu", weights_only=False)
    tm = ckpt["train_metrics"]
    igual = ((res["metrics/mAP50(B)"] - tm["metrics/mAP50(B)"]).abs() < 1e-5) & \
            ((res["metrics/mAP50-95(B)"] - tm["metrics/mAP50-95(B)"]).abs() < 1e-5)
    if igual.sum() != 1:
        raise SystemExit(f"{clave}: {int(igual.sum())} épocas de results.csv coinciden con las métricas del best.pt")
    epoca_best = int(res.loc[igual, "epoch"].iloc[0])
    n = len(res)
    total = int(leer_yaml(carpeta / "args.yaml")["epochs"])
    inicio_sin_mosaico = total - info["close_mosaic"] + 1 if n > total - info["close_mosaic"] else None
    i_max, i_suave = int(np.argmax(m50)), int(np.argmax(suave))
    i_crit = int(np.argmax(res[info["criterio"]].to_numpy()))
    # primera época en que la media móvil llega al 90 % de su máximo: desde ahí la validación ya no gana mucho
    i_meseta = int(np.argmax(suave >= 0.9 * suave.max()))
    fila = {"corrida": clave, "nombre": info["nombre"], "epocas": n, "epocas_programadas": total,
            "map50_max": m50[i_max], "epoca_map50_max": int(ep[i_max]),
            "map50_suave_max": suave[i_suave], "epoca_suave_max": int(ep[i_suave]),
            "epoca_90pct_suave": int(ep[i_meseta]),
            "map50_ultima": m50[-1], "map50_media_ultimas5": m50[-5:].mean(),
            "caida_max_a_ultimas5": m50[i_max] - m50[-5:].mean(),
            "criterio_best": info["criterio"], "epoca_best_pt": epoca_best,
            "epoca_max_criterio": int(ep[i_crit]),
            "best_pt_es_max_criterio": epoca_best == int(ep[i_crit]),
            "best_pt_es_max_map50": epoca_best == int(ep[i_max]),
            "map50_en_best_pt": float(m50[ep == epoca_best][0])}
    for p in PERDIDAS:
        tr, va = res[f"train/{p}_loss"].to_numpy(), res[f"val/{p}_loss"].to_numpy()
        i_min = int(np.argmin(va))
        fila |= {f"{p}_train_primera": tr[0], f"{p}_train_ultima": tr[-1],
                 f"{p}_val_min": va[i_min], f"{p}_epoca_val_min": int(ep[i_min]), f"{p}_val_ultima": va[-1],
                 f"{p}_brecha_en_suave_max": va[i_suave] - tr[i_suave], f"{p}_brecha_ultima": va[-1] - tr[-1],
                 f"{p}_razon_ultima": va[-1] / tr[-1],
                 f"{p}_spearman_val_tras_min": (spearmanr(ep[i_min:], va[i_min:])[0]
                                                if n - i_min >= 5 else np.nan),
                 f"{p}_spearman_train": spearmanr(ep, tr)[0]}
    if inicio_sin_mosaico is not None:  # mAP@0.5: 5 épocas antes de quitar el mosaico contra las 5 últimas
        i0 = int(np.where(ep == inicio_sin_mosaico)[0][0])
        fila |= {"map50_5_antes_sin_mosaico": m50[i0 - 5:i0].mean(), "map50_5_ultimas_sin_mosaico": m50[-5:].mean(),
                 "cambio_al_quitar_mosaico": m50[-5:].mean() - m50[i0 - 5:i0].mean()}
    k = cfg["ultimas"]
    dif = np.abs(np.diff(m50[-k:])) if n >= k else np.array([np.nan])
    fila |= {"salto_medio_ultimas": float(np.mean(dif)), "salto_max_ultimas": float(np.max(dif)),
             "desv_ultimas": float(np.std(m50[-k:], ddof=1)) if n >= k else np.nan,
             "salto_medio_todas": float(np.mean(np.abs(np.diff(m50))))}
    return fila, res, suave, epoca_best, inicio_sin_mosaico


def figura_corrida(info, res, epoca_best, inicio_sin_mosaico, ruta_png):
    """Cuatro paneles: box, cls y l1 (entrenamiento y validación) y las métricas de validación."""
    ep = res["epoch"]
    fig, ejes = plt.subplots(1, 4, figsize=(15, 3.4), constrained_layout=True)
    for ax, p in zip(ejes[:3], PERDIDAS):
        ax.plot(ep, res[f"train/{p}_loss"], color=AZUL, lw=2, label="Entrenamiento")
        ax.plot(ep, res[f"val/{p}_loss"], color=NARANJA, lw=2, label="Validación")
        estilo(ax, f"Pérdida {p}")
        marcas(ax, epoca_best, inicio_sin_mosaico)
        ax.set_ylim(bottom=0)
    ejes[0].legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper center", bbox_to_anchor=(0.5, -0.2),
                   ncol=2)
    ax = ejes[3]
    for col, nombre, color in METRICAS:
        ax.plot(ep, res[col], color=color, lw=2, label=nombre)
    estilo(ax, "Validación")
    marcas(ax, epoca_best, inicio_sin_mosaico)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    fig.suptitle(f"{info['nombre']}  ·  línea punteada: best.pt (época {epoca_best})"
                 + ("  ·  gris: sin mosaico" if inicio_sin_mosaico else ""),
                 x=0.01, ha="left", fontsize=11, color=TINTA)
    fig.savefig(ruta_png, dpi=130, facecolor="white")
    plt.close(fig)


def figura_map50(todas, ruta_png):
    """Small multiples del mAP@0.5 de validación (puntos finos) y su media móvil (línea), con el best.pt."""
    n = len(todas)
    cols = 4
    filas = -(-n // cols)
    fig, ejes = plt.subplots(filas, cols, figsize=(15, 3.1 * filas), constrained_layout=True, sharey=True)
    for ax, (info, res, suave, epoca_best, ism) in zip(ejes.flat, todas):
        ax.plot(res["epoch"], res["metrics/mAP50(B)"], color=AZUL, lw=0.8, alpha=0.45, marker="o", ms=2.5,
                label="por época")
        ax.plot(res["epoch"], suave, color=AZUL, lw=2, label="media móvil (5)")
        estilo(ax, info["nombre"])
        marcas(ax, epoca_best, ism)
        ax.set_ylim(0, 0.6)
    for ax in list(ejes.flat)[n:]:
        ax.axis("off")
    list(ejes.flat)[0].legend(frameon=False, fontsize=8, labelcolor=TINTA2, loc="upper right")
    fig.suptitle("mAP@0.5 de validación por época (FHL 0134 + MtErie 0007, 442 fotogramas)  ·  punteada: best.pt",
                 x=0.01, ha="left", fontsize=11, color=TINTA)
    fig.savefig(ruta_png, dpi=130, facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------------- ruido

def cajas_gt(carpeta, tam):
    """Cajas de referencia en píxeles (x1, y1, x2, y2) por imagen."""
    w, h = tam
    gt = {}
    for f in sorted(Path(carpeta).glob("*.txt")):
        gt[f.stem] = np.array([[(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]
                               for _, cx, cy, bw, bh in leer_cajas_yolo(f)]).reshape(-1, 4)
    return gt


def iou(a, b):
    """IoU entre una caja `a` y las cajas `b` (x1, y1, x2, y2)."""
    x1, y1 = np.maximum(a[0], b[:, 0]), np.maximum(a[1], b[:, 1])
    x2, y2 = np.minimum(a[2], b[:, 2]), np.minimum(a[3], b[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]) - inter)


def emparejar(gt, preds, umbral_iou, max_det):
    """Por imagen: (confianzas, acierto) de sus predicciones, emparejadas de forma voraz por confianza, como COCO."""
    por_imagen = defaultdict(list)
    for p in preds:
        x, y, w, h = p["bbox"]
        por_imagen[p["image_id"]].append((p["score"], [x, y, x + w, y + h]))
    salida = {}
    for img, g in gt.items():
        dets = sorted(por_imagen.get(img, []), key=lambda d: -d[0])[:max_det]
        usado = np.zeros(len(g), bool)
        conf, tp = [], []
        for s, caja in dets:
            acierto = False
            if len(g):
                ious = iou(np.array(caja), g)
                ious[usado] = -1
                j = int(np.argmax(ious))
                if ious[j] >= umbral_iou:
                    usado[j], acierto = True, True
            conf.append(s)
            tp.append(acierto)
        salida[img] = (np.array(conf), np.array(tp, bool), len(g))
    return salida


def ap50(partes):
    """AP con la interpolación de 101 puntos de COCO, juntando las imágenes de `partes` (con repetición)."""
    conf = np.concatenate([p[0] for p in partes])
    tp = np.concatenate([p[1] for p in partes])
    npos = sum(p[2] for p in partes)
    if npos == 0:
        return np.nan
    orden = np.argsort(-conf, kind="mergesort")
    tp = tp[orden]
    ctp, cfp = np.cumsum(tp), np.cumsum(~tp)
    rec = ctp / npos
    prec = ctp / np.maximum(ctp + cfp, 1e-12)
    prec = np.maximum.accumulate(prec[::-1])[::-1] if len(prec) else prec
    umbrales = np.linspace(0, 1, 101)
    idx = np.searchsorted(rec, umbrales, side="left")
    return float(np.mean([prec[i] if i < len(prec) else 0.0 for i in idx]))


def ruido(cfg, rutas):
    """Error típico del mAP@0.5 de validación de cada last.pt: remuestreo de imágenes y de bloques de fotogramas
    seguidos dentro de cada vuelo. Y el mAP@0.5 por vuelo."""
    rc = cfg["ruido"]
    gt = cajas_gt(RAIZ / rc["etiquetas"], rc["tam_imagen"])
    imagenes = sorted(gt)
    vuelos = {i: vuelo_y_posicion(i)[0] for i in imagenes}
    bloques = defaultdict(list)
    for i in imagenes:
        v, pos = vuelo_y_posicion(i)
        bloques[(v, pos // rc["bloque"])].append(i)
    bloques = list(bloques.values())
    rng = np.random.default_rng(cfg["seed"])
    filas, por_vuelo, todos = [], [], {}
    for modelo, rel in rc["predicciones"].items():
        preds = json.loads((rutas["runs"] / rel).read_text(encoding="utf-8"))
        emp = emparejar(gt, preds, rc["iou"], rc["max_det"])
        todos[modelo] = emp
        total = ap50([emp[i] for i in imagenes])
        r_img = [ap50([emp[imagenes[k]] for k in rng.integers(0, len(imagenes), len(imagenes))])
                 for _ in range(rc["remuestreos"])]
        r_blq = []
        for _ in range(rc["remuestreos"]):
            elegidos = rng.integers(0, len(bloques), len(bloques))
            r_blq.append(ap50([emp[i] for b in elegidos for i in bloques[b]]))
        ultra = json.loads((rutas["runs"] / Path(rel).parent / "ultralytics.json").read_text(encoding="utf-8"))
        filas.append({"modelo": modelo, "map50_propio": total, "map50_ultralytics": ultra["map50"],
                      "ee_imagenes": np.std(r_img, ddof=1), "ic95_imagenes": np.percentile(r_img, [2.5, 97.5]).round(3),
                      "ee_bloques": np.std(r_blq, ddof=1), "ic95_bloques": np.percentile(r_blq, [2.5, 97.5]).round(3),
                      "bloques": len(bloques), "imagenes": len(imagenes)})
        for v in sorted(set(vuelos.values())):
            ims = [i for i in imagenes if vuelos[i] == v]
            por_vuelo.append({"modelo": modelo, "vuelo": v, "imagenes": len(ims),
                              "personas": sum(emp[i][2] for i in ims), "map50": ap50([emp[i] for i in ims])})
    pares = []
    for a, b in rc["pares"]:
        difs = []
        for _ in range(rc["remuestreos"]):
            ims = [i for k in rng.integers(0, len(bloques), len(bloques)) for i in bloques[k]]
            difs.append(ap50([todos[a][i] for i in ims]) - ap50([todos[b][i] for i in ims]))
        pares.append({"a": a, "b": b, "dif": ap50([todos[a][i] for i in imagenes]) - ap50([todos[b][i] for i in imagenes]),
                      "ee_dif_bloques": np.std(difs, ddof=1), "ic95_dif": np.percentile(difs, [2.5, 97.5]).round(3)})
    return pd.DataFrame(filas), pd.DataFrame(por_vuelo), pd.DataFrame(pares)


# ---------------------------------------------------------------------------------------------- tamaños y vuelos

def tamanos_y_vuelos(cfg):
    """Lado mayor de cada persona (px, a 640) por partición y vuelo, el efecto del aumento de escala, y el balance
    de imágenes y personas entre vuelos."""
    tc = cfg["tamanos"]
    w, h = cfg["ruido"]["tam_imagen"]
    filas_t, filas_v = [], []
    rng = np.random.default_rng(cfg["seed"])
    s = tc["escala_aumento"]
    for part, rel in tc["etiquetas"].items():
        lados, por_vuelo = [], defaultdict(lambda: [0, 0, []])
        for f in sorted((RAIZ / rel).glob("*.txt")):
            v = vuelo_y_posicion(f.stem)[0]
            cajas = leer_cajas_yolo(f)
            por_vuelo[v][0] += 1
            por_vuelo[v][1] += len(cajas)
            for _, _, _, bw, bh in cajas:
                lado = max(bw * w, bh * h)
                lados.append(lado)
                por_vuelo[v][2].append(lado)
        lados = np.array(lados)
        tramos = pd.Series(pd.cut(lados, tc["tramos"], right=False)).value_counts(sort=False)
        escalado = lados * rng.uniform(1 - s, 1 + s, len(lados))
        filas_t.append({"particion": part, "personas": len(lados), "p10": np.percentile(lados, 10),
                        "mediana": np.median(lados), "p90": np.percentile(lados, 90),
                        **{f"tramo_{k}": int(c) for k, c in tramos.items()},
                        "pct_menor_12": float((lados < 12).mean()),
                        "pct_menor_12_con_aumento_escala": float((escalado < 12).mean()),
                        "celdas_P3_mediana": float(np.median(lados) / tc["paso_minimo"])})
        imgs = sum(x[0] for x in por_vuelo.values())
        pers = sum(x[1] for x in por_vuelo.values())
        for v, (ni, np_, ls) in sorted(por_vuelo.items()):
            filas_v.append({"particion": part, "vuelo": v, "imagenes": ni, "pct_imagenes": ni / imgs,
                            "personas": np_, "pct_personas": np_ / pers,
                            "mediana_lado": float(np.median(ls)) if ls else np.nan,
                            "pct_menor_12": float(np.mean(np.array(ls) < 12)) if ls else np.nan})
    return pd.DataFrame(filas_t), pd.DataFrame(filas_v)


def main():
    """Escribe las figuras y las tablas del diagnóstico en reports/<salida>/."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    salida = rutas["reports"] / cfg["salida"]
    salida.mkdir(parents=True, exist_ok=True)

    filas, todas = [], []
    for clave, info in cfg["corridas"].items():
        fila, res, suave, epoca_best, ism = analizar_corrida(clave, info, cfg, rutas)
        filas.append(fila)
        todas.append((info, res, suave, epoca_best, ism))
        figura_corrida(info, res, epoca_best, ism, salida / f"curvas_{clave}.png")
    figura_map50(todas, salida / "map50_corridas.png")
    corridas = pd.DataFrame(filas)
    corridas.to_csv(salida / "corridas.csv", index=False, float_format="%.4f")

    r, rv, rp = ruido(cfg, rutas)
    r.to_csv(salida / "ruido.csv", index=False, float_format="%.4f")
    rp.to_csv(salida / "ruido_pares.csv", index=False, float_format="%.4f")
    print(rp.to_string(index=False))
    rv.to_csv(salida / "ruido_por_vuelo.csv", index=False, float_format="%.4f")
    t, v = tamanos_y_vuelos(cfg)
    t.to_csv(salida / "tamanos.csv", index=False, float_format="%.4f")
    v.to_csv(salida / "vuelos.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    print(corridas.T.to_string())
    print(r.to_string(index=False))
    print(rv.to_string(index=False))
    print(t.T.to_string())
    print(v.to_string(index=False))
    print(f"Salidas en {salida}")


if __name__ == "__main__":
    main()
