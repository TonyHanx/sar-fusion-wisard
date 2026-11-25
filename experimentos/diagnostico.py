"""Diagnóstico del mAP@0.5 de validación (configs/diagnostico.yaml). No cambia nada de lo ya hecho: lee runs/fase5,
data/ y el dataset original, y escribe solo en runs/<carpeta>/ (y en la bitácora). La prueba (FHL 0405) no se evalúa.

Partes (--parte):
- inventario (A1): las carpetas de WiSARDv1, con modalidad, resolución, imágenes, .txt, cajas y pareja; y las
  térmicas anotadas que quedan fuera de los pares usados, por sitio y motivo.
- estado (A2): corridas de la fase 5b; época del best.pt, sus métricas, el máximo de mAP@0.5 y la última época.
- tamanos (A3): alto, ancho y lado mayor de las cajas térmicas por partición y vuelo, tramos de QFDet y tamaño
  equivalente en la RGB original (escala de la semejanza de cada vuelo).
- integridad (A6): verify_image_label de Ultralytics sobre train y val de los tres datasets, conteos contra lo esperado,
  cachés y que train, val y test no compartan archivos (nombre, original y contenido).
- validar (A4): model.val (conf 0.001) por vuelo y por "solo térmica"/resto; mAP@0.5 por tramo de tamaño con
  pycocotools (fuera del tramo = ignorada, como las áreas de COCO); predict con conf 0.25 y 0.5: personas detectadas.
- hoja (A5): 16 imágenes de validación al azar, anotadas en verde y predicciones en rojo, en la térmica y en la RGB.
- b1_datos (B1): dataset de solo térmica con los 6 vuelos que no son FHL 0405, al azar por fotograma 60/20/20.
- b_evaluar (B): model.val del best.pt de una corrida de diagnóstico en sus splits (B1: su prueba aleatoria).
- b_por_vuelo (B): lo mismo, separado por vuelo.
- copiar: copia las salidas livianas a reports/<copiar.destino>/ para git (sin los pesos).

Uso: python -m experimentos.diagnostico --config configs/diagnostico.yaml --rutas configs/rutas.yaml --parte inventario
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, ruta_del_dataset

TRAMOS_ETIQUETA = None  # se fija con la configuración


def ruta(p):
    """Ruta absoluta: si es relativa, desde la raíz del repositorio."""
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def rel(p):
    """Ruta relativa a la raíz del repositorio para mostrarla, o la ruta entera si está fuera."""
    p = Path(p)
    return p.relative_to(RAIZ).as_posix() if p.is_relative_to(RAIZ) else str(p)


@contextlib.contextmanager
def silencio():
    """Oculta lo que imprime pycocotools mientras dura el bloque."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def vuelo_de(stem):
    """Vuelo de una imagen, sacado de su nombre (<vuelo>_<posición>)."""
    return stem.rsplit("_", 1)[0]


def particion_de_vuelo(cfg):
    """Partición (entrenamiento, validación o prueba) de cada vuelo, según la partición por vuelo."""
    p = leer_yaml(ruta(cfg["particion"]))
    return {v: k for k, vs in p.items() for v in vs}


def etiquetas_tramos(tramos):
    """Rótulos de los tramos de tamaño a partir de sus bordes: <a, a-b, ..., >=z."""
    e = [f"<{tramos[0]}"] + [f"{a}-{b}" for a, b in zip(tramos[:-1], tramos[1:])] + [f">={tramos[-1]}"]
    return e


def tramo_de(x, tramos):
    """Índice del tramo de tamaño en que cae `x`."""
    return int(np.searchsorted(np.asarray(tramos, float), x, side="right"))


def escala_semejanza(H):
    """Escala de una semejanza (cuánto se reduce la RGB al llevarla a la térmica)."""
    return float(np.hypot(H[0][0], H[0][1]))


def md(df, decimales=None):
    """Tabla en markdown (sin dependencias)."""
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        celdas = []
        for c in cols:
            v = r[c]
            if isinstance(v, float) and decimales is not None and not np.isnan(v):
                celdas.append(f"{v:.{decimales}f}")
            elif isinstance(v, float) and np.isnan(v):
                celdas.append("—")
            else:
                celdas.append(str(v))
        out.append("| " + " | ".join(celdas) + " |")
    return "\n".join(out)


def cajas_txt(p, W, H):
    """Cajas de un .txt YOLO en píxeles (x0, y0, w, h)."""
    out = []
    for linea in Path(p).read_text(encoding="utf-8").splitlines():
        t = linea.split()
        if t:
            cx, cy, w, h = (float(v) for v in t[1:5])
            out.append((cx * W - w * W / 2, cy * H - h * H / 2, w * W, h * H))
    return out


def dataset_yaml(datos):
    """Carpeta raíz y contenido del yaml de un dataset de Ultralytics."""
    d = leer_yaml(ruta(datos))
    return ruta_del_dataset(d), d


# ------------------------------------------------------------------------------------------------------------- A1

