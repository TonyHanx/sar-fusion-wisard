"""Fase 2: estima, en cada par, la escala y la posición en que la RGB coincide con la térmica, para encontrar
despegues, aterrizajes y cambios de zoom.

Método: bordes (magnitud del gradiente) de las dos imágenes; la RGB se reescala a varias escalas alrededor de la
nominal (la de la franja de CLAUDE.md) y en cada una se busca el centro de la térmica con correlación normalizada
(cv2.matchTemplate). Se queda la escala con mayor correlación (búsqueda gruesa y luego fina). Un fotograma es
"distinto" si su escala se aleja de la mediana del vuelo o si la correlación cae mucho (la RGB ya no coincide con la
térmica por ninguna escala: aterrizaje, paralaje o desfase).

Uso: python scripts/fase2_escala_por_fotograma.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import pandas as pd

from comun import leer_rutas, leer_yaml, pares_utilizables


def bordes(img, sigma):
    g = cv2.GaussianBlur(img.astype(np.float32), (0, 0), sigma)
    m = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return m / (m.mean() + 1e-6)


def correlacion(rgb, plantilla, escala, sigma):
    rs = cv2.resize(rgb, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    if rs.shape[0] < plantilla.shape[0] or rs.shape[1] < plantilla.shape[1]:
        return -1.0, None
    res = cv2.matchTemplate(bordes(rs, sigma), plantilla, cv2.TM_CCOEFF_NORMED)
    _, v, _, loc = cv2.minMaxLoc(res)
    return v, loc


def estimar(args):
    ruta_rgb, ruta_ter, c = args
    ter = cv2.imread(str(ruta_ter), cv2.IMREAD_GRAYSCALE)
    rgb = cv2.imread(str(ruta_rgb), cv2.IMREAD_GRAYSCALE)
    w_rgb = rgb.shape[1]
    rgb = cv2.resize(rgb, None, fx=c["ancho_rgb_trabajo"] / w_rgb, fy=c["ancho_rgb_trabajo"] / w_rgb,
                     interpolation=cv2.INTER_AREA)
    ter = cv2.resize(ter, None, fx=1 / c["reduccion_termica"], fy=1 / c["reduccion_termica"], interpolation=cv2.INTER_AREA)
    et = bordes(ter, c["sigma_bordes"])
    h, w = et.shape
    m = (1 - c["recorte_centro"]) / 2
    plantilla = et[int(h * m):int(h * (1 - m)), int(w * m):int(w * (1 - m))]
    (x0, x1) = c["franja_x"]
    nominal = w / ((x1 - x0) * rgb.shape[1])  # px térmicos (reducidos) por px RGB (reducido)

    gruesas = np.exp(np.linspace(np.log(c["escala_min"]), np.log(c["escala_max"]), c["pasos_gruesos"]))
    mejor = max(((*correlacion(rgb, plantilla, nominal * s, c["sigma_bordes"]), s) for s in gruesas), key=lambda t: t[0])
    paso = np.log(gruesas[1] / gruesas[0])
    finas = np.exp(np.log(mejor[2]) + np.linspace(-paso, paso, c["pasos_finos"]))
    mejor = max([mejor] + [(*correlacion(rgb, plantilla, nominal * s, c["sigma_bordes"]), s) for s in finas],
                key=lambda t: t[0])
    v, loc, s = mejor
    return s, v, (np.nan if loc is None else loc[0]), (np.nan if loc is None else loc[1])


def tramos(distinto, posiciones, hueco_max):
    """Agrupa las posiciones marcadas como distintas en tramos [inicio, fin]."""
    t = []
    for pos in posiciones[distinto]:
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
    c = dict(cfg["escala_por_fotograma"], franja_x=cfg["franja_inicial"]["x"])
    rutas = leer_rutas(args.rutas)
    pares = pares_utilizables(rutas["data"] / cfg["pares"])

    tareas = [(rutas["dataset"] / r.ruta_rgb, rutas["dataset"] / r.ruta_termica, c) for r in pares.itertuples()]
    with ProcessPoolExecutor(max_workers=c["procesos"]) as ex:
        res = list(ex.map(estimar, tareas, chunksize=8))
    pares[["escala", "ncc", "dx", "dy"]] = pd.DataFrame(res, index=pares.index)

    filas = []
    for vuelo, g in pares.groupby("vuelo", sort=False):
        med_s, med_v = g.escala.median(), g.ncc.median()
        dist = (np.abs(np.log(g.escala / med_s)) > c["umbral_escala"]) | (g.ncc < c["umbral_ncc_relativo"] * med_v)
        pares.loc[g.index, "distinto"] = dist
        print(f"\n{vuelo}: {len(g)} pares, escala mediana {med_s:.3f}, ncc mediana {med_v:.3f}, "
              f"{int(dist.sum())} fotogramas distintos")
        for a, b in tramos(dist.to_numpy(), g.posicion.to_numpy(), c["hueco_max"]):
            s = g[g.posicion.between(a, b)]
            filas.append(dict(vuelo=vuelo, desde=a, hasta=b, n=len(s), distintos=int(s.distinto.sum()) if "distinto" in s
                              else None, escala_mediana=round(s.escala.median() / med_s, 3), ncc_mediana=round(s.ncc.median(), 3)))
            print(f"  tramo {a}-{b} ({len(s)} pares): escala {s.escala.median() / med_s:.2f} x la del vuelo, "
                  f"ncc mediana {s.ncc.median():.3f}")

    destino = rutas["reports"] / c["salida"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    pares[["vuelo", "posicion", "escala", "ncc", "dx", "dy", "distinto"]].to_csv(destino, index=False, encoding="utf-8")
    pd.DataFrame(filas).to_csv(destino.with_name("tramos_distintos.csv"), index=False, encoding="utf-8")
    print(f"\n{destino}")


if __name__ == "__main__":
    main()
