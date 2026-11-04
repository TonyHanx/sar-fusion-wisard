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

Uso:
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion prueba
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion prueba --solo-verificar
  python scripts/evaluar.py --config configs/fase6.yaml --rutas configs/rutas.yaml --particion validacion \
      --modelos fusion fusion_last
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

from comun import RAIZ, agregar_a_bitacora, fijar_semilla, leer_rutas, leer_yaml, pares_anotados  # noqa: E402

METRICAS = ["recall", "precision", "f2", "map50"]


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
    excl = np.asarray(sorted(excluidas))
    tramos = []  # [primer índice, último índice, con persona]
    for i in range(len(pos)):
        corta = (i > 0 and excluidos_cortan and len(excl)
                 and bool(((excl > pos[i - 1]) & (excl < pos[i])).any()))
        if tramos and tramos[-1][2] == con_persona[i] and not corta:
            tramos[-1][1] = i
        else:
            tramos.append([i, i, bool(con_persona[i])])
    bloque = np.full(len(pos), -1)
    episodios = []  # (posición inicial, posición final)
    for ini, fin, con in tramos:
        if con:
            bloque[ini:fin + 1] = len(episodios)
            episodios.append((pos[ini], pos[fin]))
    if not episodios:
        return np.zeros(len(pos), dtype=int), 1
    for i in np.where(bloque < 0)[0]:
        p = pos[i]
        ant = [k for k, (a, b) in enumerate(episodios) if b < p]
        sig = [k for k, (a, b) in enumerate(episodios) if a > p]
        a = ant[-1] if ant else None
        s = sig[0] if sig else None
        if s is None or (a is not None and p - episodios[a][1] <= episodios[s][0] - p):
            bloque[i] = a
        else:
            bloque[i] = s
    return bloque, len(episodios)


def preparar(cfg, rutas, nombre_part, modelos):
    """Fotogramas, personas (con nivel y si son dudosas) y bloques del bootstrap de la partición."""
    part = cfg["particiones"][nombre_part]
    ev = cfg["evaluacion"]
    W, H = ev["tam_imagen"]
    stems, txt = None, {}
    for m, info in modelos.items():
        d = Path(leer_yaml(ruta(info["datos"]))["path"]) / "labels" / part["split"]
        s = sorted(p.stem for p in d.glob("*.txt"))
        if stems is None:
            stems = s
            txt = {st: lineas(d / f"{st}.txt") for st in s}
        elif s != stems or any(lineas(d / f"{st}.txt") != txt[st] for st in s):
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
        n = pd.read_csv(ruta(part["niveles"]))
        n = n.set_index(["vuelo", "posicion", "indice_caja"])
        a = per[per.anotado].set_index(["vuelo", "posicion", "indice_caja"])
        if set(a.index) != set(n.index):
            raise SystemExit(f"{part['niveles']} no tiene las mismas personas que los fotogramas anotados: "
                             f"{len(set(a.index) - set(n.index))} faltan y {len(set(n.index) - set(a.index))} sobran.")
        n = n.loc[a.index]
        dif = np.abs(np.c_[a.x - n.ter_x0, a.y - n.ter_y0, a.x + a.w - n.ter_x1, a.y + a.h - n.ter_y1]).max()
        if dif > 1.0:
            raise SystemExit(f"Las cajas de {part['niveles']} no coinciden con las etiquetas (hasta {dif:.2f} px).")
        per.loc[per.anotado, "nivel"] = [v if isinstance(v, str) else "sin_nivel" for v in n.nivel]

    if "cajas_dudosas" in part:
        d = leer_yaml(ruta(part["cajas_dudosas"]))
        clave = dict(zip(zip(per.stem, per.indice_caja), per.index))
        for c in d["cajas"] + d["seguidas"]:
            k = (Path(c["etiqueta"]).stem, c["indice_caja"])
            if k not in clave or per.at[clave[k], "linea"].split() != c["linea"].split():
                raise SystemExit(f"Caja dudosa sin su línea en las etiquetas: {k}")
            per.at[clave[k], "dudosa"] = True
        if per.dudosa.sum() != d["resumen"]["total"]:
            raise SystemExit(f"Cajas dudosas: {per.dudosa.sum()}; el yaml dice {d['resumen']['total']}.")
        anot = per[per.anotado]
        if ((anot.nivel == "sin_nivel") != anot.dudosa).any():
            raise SystemExit("En los fotogramas anotados, las dudosas tienen que ser justo las sin nivel.")

    # bloques del bootstrap, vuelo por vuelo
    con = per.groupby("img_id").size()
    fot["con_persona"] = fot.img_id.map(con).fillna(0).to_numpy() > 0
    pares = pares_anotados(rutas["data"] / ev["pares"])
    fot["bloque"] = -1
    nb = 0
    for vuelo in part["vuelos"]:
        f = fot[fot.vuelo == vuelo].sort_values("posicion")
        todas = set(pares[pares.vuelo == vuelo].posicion)
        if not set(f.posicion) <= todas:
            raise SystemExit(f"{vuelo}: hay fotogramas que no están en {ev['pares']}.")
        b, k = bloques_por_episodio(f.posicion.to_numpy(), f.con_persona.to_numpy(), todas - set(f.posicion),
                                    cfg["bootstrap"]["excluidos_cortan"])
        fot.loc[f.index, "bloque"] = b + nb
        nb += k
    return {"fot": fot, "per": per, "nb": nb, "part": part, "W": W, "H": H}


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

