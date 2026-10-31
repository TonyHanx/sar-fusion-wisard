"""Fase 2: revisión de los tramos de desfase de la regla relativa y exclusiones que salen de ella.

Paso 1 (sin --aplicar). Lee desfases.csv y personas_desfase.csv de la última corrida de fase2_homografias_cajas.py y
clasifica cada tramo:
- "todas corridas": en todos los pares del tramo cuentan `min_personas_todas_corridas` personas o más, y todas se
  corren más de `umbral_desfase_relativo` alturas. Se excluyen sin revisión.
- "una persona": en todos los pares del tramo cuenta una sola persona.
- "mixto": el resto (unas personas coinciden y otras no, o algunas quedan por debajo del umbral).
Se revisan a ojo todos los que no son "todas corridas" y todos los tramos de `vuelos_revisar_todos`. Para cada uno se
hace una imagen de inspección. Todas las mezclas RGB alineada + térmica usan el mismo recorte, así se ve si el fondo
se corre: el par anterior, los del tramo y el siguiente. Además van la imagen completa del peor par y su RGB alineada
y su térmica por separado. Para cada par se mide también el desplazamiento del fondo entre la RGB alineada y la
térmica (correlación de fase de los gradientes de las dos imágenes; con respuesta menor que `fondo_respuesta_min` no
es fiable). Guarda la lista congelada en tramos.csv, el detalle por persona en personas_tramos.csv (vector de la
persona térmica a la caja RGB más cercana, en px térmicos) y el fondo por par en fondo_tramos.csv.

Paso 2 (--aplicar). Junta los "todas corridas" con las decisiones del archivo `decisiones` (escrito tras revisar),
más sus `tramos_adicionales` (tramos decididos después, p. ej. FHL 0401 371-372). Luego extiende cada tramo de desfase
excluido (y los de `semillas_manuales`) a los pares vecinos seguidos mientras el fondo esté corrido más de
`extension_fondo_min_px`, con medida fiable, usando la transformación congelada. La extensión se corta en un par sin
anotar, en una exclusión puesta a mano en configs/fase1.yaml o en otro tramo excluido. Las extensiones que caen en
`vuelos_revisar_todos` necesitan una decisión en `extensiones` del archivo `decisiones`: si falta, hace su imagen
(ext_*.jpg) y se detiene. Escribe `salida_exclusiones` con el formato de las exclusiones de configs/fase1.yaml,
incluidos los pares "solo térmica" vecinos de cada tramo excluido y de cada extensión. configs/fase1.yaml lo lee en
`exclusiones_adicionales`. Escribe revision.csv, extensiones.csv y fondo_extensiones.csv, y agrega una fila a la
bitácora.

Uso: python scripts/fase2_revision_desfases.py --config configs/fase2.yaml --rutas configs/rutas.yaml [--aplicar]
"""
import argparse
from datetime import datetime
from types import SimpleNamespace

import cv2
import numpy as np
import pandas as pd
import yaml
from PIL import Image, ImageDraw, ImageFont

from comun import AMARILLO, RAIZ, ROJO, agregar_a_bitacora, leer_rutas, leer_yaml, pares_anotados
from fase2_homografias_cajas import apilar, cajas_llevadas, cajas_px, centros, dentro, llevar

VERDE = (0, 230, 0)


def desplazamiento_fondo(al, ter, sigma, ventana):
    """Desplazamiento (dx, dy) de la RGB alineada respecto de la térmica y respuesta de la correlación de fase."""
    def gradiente(img):
        img = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float64), (0, 0), sigma)
        g = np.hypot(cv2.Sobel(img, cv2.CV_64F, 1, 0), cv2.Sobel(img, cv2.CV_64F, 0, 1))
        return (g - g.mean()) / (g.std() + 1e-9)
    (dx, dy), resp = cv2.phaseCorrelate(gradiente(ter), gradiente(al), ventana)
    return dx, dy, resp


def preparar(par, D, H, tam_ter):
    """RGB alineada y térmica del par, en RGB y al tamaño de la térmica."""
    al = cv2.cvtColor(cv2.warpPerspective(cv2.imread(str(D / par.ruta_rgb)), H, tuple(tam_ter)), cv2.COLOR_BGR2RGB)
    ter = np.array(Image.open(D / par.ruta_termica).convert("RGB"))
    return al, ter


