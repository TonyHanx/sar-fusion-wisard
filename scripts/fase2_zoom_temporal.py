"""Fase 2: zoom relativo de la RGB respecto de la térmica a lo largo de cada vuelo.

Entre cada par de fotogramas consecutivos se estima, en cada cámara por separado, la escala de la transformación de
semejanza (puntos ORB + cv2.estimateAffinePartial2D con RANSAC). Si el dron sube o baja, las dos escalas cambian igual;
si solo cambia la de la RGB, cambió su zoom. El producto acumulado de s_rgb / s_termica es el zoom relativo de la RGB.
El nivel normal del vuelo es la mediana de ese zoom; los fotogramas que se alejan más del umbral son "distintos"
(cambio de zoom o deriva gradual, por ejemplo al acercarse al suelo).

Salidas en reports/alineacion/: zoom_temporal.csv (un fotograma por fila) y tramos_zoom.csv (tramos distintos).

Uso: python scripts/fase2_zoom_temporal.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import pandas as pd

from comun import leer_rutas, leer_yaml, pares_utilizables


def leer(ruta, ancho):
    g = cv2.imread(str(ruta), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(g, None, fx=ancho / g.shape[1], fy=ancho / g.shape[1], interpolation=cv2.INTER_AREA)


def escala(a, b, c):
    orb = cv2.ORB_create(c["puntos_orb"])
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None:
        return np.nan, 0
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(m) < c["inliers_minimos"]:
        return np.nan, len(m)
    pa = np.float32([ka[x.queryIdx].pt for x in m])
    pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=c["umbral_ransac_px"])
    n = 0 if inl is None else int(inl.sum())
    if M is None or n < c["inliers_minimos"]:
        return np.nan, n
    return float(np.hypot(M[0, 0], M[1, 0])), n


def paso(args):
    """Escalas RGB y térmica entre el fotograma anterior y el actual."""
    rgb_a, ter_a, rgb_b, ter_b, c = args
    sr, ir = escala(leer(rgb_a, c["ancho_rgb"]), leer(rgb_b, c["ancho_rgb"]), c)
    st, it = escala(leer(ter_a, c["ancho_termica"]), leer(ter_b, c["ancho_termica"]), c)
    return sr, ir, st, it


def tramos(mascara, posiciones, hueco_max):
    t = []
    for pos in posiciones[mascara]:
        if t and pos - t[-1][1] <= hueco_max + 1:
            t[-1][1] = pos
        else:
            t.append([pos, pos])
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    c = cfg["zoom_temporal"]
    rutas = leer_rutas(args.rutas)
    pares = pares_utilizables(rutas["data"] / cfg["pares"]).sort_values(["vuelo", "posicion"])
    D = rutas["dataset"]

    tareas, indices = [], []
    for _, g in pares.groupby("vuelo", sort=False):
        g = g.reset_index()
        for i in range(1, len(g)):
            a, b = g.iloc[i - 1], g.iloc[i]
            tareas.append((D / a.ruta_rgb, D / a.ruta_termica, D / b.ruta_rgb, D / b.ruta_termica, c))
            indices.append(b["index"])
    with ProcessPoolExecutor(max_workers=c["procesos"]) as ex:
        res = list(ex.map(paso, tareas, chunksize=8))
    pares[["s_rgb", "inliers_rgb", "s_termica", "inliers_termica"]] = np.nan
    pares.loc[indices, ["s_rgb", "inliers_rgb", "s_termica", "inliers_termica"]] = np.array(res, dtype=float)

    filas = []
    for vuelo, g in pares.groupby("vuelo", sort=False):
        salto = np.log(g.s_rgb / g.s_termica)
        fallo = salto.isna() & (g.posicion != g.posicion.min())
        zoom = np.exp(salto.fillna(0).cumsum())
        normal = zoom.median()
        distinto = np.abs(np.log(zoom / normal)) > c["umbral_zoom"]
        pares.loc[g.index, "salto"] = salto
        pares.loc[g.index, "zoom_relativo"] = zoom / normal
        pares.loc[g.index, "distinto"] = distinto
        saltos = g.posicion[np.abs(salto) > c["umbral_salto"]]
        print(f"\n{vuelo}: {len(g)} pares, {int(fallo.sum())} pasos sin estimar, {int(distinto.sum())} fotogramas distintos")
        if len(saltos):
            print("  saltos de zoom entre fotogramas: "
                  + ", ".join(f"{p - 1}->{p} (x{np.exp(salto[g.posicion == p].iloc[0]):.2f})" for p in saltos))
        for a, b in tramos(distinto.to_numpy(), g.posicion.to_numpy(), c["hueco_max"]):
            s = g[g.posicion.between(a, b)]
            z = (zoom / normal)[s.index]
            filas.append(dict(vuelo=vuelo, desde=a, hasta=b, n=len(s), zoom_min=round(z.min(), 3),
                              zoom_max=round(z.max(), 3), pasos_sin_estimar=int(fallo[s.index].sum())))
            print(f"  tramo {a}-{b} ({len(s)} pares): zoom relativo {z.min():.2f} a {z.max():.2f}")

    destino = rutas["reports"] / c["salida"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    pares[["vuelo", "posicion", "s_rgb", "inliers_rgb", "s_termica", "inliers_termica", "salto", "zoom_relativo",
           "distinto"]].to_csv(destino, index=False, encoding="utf-8")
    pd.DataFrame(filas, columns=["vuelo", "desde", "hasta", "n", "zoom_min", "zoom_max", "pasos_sin_estimar"]).to_csv(
        destino.with_name("tramos_zoom.csv"), index=False, encoding="utf-8")
    print(f"\n{destino}")


if __name__ == "__main__":
    main()