def predecir(clave, info, cfg, rutas, nombre_part, part):
    """predictions.json del validador de Ultralytics (se reutiliza si ya existe)."""
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionValidator

    class Validador(DetectionValidator):
        def eval_json(self, stats):  # sin faster-coco-eval: la evaluación se hace aquí con pycocotools
            return stats

    carpeta = rutas["runs"] / cfg["carpeta"] / nombre_part / clave
    pj = carpeta / "predictions.json"
    pesos = rutas["runs"] / cfg["corridas"] / info["corrida"] / info.get("pesos", cfg["pesos"])
    if pj.exists():
        print(f"{clave}: se reutilizan las predicciones de {pj}")
        ultra = json.loads((carpeta / "ultralytics.json").read_text(encoding="utf-8"))
    else:
        if not pesos.exists():
            raise SystemExit(f"No existen los pesos {pesos}")
        modelo = YOLO(str(pesos))
        t = time.time()
        met = modelo.val(validator=Validador, data=str(ruta(info["datos"])), split=part["split"], save_json=True,
                         project=str(carpeta.parent), name=clave, exist_ok=True, **cfg["prediccion"])
        ultra = {"pesos": rel(pesos), "segundos": round(time.time() - t, 1),
                 "map50": float(met.box.map50), "map50_95": float(met.box.map), "precision": float(met.box.mp),
                 "recall": float(met.box.mr)}
        carpeta.mkdir(parents=True, exist_ok=True)
        if not pj.exists():  # sin ninguna predicción, Ultralytics no escribe el archivo
            pj.write_text("[]", encoding="utf-8")
        (carpeta / "ultralytics.json").write_text(json.dumps(ultra, indent=2), encoding="utf-8")
    return json.loads(pj.read_text(encoding="utf-8")), ultra


# ------------------------------------------------------------------------------------------------------- evaluación

def coco_gt(datos, ignorar):
    W, H = datos["W"], datos["H"]
    per = datos["per"]
    ds = {"images": [{"id": int(i), "width": W, "height": H} for i in datos["fot"].img_id],
          "annotations": [{"id": int(p.gt_id), "image_id": int(p.img_id), "category_id": 1,
                           "bbox": [float(p.x), float(p.y), float(p.w), float(p.h)], "area": float(p.w * p.h),
                           "iscrowd": int(ig)} for p, ig in zip(per.itertuples(), ignorar)],
          "categories": [{"id": 1, "name": "persona"}]}
    gt = COCO()
    gt.dataset = ds
    with silencio():
        gt.createIndex()
    return gt


