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

Desfases: con el modelo guardado se mide la distancia en todos los pares con persona en las dos imágenes (de las dos
mitades) y se listan los tramos de al menos `desfase_min_pares` pares seguidos por encima de `umbral_desfase_px`.

Salidas: configs/homografias_cajas.yaml y, en reports/alineacion/homografias_cajas/: resumen.csv,
comparacion_modelos.csv, distancias.csv, distancia_por_par.csv, desfases.csv, validacion_manual.csv, revisar.csv y
las imágenes (superposiciones, peores pares, tramos a revisar y puntos manuales). Agrega una fila a la bitácora.

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


def validas(cr, ct, H, tam_ter, margen):
    """Cajas RGB que caen enteras dentro de la térmica y cajas térmicas que no tocan el borde."""
    tw, th = tam_ter

    def dentro(c):
        return (c[:, 0] >= margen) & (c[:, 1] >= margen) & (c[:, 2] <= tw - margen) & (c[:, 3] <= th - margen)
    return cr[dentro(cajas_llevadas(H, cr))], ct[dentro(ct)]


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


def tramos(posiciones, hueco_max):
    t = []
    for p in posiciones:
        if t and p - t[-1][1] <= hueco_max + 1:
            t[-1][1] = p
        else:
            t.append([p, p])
    return t


# ---------------------------------------------------------------------------------------------- superposiciones
def superposicion(dataset, par, H, tam_rgb, tam_ter, alto, fuente, titulo):
    """RGB llevada a la térmica | térmica | mezcla, con cajas térmicas en rojo y RGB llevadas en verde."""
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
    return lado_a_lado(paneles, [titulo, "térmica (rojo: cajas térmicas)", "mezcla 50 % (verde: cajas RGB)"], fuente)


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

    resumen, comparacion, todas, por_par, desfases, validacion, revisar, salida_h = [], [], [], [], [], [], [], {}
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
            manual = yaml.safe_load(archivo.read_text(encoding="utf-8"))["fotogramas"]
            P_manual = np.array([q for f in manual.values() for q in f["puntos"]], np.float64)

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

        # distancia en todos los pares con persona en ambas (las dos mitades) y tramos de desfase
        dt = distancias(list(leidos.values()), H, c, tam_ter)
        pp = dt.groupby("posicion").distancia_px.agg(["size", "mean", "max"]).rename(
            columns={"size": "personas", "mean": "distancia_media_px", "max": "distancia_max_px"}).reset_index()
        pp.insert(0, "vuelo", vuelo)
        pp["mitad"] = pp.posicion.map(mitad)
        por_par.append(pp)
        altos = pp.posicion[pp.distancia_max_px > c["umbral_desfase_px"]].to_numpy()
        for a, b in tramos(altos, c["desfase_hueco_max"]):
            s = pp[pp.posicion.between(a, b)]
            if (s.distancia_max_px > c["umbral_desfase_px"]).sum() >= c["desfase_min_pares"]:
                desfases.append({"vuelo": vuelo, "desde": a, "hasta": b, "pares_con_persona": len(s),
                                 "pares_sobre_umbral": int((s.distancia_max_px > c["umbral_desfase_px"]).sum()),
                                 "distancia_max_px": s.distancia_max_px.max()})

        # tramos a revisar (giros rápidos): todos sus pares, de cualquier mitad
        if vuelo in c["revisar"]:
            a, b = c["revisar"][vuelo]
            filas_img = []
            for p in range(a, b + 1):
                if p not in g.index:
                    continue
                par = g.loc[p]
                cr = cajas_px((D / par.ruta_rgb).with_suffix(".txt"), tam_rgb)
                ct = cajas_px((D / par.ruta_termica).with_suffix(".txt"), tam_ter)
                dp = distancias([(p, cr, ct)], H, c, tam_ter)
                revisar.append({"vuelo": vuelo, "posicion": p, "mitad": mitad.get(p, "sin persona en ambas"),
                                "personas_emparejadas": len(dp),
                                "distancia_media_px": dp.distancia_px.mean() if len(dp) else np.nan,
                                "distancia_max_px": dp.distancia_px.max() if len(dp) else np.nan})
                dist = f"{dp.distancia_px.max():.1f} px" if len(dp) else "sin personas emparejadas"
                filas_img.append(superposicion(D, par, H, tam_rgb, tam_ter, c["alto_panel"] * 2 // 3, fuente,
                                               f"pos {p} | RGB alineada | distancia máx. {dist}"))
            apilar(filas_img).save(reporte / f"revisar_{vuelo}_{a:04d}-{b:04d}.jpg", quality=c["calidad_jpg"])

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
    des = pd.DataFrame(desfases, columns=["vuelo", "desde", "hasta", "pares_con_persona", "pares_sobre_umbral",
                                          "distancia_max_px"]).round(1)
    des.to_csv(reporte / "desfases.csv", index=False, encoding="utf-8")
    pd.DataFrame(validacion).round(2).to_csv(reporte / "validacion_manual.csv", index=False, encoding="utf-8")
    pd.DataFrame(revisar).round(2).to_csv(reporte / "revisar.csv", index=False, encoding="utf-8")

    pd.set_option("display.width", 250)
    print("\nComparación de modelos (pares de evaluación):")
    print(comp[["vuelo", "modelo", "pares_evaluados", "distancia_media_px", "distancia_mediana_px", "distancia_max_px",
                "vision_x", "vision_y", "deformacion_vision"]].round(2).to_string(index=False))
    if revisar:
        print("\nTramos a revisar:\n" + pd.DataFrame(revisar).round(1).to_string(index=False))
    print(f"\nTramos de desfase (>= {c['desfase_min_pares']} pares sobre {c['umbral_desfase_px']} px): {len(des)}")
    print(des.to_string(index=False))

    r = pd.DataFrame(resumen)
    agregar_a_bitacora(rutas["bitacora"], 2, f"transformación RGB->térmica por centros de cajas ({c['modelo']})",
                       f"RANSAC {c['umbral_ransac_px']} px, {c['fraccion_calibracion']:.0%} calibración, seed={seed}",
                       "distancia media / mediana en evaluación: " + "; ".join(
                           f"{v.split('_Enterprise_')[0][7:]} {v.split('_')[-1]} {m:.1f} / {md:.1f} px"
                           for v, m, md in zip(r.vuelo, r.distancia_media_px, r.distancia_mediana_px)))
    print(f"\n{RAIZ / c['salida']}\n{reporte}")


if __name__ == "__main__":
    main()