def inventario(cfg, rutas, out):
    """A1: inventario de las carpetas de WiSARDv1 y de las térmicas anotadas que quedan fuera de los pares usados, por
    sitio y motivo."""
    ds = rutas["dataset"]
    ext = set(cfg["inventario"]["extensiones"])
    pares = pd.read_csv(rutas["data"] / cfg["pares"])
    idx = pd.read_csv(rutas["data"] / cfg["indice"])
    part = particion_de_vuelo(cfg)
    parejas = pares.groupby(["carpeta_rgb", "carpeta_termica"]).vuelo.first().reset_index()
    pareja_de = {}
    for r in parejas.itertuples():
        pareja_de[r.carpeta_rgb] = r.vuelo
        pareja_de[r.carpeta_termica] = r.vuelo
    usados_rgb, usados_ter = set(idx.ruta_rgb), set(idx.ruta_termica)
    par_de_termica = {r.ruta_termica: r for r in pares.itertuples()}

    filas, fuera = [], []
    for carpeta in sorted(p for p in ds.iterdir() if p.is_dir()):
        n = carpeta.name
        m = re.search(r"_(VIS|IR)(_|$)", n)
        modalidad = m.group(1) if m else "?"
        imgs = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in ext)
        txts = {p.stem: p for p in carpeta.iterdir() if p.suffix.lower() == ".txt"}
        tam = Counter()
        n_txt = n_con_cajas = n_cajas = 0
        for im in imgs:
            with Image.open(im) as f:
                tam[f.size] += 1
            t = txts.get(im.stem)
            if t is not None:
                n_txt += 1
                k = sum(1 for linea in t.read_text(encoding="utf-8").splitlines() if linea.split())
                n_cajas += k
                n_con_cajas += k > 0
            if modalidad == "IR" and t is not None:
                clave = f"{n}/{im.name}"
                k = sum(1 for linea in t.read_text(encoding="utf-8").splitlines() if linea.split())
                if clave in usados_ter:
                    continue
                if n not in pareja_de:
                    motivo = "carpeta IR sin pareja VIS"
                elif clave not in par_de_termica:
                    motivo = "sin par (más allá de la longitud mínima de la pareja)"
                else:
                    pr = par_de_termica[clave]
                    if not pr.anotado:
                        motivo = "en un par con la RGB sin anotar"
                    elif pr.excluido:
                        motivo = "par excluido: " + str(pr.motivo_exclusion).split(":")[0].split("(")[0].strip()
                    else:
                        motivo = "?"
                fuera.append({"carpeta": n, "sitio": n.split("_")[1], "archivo": im.name, "cajas": k,
                              "motivo": motivo})
        huerfanos = sorted(set(txts) - {p.stem for p in imgs})
        vuelo = pareja_de.get(n)
        usados = (sum(1 for im in imgs if f"{n}/{im.name}" in (usados_ter if modalidad == "IR" else usados_rgb)))
        filas.append({
            "carpeta": n, "sitio": n.split("_")[1], "modalidad": modalidad,
            "resolucion": "; ".join(f"{w}×{h}" + (f" ({c})" if len(tam) > 1 else "") for (w, h), c in tam.most_common()),
            "imagenes": len(imgs), "con_txt": n_txt, "txt_con_cajas": n_con_cajas, "cajas": n_cajas,
            "txt_sin_imagen": len(huerfanos), "pareja": vuelo or "—",
            "particion": part.get(vuelo, "—") if vuelo else "—", "en_los_4617": usados,
        })
    inv = pd.DataFrame(filas)
    fu = pd.DataFrame(fuera)
    d = out / "a1"
    d.mkdir(parents=True, exist_ok=True)
    inv.to_csv(d / "inventario.csv", index=False)
    fu.to_csv(d / "termicas_fuera.csv", index=False)

    # resúmenes
    tot = inv.groupby("modalidad")[["imagenes", "con_txt", "txt_con_cajas", "cajas"]].sum()
    ir = inv[inv.modalidad == "IR"]
    tot_ir_sitio = ir.groupby("sitio")[["imagenes", "con_txt", "txt_con_cajas", "cajas"]].sum()
    fs = fu.groupby("sitio").agg(termicas_anotadas=("archivo", "size"), con_cajas=("cajas", lambda c: int((c > 0).sum())),
                                  cajas=("cajas", "sum")).reset_index()
    fm = fu.groupby(["sitio", "motivo"]).agg(termicas_anotadas=("archivo", "size"),
                                             con_cajas=("cajas", lambda c: int((c > 0).sum())),
                                             cajas=("cajas", "sum")).reset_index()
    resumen = {"carpetas": len(inv), "por_modalidad": tot.reset_index().to_dict("records"),
               "parejas": int(parejas.shape[0]), "carpetas_en_parejas": int((inv.pareja != "—").sum()),
               "termicas_anotadas_total": int(ir.con_txt.sum()), "termicas_en_los_4617": int(ir.en_los_4617.sum()),
               "termicas_anotadas_fuera": int(len(fu)), "termicas_fuera_con_cajas": int((fu.cajas > 0).sum()),
               "cajas_termicas_fuera": int(fu.cajas.sum())}
    (d / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(d / "tablas.md", "w", encoding="utf-8") as f:
        f.write(md(inv) + "\n\n" + md(tot.reset_index()) + "\n\n" + md(tot_ir_sitio.reset_index()) + "\n\n"
                + md(fs) + "\n\n" + md(fm) + "\n")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"Tablas en {rel(d / 'tablas.md')}")


# ------------------------------------------------------------------------------------------------------------- A2

def estado(cfg, rutas, out):
    """A2: estado de las corridas de la fase 5b (época de best.pt, sus métricas, el máximo de mAP@0.5 y la última
    época)."""
    e = cfg["estado"]
    base = rutas["runs"] / "fase5"
    filas = []
    for modelo, corrida in e["corridas"].items():
        c = base / corrida
        fila = {"modelo": modelo, "corrida": corrida, "existe": c.exists(),
                "terminada": (c / "resumen.json").exists()}
        if fila["terminada"]:
            r = json.loads((c / "resumen.json").read_text(encoding="utf-8"))
            res = pd.read_csv(c / "results.csv")
            res.columns = [k.strip() for k in res.columns]
            i_best = res["metrics/mAP50-95(B)"].idxmax()  # fitness de Ultralytics 8.4 = mAP@0.5:0.95
            i_max = res["metrics/mAP50(B)"].idxmax()
            bp = r["val_best_pt"]
            fila |= {"epocas": len(res), "epoca_best_pt": int(res.epoch[i_best]),
                     "best_map50": bp["metrics/mAP50(B)"], "best_map50_95": bp["metrics/mAP50-95(B)"],
                     "best_precision": bp["metrics/precision(B)"], "best_recall": bp["metrics/recall(B)"],
                     "max_map50": float(res["metrics/mAP50(B)"][i_max]), "epoca_max_map50": int(res.epoch[i_max]),
                     "ultima_map50": float(res["metrics/mAP50(B)"].iloc[-1]), "ultima_epoca": int(res.epoch.iloc[-1]),
                     "pesos_guardados": ", ".join(sorted(p.name for p in (c / "weights").glob("*.pt")))}
        filas.append(fila)
    cortadas = []
    for corrida in e["cortadas"]:
        c = base / corrida
        res = pd.read_csv(c / "results.csv")
        res.columns = [k.strip() for k in res.columns]
        i_best = res["metrics/mAP50-95(B)"].idxmax()
        i_max = res["metrics/mAP50(B)"].idxmax()
        cortadas.append({"corrida": corrida, "epocas_completas": len(res), "epoca_mayor_map50_95": int(res.epoch[i_best]),
                         "map50_esa_epoca": float(res["metrics/mAP50(B)"][i_best]),
                         "map50_95_esa_epoca": float(res["metrics/mAP50-95(B)"][i_best]),
                         "max_map50": float(res["metrics/mAP50(B)"][i_max]), "epoca_max_map50": int(res.epoch[i_max]),
                         "ultima_map50": float(res["metrics/mAP50(B)"].iloc[-1]),
                         "resumen_json": (c / "resumen.json").exists()})
    log = ruta(e["log_noche"]).read_text(encoding="utf-8").splitlines()
    noche = rutas["runs"] / "noche"
    d = out / "a2"
    d.mkdir(parents=True, exist_ok=True)
    s = {"corridas": filas, "cortadas": cortadas, "log_noche": log,
         "runs_noche": sorted(p.name for p in noche.iterdir()) if noche.exists() else []}
    (d / "estado.json").write_text(json.dumps(s, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2, default=str))