def coco_dt(gt, preds, datos, max_dets):
    """Predicciones de Ultralytics (image_id = nombre del archivo) como resultados de COCO, hasta max_dets por imagen."""
    ids = dict(zip(datos["fot"].stem, datos["fot"].img_id))
    por_img = {}
    for p in preds:
        por_img.setdefault(p["image_id"], []).append(p)
    anns = []
    for stem, ps in por_img.items():
        if stem not in ids:
            raise SystemExit(f"Predicción de una imagen que no es de la partición: {stem}")
        for p in sorted(ps, key=lambda q: -q["score"])[:max_dets]:
            anns.append({"image_id": int(ids[stem]), "category_id": 1, "bbox": p["bbox"], "score": p["score"]})
    if not anns:
        dt = COCO()
        dt.dataset = {"images": gt.dataset["images"], "annotations": [], "categories": gt.dataset["categories"]}
        with silencio():
            dt.createIndex()
        return dt
    with silencio():
        return gt.loadRes(anns)


def ap_coco(tp, fp, npig, rec_thrs):
    """AP de COCO (101 puntos) a un IoU, con las predicciones ya ordenadas por confianza (sin las ignoradas)."""
    if npig == 0:
        return np.nan
    if len(tp) == 0:
        return 0.0
    tpc = np.cumsum(tp, dtype=float)
    fpc = np.cumsum(fp, dtype=float)
    rc = tpc / npig
    pr = tpc / (tpc + fpc + np.spacing(1))
    pr = np.maximum.accumulate(pr[::-1])[::-1]
    inds = np.searchsorted(rc, rec_thrs, side="left")
    q = np.where(inds < len(pr), pr[np.minimum(inds, len(pr) - 1)], 0.0)
    return float(q.mean())


def evaluar(gt, dt, img_ids, datos, ev):
    """Evalúa con COCOeval y deja lo necesario para el bootstrap por bloques."""
    E = COCOeval(gt, dt, "bbox")
    p = E.params
    p.imgIds = sorted(int(i) for i in img_ids)
    p.catIds = [1]
    p.iouThrs = np.array([ev["iou"]])
    p.maxDets = [ev["max_dets"]]
    p.areaRng = [[0, 1e10]]
    p.areaRngLbl = ["all"]
    with silencio():
        E.evaluate()
        E.accumulate()
    q = E.eval["precision"][0, :, 0, 0, 0]
    ap_pyc = float(q[q > -1].mean()) if (q > -1).any() else np.nan

    bloque = dict(zip(datos["fot"].img_id, datos["fot"].bloque))
    nb = datos["nb"]
    npig_b, tpc_b, fpc_b = np.zeros(nb), np.zeros(nb), np.zeros(nb)
    sc, tp, fp, bl = [], [], [], []
    detectada = {}
    for e in E.evalImgs:
        if e is None:
            continue
        b = bloque[e["image_id"]]
        s = np.asarray(e["dtScores"], dtype=float)
        m = np.asarray(e["dtMatches"][0])
        ig = np.asarray(e["dtIgnore"][0]).astype(bool)
        t, f = (m > 0) & ~ig, (m == 0) & ~ig
        keep = t | f
        sc.append(s[keep])
        tp.append(t[keep])
        fp.append(f[keep])
        bl.append(np.full(int(keep.sum()), b))
        gig = np.asarray(e["gtIgnore"]).astype(bool)
        npig_b[b] += (~gig).sum()
        alta = s >= ev["conf"]
        tpc_b[b] += (t & alta).sum()
        fpc_b[b] += (f & alta).sum()
        conf_de = dict(zip(e["dtIds"], s))
        for gid, mm, g in zip(e["gtIds"], e["gtMatches"][0], gig):
            if not g:
                detectada[int(gid)] = bool(mm > 0 and conf_de[mm] >= ev["conf"])
    sc = np.concatenate(sc) if sc else np.zeros(0)
    orden = np.argsort(-sc, kind="mergesort")
    r = {"tp": np.concatenate(tp)[orden] if tp else np.zeros(0, bool),
         "fp": np.concatenate(fp)[orden] if fp else np.zeros(0, bool),
         "bl": np.concatenate(bl)[orden] if bl else np.zeros(0, int),
         "npig_b": npig_b, "tpc_b": tpc_b, "fpc_b": fpc_b, "detectada": detectada,
         "rec_thrs": p.recThrs, "beta": ev["beta"]}
    unos = np.ones(nb, dtype=int)
    r["punto"] = metricas(r, unos)
    if not (np.isnan(ap_pyc) and np.isnan(r["punto"]["map50"])) and abs(r["punto"]["map50"] - ap_pyc) > 1e-9:
        raise SystemExit(f"El mAP@0.5 propio ({r['punto']['map50']}) no coincide con el de pycocotools ({ap_pyc}).")
    r["n_fotogramas"] = len(img_ids)
    r["n_personas"] = int(npig_b.sum())
    r["tp_conf"], r["fp_conf"] = int(tpc_b.sum()), int(fpc_b.sum())
    return r