def clasificar(des, personas, c, cr):
    filas = []
    for t in des.itertuples():
        x = personas[(personas.vuelo == t.vuelo) & personas.posicion.between(t.desde, t.hasta) & personas.cuenta]
        g = x.groupby("posicion").distancia_relativa.agg(["size", "min"])
        if (g["size"] >= cr["min_personas_todas_corridas"]).all() and (g["min"] > c["umbral_desfase_relativo"]).all():
            tipo = "todas corridas"
        elif (g["size"] == 1).all():
            tipo = "una persona"
        else:
            tipo = "mixto"
        filas.append({"vuelo": t.vuelo, "desde": t.desde, "hasta": t.hasta, "pares": t.pares, "tipo": tipo,
                      "personas_por_par": "/".join(map(str, g["size"])),
                      "relativa_min": round(float(g["min"].min()), 2), "mediana_relativa_max": t.mediana_relativa_max,
                      "peor": t.peor, "posiciones_solo_termica": t.posiciones_solo_termica})
    tr = pd.DataFrame(filas).sort_values(["vuelo", "desde"]).reset_index(drop=True)
    tr.insert(0, "tramo", np.arange(1, len(tr) + 1))
    tr["revisar"] = (tr.tipo != "todas corridas") | tr.vuelo.isin(cr["vuelos_revisar_todos"])
    return tr


def personas_de(par, D, H, tam_rgb, tam_ter, c):
    """Cajas del par y, por persona térmica que no toca el borde, la caja RGB más cercana."""
    cr = cajas_px((D / par.ruta_rgb).with_suffix(".txt"), tam_rgb)
    ct = cajas_px((D / par.ruta_termica).with_suffix(".txt"), tam_ter)
    ctv = ct[dentro(ct, tam_ter, c["margen_borde_px"])] if len(ct) else ct
    filas = []
    if len(ctv) and len(cr):
        cc, rc = centros(ctv), llevar(H, centros(cr))
        d = np.linalg.norm(cc[:, None] - rc[None], axis=2)
        k = d.argmin(1)
        for i in range(len(ctv)):
            alto = ctv[i, 3] - ctv[i, 1]
            rel = d[i, k[i]] / alto
            filas.append({"x_termica": cc[i, 0], "y_termica": cc[i, 1], "alto_px": alto, "relativa": rel,
                          "dx_px": rc[k[i], 0] - cc[i, 0], "dy_px": rc[k[i], 1] - cc[i, 1],
                          "cuenta": rel <= c["radio_cerca_alturas"]})
    return cr, ct, filas


