"""Fase 2: transformación RGB -> térmica de cada vuelo a partir de los centros de las cajas de personas.

Para cada vuelo se toman los pares utilizables con persona en la RGB y en la térmica y se reparten al azar (seed) en
dos mitades:
- calibración: se emparejan las personas de la RGB con las de la térmica (algoritmo húngaro sobre la distancia entre
  centros, empezando con la franja nominal de CLAUDE.md) y se estima la transformación con RANSAC. Se repite
  `iteraciones` veces, emparejando cada vez con la estimación anterior y una compuerta de distancia.
- evaluación: se emparejan las personas con la transformación final, sin compuerta, y se mide la distancia entre el
  centro de la caja térmica y el centro de la caja RGB llevado a la térmica (px térmicos).

El modelo que se guarda es `modelo` (homografia, afin o semejanza). Además se comparan los `modelos_comparados` con
la misma partición, incluida la franja nominal sin estimar nada. "Campo de visión" es la zona de la RGB que ve la
térmica según cada modelo (esquinas de la térmica llevadas a la RGB, normalizadas).

Se ignoran las cajas térmicas que tocan el borde de la imagen y las cajas RGB que, llevadas a la térmica, se salen de
ella (personas cortadas o fuera de la vista de la térmica). Las cajas repetidas dentro de un mismo .txt cuentan una
vez (no se modifica ningún archivo).

Regla de desfase (con el modelo guardado, en todos los pares con persona en las dos imágenes, de las dos mitades): para
cada persona térmica que no toca el borde se toma la caja RGB alineada más cercana (no el emparejamiento húngaro) y la
distancia entre centros se divide por la altura de la caja térmica. Las personas sin ninguna caja RGB a
`radio_cerca_alturas` alturas o menos no cuentan (pueden estar tapadas). Un par está desfasado si la mediana de sus
personas que cuentan pasa de `umbral_desfase_relativo`. Un tramo de desfase son `desfase_min_pares` o más pares
desfasados seguidos (un par sin personas que cuenten corta el tramo). Se proponen para excluir los pares de esos tramos
y los pares "solo térmica" dentro de ellos o a `vecindad_solo_termica` posiciones o menos. Para comparar se calcula
también la regla anterior (alguna persona a más de `umbral_desfase_px` con el emparejamiento húngaro) y la regla nueva
con otros radios. El script solo propone (exclusion_desfase_propuesta.csv) y hace una hoja de ejemplos. Los tramos se
revisan y se excluyen con scripts/fase2_revision_desfases.py, que escribe configs/exclusiones_desfase.yaml (lo lee
configs/fase1.yaml).

Salidas: configs/homografias_cajas.yaml y, en reports/alineacion/homografias_cajas/: resumen.csv,
comparacion_modelos.csv, distancias.csv, distancia_por_par.csv, personas_desfase.csv, desfases.csv,
exclusion_desfase_propuesta.csv, sensibilidad_radio.csv, validacion_manual.csv y las imágenes (superposiciones, peores
pares, ejemplos de desfase y puntos manuales). Agrega una fila a la bitácora.

Uso: python scripts/fase2_homografias_cajas.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import yaml
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment

from comun import (AMARILLO, RAIZ, ROJO, agregar_a_bitacora, homografia_franja, lado_a_lado, leer_cajas_yolo,
                   leer_rutas, leer_yaml, pares_utilizables)

VERDE = (0, 230, 0)


# ---------------------------------------------------------------------------------------------------- geometría
def llevar(H, puntos):
    return cv2.perspectiveTransform(np.asarray(puntos, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


def cajas_px(ruta_txt, tam):
    """Cajas (x0, y0, x1, y1) en píxeles, sin repetidas."""
    w, h = tam
    unicas = sorted(set(leer_cajas_yolo(ruta_txt)))
    return np.array([[(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]
                     for _, cx, cy, bw, bh in unicas], dtype=np.float64).reshape(-1, 4)


def centros(cajas):
    return np.column_stack([(cajas[:, 0] + cajas[:, 2]) / 2, (cajas[:, 1] + cajas[:, 3]) / 2])


def cajas_llevadas(H, cajas):
    """Rectángulo que encierra cada caja RGB llevada a la térmica."""
    esquinas = llevar(H, cajas[:, [0, 1, 2, 1, 2, 3, 0, 3]].reshape(-1, 2)).reshape(-1, 4, 2)
    return np.column_stack([esquinas[..., 0].min(1), esquinas[..., 1].min(1),
                            esquinas[..., 0].max(1), esquinas[..., 1].max(1)])


def dentro(cajas, tam_ter, margen):
    """Cajas (en px térmicos) que no tocan el borde de la térmica."""
    tw, th = tam_ter
    return (cajas[:, 0] >= margen) & (cajas[:, 1] >= margen) & (cajas[:, 2] <= tw - margen) & (cajas[:, 3] <= th - margen)


def validas(cr, ct, H, tam_ter, margen):
    """Cajas RGB que caen enteras dentro de la térmica y cajas térmicas que no tocan el borde."""
    return cr[dentro(cajas_llevadas(H, cr), tam_ter, margen)], ct[dentro(ct, tam_ter, margen)]


def emparejar(cr, ct, H, compuerta=None):
    """Empareja personas RGB y térmicas (húngaro). Devuelve índices y distancias en px térmicos."""
    if not len(cr) or not len(ct):
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    d = np.linalg.norm(llevar(H, centros(cr))[:, None, :] - centros(ct)[None, :, :], axis=2)
    i, j = linear_sum_assignment(d)
    dist = d[i, j]
    if compuerta is not None:
        m = dist <= compuerta
        i, j, dist = i[m], j[m], dist[m]
    return i, j, dist


def campo_de_vision(H, tam_rgb, tam_ter):
    """Esquinas de la térmica llevadas a la RGB, normalizadas (sup. izq., sup. der., inf. der., inf. izq.)."""
    tw, th = tam_ter
    return llevar(np.linalg.inv(H), [[0, 0], [tw, 0], [tw, th], [0, th]]) / np.asarray(tam_rgb, np.float64)


def ajustar(src, dst, modelo, c, seed):
    """Transformación 3x3 con RANSAC. homografia: 8 grados de libertad; afin: 6; semejanza: 4 (escala, giro, traslación)."""
    cv2.setRNGSeed(seed)
    if modelo == "homografia":
        H, inl = cv2.findHomography(src, dst, cv2.RANSAC, c["umbral_ransac_px"], maxIters=c["max_iter_ransac"],
                                    confidence=c["confianza_ransac"])
        return (None, None) if H is None else (H / H[2, 2], inl)
    funcion = {"afin": cv2.estimateAffine2D, "semejanza": cv2.estimateAffinePartial2D}[modelo]
    A, inl = funcion(src.astype(np.float32), dst.astype(np.float32), method=cv2.RANSAC,
                     ransacReprojThreshold=c["umbral_ransac_px"], maxIters=c["max_iter_ransac"],
                     confidence=c["confianza_ransac"])
    return (None, None) if A is None else (np.vstack([A, [0, 0, 1]]).astype(np.float64), inl)


def estimar(cal, H0, c, tam_ter, modelo, seed):
    """Transformación con RANSAC sobre los centros emparejados de los pares de calibración."""
    H = H0
    for it in range(c["iteraciones"]):
        compuerta = c["compuerta_inicial_px"] if it == 0 else c["compuerta_px"]
        src, dst, usados = [], [], 0
        for _, cr, ct in cal:
            cr, ct = validas(cr, ct, H, tam_ter, c["margen_borde_px"])
            i, j, _ = emparejar(cr, ct, H, compuerta)
            if len(i):
                usados += 1
                src.append(centros(cr)[i])
                dst.append(centros(ct)[j])
        if sum(len(s) for s in src) < 4:
            return None, {"pares_calibracion_usados": usados}
        src, dst = np.vstack(src), np.vstack(dst)
        H, inl = ajustar(src, dst, modelo, c, seed)
        if H is None:
            return None, {"pares_calibracion_usados": usados}
    inl = inl.ravel().astype(bool)
    err = np.linalg.norm(llevar(H, src[inl]) - dst[inl], axis=1)
    cobertura = cv2.contourArea(cv2.convexHull(dst[inl].astype(np.float32))) / (tam_ter[0] * tam_ter[1])
    return H, {"pares_calibracion_usados": usados, "correspondencias": len(src), "inliers": int(inl.sum()),
               "error_inliers_medio_px": float(err.mean()), "cobertura": float(cobertura)}


def distancias(pares, H, c, tam_ter):
    """Una fila por persona emparejada (sin compuerta)."""
    filas = []
    for pos, cr, ct in pares:
        cr, ct = validas(cr, ct, H, tam_ter, c["margen_borde_px"])
        i, j, d = emparejar(cr, ct, H)
        for k in range(len(i)):
            filas.append({"posicion": pos, "distancia_px": d[k], "alto_caja_termica_px": ct[j[k], 3] - ct[j[k], 1]})
    return pd.DataFrame(filas, columns=["posicion", "distancia_px", "alto_caja_termica_px"])


def mas_cercana(pares, H, c, tam_ter):
    """Una fila por persona térmica que no toca el borde: distancia a la caja RGB alineada más cercana (todas las cajas
    RGB del par, sin emparejamiento húngaro), en px térmicos y relativa a la altura de la caja térmica."""
    filas = []
    for pos, cr, ct in pares:
        ct = ct[dentro(ct, tam_ter, c["margen_borde_px"])]
        if not len(ct) or not len(cr):
            continue
        d = np.linalg.norm(centros(ct)[:, None, :] - llevar(H, centros(cr))[None, :, :], axis=2).min(axis=1)
        alto = ct[:, 3] - ct[:, 1]
        filas += [{"posicion": pos, "distancia_px": d[k], "alto_caja_termica_px": alto[k],
                   "distancia_relativa": d[k] / alto[k]} for k in range(len(ct))]
    return pd.DataFrame(filas, columns=["posicion", "distancia_px", "alto_caja_termica_px", "distancia_relativa"])


def mediana_relativa(personas, radio):
    """Por par: personas que cuentan (caja RGB a `radio` alturas o menos; None = sin límite) y su mediana relativa."""
    x = personas if radio is None else personas[personas.distancia_relativa <= radio]
    return x.groupby("posicion").distancia_relativa.agg(["size", "median"]).rename(
        columns={"size": "personas_cerca", "median": "mediana_relativa"})


def tramos(posiciones, hueco_max):
    t = []
    for p in posiciones:
        if t and p - t[-1][1] <= hueco_max + 1:
            t[-1][1] = p
        else:
            t.append([p, p])
    return t


def regla_desfase(valor, umbral, min_pares, solo_ter, vecindad):
    """valor: posicion -> medida de los pares medidos. Tramos de `min_pares` o más posiciones seguidas con valor mayor
    que `umbral` (un par sin medir corta el tramo), con los pares 'solo térmica' dentro o a `vecindad` o menos."""
    altos = np.sort(valor.index[valor > umbral].to_numpy())
    return [(int(a), int(b), sorted(int(p) for p in solo_ter if a - vecindad <= p <= b + vecindad))
            for a, b in tramos(altos, 0) if b - a + 1 >= min_pares]


def pares_que_salen(tramos_regla):
    desfase = {p for a, b, _ in tramos_regla for p in range(a, b + 1)}
    return desfase, {p for *_, v in tramos_regla for p in v} - desfase


# ---------------------------------------------------------------------------------------------- superposiciones
def superposicion(dataset, par, H, tam_rgb, tam_ter, alto, fuente, titulo):
    """RGB llevada a la térmica | térmica | mezcla, con cajas térmicas en rojo y RGB llevadas en verde."""
    paneles = paneles_superposicion(dataset, par, H, tam_rgb, tam_ter, alto)
    return lado_a_lado(paneles, [titulo, "térmica (rojo: cajas térmicas)", "mezcla 50 % (verde: cajas RGB)"], fuente)


def paneles_superposicion(dataset, par, H, tam_rgb, tam_ter, alto):
    rgb = cv2.imread(str(dataset / par.ruta_rgb))
    al = Image.fromarray(cv2.cvtColor(cv2.warpPerspective(rgb, H, tuple(tam_ter)), cv2.COLOR_BGR2RGB))
    ter = Image.open(dataset / par.ruta_termica).convert("RGB")
    mezcla = Image.blend(al, ter, 0.5)
    cr = cajas_px((dataset / par.ruta_rgb).with_suffix(".txt"), tam_rgb)
    ct = cajas_px((dataset / par.ruta_termica).with_suffix(".txt"), tam_ter)
    crl = cajas_llevadas(H, cr) if len(cr) else cr
    paneles = []
    for img in (al, ter, mezcla):
        d = ImageDraw.Draw(img)
        for b in ct:
            d.rectangle(list(b), outline=ROJO, width=2)
        for b in crl:
            d.rectangle(list(b), outline=VERDE, width=2)
        paneles.append(img.resize((round(alto * tam_ter[0] / tam_ter[1]), alto)))
    return paneles


def hoja_ejemplos(dataset, ejemplos, alto, fuente, tam_ter):
    """Una fila por tramo: título y tres mezclas (par antes del tramo, el peor del tramo, par después), cada una con
    su medida y si la regla la excluye."""
    ancho = round(alto * tam_ter[0] / tam_ter[1])
    filas = []
    for e in ejemplos:
        celdas = []
        for nombre, p in (("antes", e["desde"] - 1), ("peor", e["peor"]), ("después", e["hasta"] + 1)):
            if p in e["g"].index:
                img = paneles_superposicion(dataset, e["g"].loc[p], e["H"], e["tam_rgb"], tam_ter, alto)[2]
                texto = (f"{nombre}: pos {p}, " + ("SE EXCLUYE" if p in e["excluidos"] else "se queda")
                         + f"\n{e['etiquetas'].get(p, 'sin persona en las dos imágenes')}")
            else:
                img = Image.new("RGB", (ancho, alto), (235, 235, 235))
                texto = f"{nombre}: pos {p}\nya excluido o fuera del vuelo"
            celdas.append((img, texto))
        fila = lado_a_lado([c[0] for c in celdas], [c[1] for c in celdas], fuente, banda=46)
        cab = Image.new("RGB", (fila.width, 26), (255, 255, 255))
        ImageDraw.Draw(cab).text((6, 4), e["titulo"], fill=(0, 0, 0), font=fuente)
        filas.append(apilar([cab, fila], sep=0))
    return apilar(filas, sep=14)


def figura_puntos(dataset, fotogramas, H, alto, fuente):
    """Por fotograma: RGB con los puntos manuales (rojo) | térmica con los puntos manuales (rojo) y los puntos RGB
    llevados con la transformación automática (amarillo), unidos por una línea."""
    filas = []
    for nombre, f in fotogramas.items():
        P = np.array(f["puntos"], np.float64)
        rgb = Image.open(dataset / f["ruta_rgb"]).convert("RGB")
        s = alto / rgb.height
        rgb = rgb.resize((round(rgb.width * s), alto))
        ter = Image.open(dataset / f["ruta_termica"]).convert("RGB")
        t = alto / ter.height
        ter = ter.resize((round(ter.width * t), alto))
        dr, dt = ImageDraw.Draw(rgb), ImageDraw.Draw(ter)
        pred = llevar(H, P[:, :2])
        for k, (q, p) in enumerate(zip(P, pred), 1):
            xr, yr, xt, yt = q * [s, s, t, t]
            px, py = p * t
            dr.ellipse([xr - 6, yr - 6, xr + 6, yr + 6], outline=ROJO, width=3)
            dr.text((xr + 8, yr - 10), str(k), fill=ROJO, font=fuente)
            dt.line([xt, yt, px, py], fill=AMARILLO, width=2)
            dt.ellipse([px - 5, py - 5, px + 5, py + 5], outline=AMARILLO, width=2)
            dt.ellipse([xt - 6, yt - 6, xt + 6, yt + 6], outline=ROJO, width=3)
            dt.text((xt + 8, yt - 10), str(k), fill=ROJO, font=fuente)
        err = np.linalg.norm(pred - P[:, 2:], axis=1)
        filas.append(lado_a_lado([rgb, ter], [f"{nombre}, pos {f['posicion']}: puntos marcados en la RGB",
                                             f"térmica: marcados (rojo) y llevados (amarillo); error medio "
                                             f"{err.mean():.1f} px"], fuente))
    return apilar(filas)


def apilar(filas, sep=8):
    lienzo = Image.new("RGB", (max(f.width for f in filas), sum(f.height for f in filas) + sep * (len(filas) - 1)),
                       (255, 255, 255))
    y = 0
    for f in filas:
        lienzo.paste(f, (0, y))
        y += f.height + sep
    return lienzo


# --------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    c = cfg["homografias_cajas"]
    seed = cfg["seed"]
    rutas = leer_rutas(args.rutas)
    D = rutas["dataset"]
    tam_ter = tuple(cfg["tam_termica"])
    pares = pares_utilizables(rutas["data"] / cfg["pares"])
    reporte = rutas["reports"] / c["carpeta_reporte"]
    reporte.mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(cfg["fuente"], 15)

    resumen, comparacion, todas, por_par, desfases, excluir, validacion, salida_h = [], [], [], [], [], [], [], {}
    personas_desfase, sensibilidad, contexto = [], [], {}
    for vuelo, g in pares.groupby("vuelo"):
        g = g.sort_values("posicion").set_index("posicion", drop=False)
        tam_rgb = Image.open(D / g.ruta_rgb.iloc[0]).size
        H0 = homografia_franja(cfg["franja_inicial"], tam_rgb, tam_ter)
        ambos = g[(g.cajas_rgb > 0) & (g.cajas_termica > 0)]
        orden = np.random.default_rng(seed).permutation(len(ambos))
        n_cal = round(len(ambos) * c["fraccion_calibracion"])
        mitad = pd.Series("evaluación", index=ambos.index)
        mitad.iloc[orden[:n_cal]] = "calibración"
        leidos = {r.posicion: (r.posicion, cajas_px((D / r.ruta_rgb).with_suffix(".txt"), tam_rgb),
                               cajas_px((D / r.ruta_termica).with_suffix(".txt"), tam_ter)) for r in ambos.itertuples()}
        cal = [leidos[p] for p in mitad.index[mitad == "calibración"]]
        ev = [leidos[p] for p in mitad.index[mitad == "evaluación"]]

        archivo = RAIZ / cfg["marcado"]["carpeta_puntos"] / f"{vuelo}.yaml"
        manual = None
        if vuelo in c["validacion_manual"] and archivo.exists():
            fot = yaml.safe_load(archivo.read_text(encoding="utf-8"))["fotogramas"]
            manual = {n: fot[n] for n in c["validacion_manual"][vuelo] if fot.get(n, {}).get("puntos")}
            if manual:
                P_manual = np.array([q for f in manual.values() for q in f["puntos"]], np.float64)
            else:
                manual = None

        # comparación de modelos con la misma partición
        modelos = {}
        for modelo in ["franja", *c["modelos_comparados"]]:
            H, info = (H0, {}) if modelo == "franja" else estimar(cal, H0, c, tam_ter, modelo, seed)
            if H is None:
                comparacion.append({"vuelo": vuelo, "modelo": modelo, "estimada": False})
                continue
            d = distancias(ev, H, c, tam_ter)
            cv = campo_de_vision(H, tam_rgb, tam_ter)
            fila = {"vuelo": vuelo, "modelo": modelo, "estimada": True, **info,
                    "pares_evaluados": d.posicion.nunique(), "personas_evaluadas": len(d),
                    "distancia_media_px": d.distancia_px.mean(), "distancia_mediana_px": d.distancia_px.median(),
                    "distancia_p95_px": d.distancia_px.quantile(0.95), "distancia_max_px": d.distancia_px.max(),
                    "vision_x": f"{cv[[0, 3], 0].mean():.2f} a {cv[[1, 2], 0].mean():.2f}",
                    "vision_y": f"{cv[[0, 1], 1].mean():.2f} a {cv[[2, 3], 1].mean():.2f}",
                    "deformacion_vision": float(np.ptp(cv[[0, 3], 0]) + np.ptp(cv[[1, 2], 0])
                                                + np.ptp(cv[[0, 1], 1]) + np.ptp(cv[[2, 3], 1]))}
            if manual is not None:
                e = np.linalg.norm(llevar(H, P_manual[:, :2]) - P_manual[:, 2:], axis=1)
                fila.update({"error_manual_medio_px": e.mean(), "error_manual_max_px": e.max()})
                k = 0
                for nombre, f in manual.items():
                    n = len(f["puntos"])
                    fila[f"error_manual_{nombre}_px"] = e[k:k + n].mean()
                    k += n
            comparacion.append(fila)
            modelos[modelo] = (H, info, d, fila)

        if c["modelo"] not in modelos:
            resumen.append({"vuelo": vuelo, "revisar_a_mano": "no se pudo estimar"})
            print(f"\n{vuelo}: no se pudo estimar la transformación")
            continue
        H, info, d, fila = modelos[c["modelo"]]
        d.insert(0, "vuelo", vuelo)
        todas.append(d)
        lo, hi = g.posicion.min(), g.posicion.max()
        tercio = np.minimum(((d.posicion - lo) * 3 // (hi - lo + 1)).astype(int), 2)
        fila = {k: v for k, v in fila.items() if k not in ("modelo", "estimada")}
        fila.update({"tam_rgb": f"{tam_rgb[0]}x{tam_rgb[1]}", "pares_con_persona_en_ambas": len(ambos),
                     "pares_calibracion": len(cal), "pares_evaluacion": len(ev),
                     "distancia_relativa_mediana": (d.distancia_px / d.alto_caja_termica_px).median(),
                     **{f"media_tercio_{k + 1}_px": d.distancia_px[tercio == k].mean() for k in range(3)},
                     "distancia_media_franja_px": modelos["franja"][3]["distancia_media_px"]})

        if manual is not None:
            for nombre, f in manual.items():
                for q in f["puntos"]:
                    q = np.array(q, np.float64)
                    validacion.append({
                        "vuelo": vuelo, "fotograma": nombre, "posicion": f["posicion"], "x_rgb": q[0], "y_rgb": q[1],
                        "x_termica": q[2], "y_termica": q[3],
                        **{f"error_{m}_px": float(np.linalg.norm(llevar(modelos[m][0], q[:2])[0] - q[2:]))
                           for m in modelos}})
            figura_puntos(D, manual, H, c["alto_panel"], fuente).save(reporte / f"puntos_manuales_{vuelo}.jpg",
                                                                       quality=c["calidad_jpg"])

        motivos = []
        if len(cal) < c["pares_calibracion_minimos"]:
            motivos.append(f"solo {len(cal)} pares de calibración")
        if info["cobertura"] < c["cobertura_minima"]:
            motivos.append(f"las personas cubren solo el {info['cobertura']:.0%} de la térmica")
        if fila["deformacion_vision"] > c["deformacion_maxima"]:
            motivos.append(f"campo de visión deformado ({fila['vision_x']} x {fila['vision_y']})")
        if fila["distancia_mediana_px"] > c["distancia_mediana_maxima_px"]:
            motivos.append(f"distancia mediana {fila['distancia_mediana_px']:.1f} px")
        if fila.get("error_manual_medio_px", 0) > c["error_puntos_manuales_max_px"]:
            motivos.append(f"error con puntos manuales {fila['error_manual_medio_px']:.1f} px")
        fila["revisar_a_mano"] = "; ".join(motivos)
        resumen.append(fila)
        salida_h[vuelo] = {"H_rgb_a_termica": [[float(x) for x in r] for r in H], "modelo": c["modelo"],
                           "tam_rgb": list(tam_rgb), "tam_termica": list(tam_ter),
                           "metodo": "centros de cajas de personas, RANSAC", "pares_calibracion": len(cal),
                           "inliers": info["inliers"], "error_inliers_medio_px": round(info["error_inliers_medio_px"], 2),
                           "distancia_media_evaluacion_px": round(float(fila["distancia_media_px"]), 2),
                           "distancia_mediana_evaluacion_px": round(float(fila["distancia_mediana_px"]), 2),
                           "calculada": datetime.now().isoformat(timespec="seconds")}

        # medidas por par en todos los pares con persona en ambas (las dos mitades): distancia con el emparejamiento
        # húngaro (regla anterior) y mediana relativa a la caja RGB más cercana (regla nueva)
        todos = list(leidos.values())
        dt = distancias(todos, H, c, tam_ter)
        pers = mas_cercana(todos, H, c, tam_ter)
        pers["cuenta"] = pers.distancia_relativa <= c["radio_cerca_alturas"]
        personas_desfase.append(pers.assign(vuelo=vuelo))
        pp = dt.groupby("posicion").distancia_px.agg(["size", "mean", "max"]).rename(
            columns={"size": "personas", "mean": "distancia_media_px", "max": "distancia_max_px"})
        pp = pp.join(pers.groupby("posicion").size().rename("personas_termicas"), how="outer")
        pp = pp.join(mediana_relativa(pers, c["radio_cerca_alturas"]), how="outer").reset_index()
        pp.insert(0, "vuelo", vuelo)
        pp["mitad"] = pp.posicion.map(mitad)
        por_par.append(pp)
        pp = pp.set_index("posicion")

        solo_ter = set(g.posicion[(g.cajas_termica > 0) & (g.cajas_rgb == 0)].astype(int))
        reglas = (c["desfase_min_pares"], solo_ter, c["vecindad_solo_termica"])
        nueva = regla_desfase(pp.mediana_relativa.dropna(), c["umbral_desfase_relativo"], *reglas)
        anterior = regla_desfase(pp.distancia_max_px.dropna(), c["umbral_desfase_px"], *reglas)
        for a, b, vecinos in nueva:
            s = pp.loc[a:b]
            desfases.append({"vuelo": vuelo, "desde": a, "hasta": b, "pares": b - a + 1,
                             "mediana_relativa_max": s.mediana_relativa.max(),
                             "peor": int(s.mediana_relativa.idxmax()),
                             "distancia_max_px": s.distancia_max_px.max(),
                             "en_regla_anterior": any(a <= y and x <= b for x, y, _ in anterior),
                             "solo_termica_cerca": len(vecinos), "posiciones_solo_termica": " ".join(map(str, vecinos))})
        desfase, vecinos = pares_que_salen(nueva)
        excluir += [{"vuelo": vuelo, "posicion": p, "motivo": "desfase"} for p in sorted(desfase)]
        excluir += [{"vuelo": vuelo, "posicion": p, "motivo": "solo térmica junto a un desfase"} for p in sorted(vecinos)]
        for regla, t in [("anterior (25 px)", anterior)] + [
                (f"radio {r} alturas" if r is not None else "sin límite de radio",
                 regla_desfase(mediana_relativa(pers, r)["mediana_relativa"], c["umbral_desfase_relativo"], *reglas))
                for r in c["radios_comparados_alturas"]]:
            d_, v_ = pares_que_salen(t)
            sensibilidad.append({"vuelo": vuelo, "regla": regla, "tramos": len(t), "desfase": len(d_),
                                 "solo_termica_vecinos": len(v_), "salen": len(d_) + len(v_)})

        etiquetas = {}
        for p, r in pp.iterrows():
            if pd.notna(r.mediana_relativa):
                etiquetas[p] = (f"mediana rel. {r.mediana_relativa:.2f} ({r.personas_cerca:.0f} de "
                                f"{r.personas_termicas:.0f} pers.)")
            elif pd.notna(r.personas_termicas):
                etiquetas[p] = f"ninguna de {r.personas_termicas:.0f} pers. tiene caja RGB cerca"
            if pd.notna(r.distancia_max_px):
                etiquetas[p] = etiquetas.get(p, "") + f", húngaro máx. {r.distancia_max_px:.0f} px"
        for r in g.itertuples():
            if r.posicion not in etiquetas:
                etiquetas[r.posicion] = ("solo térmica" if r.posicion in solo_ter else
                                         "sin personas" if r.cajas_termica == 0 and r.cajas_rgb == 0 else
                                         "solo RGB" if r.cajas_termica == 0 else "personas térmicas en el borde")
        contexto[vuelo] ={"g": g, "H": H, "tam_rgb": tam_rgb, "etiquetas": etiquetas, "pp": pp,
                           "excluidos": desfase | vecinos}

        # peores pares de evaluación
        peores = d.groupby("posicion").distancia_px.max().nlargest(c["peores_por_vuelo"])
        filas_img = [superposicion(D, g.loc[p], H, tam_rgb, tam_ter, c["alto_panel"], fuente,
                                   f"pos {p} | RGB alineada | distancia máx. {v:.1f} px") for p, v in peores.items()]
        apilar(filas_img).save(reporte / f"peores_{vuelo}.jpg", quality=c["calidad_jpg"])

        # hoja de superposiciones: pares repartidos a lo largo del vuelo
        posiciones = g.posicion.to_numpy()[np.linspace(0, len(g) - 1, c["superposiciones_por_vuelo"]).round().astype(int)]
        filas_img = [superposicion(D, g.loc[p], H, tam_rgb, tam_ter, c["alto_panel"] // 2, fuente,
                                   f"pos {p} | RGB alineada") for p in posiciones]
        apilar(filas_img).save(reporte / f"superposiciones_{vuelo}.jpg", quality=c["calidad_jpg"])

        print(f"\n{vuelo} ({tam_rgb[0]}x{tam_rgb[1]}, modelo {c['modelo']}): {len(ambos)} pares con persona en ambas, "
              f"{len(cal)} de calibración ({info['inliers']} de {info['correspondencias']} correspondencias inliers, "
              f"error {info['error_inliers_medio_px']:.2f} px, cobertura {info['cobertura']:.0%})")
        print(f"  evaluación: {fila['pares_evaluados']} pares, {fila['personas_evaluadas']} personas; distancia media "
              f"{fila['distancia_media_px']:.2f} px (franja {fila['distancia_media_franja_px']:.2f}), mediana "
              f"{fila['distancia_mediana_px']:.2f}, p95 {fila['distancia_p95_px']:.2f}, máx. {fila['distancia_max_px']:.1f}; "
              f"por tercios {fila['media_tercio_1_px']:.2f} / {fila['media_tercio_2_px']:.2f} / {fila['media_tercio_3_px']:.2f}")
        print(f"  campo de visión en la RGB: x {fila['vision_x']}, y {fila['vision_y']} "
              f"(deformación {fila['deformacion_vision']:.2f})")
        if "error_manual_medio_px" in fila:
            print(f"  puntos manuales: error medio {fila['error_manual_medio_px']:.2f} px, "
                  f"máx. {fila['error_manual_max_px']:.2f} px")
        if fila["revisar_a_mano"]:
            print(f"  REVISAR: {fila['revisar_a_mano']}")

    (RAIZ / c["salida"]).write_text(yaml.safe_dump(salida_h, allow_unicode=True, sort_keys=False), encoding="utf-8")
    pd.DataFrame(resumen).round(3).to_csv(reporte / "resumen.csv", index=False, encoding="utf-8")
    comp = pd.DataFrame(comparacion).round(3)
    comp.to_csv(reporte / "comparacion_modelos.csv", index=False, encoding="utf-8")
    pd.concat(todas).round(2).to_csv(reporte / "distancias.csv", index=False, encoding="utf-8")
    pd.concat(por_par).round(2).to_csv(reporte / "distancia_por_par.csv", index=False, encoding="utf-8")
    pd.concat(personas_desfase)[["vuelo", "posicion", "distancia_px", "alto_caja_termica_px", "distancia_relativa",
                                 "cuenta"]].round(3).to_csv(reporte / "personas_desfase.csv", index=False, encoding="utf-8")
    des = pd.DataFrame(desfases, columns=["vuelo", "desde", "hasta", "pares", "mediana_relativa_max", "peor",
                                          "distancia_max_px", "en_regla_anterior", "solo_termica_cerca",
                                          "posiciones_solo_termica"]).round(2)
    des.to_csv(reporte / "desfases.csv", index=False, encoding="utf-8")
    exc = pd.DataFrame(excluir, columns=["vuelo", "posicion", "motivo"])
    exc.to_csv(reporte / "exclusion_desfase_propuesta.csv", index=False, encoding="utf-8")
    sens = pd.DataFrame(sensibilidad)
    sens.to_csv(reporte / "sensibilidad_radio.csv", index=False, encoding="utf-8")
    pd.DataFrame(validacion).round(2).to_csv(reporte / "validacion_manual.csv", index=False, encoding="utf-8")

    pd.set_option("display.width", 250)
    print("\nComparación de modelos (pares de evaluación):")
    print(comp[["vuelo", "modelo", "pares_evaluados", "distancia_media_px", "distancia_mediana_px", "distancia_max_px",
                "vision_x", "vision_y", "deformacion_vision"]].round(2).to_string(index=False))

    # resumen de la regla de desfase
    print(f"\nRegla de desfase: mediana de la distancia relativa a la caja RGB más cercana > "
          f"{c['umbral_desfase_relativo']} (cuentan las personas con caja RGB a {c['radio_cerca_alturas']} alturas o "
          f"menos), {c['desfase_min_pares']} o más pares seguidos, 'solo térmica' a {c['vecindad_solo_termica']} "
          f"posiciones o menos: {len(des)} tramos ({(~des.en_regla_anterior).sum()} que la regla anterior no tenía)")
    solo_por_vuelo = pares[(pares.cajas_termica > 0) & (pares.cajas_rgb == 0)].groupby("vuelo").size()
    cuenta = pares.groupby("vuelo").size().rename("pares_utilizables").to_frame().join(
        exc.groupby(["vuelo", "motivo"]).size().unstack()).fillna(0).astype(int)
    for col in ("desfase", "solo térmica junto a un desfase"):
        if col not in cuenta:
            cuenta[col] = 0
    cuenta["salen"] = cuenta[["desfase", "solo térmica junto a un desfase"]].sum(axis=1)
    cuenta["quedarian"] = cuenta.pares_utilizables - cuenta.salen
    cuenta["solo_termica_hoy"] = solo_por_vuelo.reindex(cuenta.index).fillna(0).astype(int)
    cuenta["solo_termica_quedarian"] = cuenta.solo_termica_hoy - cuenta["solo térmica junto a un desfase"]
    cuenta.loc["TOTAL"] = cuenta.sum()
    print(cuenta.to_string())
    print("\nSensibilidad (pares que salen por vuelo):")
    print(sens.pivot(index="vuelo", columns="regla", values="salen").pipe(
        lambda t: pd.concat([t, t.sum().rename("TOTAL").to_frame().T])).to_string())
    for vuelo, f in cfg["marcado"].get("fotogramas", {}).items():
        en_exc = [n for n, p in f.items() if ((exc.vuelo == vuelo) & (exc.posicion == p)).any()]
        if en_exc:
            print(f"AVISO: fotogramas de marcado de {vuelo} dentro de la exclusión propuesta: {en_exc}")

    # hoja de ejemplos: los tramos de la hoja anterior y `ejemplos_desfase_nuevos` tramos de la regla nueva que la
    # anterior no tenía, repartidos según su mediana relativa
    ejemplos = []
    for t in c["ejemplos_desfase_anteriores"]:
        x = contexto[t["vuelo"]]
        s = x["pp"].loc[t["desde"]:t["hasta"]]
        peor = int(s.mediana_relativa.idxmax()) if s.mediana_relativa.notna().any() else t["desde"]
        salen = sorted(p for p in range(t["desde"], t["hasta"] + 1) if p in x["excluidos"])
        ejemplos.append({**x, **t, "peor": peor,
                         "titulo": f"{t['vuelo']}: tramo {t['desde']}-{t['hasta']} (hoja anterior) | regla nueva: "
                                   + (f"excluye {' '.join(map(str, salen))}" if salen else "no lo excluye")})
    nuevos = des[~des.en_regla_anterior]
    if len(nuevos) < c["ejemplos_desfase_nuevos"]:  # si faltan, tramos que la anterior también tenía
        nuevos = pd.concat([nuevos, des[des.en_regla_anterior]])
    nuevos = nuevos.sort_values(["mediana_relativa_max", "vuelo", "desde"]).reset_index(drop=True)
    k = min(c["ejemplos_desfase_nuevos"], len(nuevos))
    elegidos = nuevos.iloc[sorted(set(np.linspace(0, len(nuevos) - 1, k).round().astype(int)))] if k else nuevos
    for t in elegidos.itertuples():
        ejemplos.append({**contexto[t.vuelo], "desde": t.desde, "hasta": t.hasta, "peor": t.peor,
                         "titulo": f"{t.vuelo}: tramo {t.desde}-{t.hasta} (nuevo; {t.pares} pares, mediana rel. máx. "
                                   f"{t.mediana_relativa_max:.2f}; "
                                   + ("también en la regla anterior" if t.en_regla_anterior else "no estaba en la regla anterior")
                                   + f"; solo térmica cerca: {t.solo_termica_cerca})"})
    hoja_ejemplos(D, ejemplos, c["alto_panel_ejemplos"], fuente, tam_ter).save(
        reporte / "ejemplos_desfase.jpg", quality=c["calidad_jpg"])
    print("\nEjemplos en la hoja:\n" + "\n".join(e["titulo"] for e in ejemplos))

    r = pd.DataFrame(resumen)
    agregar_a_bitacora(rutas["bitacora"], 2, f"transformación RGB->térmica por centros de cajas ({c['modelo']})",
                       f"RANSAC {c['umbral_ransac_px']} px, {c['fraccion_calibracion']:.0%} calibración, seed={seed}",
                       "distancia media / mediana en evaluación: " + "; ".join(
                           f"{v.split('_Enterprise_')[0][7:]} {v.split('_')[-1]} {m:.1f} / {md:.1f} px"
                           for v, m, md in zip(r.vuelo, r.distancia_media_px, r.distancia_mediana_px))
                       + f"; regla de desfase propuesta (mediana relativa > {c['umbral_desfase_relativo']}, radio "
                         f"{c['radio_cerca_alturas']} alturas): salen {cuenta.loc['TOTAL', 'salen']} de "
                         f"{cuenta.loc['TOTAL', 'pares_utilizables']} pares")
    print(f"\n{RAIZ / c['salida']}\n{reporte}")


if __name__ == "__main__":
    main()