def metricas(r, cuentas):
    """Métricas con cada bloque repetido `cuentas` veces (todo 1 = la muestra original)."""
    npig = cuentas @ r["npig_b"]
    tp, fp = cuentas @ r["tpc_b"], cuentas @ r["fpc_b"]
    rec = tp / npig if npig else np.nan
    pre = tp / (tp + fp) if (tp + fp) else np.nan  # sin predicciones >= conf, la precisión no está definida
    b2 = r["beta"] ** 2
    den = (1 + b2) * tp + b2 * (npig - tp) + fp  # F-beta con conteos: igual a la de P y R, y 0 si no hay aciertos
    f2 = (1 + b2) * tp / den if den else np.nan
    w = cuentas[r["bl"]]
    ap = ap_coco(np.repeat(r["tp"], w), np.repeat(r["fp"], w), npig, r["rec_thrs"])
    return {"recall": rec, "precision": pre, "f2": f2, "map50": ap}


def bootstrap(r, cuentas_b):
    return {k: np.array(v) for k, v in pd.DataFrame([metricas(r, c) for c in cuentas_b]).items()}


def intervalo(valores, confianza):
    v = valores[~np.isnan(valores)]
    if not len(v):
        return np.nan, np.nan
    a = (1 - confianza) / 2 * 100
    lo, hi = np.percentile(v, [a, 100 - a])
    return float(lo), float(hi)


# ----------------------------------------------------------------------------------------------------------- salidas