def imagen_tramo(t, g, D, H, tam_rgb, tam_ter, c, cr, fuente, fuente_t):
    fuera = [p for p in range(t.desde, t.hasta + 1)]
    if len(fuera) > cr["max_posiciones_por_tramo"]:  # el principio, el final, el peor y repartidas
        idx = np.linspace(0, len(fuera) - 1, cr["max_posiciones_por_tramo"] - 1).round().astype(int)
        fuera = sorted(set([fuera[i] for i in idx] + [t.peor]))
    posiciones = [p for p in [t.desde - 1, *fuera, t.hasta + 1] if p in g.index]
    datos = {p: personas_de(g.loc[p], D, H, tam_rgb, tam_ter, c) for p in posiciones}
    # recorte común: cajas térmicas de todas las posiciones más un margen proporcional a la altura de las personas
    ct_todas = np.vstack([d[1] for d in datos.values() if len(d[1])] or [np.zeros((0, 4))])
    if len(ct_todas):
        alto_med = np.median(ct_todas[:, 3] - ct_todas[:, 1])
        m = max(cr["margen_recorte_px"], c["radio_cerca_alturas"] * alto_med)
        x0, y0 = np.maximum(ct_todas[:, :2].min(0) - m, 0)
        x1, y1 = np.minimum(ct_todas[:, 2:].max(0) + m, tam_ter)
    else:
        x0, y0, (x1, y1) = 0, 0, tam_ter
    rec = tuple(int(round(v)) for v in (x0, y0, x1, y1))
    w, h = rec[2] - rec[0], rec[3] - rec[1]
    s = min(cr["panel_ancho_max"] / w, cr["panel_alto_max"] / h, cr["zoom_max"])

    def dibujar(img, p, escala, desplaz, cajas=True):
        if not cajas:
            return img
        d = ImageDraw.Draw(img)
        cr_, ct_, _ = datos[p]
        for b in ct_:
            d.rectangle([(b[0] - desplaz[0]) * escala, (b[1] - desplaz[1]) * escala,
                         (b[2] - desplaz[0]) * escala, (b[3] - desplaz[1]) * escala], outline=ROJO, width=2)
        if len(cr_):
            for b in cajas_llevadas(H, cr_):
                d.rectangle([(b[0] - desplaz[0]) * escala, (b[1] - desplaz[1]) * escala,
                             (b[2] - desplaz[0]) * escala, (b[3] - desplaz[1]) * escala], outline=VERDE, width=2)
        return img

    def recortar(arr):
        return Image.fromarray(arr).crop(rec).resize((round(w * s), round(h * s)), Image.LANCZOS)

    ventana = cv2.createHanningWindow(tuple(tam_ter), cv2.CV_64F)
    paneles, fondo = [], []
    for p in posiciones:
        al, ter = preparar(g.loc[p], D, H, tam_ter)
        dx, dy, resp = desplazamiento_fondo(al, ter, cr["fondo_sigma"], ventana)
        fiable = resp >= cr["fondo_respuesta_min"]
        fondo.append({"tramo": t.tramo, "vuelo": t.vuelo, "posicion": p, "fondo_dx_px": dx, "fondo_dy_px": dy,
                      "respuesta": resp, "fiable": fiable})
        img = dibujar(recortar(((al.astype(float) + ter) / 2).astype(np.uint8)), p, s, rec[:2])
        _, _, fil = datos[p]
        cuentan = [f for f in fil if f["cuenta"]]
        donde = "en el tramo" if t.desde <= p <= t.hasta else ("antes" if p < t.desde else "después")
        med = f"mediana {np.median([f['relativa'] for f in cuentan]):.2f}" if cuentan else "nadie cuenta"
        orden = sorted(fil, key=lambda f: f["x_termica"])
        texto = (f"pos {p} ({donde}) · {med} · fondo ({dx:+.0f},{dy:+.0f})" + ("" if fiable else " no fiable") + "\n"
                 + "rel: " + " ".join(f"{f['relativa']:.2f}" + ("" if f["cuenta"] else "*") for f in orden) + "\n"
                 + "dxy: " + " ".join(f"({f['dx_px']:+.0f},{f['dy_px']:+.0f})" for f in orden))
        paneles.append((img, texto))
    # peor par: completa (con el recorte en amarillo), RGB alineada y térmica del recorte
    al, ter = preparar(g.loc[t.peor], D, H, tam_ter)
    ancho_c = cr["panel_ancho_max"]
    sc = ancho_c / tam_ter[0]
    completa = Image.fromarray(((al.astype(float) + ter) / 2).astype(np.uint8)).resize(
        (ancho_c, round(tam_ter[1] * sc)), Image.LANCZOS)
    completa = dibujar(completa, t.peor, sc, (0, 0))
    ImageDraw.Draw(completa).rectangle([v * sc for v in rec], outline=AMARILLO, width=2)
    paneles.append((completa, f"pos {t.peor} (peor), imagen completa\namarillo: recorte"))
    paneles.append((dibujar(recortar(al), t.peor, s, rec[:2]), f"pos {t.peor} (peor): RGB alineada"))
    paneles.append((dibujar(recortar(ter), t.peor, s, rec[:2]), f"pos {t.peor} (peor): térmica"))

    banda, sep, n = 62, 10, cr["paneles_por_fila"]
    celda_w = max(im.width for im, _ in paneles)
    celda_h = max(im.height for im, _ in paneles) + banda
    filas = []
    for i in range(0, len(paneles), n):
        fila = Image.new("RGB", (n * celda_w + (n - 1) * sep, celda_h), (255, 255, 255))
        d = ImageDraw.Draw(fila)
        for j, (im, texto) in enumerate(paneles[i:i + n]):
            x = j * (celda_w + sep)
            fila.paste(im, (x, 0))
            d.multiline_text((x + 4, im.height + 3), texto, fill=(0, 0, 0), font=fuente_t, spacing=2)
        filas.append(fila)
    cab = Image.new("RGB", (filas[0].width, 30), (255, 255, 255))
    cabecera = getattr(t, "cabecera", None) or (
        f"Tramo {t.tramo}: {t.vuelo} {t.desde}-{t.hasta} | {t.tipo} | personas por par {t.personas_por_par} | "
        f"mediana máx. {t.mediana_relativa_max:.2f}")
    ImageDraw.Draw(cab).text((6, 5), cabecera + " | rojo: térmica, verde: RGB alineada, *: no cuenta", fill=(0, 0, 0),
                             font=fuente)
    filas_personas = [{"tramo": t.tramo, "vuelo": t.vuelo, "posicion": p, **f}
                      for p in posiciones for f in datos[p][2]]
    return apilar([cab, *filas], sep=6), filas_personas, fondo