# ------------------------------------------------------------------------------------------------------------- A3

def tamanos(cfg, rutas, out):
    """A3: tamaño de las cajas térmicas por partición y vuelo, por tramos, y su tamaño equivalente en la RGB original.
    """
    t = cfg["tamanos"]
    W, H = cfg["tam_termica"]
    raiz, _ = dataset_yaml(t["datos"])
    trans = leer_yaml(ruta(cfg["transformaciones"]))
    tramos = t["tramos_px"]
    etq = etiquetas_tramos(tramos)
    filas = []
    for nombre, split in t["splits"].items():
        for lb in sorted((raiz / "labels" / split).glob("*.txt")):
            v = vuelo_de(lb.stem)
            for x0, y0, w, h in cajas_txt(lb, W, H):
                filas.append({"particion": nombre, "vuelo": v, "stem": lb.stem, "w": w, "h": h, "lado": max(w, h)})
    c = pd.DataFrame(filas)
    c["escala"] = c.vuelo.map(lambda v: escala_semejanza(trans[v]["H_rgb_a_termica"]))
    c["lado_rgb"] = c.lado / c.escala
    c["tramo"] = [etq[tramo_de(x, tramos)] for x in c.lado]
    pc = t["percentiles"]

    def resumen(g):
        """Percentiles del ancho, el alto y el lado mayor de un grupo de cajas."""
        r = {"cajas": len(g)}
        for col, nom in [("w", "ancho"), ("h", "alto"), ("lado", "lado mayor"), ("lado_rgb", "lado mayor RGB orig.")]:
            q = np.percentile(g[col], pc)
            r[f"{nom} (p{pc[0]} / p{pc[1]} / p{pc[2]})"] = " / ".join(f"{v:.1f}" for v in q)
        for e_ in etq:
            k = int((g.tramo == e_).sum())
            r[e_] = f"{k} ({100 * k / len(g):.1f} %)"
        return pd.Series(r)

    por_part = c.groupby("particion", sort=False).apply(resumen, include_groups=False).reset_index()
    por_vuelo = c.groupby(["particion", "vuelo"], sort=False).apply(resumen, include_groups=False).reset_index()
    esc = pd.DataFrame([{"vuelo": v, "rgb_original": "×".join(str(x) for x in trans[v]["tam_rgb"]),
                         "escala_termica_por_px_rgb": round(escala_semejanza(trans[v]["H_rgb_a_termica"]), 4),
                         "px_rgb_por_px_termico": round(1 / escala_semejanza(trans[v]["H_rgb_a_termica"]), 2)}
                        for v in c.vuelo.unique()])
    d = out / "a3"
    d.mkdir(parents=True, exist_ok=True)
    c.to_csv(d / "cajas.csv", index=False)
    with open(d / "tablas.md", "w", encoding="utf-8") as f:
        f.write(md(por_part) + "\n\n" + md(por_vuelo) + "\n\n" + md(esc) + "\n")
    print((d / "tablas.md").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------------------- A6

def integridad(cfg, rutas, out):
    """A6: comprueba con Ultralytics las imágenes y etiquetas de los tres datasets, los conteos, las cachés y que las
    particiones no compartan archivos."""
    from ultralytics.data.utils import get_hash, img2label_paths, load_dataset_cache_file, verify_image_label

    g = cfg["integridad"]
    filas, avisos = [], []
    nombres = {}
    for nombre, datos in g["datasets"].items():
        raiz, y = dataset_yaml(datos)
        for split in g["splits_comparar"]:
            ims = sorted((raiz / "images" / split).iterdir())
            nombres[(nombre, split)] = [p.stem for p in ims]
            if split not in g["splits_cargar"]:
                continue
            lbs = img2label_paths([str(p) for p in ims])
            tot = Counter()
            cajas = 0
            for im, lb in zip(ims, lbs):
                r = verify_image_label((str(im), lb, "", False, len(y["names"]), 0, 0, False))
                _, l, shape, _, _, nm, nf, ne, nc, msg = r
                tot.update({"faltan": nm, "encontradas": nf, "vacias": ne, "corruptas": nc})
                if l is not None:
                    cajas += len(l)
                if msg:
                    avisos.append({"dataset": nombre, "split": split, "imagen": im.name, "aviso": msg.strip()})
            cache = raiz / "labels" / f"{split}.cache"
            info_cache = {}
            if cache.exists():
                cc = load_dataset_cache_file(cache)
                nf, nm, ne, nc, n = cc["results"]
                scan_args = (False, len(y["names"]), y.get("kpt_shape"), False)  # YOLODataset.get_cache_hash
                info_cache = {"cache_vigente": cc["hash"] == get_hash(lbs + [str(p) for p in ims] + [str(scan_args)]),
                              "cache_avisos": len(cc["msgs"]), "cache_imagenes": n, "cache_corruptas": nc}
                for m in cc["msgs"]:
                    avisos.append({"dataset": nombre, "split": split, "imagen": "(caché)", "aviso": m.strip()})
            esp = g["esperado"][split]
            filas.append({"dataset": nombre, "split": split, "imagenes": len(ims), "esperadas": esp["imagenes"],
                          "cajas": cajas, "cajas_esperadas": esp["cajas"], "etiquetas_encontradas": tot["encontradas"],
                          "sin_etiqueta": tot["faltan"], "etiquetas_vacias": tot["vacias"],
                          "corruptas": tot["corruptas"], **info_cache})
    # que los splits no compartan archivos: nombres, archivos originales y contenido
    idx = pd.read_csv(rutas["data"] / cfg["indice"])
    idx["stem"] = [Path(p).stem for p in idx.termica]
    split_de = {}
    choques = []
    for (nombre, split), stems in nombres.items():
        for s in stems:
            k = (nombre, s)
            if k in split_de and split_de[k] != split:
                choques.append({"tipo": "nombre", "dataset": nombre, "archivo": s, "splits": f"{split_de[k]}, {split}"})
            split_de[k] = split
    ref = {s: sp for (n, s), sp in split_de.items() if n == "termico"}
    for nombre in g["datasets"]:
        otro = {s: sp for (n, s), sp in split_de.items() if n == nombre}
        if otro != ref:
            choques.append({"tipo": "reparto distinto", "dataset": nombre, "archivo": "", "splits": ""})
    idx["split"] = idx.stem.map(ref)
    for col in ["ruta_rgb", "ruta_termica"]:
        dup = idx[idx.duplicated(col, keep=False)]
        for v, gg in dup.groupby(col):
            if gg.split.nunique() > 1:
                choques.append({"tipo": f"mismo original ({col})", "dataset": "", "archivo": v,
                                "splits": ", ".join(sorted(gg.split))})
    hashes = {}
    for col in ["termica", "rgb"]:
        h = {}
        for r in idx.itertuples():
            p = rutas["data"] / "alineados" / getattr(r, col)
            h.setdefault(hashlib.md5(p.read_bytes()).hexdigest(), []).append(r.split)
        rep = {k: v for k, v in h.items() if len(v) > 1}
        cruzan = {k: v for k, v in rep.items() if len(set(v)) > 1}
        hashes[col] = {"archivos": len(idx), "contenidos_distintos": len(h), "contenidos_repetidos": len(rep),
                       "repetidos_entre_splits": len(cruzan)}
        for k, v in cruzan.items():
            choques.append({"tipo": f"mismo contenido ({col})", "dataset": "", "archivo": k,
                            "splits": ", ".join(sorted(set(v)))})
    d = out / "a6"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(d / "conteos.csv", index=False)
    pd.DataFrame(avisos, columns=["dataset", "split", "imagen", "aviso"]).to_csv(d / "avisos.csv", index=False)
    pd.DataFrame(choques, columns=["tipo", "dataset", "archivo", "splits"]).to_csv(d / "choques.csv", index=False)
    s = {"conteos": filas, "avisos": len(avisos), "avisos_distintos": Counter(re.sub(r"\S+\.(png|tif|jpe?g)", "<img>",
                                                                                     a["aviso"]) for a in avisos),
         "choques": choques, "hashes": hashes,
         "por_split": {sp: int((idx.split == sp).sum()) for sp in g["splits_comparar"]}}
    (d / "resumen.json").write_text(json.dumps(s, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2, default=str))


# ------------------------------------------------------------------------------------------------------------- A4

def enlazar(origen, destino):
    """Enlace duro de `origen` en `destino`, si todavía no existe."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists():
        os.link(origen, destino)


def subconjunto(nombre, raiz_origen, y_origen, split, stems, d):
    """Dataset de Ultralytics con enlaces duros a `stems` del split de origen (los cachés quedan dentro de `d`)."""
    ims = {p.stem: p for p in (raiz_origen / "images" / split).iterdir()}
    for s in stems:
        enlazar(ims[s], d / "images" / "val" / ims[s].name)
        enlazar(raiz_origen / "labels" / split / f"{s}.txt", d / "labels" / "val" / f"{s}.txt")
    y = {"path": d.as_posix(), "train": "images/val", "val": "images/val", "channels": y_origen.get("channels", 3),
         "names": y_origen["names"]}
    p = d / f"{nombre}.yaml"
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(y, ensure_ascii=False))  # JSON es YAML válido
    return p


def validador():
    """Validador de Ultralytics que no hace la evaluación COCO (se hace aquí con pycocotools)."""
    from ultralytics.models.yolo.detect import DetectionValidator

    class Validador(DetectionValidator):
        def eval_json(self, stats):  # sin faster-coco-eval: lo de COCO se hace aquí con pycocotools
            """No hace la evaluación COCO de Ultralytics: se hace aquí con pycocotools."""
            return stats
    return Validador


def iou_matriz(a, b):
    """IoU entre cajas (x0, y0, w, h)."""
    a, b = np.asarray(a, float).reshape(-1, 4), np.asarray(b, float).reshape(-1, 4)
    ax1, ay1, bx1, by1 = a[:, 0] + a[:, 2], a[:, 1] + a[:, 3], b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
    iw = np.clip(np.minimum(ax1[:, None], bx1[None]) - np.maximum(a[:, None, 0], b[None, :, 0]), 0, None)
    ih = np.clip(np.minimum(ay1[:, None], by1[None]) - np.maximum(a[:, None, 1], b[None, :, 1]), 0, None)
    inter = iw * ih
    return inter / (a[:, None, 2] * a[:, None, 3] + b[None, :, 2] * b[None, :, 3] - inter + 1e-12)


def emparejar(gt, pr, scores, iou_min):
    """Greedy por confianza, como COCO: cada predicción a la anotada libre de mayor IoU >= iou_min."""
    det = np.zeros(len(gt), bool)
    tp = np.zeros(len(pr), bool)
    if len(gt) and len(pr):
        m = iou_matriz(pr, gt)
        for i in np.argsort(-np.asarray(scores), kind="mergesort"):
            cand = np.where(~det & (m[i] >= iou_min))[0]
            if len(cand):
                j = cand[np.argmax(m[i, cand])]
                det[j] = tp[i] = True
    return det, tp


def map50_por_tramo(gt_df, preds, stems, tramos, etq, iou, max_dets):
    """mAP@0.5 con pycocotools por tramo de lado mayor: fuera del tramo, la anotada se ignora y la predicción que no
    acierta también (la misma regla que las áreas de COCO, con el lado mayor en lugar del área)."""
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    ids = {s: i for i, s in enumerate(stems, start=1)}
    gt = COCO()
    gt.dataset = {"images": [{"id": i} for i in ids.values()],
                  "annotations": [{"id": k + 1, "image_id": ids[r.stem], "category_id": 1,
                                   "bbox": [r.x, r.y, r.w, r.h], "area": max(r.w, r.h), "iscrowd": 0}
                                  for k, r in enumerate(gt_df.itertuples())],
                  "categories": [{"id": 1, "name": "persona"}]}
    with silencio():
        gt.createIndex()
    anns = []
    por = {}
    for p in preds:
        por.setdefault(p["image_id"], []).append(p)
    for s, ps in por.items():
        for p in sorted(ps, key=lambda q: -q["score"])[:max_dets]:
            anns.append({"image_id": ids[s], "category_id": 1, "bbox": p["bbox"], "score": p["score"]})
    with silencio():
        dt = gt.loadRes(anns)
    for a in dt.dataset["annotations"]:
        a["area"] = max(a["bbox"][2], a["bbox"][3])
    with silencio():
        dt.createIndex()
    lim = [0.0] + list(map(float, tramos)) + [1e9]
    out = {}
    rangos = [("todas", [0, 1e10])] + [(e, [lim[i], lim[i + 1] - 1e-6]) for i, e in enumerate(etq)]
    for nombre, rng in rangos:
        E = COCOeval(gt, dt, "bbox")
        E.params.imgIds = sorted(ids.values())
        E.params.catIds = [1]
        E.params.iouThrs = np.array([iou])
        E.params.maxDets = [max_dets]
        E.params.areaRng = [rng]
        E.params.areaRngLbl = [nombre]
        with silencio():
            E.evaluate()
            E.accumulate()
        q = E.eval["precision"][0, :, 0, 0, 0]
        out[nombre] = float(q[q > -1].mean()) if (q > -1).any() else float("nan")
    return out


def validar(cfg, rutas, out):
    """A4: valida por vuelo y por grupo (solo térmica y resto), el mAP@0.5 por tramo de tamaño y las personas detectadas
    con confianza 0.25 y 0.5."""
    from ultralytics import YOLO

    v = cfg["validar"]
    W, H = cfg["tam_termica"]
    tramos = cfg["tamanos"]["tramos_px"]
    etq = etiquetas_tramos(tramos)
    pares = pd.read_csv(rutas["data"] / cfg["pares"])
    solo_t = {(r.vuelo, int(r.posicion)) for r in pares.itertuples() if r.cajas_rgb == 0 and r.cajas_termica > 0}
    d = out / "a4"
    d.mkdir(parents=True, exist_ok=True)
    filas_val, filas_tramo, filas_det = [], [], []
    for modelo, info in v["modelos"].items():
        corrida = rutas["runs"] / "fase5" / info["corrida"]
        if not (corrida / "resumen.json").exists():
            print(f"{modelo}: {info['corrida']} no terminó; no se valida.")
            continue
        raiz, y = dataset_yaml(info["datos"])
        stems = sorted(p.stem for p in (raiz / "labels" / v["split"]).glob("*.txt"))
        ims = {p.stem: p for p in (raiz / "images" / v["split"]).iterdir()}
        gt_rows = []
        for s in stems:
            for k, (x0, y0, w, h) in enumerate(cajas_txt(raiz / "labels" / v["split"] / f"{s}.txt", W, H)):
                gt_rows.append({"stem": s, "k": k, "x": x0, "y": y0, "w": w, "h": h, "lado": max(w, h)})
        gt_df = pd.DataFrame(gt_rows)
        gt_df["vuelo"] = gt_df.stem.map(vuelo_de)
        gt_df["solo_termica"] = [(vuelo_de(s), int(s.rsplit("_", 1)[1])) in solo_t for s in gt_df.stem]
        gt_df["tramo"] = [etq[tramo_de(x, tramos)] for x in gt_df.lado]
        subs = {"todas": stems}
        for vu in sorted({vuelo_de(s) for s in stems}):
            subs[vu] = [s for s in stems if vuelo_de(s) == vu]
        subs["solo_termica"] = [s for s in stems if (vuelo_de(s), int(s.rsplit("_", 1)[1])) in solo_t]
        subs["resto"] = [s for s in stems if (vuelo_de(s), int(s.rsplit("_", 1)[1])) not in solo_t]
        yamls = {n: subconjunto(f"{modelo}_{n}", raiz, y, v["split"], ss, out / "datasets" / f"a4_{modelo}_{n}")
                 for n, ss in subs.items()}
        for peso in v["pesos"]:
            w_path = corrida / "weights" / peso
            m = YOLO(str(w_path))
            preds_todas = None
            for n, yp in yamls.items():
                carpeta = d / f"{modelo}_{Path(peso).stem}" / n
                met = m.val(validator=validador(), data=str(yp), split="val", save_json=(n == "todas"),
                            project=str(carpeta.parent), name=n, exist_ok=True, verbose=False, **v["val"])
                g = gt_df[gt_df.stem.isin(subs[n])]
                filas_val.append({"modelo": modelo, "pesos": peso, "subconjunto": n, "imagenes": len(subs[n]),
                                  "personas": len(g), "imagenes_sin_persona": len(set(subs[n]) - set(g.stem)),
                                  "map50": float(met.box.map50), "map50_95": float(met.box.map),
                                  "precision": float(met.box.mp), "recall": float(met.box.mr)})
                if n == "todas":
                    preds_todas = json.loads((carpeta / "predictions.json").read_text(encoding="utf-8"))
            # mAP@0.5 por tramo (y por vuelo, para comparar con el de Ultralytics), con pycocotools
            for n in subs:
                ss = subs[n]
                ps = [p for p in preds_todas if p["image_id"] in set(ss)]
                r = map50_por_tramo(gt_df[gt_df.stem.isin(ss)], ps, ss, tramos, etq, v["iou"], v["max_dets"])
                for tr, ap in r.items():
                    filas_tramo.append({"modelo": modelo, "pesos": peso, "subconjunto": n, "tramo": tr,
                                        "personas": int(((gt_df.stem.isin(ss)) & ((gt_df.tramo == tr) | (tr == "todas"))).sum()),
                                        "map50_pycocotools": ap})
            # predict con conf 0.25 y 0.5: personas detectadas (IoU >= 0.5)
            for conf in v["confianzas"]:
                det_rows, fp_img = [], {}
                regs = []
                # con una lista de rutas, Ultralytics abre las imágenes con PIL en RGB (3 canales); con un .txt usa
                # LoadImagesAndVideos, que lee como la validación (los 4 canales del TIFF)
                lista = d / f"lista_{modelo}_{v['split']}.txt"
                lista.write_text("\n".join(str(ims[s]) for s in stems), encoding="utf-8")
                vistos = set()
                for r in m.predict(str(lista), conf=conf, imgsz=v["predict"]["imgsz"], device=v["predict"]["device"],
                                   batch=v["predict"]["batch"], stream=True, verbose=False):
                    s = Path(r.path).stem
                    vistos.add(s)
                    xyxy = r.boxes.xyxy.cpu().numpy()
                    sc = r.boxes.conf.cpu().numpy()
                    pr = np.c_[xyxy[:, :2], xyxy[:, 2:] - xyxy[:, :2]] if len(xyxy) else np.zeros((0, 4))
                    g = gt_df[gt_df.stem == s]
                    det, tp = emparejar(g[["x", "y", "w", "h"]].to_numpy(), pr, sc, v["iou"])
                    for row, dd in zip(g.itertuples(), det):
                        det_rows.append({"stem": s, "k": row.k, "detectada": bool(dd)})
                    fp_img[s] = int((~tp).sum())
                    regs.append({"image_id": s, "bboxes": pr.round(2).tolist(), "scores": sc.round(4).tolist(),
                                 "tp": tp.tolist()})
                if vistos != set(stems):
                    raise SystemExit(f"predict devolvió {len(vistos)} imágenes de {len(stems)}")
                (d / f"predict_{modelo}_{Path(peso).stem}_conf{conf}.json").write_text(json.dumps(regs), encoding="utf-8")
                dd = gt_df.merge(pd.DataFrame(det_rows), on=["stem", "k"])
                grupos = [("todas", dd)] + [(vu, dd[dd.vuelo == vu]) for vu in sorted(dd.vuelo.unique())] + \
                         [("solo_termica", dd[dd.solo_termica]), ("resto", dd[~dd.solo_termica])] + \
                         [(f"tramo {e_}", dd[dd.tramo == e_]) for e_ in etq]
                for n, g in grupos:
                    if n == "todas":
                        ss = stems
                    elif n in subs:
                        ss = subs[n]
                    else:
                        ss = None
                    filas_det.append({"modelo": modelo, "pesos": peso, "conf": conf, "grupo": n, "personas": len(g),
                                      "detectadas": int(g.detectada.sum()),
                                      "recall": g.detectada.mean() if len(g) else float("nan"),
                                      "falsos_positivos": sum(fp_img[s] for s in ss) if ss is not None else "—",
                                      "imagenes": len(ss) if ss is not None else "—"})
            agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {modelo}",
                               f"A4: model.val (conf {v['val']['conf']}, imgsz {v['val']['imgsz']}) por vuelo y solo "
                               f"térmica/resto, mAP@0.5 por tramo con pycocotools, predict con conf "
                               f"{', '.join(map(str, v['confianzas']))}; pesos {rel(w_path)}; partición validación; "
                               f"salidas {rel(d)}",
                               "; ".join(f"{f['subconjunto']}: mAP50 {f['map50']:.4f}, R {f['recall']:.3f}"
                                         for f in filas_val if f["modelo"] == modelo and f["pesos"] == peso))
    pd.DataFrame(filas_val).to_csv(d / "val.csv", index=False)
    pd.DataFrame(filas_tramo).to_csv(d / "tramos.csv", index=False)
    pd.DataFrame(filas_det).to_csv(d / "detectadas.csv", index=False)
    with open(d / "tablas.md", "w", encoding="utf-8") as f:
        f.write(md(pd.DataFrame(filas_val), 4) + "\n\n" + md(pd.DataFrame(filas_tramo), 4) + "\n\n"
                + md(pd.DataFrame(filas_det), 3) + "\n")
    print((d / "tablas.md").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------------------- A5

def hoja(cfg, rutas, out):
    """A5: hoja de imágenes de validación al azar, con las cajas en verde y las predicciones en rojo, en la térmica y en
    la RGB."""
    h = cfg["hoja"]
    v = cfg["validar"]
    W, H = cfg["tam_termica"]
    idx = pd.read_csv(rutas["data"] / cfg["indice"])
    idx["stem"] = [Path(p).stem for p in idx.termica]
    idx = idx.set_index("stem")
    raiz, _ = dataset_yaml(v["modelos"]["fusion"]["datos"])
    stems = sorted(p.stem for p in (raiz / "labels" / v["split"]).glob("*.txt"))
    rng = np.random.default_rng(h["seed"])
    elegidas = sorted(rng.choice(len(stems), size=h["imagenes"], replace=False))
    elegidas = [stems[i] for i in elegidas]
    pj = out / "a4" / f"predict_fusion_best_conf{h['conf']}.json"
    preds = {r["image_id"]: r for r in json.loads(pj.read_text(encoding="utf-8"))}
    try:
        # fuente de Windows; si no está, la de PIL por omisión (solo cambia el aspecto de la hoja)
        fuente = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        fuente = ImageFont.load_default()
    d = out / "a5"
    d.mkdir(parents=True, exist_ok=True)
    paneles = []
    filas = []
    for s in elegidas:
        r = idx.loc[s]
        gt = cajas_txt(raiz / "labels" / v["split"] / f"{s}.txt", W, H)
        p = preds[s]
        ims = []
        for col in ["termica", "rgb"]:
            im = Image.open(rutas["data"] / "alineados" / r[col]).convert("RGB")
            dr = ImageDraw.Draw(im)
            for x0, y0, w, hh in gt:
                dr.rectangle([x0, y0, x0 + w, y0 + hh], outline=tuple(h["color_anotada"]), width=h["grosor"])
            for (x0, y0, w, hh), sc in zip(p["bboxes"], p["scores"]):
                dr.rectangle([x0, y0, x0 + w, y0 + hh], outline=tuple(h["color_prediccion"]), width=h["grosor"])
            ims.append(im)
        banda = 28
        par = Image.new("RGB", (2 * W + 6, H + banda), (255, 255, 255))
        par.paste(ims[0], (0, banda))
        par.paste(ims[1], (W + 6, banda))
        n_tp = int(sum(p["tp"]))
        ImageDraw.Draw(par).text((6, 4), f"{s}  anotadas {len(gt)}  predicciones {len(p['scores'])} (aciertos {n_tp})",
                                 fill=(0, 0, 0), font=fuente)
        par.save(d / f"{s}.png")
        paneles.append(par)
        filas.append({"stem": s, "anotadas": len(gt), "predicciones": len(p["scores"]), "aciertos": n_tp,
                      "detectadas": n_tp, "falsos_positivos": len(p["scores"]) - n_tp,
                      "confianzas": ", ".join(f"{x:.2f}" for x in p["scores"])})
    cols = h["columnas"]
    pw, ph = paneles[0].size
    filas_n = (len(paneles) + cols - 1) // cols
    lienzo = Image.new("RGB", (cols * pw + (cols - 1) * 10, filas_n * ph + (filas_n - 1) * 10), (255, 255, 255))
    for i, p in enumerate(paneles):
        lienzo.paste(p, ((i % cols) * (pw + 10), (i // cols) * (ph + 10)))
    lienzo.save(d / "hoja.png")
    pd.DataFrame(filas).to_csv(d / "hoja.csv", index=False)
    print(md(pd.DataFrame(filas)))
    print(f"Hoja en {rel(d / 'hoja.png')}")


# ------------------------------------------------------------------------------------------------------------- B

def b1_datos(cfg, rutas, out):
    """B1: dataset de solo térmica con los vuelos que no son de la prueba, repartido al azar por fotograma."""
    b = cfg["b1"]
    raiz, y = dataset_yaml(b["origen"])
    filas = []
    for split in ["train", "val"]:
        for p in sorted((raiz / "images" / split).iterdir()):
            if vuelo_de(p.stem) in b["vuelos"]:
                filas.append({"stem": p.stem, "vuelo": vuelo_de(p.stem), "origen": split, "imagen": p})
    df = pd.DataFrame(filas).sort_values("stem").reset_index(drop=True)
    if set(df.vuelo) != set(b["vuelos"]):
        raise SystemExit(f"Vuelos: {sorted(set(df.vuelo))}; se esperaban {b['vuelos']}")
    n = len(df)
    rng = np.random.default_rng(b["seed"])
    orden = rng.permutation(n)
    fr = b["fracciones"]
    n_tr, n_va = round(fr["train"] * n), round(fr["val"] * n)
    df["split"] = ""
    df.loc[orden[:n_tr], "split"] = "train"
    df.loc[orden[n_tr:n_tr + n_va], "split"] = "val"
    df.loc[orden[n_tr + n_va:], "split"] = "test"
    d = out / b["dataset"]
    if d.exists():
        raise SystemExit(f"Ya existe {d}: no se vuelve a crear.")
    for r in df.itertuples():
        enlazar(r.imagen, d / "images" / r.split / r.imagen.name)
        enlazar(raiz / "labels" / r.origen / f"{r.stem}.txt", d / "labels" / r.split / f"{r.stem}.txt")
    yy = {"path": d.as_posix(), "train": "images/train", "val": "images/val", "test": "images/test",
          "channels": y.get("channels", 3), "names": y["names"]}
    (d / "b1.yaml").write_text(json.dumps(yy, ensure_ascii=False), encoding="utf-8")
    cajas = {r.stem: sum(1 for l_ in (raiz / "labels" / r.origen / f"{r.stem}.txt").read_text().splitlines()
                         if l_.split()) for r in df.itertuples()}
    df["cajas"] = df.stem.map(cajas)
    df.drop(columns="imagen").to_csv(d / "reparto.csv", index=False)
    t = df.pivot_table(index="vuelo", columns="split", values="stem", aggfunc="count").fillna(0).astype(int)
    tc = df.groupby("split").agg(imagenes=("stem", "size"), cajas=("cajas", "sum"))
    print(md(t.reset_index()))
    print(md(tc.reset_index()))


def b_evaluar(cfg, rutas, out, corrida):
    """B: valida el best.pt de una corrida de diagnóstico en sus particiones."""
    from ultralytics import YOLO

    c = rutas["runs"] / cfg["base"]["carpeta"] / corrida
    r = json.loads((c / "resumen.json").read_text(encoding="utf-8"))
    conf = r["configuracion"]
    datos = ruta(conf["datos"])
    res = pd.read_csv(c / "results.csv")
    res.columns = [k.strip() for k in res.columns]
    i_best = res["metrics/mAP50-95(B)"].idxmax()
    i_max = res["metrics/mAP50(B)"].idxmax()
    v = dict(cfg["validar"]["val"])
    v["imgsz"] = conf["ultralytics"]["imgsz"]
    v["batch"] = r.get("lote_final") or v["batch"]
    m = YOLO(str(c / "weights" / "best.pt"))
    filas = []
    for split in cfg["evaluar_b"][corrida]["splits"]:
        met = m.val(validator=validador(), data=str(datos), split=split, project=str(c), name=f"eval_{split}",
                    exist_ok=True, verbose=False, **v)
        filas.append({"corrida": corrida, "split": split, "pesos": "best.pt", "imgsz": v["imgsz"],
                      "map50": float(met.box.map50), "map50_95": float(met.box.map), "precision": float(met.box.mp),
                      "recall": float(met.box.mr)})
    s = {"evaluacion": filas, "epoca_best_pt": int(res.epoch[i_best]),
         "max_map50_val": float(res["metrics/mAP50(B)"][i_max]), "epoca_max_map50": int(res.epoch[i_max]),
         "ultima_epoca_val": {k: float(res[k].iloc[-1]) for k in ["metrics/precision(B)", "metrics/recall(B)",
                                                                 "metrics/mAP50(B)", "metrics/mAP50-95(B)"]},
         "s_total": r.get("s_total_corrida"), "lote_final": r.get("lote_final"),
         "limite_w": r.get("gpu_limite_aplicado_mediana_w")}
    (c / "evaluacion.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {datos.stem}",
                       f"evaluación de {corrida}: model.val con best.pt (época {s['epoca_best_pt']}), conf "
                       f"{v['conf']}, imgsz {v['imgsz']}, splits {', '.join(f['split'] for f in filas)}; {rel(c)}",
                       "; ".join(f"{f['split']}: mAP50 {f['map50']:.4f}, mAP50-95 {f['map50_95']:.4f}, "
                                 f"P {f['precision']:.3f}, R {f['recall']:.3f}" for f in filas))
    print(json.dumps(s, ensure_ascii=False, indent=2))


def b_por_vuelo(cfg, rutas, out, corrida):
    """model.val del best.pt de una corrida de B por vuelo, en cada split de `evaluar_b` (datasets con enlaces duros
    en runs/<carpeta>/datasets/<corrida>_<split>_<vuelo>/). En B1 agrega cuántos fotogramas de ese split tienen uno de
    entrenamiento a 1 o 2 posiciones."""
    from ultralytics import YOLO

    c = rutas["runs"] / cfg["base"]["carpeta"] / corrida
    r = json.loads((c / "resumen.json").read_text(encoding="utf-8"))
    conf = r["configuracion"]
    raiz, y = dataset_yaml(conf["datos"])
    v = dict(cfg["validar"]["val"])
    v["imgsz"] = conf["ultralytics"]["imgsz"]
    v["batch"] = r.get("lote_final") or v["batch"]
    m = YOLO(str(c / "weights" / "best.pt"))
    reparto = None
    if (raiz / "reparto.csv").exists():
        reparto = pd.read_csv(raiz / "reparto.csv")
        reparto["pos"] = reparto.stem.str.rsplit("_", n=1).str[1].astype(int)
    filas = []
    for split in cfg["evaluar_b"][corrida]["splits"]:
        stems = sorted(p.stem for p in (raiz / "labels" / split).glob("*.txt"))
        for vu in sorted({vuelo_de(s) for s in stems}):
            ss = [s for s in stems if vuelo_de(s) == vu]
            yp = subconjunto(f"{corrida}_{split}_{vu}", raiz, y, split, ss,
                             out / "datasets" / f"{corrida}_{split}_{vu}")
            met = m.val(validator=validador(), data=str(yp), split="val", project=str(c / "por_vuelo"),
                        name=f"{split}_{vu}", exist_ok=True, verbose=False, **v)
            fila = {"corrida": corrida, "split": split, "vuelo": vu, "imagenes": len(ss),
                    "personas": sum(len(cajas_txt(raiz / "labels" / split / f"{s}.txt", 1, 1)) for s in ss),
                    "map50": float(met.box.map50), "map50_95": float(met.box.map), "precision": float(met.box.mp),
                    "recall": float(met.box.mr)}
            if reparto is not None:
                tr = np.sort(reparto[(reparto.vuelo == vu) & (reparto.split == "train")].pos.to_numpy())
                d = []
                for p in reparto[(reparto.vuelo == vu) & (reparto.split == split)].pos:
                    i = np.searchsorted(tr, p)
                    d.append(min(abs(p - tr[j]) for j in (i - 1, i) if 0 <= j < len(tr)))
                d = np.asarray(d)
                fila |= {"con_vecino_train_a_1": f"{(d == 1).mean():.3f}", "con_vecino_train_a_2_o_menos": f"{(d <= 2).mean():.3f}"}
            filas.append(fila)
    df = pd.DataFrame(filas)
    df.to_csv(c / "por_vuelo.csv", index=False)
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {Path(conf['datos']).stem}",
                       f"evaluación por vuelo de {corrida}: model.val con best.pt, conf {v['conf']}, imgsz {v['imgsz']}; "
                       f"{rel(c / 'por_vuelo.csv')}",
                       "; ".join(f"{f['split']} {f['vuelo']}: mAP50 {f['map50']:.4f}, R {f['recall']:.3f}" for f in filas))
    print(md(df, 4))


def copiar(cfg, rutas, out):
    """Copia para git las salidas livianas del diagnóstico a reports/<copiar.destino>/: los globs de
    `copiar.desde_runs` (dentro de runs/<carpeta>/, con la misma estructura) y los archivos de `copiar.extra` (dentro de
    runs/, solo lectura). No copia lo que coincide con `copiar.excluir` (los pesos)."""
    import shutil

    c = cfg["copiar"]
    destino = rutas["reports"] / c["destino"]
    pares = []
    for patron in c["desde_runs"]:
        hallados = [p for p in sorted(out.glob(patron))
                    if p.is_file() and not any(p.match(e) for e in c.get("excluir", []))]
        if not hallados:
            raise SystemExit(f"copiar: '{patron}' no encontró nada en {rel(out)}")
        pares += [(p, destino / p.relative_to(out)) for p in hallados]
    for origen, dest in (c.get("extra") or {}).items():
        p = rutas["runs"] / origen
        if not p.is_file():
            raise SystemExit(f"copiar: falta {rel(p)}")
        pares.append((p, destino / dest))
    for o, d in pares:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(o, d)
    print(f"{len(pares)} archivos, {sum(o.stat().st_size for o, _ in pares) / 1e6:.1f} MB en {rel(destino)}")


def main():
    """Corre la parte pedida del diagnóstico (A1 a A6, B1 o B)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True,
                    choices=["inventario", "estado", "tamanos", "integridad", "validar", "hoja", "b1_datos", "b_evaluar",
                             "b_por_vuelo", "copiar"])
    ap.add_argument("--corrida")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    out = rutas["runs"] / cfg["carpeta"]
    out.mkdir(parents=True, exist_ok=True)
    if args.parte in ("b_evaluar", "b_por_vuelo"):
        if not args.corrida:
            raise SystemExit(f"--parte {args.parte} pide --corrida")
        globals()[args.parte](cfg, rutas, out, args.corrida)
    else:
        globals()[args.parte](cfg, rutas, out)


if __name__ == "__main__":
    main()
