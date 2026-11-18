"""Fase 7, parte C0: auditoría de las térmicas anotadas que quedan fuera de los 4 617 pares (sin entrenar).

Por cada carpeta IR de `c0.carpetas` (configs/fase7.yaml):
  - estadísticas de las etiquetas: fotogramas, .txt, cajas, repetidas, cajas raras, tramos seguidos con caja;
  - tamaño de las personas (lado mayor en px de 640 x 512) y tramos de QFDet;
  - el detector de `c0.detector` corre sobre todos los fotogramas y señala candidatos: predicciones >= conf_alta sin
    caja cerca (posible persona sin caja) y cajas sin ninguna predicción cerca (posible caja mal puesta);
  - muestra al azar (seed 0) de 10 fotogramas con cajas y 10 sin cajas, en un mosaico para revisarlo a ojo, con las
    cajas en verde, las predicciones en rojo, recortes ampliados de los candidatos y un gráfico por fotograma.

Otras partes:
  - alineacion: corrimiento del fondo de FHL 0403/0564/0566 con las semejanzas candidatas (`c0.alineacion`);
  - clasificar: aplica `c0.clasificacion` y cuenta fotogramas, personas y tramos de tamaño por carpeta y por sitio;
  - puntos: error de las semejanzas en los puntos marcados a mano con scripts/fase7_marcar_puntos.py.

Uso:
  .venv\\Scripts\\python.exe scripts\\fase7_c0_auditoria.py --config configs\\fase7.yaml --rutas configs\\rutas.yaml --parte auditar
  (partes: auditar, alineacion, clasificar, puntos)
Salidas en runs/<carpeta>/c0/<parte>/ (alineacion y puntos en c0/alineacion/).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from comun import RAIZ, agregar_a_bitacora, leer_cajas_yolo, leer_rutas, leer_yaml
from fase1_pares import clave_natural

VERDE, ROJO, AMARILLO, BLANCO = (0, 230, 0), (255, 40, 40), (255, 220, 0), (255, 255, 255)


def ruta(p):
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def rel(p):
    p = Path(p)
    return p.relative_to(RAIZ).as_posix() if p.is_relative_to(RAIZ) else str(p)


def comprobar_prohibidas(cfg, nombres):
    malas = sorted(set(nombres) & set(cfg["prohibidas"]))
    if malas:
        raise SystemExit(f"Carpetas prohibidas (FHL 0405) en la configuración: {malas}")


def md(df, dec=3):
    cols = list(df.columns)
    filas = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        filas.append("| " + " | ".join(f"{v:.{dec}f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(filas)


def iou(a, b):
    """IoU entre cajas xyxy: a (n, 4) y b (m, 4) -> (n, m)."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x0 = np.maximum(a[:, None, 0], b[None, :, 0])
    y0 = np.maximum(a[:, None, 1], b[None, :, 1])
    x1 = np.minimum(a[:, None, 2], b[None, :, 2])
    y1 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = lambda c: (c[:, 2] - c[:, 0]) * (c[:, 3] - c[:, 1])
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


def tramos_seguidos(pos):
    """Tramos [a, b] de posiciones seguidas."""
    pos = sorted(pos)
    out = []
    for p in pos:
        if out and p == out[-1][1] + 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return out


def leer_carpeta(cfg, D, nombre):
    """Fotogramas de una carpeta en orden natural, con sus cajas (xyxy en px de la térmica)."""
    tw, th = cfg["tam_termica"]
    d = D / nombre
    ims = sorted((f for f in d.iterdir() if f.suffix.lower() in cfg["extensiones"]), key=lambda f: clave_natural(f.name))
    filas, raras, repetidas = [], 0, 0
    for i, f in enumerate(ims):
        txt = f.with_suffix(".txt")
        cajas = []
        if txt.exists():
            lineas = [l.strip() for l in txt.read_text().splitlines() if l.strip()]
            repetidas += len(lineas) - len(set(lineas))
            for c, cx, cy, w, h in leer_cajas_yolo(txt):
                if c != 0 or w <= 0 or h <= 0 or not (0 <= cx <= 1 and 0 <= cy <= 1):
                    raras += 1
                cajas.append([(cx - w / 2) * tw, (cy - h / 2) * th, (cx + w / 2) * tw, (cy + h / 2) * th])
            # las repetidas se quitan, como en la fase 3a
            cajas = [list(c) for c in dict.fromkeys(tuple(round(v, 4) for v in c) for c in cajas)]
        filas.append({"posicion": i, "archivo": f.name, "tiene_txt": txt.exists(), "cajas": np.array(cajas).reshape(-1, 4)})
    return filas, raras, repetidas