def revisar(cfg, c, cr, rutas, carpeta):
    rep_al = rutas["reports"] / c["carpeta_reporte"]
    des = pd.read_csv(rep_al / "desfases.csv", keep_default_na=False)
    personas = pd.read_csv(rep_al / "personas_desfase.csv")
    tr = clasificar(des, personas, c, cr)
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("*.jpg"):
        viejo.unlink()
    tr.to_csv(carpeta / "tramos.csv", index=False, encoding="utf-8")
    Hs = yaml.safe_load((RAIZ / c["salida"]).read_text(encoding="utf-8"))
    pares = pares_anotados(rutas["data"] / cfg["pares"])
    D, tam_ter = rutas["dataset"], tuple(cfg["tam_termica"])
    fuente = ImageFont.truetype(cfg["fuente"], 16)
    fuente_t = ImageFont.truetype(cfg["fuente"], 13)
    detalle, fondo = [], []
    for t in tr[tr.revisar].itertuples():
        g = pares[(pares.vuelo == t.vuelo) & ~pares.excluido].set_index("posicion")
        H = np.array(Hs[t.vuelo]["H_rgb_a_termica"], float)
        img, fil, fon = imagen_tramo(t, g, D, H, tuple(Hs[t.vuelo]["tam_rgb"]), tam_ter, c, cr, fuente, fuente_t)
        fondo += fon
        img.save(carpeta / f"{t.tramo:02d}_{t.vuelo}_{t.desde:04d}-{t.hasta:04d}.jpg", quality=cr["calidad_jpg"])
        detalle += fil
    pd.DataFrame(detalle).round(2).to_csv(carpeta / "personas_tramos.csv", index=False, encoding="utf-8")
    pd.DataFrame(fondo).round(2).to_csv(carpeta / "fondo_tramos.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 220)
    print(tr.drop(columns="posiciones_solo_termica").to_string(index=False))
    print(tr.groupby("tipo").agg(tramos=("pares", "size"), pares=("pares", "sum")).to_string())
    print(f"a revisar: {tr.revisar.sum()} tramos ({tr[tr.revisar].pares.sum()} pares); imágenes en {carpeta}")


def solo_termica(g):
    """Posiciones con persona en la térmica y ninguna en la RGB (g indexado por posición)."""
    return set(g.index[(g.cajas_termica > 0) & (g.cajas_rgb == 0)].astype(int))


def bloques(posiciones):
    """Tramos de posiciones seguidas: [(desde, hasta), ...]."""
    out = []
    for p in sorted(posiciones):
        if out and p == out[-1][1] + 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return [tuple(b) for b in out]


def extender(vuelo, ocupadas, g, bloqueadas, H, D, tam_ter, cr, ventana):
    """Extiende cada bloque de posiciones excluidas por desfase a los vecinos seguidos con el fondo corrido más de
    `extension_fondo_min_px` (medida fiable). Se corta en un par sin anotar, en una exclusión puesta a mano o en otro
    bloque. Devuelve las medidas (incluido el par donde se corta) y las extensiones."""
    medidas, extensiones = [], []
    for a, b in bloques(ocupadas):
        for lado, paso, p in (("antes", -1, a - 1), ("después", 1, b + 1)):
            nuevos = []
            while p in g.index and p not in bloqueadas and p not in ocupadas:
                dx, dy, resp = desplazamiento_fondo(*preparar(g.loc[p], D, H, tam_ter), cr["fondo_sigma"], ventana)
                fiable = resp >= cr["fondo_respuesta_min"]
                extiende = bool(fiable and np.hypot(dx, dy) > cr["extension_fondo_min_px"])
                medidas.append({"vuelo": vuelo, "bloque": f"{a}-{b}", "lado": lado, "posicion": p, "fondo_dx_px": dx,
                                "fondo_dy_px": dy, "fondo_px": float(np.hypot(dx, dy)), "respuesta": resp,
                                "fiable": fiable, "extiende": extiende})
                if not extiende:
                    break
                nuevos.append(p)
                p += paso
            if nuevos:
                extensiones.append({"vuelo": vuelo, "bloque": f"{a}-{b}", "lado": lado, "desde": min(nuevos),
                                    "hasta": max(nuevos), "pares": len(nuevos)})
    return medidas, extensiones


def aplicar(cfg, c, cr, rutas, carpeta):
    decisiones = leer_yaml(RAIZ / cr["decisiones"])
    tr = pd.read_csv(carpeta / "tramos.csv", keep_default_na=False)
    dec = pd.DataFrame(decisiones["tramos"])
    tr = tr.merge(dec[["vuelo", "desde", "hasta", "decision", "motivo"]], on=["vuelo", "desde", "hasta"], how="left")
    sin = tr[tr.revisar & tr.decision.isna()]
    if len(sin):
        raise SystemExit(f"Tramos a revisar sin decisión:\n{sin[['tramo', 'vuelo', 'desde', 'hasta']].to_string()}")
    auto = ~tr.revisar
    tr.loc[auto, "decision"] = "excluir"
    tr.loc[auto, "motivo"] = "todas las personas (2 o más) se corren más de 1 altura: sin revisión"

    pares = pares_anotados(rutas["data"] / cfg["pares"])
    carpetas = pares.groupby("vuelo")[["carpeta_rgb", "carpeta_termica"]].first()
    grupos = {v: g.set_index("posicion") for v, g in pares.groupby("vuelo")}
    vuelo_de = pares.groupby("carpeta_rgb").vuelo.first()
    bloq = {}  # exclusiones puestas a mano en configs/fase1.yaml (no las generadas)
    for e in leer_yaml(RAIZ / cr["config_fase1"])["exclusiones"]:
        if e["carpeta_rgb"] in vuelo_de.index:
            bloq.setdefault(vuelo_de[e["carpeta_rgb"]], set()).update(range(e["desde"], e["hasta"] + 1))
    vec = c["vecindad_solo_termica"]

    def vecinos_solo_termica(vuelo, desde, hasta, ya):
        return [p for p in sorted(solo_termica(grupos[vuelo])) if desde - vec <= p <= hasta + vec
                and not desde <= p <= hasta and p not in bloq.get(vuelo, set()) and p not in ya]

    # tramos decididos después de la revisión (p. ej. tras volver a estimar la semejanza)
    adic = []
    for i, a in enumerate(decisiones.get("tramos_adicionales") or []):
        adic.append({"tramo": int(tr.tramo.max()) + i + 1, "vuelo": a["vuelo"], "desde": a["desde"],
                     "hasta": a["hasta"], "pares": a["hasta"] - a["desde"] + 1, "tipo": "adicional", "revisar": True,
                     "decision": a["decision"], "motivo": a["motivo"],
                     "posiciones_solo_termica": " ".join(map(str, vecinos_solo_termica(a["vuelo"], a["desde"],
                                                                                         a["hasta"], set())))})
    tr = pd.concat([tr, pd.DataFrame(adic)], ignore_index=True) if adic else tr

    exclusiones, filas, ocupadas = [], [], {}
    for t in tr.itertuples():
        vecinos = [int(p) for p in str(t.posiciones_solo_termica).split()] if t.decision == "excluir" else []
        vecinos = [p for p in vecinos if not t.desde <= p <= t.hasta]
        filas.append({"tramo": t.tramo, "vuelo": t.vuelo, "desde": t.desde, "hasta": t.hasta, "pares": t.pares,
                      "tipo": t.tipo, "revisado": t.revisar, "decision": t.decision, "motivo": t.motivo,
                      "solo_termica_excluidos": " ".join(map(str, vecinos))})
        if t.decision != "excluir":
            continue
        base = {"carpeta_rgb": carpetas.loc[t.vuelo, "carpeta_rgb"],
                "carpeta_termica": carpetas.loc[t.vuelo, "carpeta_termica"]}
        origen = "regla relativa" if t.tipo != "adicional" else "regla relativa, tras volver a estimar la semejanza"
        exclusiones.append({**base, "desde": int(t.desde), "hasta": int(t.hasta),
                            "motivo": f"desfase entre cámaras ({origen}, {t.tipo}): {t.motivo}"})
        exclusiones += [{**base, "desde": p, "hasta": p,
                         "motivo": f"solo térmica a {vec} posiciones o menos del desfase {t.desde}-{t.hasta}"}
                        for p in vecinos]
        ocupadas.setdefault(t.vuelo, set()).update(range(int(t.desde), int(t.hasta) + 1), vecinos)
    rev = pd.DataFrame(filas)
    rev.to_csv(carpeta / "revision.csv", index=False, encoding="utf-8")

    # extensión por el fondo, con la transformación congelada
    for s in cr["semillas_manuales"]:
        ocupadas.setdefault(s["vuelo"], set()).update(range(s["desde"], s["hasta"] + 1))
    Hs = yaml.safe_load((RAIZ / c["salida"]).read_text(encoding="utf-8"))
    D, tam_ter = rutas["dataset"], tuple(cfg["tam_termica"])
    ventana = cv2.createHanningWindow(tam_ter, cv2.CV_64F)
    medidas, ext = [], []
    for vuelo in sorted(ocupadas):
        H = np.array(Hs[vuelo]["H_rgb_a_termica"], np.float64)
        m, e = extender(vuelo, ocupadas[vuelo], grupos[vuelo], bloq.get(vuelo, set()), H, D, tam_ter, cr, ventana)
        medidas += m
        ext += e
    med = pd.DataFrame(medidas)
    med.round(2).to_csv(carpeta / "fondo_extensiones.csv", index=False, encoding="utf-8")
    ext = pd.DataFrame(ext, columns=["vuelo", "bloque", "lado", "desde", "hasta", "pares"])
    ext["revisar"] = ext.vuelo.isin(cr["vuelos_revisar_todos"])
    dext = pd.DataFrame(decisiones.get("extensiones") or [], columns=["vuelo", "desde", "hasta", "decision", "motivo"])
    ext = ext.merge(dext, on=["vuelo", "desde", "hasta"], how="left")
    umbral = cr["extension_fondo_min_px"]

    def fondo_de(e):
        x = med[(med.vuelo == e.vuelo) & med.posicion.between(e.desde, e.hasta)].sort_values("posicion")
        return x, ", ".join(f"{int(r.posicion)}: ({r.fondo_dx_px:+.0f}, {r.fondo_dy_px:+.0f})" for r in x.itertuples())

    # imágenes de las extensiones que se revisan a ojo
    fuente = ImageFont.truetype(cfg["fuente"], 16)
    fuente_t = ImageFont.truetype(cfg["fuente"], 13)
    for i, e in enumerate(ext[ext.revisar].itertuples()):
        x, texto = fondo_de(e)
        t = SimpleNamespace(tramo=f"E{i + 1}", vuelo=e.vuelo, desde=e.desde, hasta=e.hasta, tipo="extensión",
                            peor=int(x.loc[x.fondo_px.idxmax(), "posicion"]),
                            cabecera=f"Extensión {e.lado} del desfase {e.bloque}: {e.vuelo} {e.desde}-{e.hasta} "
                                     f"({e.pares} pares, fondo > {umbral} px)")
        H = np.array(Hs[e.vuelo]["H_rgb_a_termica"], np.float64)
        img, _, _ = imagen_tramo(t, grupos[e.vuelo], D, H, tuple(Hs[e.vuelo]["tam_rgb"]), tam_ter, c, cr, fuente,
                                 fuente_t)
        img.save(carpeta / f"ext_{e.vuelo}_{e.desde:04d}-{e.hasta:04d}.jpg", quality=cr["calidad_jpg"])
    sin = ext[ext.revisar & ext.decision.isna()]
    if len(sin):
        ext.to_csv(carpeta / "extensiones.csv", index=False, encoding="utf-8")
        raise SystemExit(f"Extensiones a revisar sin decisión (imágenes ext_*.jpg en {carpeta}):\n"
                         f"{sin[['vuelo', 'bloque', 'lado', 'desde', 'hasta', 'pares']].to_string()}")
    for k, e in zip(ext.index, ext.itertuples()):
        if not e.revisar:
            ext.loc[k, ["decision", "motivo"]] = ["excluir", f"fondo corrido más de {umbral} px (sin revisión): "
                                                             + fondo_de(e)[1]]

    excluidas = {v: set(p) for v, p in ocupadas.items()}
    ext["solo_termica_excluidos"] = ""
    for k, e in zip(ext.index, ext.itertuples()):
        if e.decision != "excluir":
            continue
        base = {"carpeta_rgb": carpetas.loc[e.vuelo, "carpeta_rgb"],
                "carpeta_termica": carpetas.loc[e.vuelo, "carpeta_termica"]}
        nuevos = [p for p in range(e.desde, e.hasta + 1) if p not in excluidas[e.vuelo]]
        if nuevos:
            exclusiones.append({**base, "desde": int(min(nuevos)), "hasta": int(max(nuevos)),
                                "motivo": f"desfase entre cámaras (extensión {e.lado} del tramo {e.bloque} por el "
                                          f"fondo): {e.motivo}"})
        excluidas[e.vuelo].update(range(e.desde, e.hasta + 1))
        vecinos = vecinos_solo_termica(e.vuelo, e.desde, e.hasta, excluidas[e.vuelo])
        exclusiones += [{**base, "desde": p, "hasta": p,
                         "motivo": f"solo térmica a {vec} posiciones o menos de la extensión {e.desde}-{e.hasta}"}
                        for p in vecinos]
        excluidas[e.vuelo].update(vecinos)
        ext.loc[k, "solo_termica_excluidos"] = " ".join(map(str, vecinos))
    ext.to_csv(carpeta / "extensiones.csv", index=False, encoding="utf-8")

    cabecera = (f"# Generado por scripts/fase2_revision_desfases.py --aplicar el "
                f"{datetime.now().isoformat(timespec='seconds')} (no editar a mano).\n"
                f"# Desfases de la regla relativa: los tramos 'todas corridas' sin revisión, los revisados a ojo con "
                f"decisión 'excluir' y los tramos adicionales ({cr['decisiones']}), más su extensión por el fondo.\n")
    (RAIZ / cr["salida_exclusiones"]).write_text(
        cabecera + yaml.safe_dump({"exclusiones": exclusiones}, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8")

    ex = rev[rev.decision == "excluir"]
    n_vec = sum(len(s.split()) for s in ex.solo_termica_excluidos)
    ee = ext[ext.decision == "excluir"]
    n_ext = len(set((e.vuelo, p) for e in ee.itertuples() for p in range(e.desde, e.hasta + 1))
                - {(v, p) for v, s in ocupadas.items() for p in s})
    n_vec_ext = sum(len(s.split()) for s in ee.solo_termica_excluidos)
    resumen = (f"{len(ex)} de {len(rev)} tramos excluidos ({(~rev.revisado).sum()} sin revisión, "
               f"{(ex.tipo == 'adicional').sum()} adicionales): {ex.pares.sum()} pares de desfase + {n_vec} solo "
               f"térmica; extensión por el fondo (> {umbral} px): {len(ee)} de {len(ext)} extensiones, {n_ext} pares "
               f"+ {n_vec_ext} solo térmica")
    pd.set_option("display.width", 250)
    print(rev.to_string(index=False))
    print(ext.to_string(index=False))
    print(resumen)
    agregar_a_bitacora(rutas["bitacora"], 2, "revisión de desfases (regla relativa) y extensión por el fondo",
                       f"mediana relativa > {c['umbral_desfase_relativo']}, radio {c['radio_cerca_alturas']} alturas, "
                       f"fondo > {umbral} px, transformación congelada, {cr['decisiones']}", resumen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    c, cr = cfg["homografias_cajas"], cfg["revision_desfases"]
    rutas = leer_rutas(args.rutas)
    carpeta = rutas["reports"] / cr["carpeta"]
    (aplicar if args.aplicar else revisar)(cfg, c, cr, rutas, carpeta)


if __name__ == "__main__":
    main()
