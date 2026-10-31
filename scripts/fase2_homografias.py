"""Fase 2: homografías RGB -> térmica a partir de los puntos de control marcados a mano.

Por cada vuelo con puntos (configs/puntos_control/<vuelo>.yaml):
  1. Una homografía por fotograma (inicio, mitad, final) con cv2.findHomography y RANSAC.
  2. Cuánto difieren entre sí:
     - error cruzado: la homografía de un fotograma aplicada a los puntos de otro (px térmicos). Si el zoom no cambió,
       es del orden del error de marcado; si cambió, crece. Es el criterio de decisión.
     - desplazamiento de una rejilla llevada de la térmica a la RGB con una homografía y de vuelta con la otra, solo
       dentro del rectángulo que cubren los puntos marcados (fuera de él las homografías extrapolan). Informativo.
  3. Si el error cruzado medio no supera el umbral, una sola homografía con los puntos de los tres fotogramas, que se
     guarda en configs/homografias.yaml. Si lo supera, no se guarda y se avisa.

Uso: python scripts/fase2_homografias.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse
import itertools
from datetime import datetime

import cv2
import numpy as np
import yaml

from comun import RAIZ, leer_rutas, leer_yaml, pares_utilizables

NOMBRES = ["inicio", "mitad", "final"]


def ajustar(puntos, umbral):
    a = np.array(puntos, dtype=np.float64)
    H, mascara = cv2.findHomography(a[:, :2], a[:, 2:], cv2.RANSAC, umbral)
    if H is None:
        return None
    error = np.linalg.norm(cv2.perspectiveTransform(a[:, None, :2], H)[:, 0] - a[:, 2:], axis=1)
    return {"H": H, "inliers": int(mascara.sum()), "n": len(a), "error": error, "mascara": mascara.ravel().astype(bool)}


def error_cruzado(H, puntos):
    """Error (px térmicos) de la homografía H sobre puntos marcados en otro fotograma."""
    b = np.array(puntos, dtype=np.float64)
    return np.linalg.norm(cv2.perspectiveTransform(b[:, None, :2], H)[:, 0] - b[:, 2:], axis=1)


def diferencia_rejilla(Ha, Hb, puntos, n):
    """Desplazamiento (px térmicos) de una rejilla llevada a la RGB con Ha y de vuelta con Hb, dentro del rectángulo
    que cubren los puntos térmicos marcados."""
    t = np.array(puntos, dtype=np.float64)[:, 2:]
    xs, ys = np.meshgrid(np.linspace(t[:, 0].min(), t[:, 0].max(), n), np.linspace(t[:, 1].min(), t[:, 1].max(), n))
    g = np.stack([xs.ravel(), ys.ravel()], axis=1)
    vuelta = cv2.perspectiveTransform(cv2.perspectiveTransform(g[:, None], np.linalg.inv(Ha)), Hb)[:, 0]
    d = np.linalg.norm(vuelta - g, axis=1)
    return float(d.mean()), float(d.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    hc, minimo = cfg["homografias"], cfg["marcado"]["puntos_minimos"]
    rutas = leer_rutas(args.rutas)
    tam_termica = tuple(cfg["tam_termica"])

    vuelos = pares_utilizables(rutas["data"] / cfg["pares"]).vuelo.unique()
    salida = RAIZ / hc["salida"]
    homografias = yaml.safe_load(salida.read_text(encoding="utf-8")) if salida.exists() else {}

    for vuelo in vuelos:
        archivo = RAIZ / cfg["marcado"]["carpeta_puntos"] / f"{vuelo}.yaml"
        if not archivo.exists():
            print(f"\n{vuelo}: sin puntos")
            continue
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        tam_rgb = tuple(datos["tam_rgb"])
        print(f"\n{vuelo} (RGB {tam_rgb[0]}x{tam_rgb[1]})")
        por_fotograma, completo = {}, True
        for n in NOMBRES:
            f = datos["fotogramas"][n]
            if len(f["puntos"]) < minimo:
                print(f"  {n:6s} pos {f['posicion']:4d}: {len(f['puntos'])} puntos (mínimo {minimo}) -> incompleto")
                completo = False
                continue
            r = ajustar(f["puntos"], hc["umbral_ransac_px"])
            por_fotograma[n] = r
            e = r["error"][r["mascara"]]
            print(f"  {n:6s} pos {f['posicion']:4d}: {r['n']} puntos, {r['inliers']} inliers, "
                  f"error medio {e.mean():.2f} px, máximo {e.max():.2f} px")
        if not completo:
            continue

        variacion = 0.0
        for a, b in itertools.permutations(NOMBRES, 2):
            pa, pb = datos["fotogramas"][a]["puntos"], datos["fotogramas"][b]["puntos"]
            e = error_cruzado(por_fotograma[a]["H"], pb)
            media, maximo = diferencia_rejilla(por_fotograma[a]["H"], por_fotograma[b]["H"], pa + pb, hc["rejilla"])
            variacion = max(variacion, float(e.mean()))
            print(f"  H de {a:6s} sobre los puntos de {b:6s}: error medio {e.mean():.2f} px, máximo {e.max():.2f} px"
                  f" | rejilla: media {media:.2f} px, máxima {maximo:.2f} px")

        if variacion > hc["umbral_variacion_px"]:
            print(f"  -> LAS HOMOGRAFÍAS CAMBIAN MÁS DE {hc['umbral_variacion_px']} px: no se guarda (revisar a mano)")
            homografias.pop(vuelo, None)
            continue
        todos = [q for n in NOMBRES for q in datos["fotogramas"][n]["puntos"]]
        r = ajustar(todos, hc["umbral_ransac_px"])
        e = r["error"][r["mascara"]]
        print(f"  -> una sola homografía: {r['n']} puntos, {r['inliers']} inliers, "
              f"error medio {e.mean():.2f} px, máximo {e.max():.2f} px")
        homografias[vuelo] = {
            "H_rgb_a_termica": [[float(v) for v in fila] for fila in r["H"]],
            "tam_rgb": list(tam_rgb), "tam_termica": list(tam_termica),
            "puntos": r["n"], "inliers": r["inliers"],
            "error_medio_px": round(float(e.mean()), 3), "error_max_px": round(float(e.max()), 3),
            "variacion_entre_fotogramas_px": round(variacion, 3),
            "posiciones": {n: datos["fotogramas"][n]["posicion"] for n in NOMBRES},
            "calculada": datetime.now().isoformat(timespec="seconds"),
        }

    salida.write_text("# Generado por scripts/fase2_homografias.py. H lleva píxeles RGB originales a píxeles térmicos.\n"
                      + yaml.safe_dump(homografias, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"\n{len(homografias)} vuelos con homografía en {salida}")


if __name__ == "__main__":
    main()