def predecir(cfg, rutas, D, nombre, filas, out):
    """Predicciones del detector en todos los fotogramas (xyxy, conf); se guardan en un csv y se reutilizan."""
    from ultralytics import YOLO

    archivo = out / "predicciones" / f"{nombre}.csv"
    if archivo.exists():
        p = pd.read_csv(archivo)
    else:
        det = cfg["c0"]["detector"]
        m = YOLO(str(ruta(det["pesos"])))
        lista = out / "predicciones" / f"{nombre}.txt"
        lista.parent.mkdir(parents=True, exist_ok=True)
        lista.write_text("\n".join(str(D / nombre / f["archivo"]) for f in filas), encoding="utf-8")
        reg, vistos = [], 0
        idx = {f["archivo"]: f["posicion"] for f in filas}
        for r in m.predict(str(lista), conf=det["conf_minima"], imgsz=det["imgsz"], device=det["device"],
                           batch=det["batch"], stream=True, verbose=False):
            vistos += 1
            pos = idx[Path(r.path).name]
            for (x0, y0, x1, y1), c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
                reg.append({"posicion": pos, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "conf": float(c)})
        if vistos != len(filas):
            raise SystemExit(f"{nombre}: el detector vio {vistos} de {len(filas)} fotogramas")
        p = pd.DataFrame(reg, columns=["posicion", "x0", "y0", "x1", "y1", "conf"])
        p.to_csv(archivo, index=False)
    if tiene_logo(cfg, D, nombre, filas):
        lg = cfg["c0"]["logo"]
        x0, y0, x1, y1 = lg["caja"]
        mg = lg["margen"]
        cx, cy = (p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2
        p = p[~((cx >= x0 - mg) & (cx <= x1 + mg) & (cy >= y0 - mg) & (cy <= y1 + mg))]
    return {k: g[["x0", "y0", "x1", "y1", "conf"]].to_numpy() for k, g in p.groupby("posicion")}


def tiene_logo(cfg, D, nombre, filas):
    """True si la marca de agua FLIR está en la caja de `c0.logo` en todos los fotogramas revisados."""
    lg = cfg["c0"]["logo"]
    x0, y0, x1, y1 = lg["caja"]
    sel = filas[:: max(1, len(filas) // lg["fotogramas"])][: lg["fotogramas"]]
    a = np.stack([np.asarray(Image.open(D / nombre / f["archivo"]).convert("L"))[y0:y1 + 1, x0:x1 + 1] for f in sel])
    return int((a.min(0) >= 235).sum()) >= lg["pixeles_minimos"]


def candidatos(cfg, f, preds):
    """Índices de predicciones >= conf_dibujo sin caja cerca y de cajas sin predicción >= conf_minima cerca."""
    det = cfg["c0"]["detector"]
    g = f["cajas"]
    p = preds.get(f["posicion"], np.zeros((0, 5)))
    m = iou(p[:, :4], g)
    pred_sin = [i for i in range(len(p)) if p[i, 4] >= det["conf_dibujo"] and (m.shape[1] == 0 or m[i].max() < det["iou_minimo"])]
    caja_sin = [j for j in range(len(g)) if m.shape[0] == 0 or m[:, j].max() < det["iou_minimo"]]
    return p, pred_sin, caja_sin


def vecinos_con_caja(filas, pos, maximo):
    """Fotogramas con caja más cercanos antes y después de `pos`, a `maximo` posiciones o menos."""
    out = []
    for paso in (-1, 1):
        q = pos + paso
        while 0 <= q < len(filas) and abs(q - pos) <= maximo:
            if len(filas[q]["cajas"]):
                out.append(q)
                break
            q += paso
    return out


def huecos_cortos(filas, maximo):
    """Tramos de fotogramas con .txt vacío, de `maximo` o menos, con fotogramas con caja a los dos lados."""
    con = [len(f["cajas"]) > 0 for f in filas]
    n, i, huecos = len(filas), 0, []
    while i < n:
        if not con[i] and filas[i]["tiene_txt"]:
            j = i
            while j + 1 < n and not con[j + 1]:
                j += 1
            if i > 0 and j + 1 < n and con[i - 1] and con[j + 1] and j - i + 1 <= maximo:
                huecos.append((i, j))
            i = j + 1
        else:
            i += 1
    return huecos


def mosaico(cfg, D, nombre, filas, preds, muestra, salida, fuente, fuente_c):
    mc = cfg["c0"]["mosaico"]
    det = cfg["c0"]["detector"]
    tw, th = cfg["tam_termica"]
    e = mc["escala"]
    W, H = int(tw * e), int(th * e)
    cols = mc["columnas"]
    filas_m = int(np.ceil(len(muestra) / cols))
    lado, z = mc["lado_recorte"], mc["zoom_recorte"]
    R = lado * z
    recortes = []
    ancho = cols * W
    lienzo_t = Image.new("RGB", (ancho, filas_m * (H + 18)), (30, 30, 30))
    dib = ImageDraw.Draw(lienzo_t)
    for k, pos in enumerate(muestra):
        f = filas[pos]
        im = Image.open(D / nombre / f["archivo"]).convert("RGB")
        p, pred_sin, caja_sin = candidatos(cfg, f, preds)
        x, y = (k % cols) * W, (k // cols) * (H + 18)
        lienzo_t.paste(im.resize((W, H)), (x, y + 18))
        for c in f["cajas"]:
            dib.rectangle([x + c[0] * e, y + 18 + c[1] * e, x + c[2] * e, y + 18 + c[3] * e], outline=VERDE)
        for i in range(len(p)):
            if p[i, 4] >= det["conf_dibujo"]:
                dib.rectangle([x + p[i, 0] * e - 1, y + 18 + p[i, 1] * e - 1, x + p[i, 2] * e + 1, y + 18 + p[i, 3] * e + 1],
                              outline=ROJO)
        n_p = int((p[:, 4] >= det["conf_dibujo"]).sum()) if len(p) else 0
        dib.text((x + 3, y + 2), f"#{k + 1} pos {pos}  cajas {len(f['cajas'])}  pred {n_p}", fill=BLANCO, font=fuente)
        for i in pred_sin:
            recortes.append((k + 1, "P", p[i, :4], p[i, 4], im))
        for j in caja_sin:
            recortes.append((k + 1, "C", f["cajas"][j], None, im))
        if not len(f["cajas"]):
            # continuidad: dónde estaban las cajas del fotograma anotado más cercano (antes y después)
            for ref in vecinos_con_caja(filas, pos, mc["vecino_max"]):
                for c in filas[ref]["cajas"]:
                    recortes.append((k + 1, f"R{ref}", c, None, im))
    recortes = sorted(recortes, key=lambda r: ({"C": 0, "P": 2}.get(r[1], 1), -(r[3] or 0)))[: mc["recortes_max"]]
    por_fila = max(1, ancho // R)
    alto_rec = int(np.ceil(len(recortes) / por_fila)) * (R + 16) if recortes else 0
    lienzo_r = Image.new("RGB", (ancho, alto_rec), (30, 30, 30))
    dr = ImageDraw.Draw(lienzo_r)
    for k, (n, tipo, c, conf, im) in enumerate(recortes):
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        L = max(lado, int(1.6 * max(c[2] - c[0], c[3] - c[1])))
        caja = (int(cx - L / 2), int(cy - L / 2), int(cx - L / 2) + L, int(cy - L / 2) + L)
        rec = im.crop(caja).resize((R, R), Image.NEAREST)
        x, y = (k % por_fila) * R, (k // por_fila) * (R + 16)
        lienzo_r.paste(rec, (x, y + 16))
        s = R / L
        color = VERDE if tipo == "C" else ROJO if tipo == "P" else AMARILLO
        dr.rectangle([x + (c[0] - caja[0]) * s, y + 16 + (c[1] - caja[1]) * s, x + (c[2] - caja[0]) * s,
                      y + 16 + (c[3] - caja[1]) * s], outline=color)
        rot = {"C": f"#{n} caja sin pred", "P": f"#{n} pred {conf or 0:.2f}"}.get(tipo, f"#{n} caja de pos {tipo[1:]}")
        dr.text((x + 2, y + 1), rot, fill=color, font=fuente_c)
    # gráfico por fotograma: cajas (verde, hacia arriba) y predicciones >= conf_alta sin caja (rojo, hacia abajo)
    G = mc["alto_grafico"]
    graf = Image.new("RGB", (ancho, G), (20, 20, 20))
    dg = ImageDraw.Draw(graf)
    n = len(filas)
    mid = G // 2
    tope = max([len(f["cajas"]) for f in filas] + [1])
    for f in filas:
        xg = int(f["posicion"] / max(n - 1, 1) * (ancho - 1))
        if len(f["cajas"]):
            dg.line([xg, mid, xg, mid - int(len(f["cajas"]) / tope * (mid - 14))], fill=VERDE)
        p, _, _ = candidatos(cfg, f, preds)
        if len(p):
            m = iou(p[:, :4], f["cajas"])
            k_alta = int(sum(1 for i in range(len(p)) if p[i, 4] >= det["conf_alta"]
                             and (m.shape[1] == 0 or m[i].max() < det["iou_minimo"])))
            if k_alta:
                dg.line([xg, mid + 1, xg, mid + 1 + int(min(k_alta, tope) / tope * (mid - 14))], fill=ROJO)
    for k, pos in enumerate(muestra):
        xg = int(pos / max(n - 1, 1) * (ancho - 1))
        dg.line([xg, G - 6, xg, G - 1], fill=AMARILLO)
    dg.text((4, 1), f"{nombre}: cajas por fotograma (verde) y predicciones >= {det['conf_alta']} sin caja (rojo); "
                    f"amarillo = muestra; {n} fotogramas", fill=BLANCO, font=fuente_c)
    total = Image.new("RGB", (ancho, lienzo_t.height + alto_rec + G + 8), (0, 0, 0))
    total.paste(lienzo_t, (0, 0))
    total.paste(lienzo_r, (0, lienzo_t.height + 4))
    total.paste(graf, (0, lienzo_t.height + alto_rec + 8))
    total.save(salida)


def auditar(cfg, rutas, out):
    c0 = cfg["c0"]
    comprobar_prohibidas(cfg, c0["carpetas"])
    D = rutas["dataset"]
    tw, th = cfg["tam_termica"]
    det = c0["detector"]
    out = out / "c0" / "auditoria"
    (out / "mosaicos").mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(cfg["fuente"], 13)
    fuente_c = ImageFont.truetype(cfg["fuente"], 11)
    bordes = [0] + cfg["tramos_px"] + [np.inf]
    etiquetas = [f"<{bordes[1]}"] + [f"{a}-{b}" for a, b in zip(bordes[1:-2], bordes[2:-1])] + [f">={bordes[-2]}"]
    resumen, muestras, cajas_todas = [], [], []
    for nombre in c0["carpetas"]:
        filas, raras, repetidas = leer_carpeta(cfg, D, nombre)
        preds = predecir(cfg, rutas, D, nombre, filas, out)
        con = [f["posicion"] for f in filas if len(f["cajas"])]
        sin = [f["posicion"] for f in filas if f["tiene_txt"] and not len(f["cajas"])]
        rng = np.random.default_rng(c0["muestra"]["seed"])
        m_con = sorted(rng.choice(con, min(len(con), c0["muestra"]["con_cajas"]), replace=False).tolist()) if con else []
        m_sin = sorted(rng.choice(sin, min(len(sin), c0["muestra"]["sin_cajas"]), replace=False).tolist()) if sin else []
        muestra = m_con + m_sin
        mosaico(cfg, D, nombre, filas, preds, muestra, out / "mosaicos" / f"{nombre}.png", fuente, fuente_c)
        lados = []
        n_pred_alta_sin, n_caja_sin, fot_sin_con_pred = 0, 0, 0
        for f in filas:
            g = f["cajas"]
            for c in g:
                lado = max(c[2] - c[0], c[3] - c[1])
                lados.append(lado)
                cajas_todas.append({"carpeta": nombre, "posicion": f["posicion"], "ancho": c[2] - c[0],
                                    "alto": c[3] - c[1], "lado_mayor": lado})
            p = preds.get(f["posicion"], np.zeros((0, 5)))
            m = iou(p[:, :4], g)
            alta_sin = sum(1 for i in range(len(p)) if p[i, 4] >= det["conf_alta"] and (m.shape[1] == 0 or m[i].max() < det["iou_minimo"]))
            n_pred_alta_sin += alta_sin
            n_caja_sin += sum(1 for j in range(len(g)) if m.shape[0] == 0 or m[:, j].max() < det["iou_minimo"])
            if not len(g) and f["tiene_txt"] and alta_sin:
                fot_sin_con_pred += 1
        lados = np.array(lados)
        tramos = tramos_seguidos(con)
        fila = {"carpeta": nombre, "logo_flir": tiene_logo(cfg, D, nombre, filas), "fotogramas": len(filas), "con_txt": sum(f["tiene_txt"] for f in filas),
                "con_cajas": len(con), "cajas": int(len(lados)), "repetidas": repetidas, "raras": raras,
                "tramos_con_caja": len(tramos), "primera_con_caja": con[0] if con else None,
                "ultima_con_caja": con[-1] if con else None,
                "lado_p10": float(np.percentile(lados, 10)) if len(lados) else None,
                "lado_p50": float(np.median(lados)) if len(lados) else None,
                "lado_p90": float(np.percentile(lados, 90)) if len(lados) else None}
        cuenta = np.histogram(lados, bins=bordes)[0] if len(lados) else np.zeros(len(etiquetas), int)
        fila |= {f"tramo {e}": int(c) for e, c in zip(etiquetas, cuenta)}
        hc = huecos_cortos(filas, c0["mosaico"]["vecino_max"])
        fila |= {"huecos_cortos": len(hc), "fotogramas_en_huecos_cortos": sum(b - a + 1 for a, b in hc)}
        fila |= {"pred_alta_sin_caja": n_pred_alta_sin, "cajas_sin_pred": n_caja_sin,
                 "fotogramas_sin_caja_con_pred_alta": fot_sin_con_pred}
        resumen.append(fila)
        for k, pos in enumerate(muestra):
            f = filas[pos]
            p, pred_sin, caja_sin = candidatos(cfg, f, preds)
            muestras.append({"carpeta": nombre, "n": k + 1, "grupo": "con cajas" if pos in m_con else "sin cajas",
                             "posicion": pos, "archivo": f["archivo"], "cajas": len(f["cajas"]),
                             "pred_dibujadas": int((p[:, 4] >= det["conf_dibujo"]).sum()) if len(p) else 0,
                             "pred_sin_caja": len(pred_sin), "cajas_sin_pred": len(caja_sin)})
        print(f"{nombre}: {len(filas)} fotogramas, {len(con)} con cajas, {len(lados)} cajas, mediana "
              f"{fila['lado_p50']}, pred alta sin caja {n_pred_alta_sin}, cajas sin pred {n_caja_sin}", flush=True)
    r = pd.DataFrame(resumen)
    r.to_csv(out / "por_carpeta.csv", index=False)
    pd.DataFrame(muestras).to_csv(out / "muestra.csv", index=False)
    pd.DataFrame(cajas_todas).to_csv(out / "cajas.csv", index=False)
    (out / "tablas.md").write_text(md(r, 1) + "\n", encoding="utf-8")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "YOLO26s b1 (detector de apoyo)",
                       f"C0 auditoría: predict con {det['pesos']} (conf >= {det['conf_minima']}, imgsz {det['imgsz']}) "
                       f"en {len(c0['carpetas'])} carpetas IR fuera de los 4 617 pares; muestra {c0['muestra']}; "
                       f"salidas en {rel(out)}",
                       f"{int(r.fotogramas.sum())} fotogramas, {int(r.cajas.sum())} cajas; predicciones >= "
                       f"{det['conf_alta']} sin caja: {int(r.pred_alta_sin_caja.sum())}; cajas sin predicción: "
                       f"{int(r.cajas_sin_pred.sum())}")
    print(md(r, 1))


def alineacion(cfg, rutas, out):
    """Corrimiento del fondo (correlación de fase de los gradientes) entre la RGB llevada con cada semejanza candidata
    y la térmica, en una muestra de pares de cada vuelo; las referencias usan su propia semejanza."""
    import cv2
    import yaml

    from fase2_revision_desfases import desplazamiento_fondo, preparar

    a = cfg["c0"]["alineacion"]
    todos = list(a["vuelos"]) + a["referencias"]
    comprobar_prohibidas(cfg, [f"{v[:-5]}{x}_{v[-4:]}" for v in todos for x in ("IR", "VIS")])
    if any(v.endswith("0405") for v in todos):
        raise SystemExit("FHL 0405 no se mide: sus imágenes no se usan")
    D = rutas["dataset"]
    tw, th = cfg["tam_termica"]
    T = yaml.safe_load(ruta(a["transformaciones"]).read_text(encoding="utf-8"))
    H = {v: np.array(T[v]["H_rgb_a_termica"], dtype=np.float64) for v in set(a["candidatas"]) | set(a["referencias"])}
    pares = pd.read_csv(rutas["data"] / cfg["pares"])
    ventana = cv2.createHanningWindow((tw, th), cv2.CV_64F)
    out = out / "c0" / "alineacion"
    out.mkdir(parents=True, exist_ok=True)
    filas = []

    def medir(vuelo, cand, g):
        for par in g.itertuples():
            al, ter = preparar(par, D, H[cand], (tw, th))
            dx, dy, resp = desplazamiento_fondo(al, ter, a["fondo_sigma"], ventana)
            filas.append({"vuelo": vuelo, "semejanza": cand, "posicion": par.posicion, "dx": dx, "dy": dy,
                          "norma": float(np.hypot(dx, dy)), "respuesta": resp})

    for vuelo in a["referencias"]:
        g = pares[(pares.vuelo == vuelo) & pares.anotado & ~pares.excluido].sort_values("posicion")
        g = g.iloc[np.linspace(0, len(g) - 1, min(a["muestra"], len(g))).astype(int)]
        medir(vuelo, vuelo, g)
    fuente = ImageFont.truetype(cfg["fuente"], 16)
    for vuelo, rango in a["vuelos"].items():
        g = pares[pares.vuelo == vuelo].sort_values("posicion")
        if rango:
            g = g[g.posicion.between(*rango)]
        m = g.iloc[np.linspace(0, len(g) - 1, min(a["muestra"], len(g))).astype(int)]
        for cand in a["candidatas"]:
            medir(vuelo, cand, m)
        # superposiciones: bordes de la RGB llevada (verde) sobre la térmica
        sup = g.iloc[np.linspace(len(g) * 0.25, len(g) * 0.75, a["superposiciones"]).astype(int)]
        lienzo = Image.new("RGB", (len(a["candidatas"]) * tw, len(sup) * (th + 22)), (0, 0, 0))
        d = ImageDraw.Draw(lienzo)
        for i, par in enumerate(sup.itertuples()):
            for j, cand in enumerate(a["candidatas"]):
                al, ter = preparar(par, D, H[cand], (tw, th))
                bordes = cv2.Canny(cv2.cvtColor(al, cv2.COLOR_RGB2GRAY), *a["canny"]) > 0
                im = (ter.astype(np.float64) * 0.8).astype(np.uint8)
                im[bordes] = (0, 255, 0)
                lienzo.paste(Image.fromarray(im), (j * tw, i * (th + 22) + 22))
                d.text((j * tw + 4, i * (th + 22) + 2), f"{vuelo[-4:]} pos {par.posicion}: semejanza de {cand[-4:]}",
                       fill=(255, 255, 255), font=fuente)
        lienzo.save(out / f"superposicion_{vuelo}.png")
    df = pd.DataFrame(filas)
    df.to_csv(out / "fondo.csv", index=False)
    fiable = df[df.respuesta >= a["fondo_respuesta_min"]]
    r = (df.groupby(["vuelo", "semejanza"])
         .agg(pares=("posicion", "size"), respuesta_mediana=("respuesta", "median")).reset_index()
         .merge(fiable.groupby(["vuelo", "semejanza"]).agg(
             fiables=("norma", "size"), dx_mediana=("dx", "median"), dy_mediana=("dy", "median"),
             corrimiento_mediano=("norma", "median"), corrimiento_p90=("norma", lambda x: float(np.percentile(x, 90)))
         ).reset_index(), on=["vuelo", "semejanza"], how="left"))
    ref = r[r.vuelo == r.semejanza].corrimiento_mediano.max()
    limite = a["criterio"]["fondo_factor_referencia"] * ref
    r["pasa_fondo"] = (r.vuelo != r.semejanza) & (r.corrimiento_mediano <= limite)
    r.to_csv(out / "resumen.csv", index=False)
    nota = (f"Límite del fondo: {limite:.2f} px (= {a['criterio']['fondo_factor_referencia']} x {ref:.2f}, "
            "la mayor mediana de las referencias)")
    (out / "tablas.md").write_text(md(r, 2) + "\n\n" + nota + "\n", encoding="utf-8")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "semejanza congelada (fase 2)",
                       f"C0 alineación: corrimiento del fondo (correlación de fase) de FHL 0403/0564/0566 con las "
                       f"semejanzas de {', '.join(c[-4:] for c in a['candidatas'])}; {a['muestra']} pares por vuelo; "
                       f"salidas en {rel(out)}",
                       "; ".join(f"{t.vuelo[-4:]} con {t.semejanza[-4:]}: {t.corrimiento_mediano:.2f} px "
                                 f"({t.fiables}/{t.pares} fiables)" for t in r.itertuples()) + f"; límite {limite:.2f} px")
    print(md(r, 2))
    print(f"límite {limite:.2f} px")


def ampliar(cfg, rutas, out):
    """Fotogramas completos de `c0.ampliaciones`, 2 por fila, con las cajas (verde) y las predicciones del detector de
    la auditoría (rojo, con su confianza; sin las de la marca de agua)."""
    c0 = cfg["c0"]
    comprobar_prohibidas(cfg, c0["ampliaciones"])
    D = rutas["dataset"]
    tw, th = cfg["tam_termica"]
    det = c0["detector"]
    fuente = ImageFont.truetype(cfg["fuente"], 14)
    destino = out / "c0" / "revision"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, posiciones in c0["ampliaciones"].items():
        filas, _, _ = leer_carpeta(cfg, D, nombre)
        preds = predecir(cfg, rutas, D, nombre, filas, out / "c0" / "auditoria")
        lienzo = Image.new("RGB", (2 * tw, int(np.ceil(len(posiciones) / 2)) * (th + 20)), (0, 0, 0))
        d = ImageDraw.Draw(lienzo)
        for k, pos in enumerate(posiciones):
            f = filas[pos]
            x, y = (k % 2) * tw, (k // 2) * (th + 20) + 20
            lienzo.paste(Image.open(D / nombre / f["archivo"]).convert("RGB"), (x, y))
            for c in f["cajas"]:
                d.rectangle([x + c[0] - 2, y + c[1] - 2, x + c[2] + 2, y + c[3] + 2], outline=VERDE, width=2)
            for x0, y0, x1, y1, conf in preds.get(pos, np.zeros((0, 5))):
                if conf >= det["conf_dibujo"]:
                    d.rectangle([x + x0 - 4, y + y0 - 4, x + x1 + 4, y + y1 + 4], outline=ROJO)
                    d.text((x + x1 + 5, y + y0), f"{conf:.2f}", fill=ROJO, font=fuente)
            d.text((x + 4, y - 18), f"{nombre} pos {pos}  cajas {len(f['cajas'])}", fill=BLANCO, font=fuente)
        lienzo.save(destino / f"{nombre}.png")
        print(destino / f"{nombre}.png")


def clasificar(cfg, rutas, out):
    """Aplica `c0.clasificacion` y cuenta lo que queda por carpeta y por sitio: fotogramas, personas y tramos de tamaño.
    Escribe runs/<carpeta>/c0/clasificacion/fotogramas.csv (uno por fotograma, con `usar` y el motivo)."""
    c0 = cfg["c0"]
    cl = c0["clasificacion"]
    clase = {**{n: "usable" for n in cl["usable"]}, **{n: "con tramos" for n in cl["con_tramos"]},
             **{n: "no usable" for n in cl["no_usable"]}}
    faltan = set(c0["carpetas"]) - set(clase)
    if faltan:
        raise SystemExit(f"Carpetas sin clasificar: {sorted(faltan)}")
    comprobar_prohibidas(cfg, c0["carpetas"])
    D = rutas["dataset"]
    bordes = [0] + cfg["tramos_px"] + [np.inf]
    etiquetas = [f"<{bordes[1]}"] + [f"{a}-{b}" for a, b in zip(bordes[1:-2], bordes[2:-1])] + [f">={bordes[-2]}"]
    out = out / "c0" / "clasificacion"
    out.mkdir(parents=True, exist_ok=True)
    fot, resumen = [], []
    for nombre in c0["carpetas"]:
        filas, _, _ = leer_carpeta(cfg, D, nombre)
        motivo = {}
        if cl["huecos_cortos"]:
            for a, b in huecos_cortos(filas, c0["mosaico"]["vecino_max"]):
                motivo |= {q: "hueco corto" for q in range(a, b + 1)}
        for a, b in cl["con_tramos"].get(nombre, []):
            motivo |= {q: "tramo excluido" for q in range(a, b + 1)}
        propias = []
        for f in filas:
            m = ("carpeta no usable" if clase[nombre] == "no usable" else "sin .txt" if not f["tiene_txt"]
                 else motivo.get(f["posicion"], ""))
            lados = [max(c[2] - c[0], c[3] - c[1]) for c in f["cajas"]]
            propias.append({"carpeta": nombre, "posicion": f["posicion"], "archivo": f["archivo"], "usar": m == "",
                            "motivo": m, "cajas": len(f["cajas"]), "lados": ";".join(f"{l:.2f}" for l in lados)})
        fot += propias
        u = [x for x in propias if x["usar"]]
        lados = np.array([float(l) for x in u if x["lados"] for l in x["lados"].split(";")])
        cuenta = np.histogram(lados, bins=bordes)[0] if len(lados) else np.zeros(len(etiquetas), int)
        resumen.append({"carpeta": nombre, "sitio": nombre.split("_")[1], "clase": clase[nombre],
                        "fotogramas": len(filas), "usados": len(u), "usados_con_persona": sum(x["cajas"] > 0 for x in u),
                        "quitados_hueco": sum(x["motivo"] == "hueco corto" for x in propias),
                        "quitados_tramo": sum(x["motivo"] == "tramo excluido" for x in propias),
                        "personas": int(len(lados)), "lado_mediano": float(np.median(lados)) if len(lados) else None,
                        **{f"tramo {e}": int(c) for e, c in zip(etiquetas, cuenta)}})
    pd.DataFrame(fot).to_csv(out / "fotogramas.csv", index=False)
    r = pd.DataFrame(resumen)
    r.to_csv(out / "por_carpeta.csv", index=False)
    cols = ["fotogramas", "usados", "usados_con_persona", "personas"] + [f"tramo {e}" for e in etiquetas]
    s = r.groupby("sitio")[cols].sum().reset_index()
    s = pd.concat([s, pd.DataFrame([{"sitio": "total", **r[cols].sum().to_dict()}])], ignore_index=True)
    s.to_csv(out / "por_sitio.csv", index=False)
    (out / "tablas.md").write_text(md(r, 1) + "\n\n" + md(s, 1) + "\n", encoding="utf-8")
    print(md(r, 1))
    print(md(s, 1))


def puntos(cfg, rutas, out):
    """Error de cada semejanza candidata en los puntos marcados a mano (scripts/fase7_marcar_puntos.py): distancia en
    la térmica entre el punto RGB llevado con la semejanza y el punto térmico marcado. Coherencia de los puntos: se quita
    uno, se ajusta una semejanza con los demás del fotograma y se mide dónde cae el quitado."""
    import cv2
    import yaml

    a = cfg["c0"]["alineacion"]
    mk = cfg["c0"]["marcado"]
    T = yaml.safe_load(ruta(a["transformaciones"]).read_text(encoding="utf-8"))
    out = out / "c0" / "alineacion"
    out.mkdir(parents=True, exist_ok=True)
    filas = []
    for vuelo in a["vuelos"]:
        archivo = ruta(mk["carpeta_puntos"]) / f"{vuelo}.yaml"
        if not archivo.exists():
            print(f"{vuelo}: sin puntos marcados")
            continue
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        for nombre, f in datos["fotogramas"].items():
            P = np.array(f["puntos"], dtype=np.float64).reshape(-1, 4)
            coh = np.full(len(P), np.nan)
            if len(P) >= 3:
                for i in range(len(P)):
                    resto = np.delete(P, i, axis=0)
                    M, _ = cv2.estimateAffinePartial2D(resto[:, :2], resto[:, 2:], method=cv2.LMEDS)
                    if M is not None:
                        coh[i] = np.hypot(*(M @ np.r_[P[i, :2], 1] - P[i, 2:]))
            for cand in a["candidatas"]:
                H = np.array(T[cand]["H_rgb_a_termica"], dtype=np.float64)
                q = (H @ np.c_[P[:, :2], np.ones(len(P))].T).T
                e = np.hypot(*(q[:, :2] / q[:, 2:3] - P[:, 2:]).T)
                filas += [{"vuelo": vuelo, "fotograma": nombre, "posicion": f["posicion"], "punto": i + 1,
                           "semejanza": cand, "error_px": float(e[i]), "coherencia_px": float(coh[i])}
                          for i in range(len(P))]
    if not filas:
        raise SystemExit("No hay puntos marcados todavía")
    df = pd.DataFrame(filas)
    df.to_csv(out / "puntos.csv", index=False)
    r = (df.groupby(["vuelo", "semejanza"])
         .agg(puntos=("error_px", "size"), error_medio=("error_px", "mean"), error_mediano=("error_px", "median"),
              error_max=("error_px", "max"), coherencia_mediana=("coherencia_px", "median")).reset_index())
    r["pasa_puntos"] = r.error_medio <= a["criterio"]["puntos_error_medio_px"]
    r.to_csv(out / "puntos_resumen.csv", index=False)
    (out / "puntos_tablas.md").write_text(md(r, 2) + "\n", encoding="utf-8")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "semejanza congelada (fase 2)",
                       f"C0 alineación con puntos a mano ({mk['carpeta_puntos']}); criterio error medio <= "
                       f"{a['criterio']['puntos_error_medio_px']} px; salidas en {rel(out)}",
                       "; ".join(f"{t.vuelo[-4:]} con {t.semejanza[-4:]}: {t.error_medio:.1f} px ({t.puntos} puntos)"
                                 for t in r.itertuples()))
    print(md(r, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["auditar", "ampliar", "alineacion", "clasificar", "puntos"])
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    out = rutas["runs"] / cfg["carpeta"]
    globals()[args.parte](cfg, rutas, out)


if __name__ == "__main__":
    main()