def grafico(res, cfg, part, modelos, ruta_png, dudosas, n_remuestreos):
    f = cfg["figura"]
    scs = [s for s in part["subconjuntos"] if s.get("grafico")]
    nombres = [s["nombre"] for s in scs]
    fig, ax = plt.subplots(figsize=(5.6, 4.0), facecolor=f["fondo"])
    ax.set_facecolor(f["fondo"])
    x = np.arange(len(nombres))
    for k, (m, info) in enumerate(modelos.items()):
        d = res[(res.tipo == "modelo") & (res.modelo == m) & (res.dudosas == dudosas)].set_index("subconjunto")
        d = d.loc[nombres]
        y = d.recall.to_numpy(dtype=float)
        err = np.vstack([y - d.recall_ic_inf.to_numpy(dtype=float), d.recall_ic_sup.to_numpy(dtype=float) - y])
        dx = (k - (len(modelos) - 1) / 2) * 0.07
        ax.errorbar(x + dx, y, yerr=err, color=info["color"], marker="o", markersize=7, linewidth=2, capsize=3,
                    elinewidth=1, label=info["nombre"], markeredgecolor=f["fondo"], markeredgewidth=1.5, zorder=3)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(f["rejilla"])
    ax.grid(axis="y", color=f["rejilla"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xticks(x, [s.get("rotulo", s["nombre"]) for s in scs])
    ax.set_xlim(-0.5, len(nombres) - 0.5)
    ax.set_ylim(0, 1)
    ax.set_ylabel(f"Recall (confianza ≥ {cfg['evaluacion']['conf']})", fontsize=9, color=f["texto_secundario"])
    ax.tick_params(colors=f["texto_secundario"], labelsize=8)
    fig.suptitle(part["titulo"], x=0.01, y=0.99, ha="left", va="top", fontsize=10, color=f["texto"])
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.005, 0.94), ncol=len(l), frameon=False, fontsize=8,
               labelcolor=f["texto"])
    fig.text(0.01, 0.01, f"Barras: IC del {int(cfg['bootstrap']['confianza'] * 100)} % por bootstrap de episodios "
             f"({n_remuestreos:,} remuestreos).".replace(",", " "), fontsize=7, color=f["texto_secundario"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.88))
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_png, dpi=f["dpi"], facecolor=f["fondo"])
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--particion", required=True)
    ap.add_argument("--modelos", nargs="+", help="por omisión, los de `modelos`")
    ap.add_argument("--solo-verificar", action="store_true", help="etiquetas, niveles, dudosas y bloques; sin predecir")
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

    datos = preparar(cfg, rutas, args.particion, modelos)
    verificar(datos, args.particion)
    if args.solo_verificar:
        return
    if part.get("una_sola_vez") and any(p.exists() for p in salidas.values()):
        raise SystemExit("La partición ya se evaluó (existen " + ", ".join(rel(p) for p in
                                                                           salidas.values() if p.exists())
                         + "). Se evalúa una sola vez.")

    t0 = time.time()
    ev = cfg["evaluacion"]
    dudosas = ["con", "sin"] if "cajas_dudosas" in part else ["con"]
    B = cfg["bootstrap"]["remuestreos"]
    rng = np.random.default_rng(cfg["bootstrap"]["seed"])
    nb = datos["nb"]
    cuentas_b = np.stack([np.bincount(rng.integers(0, nb, nb), minlength=nb) for _ in range(B)])
    conf_ic = cfg["bootstrap"]["confianza"]

    preds, ultra = {}, {}
    for k, info in modelos.items():
        preds[k], ultra[k] = predecir(k, info, cfg, rutas, args.particion, part)
        print(f"{k}: {len(preds[k])} predicciones; Ultralytics: mAP@0.5 {ultra[k]['map50']:.4f}")

    per = datos["per"]
    filas, filas_mc, evals = [], [], {}
    for sc in part["subconjuntos"]:
        imgs = datos["fot"] if sc["fotogramas"] == "todos" else datos["fot"][datos["fot"].anotado]
        for dud in dudosas:
            cuenta = pd.Series(True, index=per.index) if sc["personas"] == "todas" else (per.nivel == sc["personas"])
            if dud == "sin":
                cuenta &= ~per.dudosa
            gt = coco_gt(datos, ~cuenta.to_numpy())
            boot = {}
            for k in modelos:
                dt = coco_dt(gt, preds[k], datos, ev["max_dets"])
                r = evaluar(gt, dt, imgs.img_id, datos, ev)
                evals[(sc["nombre"], dud, k)] = r
                t = time.time()
                boot[k] = bootstrap(r, cuentas_b)
                fila = {"particion": args.particion, "subconjunto": sc["nombre"], "dudosas": dud, "tipo": "modelo",
                        "modelo": k, "nombre": modelos[k]["nombre"], "n_fotogramas": r["n_fotogramas"],
                        "n_personas": r["n_personas"], "tp": r["tp_conf"], "fp": r["fp_conf"],
                        "fn": r["n_personas"] - r["tp_conf"]}
                for mt in METRICAS:
                    fila[mt] = r["punto"][mt]
                    fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = intervalo(boot[k][mt], conf_ic)
                fila["remuestreos"] = B
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[k][mt]).sum() for mt in METRICAS))
                filas.append(fila)
                print(f"{sc['nombre']:>13} {dud} {k:>11}: recall {fila['recall']:.3f} "
                      f"[{fila['recall_ic_inf']:.3f}, {fila['recall_ic_sup']:.3f}], precisión {fila['precision']:.3f}, "
                      f"F2 {fila['f2']:.3f}, mAP@0.5 {fila['map50']:.3f}  ({time.time() - t:.0f} s de bootstrap)",
                      flush=True)
            for a, b in combinations(modelos, 2):
                fila = {"particion": args.particion, "subconjunto": sc["nombre"], "dudosas": dud,
                        "tipo": "diferencia", "modelo": f"{a} - {b}",
                        "nombre": f"{modelos[a]['nombre']} − {modelos[b]['nombre']}",
                        "n_fotogramas": evals[(sc["nombre"], dud, a)]["n_fotogramas"],
                        "n_personas": evals[(sc["nombre"], dud, a)]["n_personas"]}
                for mt in METRICAS:
                    fila[mt] = evals[(sc["nombre"], dud, a)]["punto"][mt] - evals[(sc["nombre"], dud, b)]["punto"][mt]
                    fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = intervalo(boot[a][mt] - boot[b][mt], conf_ic)
                fila["remuestreos"] = B
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[a][mt] - boot[b][mt]).sum() for mt in METRICAS))
                filas.append(fila)

        if sc.get("mcnemar") and len(modelos) > 1:
            dud = cfg["mcnemar"]["dudosas"] if cfg["mcnemar"]["dudosas"] in dudosas else dudosas[0]
            pares = list(combinations(modelos, 2))
            for a, b in pares:
                da, db = evals[(sc["nombre"], dud, a)]["detectada"], evals[(sc["nombre"], dud, b)]["detectada"]
                if set(da) != set(db):
                    raise SystemExit(f"McNemar: no son las mismas personas en {a} y {b} ({sc['nombre']}).")
                ids = sorted(da)
                xa = np.array([da[i] for i in ids])
                xb = np.array([db[i] for i in ids])
                tabla = [[int((xa & xb).sum()), int((xa & ~xb).sum())], [int((~xa & xb).sum()), int((~xa & ~xb).sum())]]
                res = mcnemar(tabla, exact=cfg["mcnemar"]["exacta"])
                p_b = min(1.0, float(res.pvalue) * len(pares))
                filas_mc.append({"particion": args.particion, "subconjunto": sc["nombre"], "dudosas": dud,
                                 "modelo_a": a, "modelo_b": b, "n_personas": len(ids), "ambos": tabla[0][0],
                                 "solo_a": tabla[0][1], "solo_b": tabla[1][0], "ninguno": tabla[1][1],
                                 "recall_a": float(xa.mean()), "recall_b": float(xb.mean()),
                                 "estadistico": float(res.statistic), "p": float(res.pvalue),
                                 "comparaciones": len(pares), "p_bonferroni": p_b, "alfa": cfg["mcnemar"]["alfa"],
                                 "significativo": p_b < cfg["mcnemar"]["alfa"]})

    res = pd.DataFrame(filas)
    for p in salidas.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(salidas["resultados"], index=False)
    mc = pd.DataFrame(filas_mc)
    mc.to_csv(salidas["mcnemar"], index=False)
    dud_g = cfg["mcnemar"]["dudosas"] if cfg["mcnemar"]["dudosas"] in dudosas else dudosas[0]
    grafico(res, cfg, part, modelos, salidas["grafico"], dud_g, B)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.precision", 3):
        print(res[["subconjunto", "dudosas", "modelo", "n_personas", "recall", "recall_ic_inf", "recall_ic_sup",
                   "precision", "f2", "map50"]].to_string(index=False))
        if len(mc):
            print(mc[["subconjunto", "modelo_a", "modelo_b", "n_personas", "solo_a", "solo_b", "p", "p_bonferroni",
                      "significativo"]].to_string(index=False))
    print(f"Salidas: {', '.join(rel(p) for p in salidas.values())} ({time.time() - t0:.0f} s)")

    for k, info in modelos.items():
        resumen = []
        for sc in part["subconjuntos"]:
            d = res[(res.tipo == "modelo") & (res.modelo == k) & (res.subconjunto == sc["nombre"])
                    & (res.dudosas == dudosas[0])].iloc[0]
            resumen.append(f"{sc['nombre']} ({dudosas[0]} dudosas): recall {d.recall:.3f} "
                           f"[{d.recall_ic_inf:.3f}, {d.recall_ic_sup:.3f}], P {d.precision:.3f}, F2 {d.f2:.3f}, "
                           f"mAP50 {d.map50:.3f}")
        config = (f"partición {args.particion} (split {part['split']}); pesos {ultra[k]['pesos']}; conf {ev['conf']} "
                  f"e IoU {ev['iou']} (mAP@0.5 con conf {cfg['prediccion']['conf']}), maxDets {ev['max_dets']}; "
                  f"bootstrap {B} remuestreos de {nb} bloques (episodios), seed={cfg['bootstrap']['seed']}; "
                  f"salidas {', '.join(rel(p) for p in salidas.values())}")
        agregar_a_bitacora(rutas["bitacora"], part["fase_bitacora"], f"YOLO26s {k}", config,
                           "; ".join(resumen) + f"; Ultralytics (su AP) mAP50 {ultra[k]['map50']:.4f}")


if __name__ == "__main__":
    main()
