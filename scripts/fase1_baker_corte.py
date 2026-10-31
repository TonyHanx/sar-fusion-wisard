"""Fase 1: imágenes lado a lado (RGB y térmica, con sus cajas) del inicio del tramo excluido de Baker.

En la RGB se dibuja en amarillo la zona aproximada que ve la térmica, para distinguir personas fuera del encuadre
térmico de personas sin caja. Una imagen a la vez.

Uso: python scripts/fase1_baker_corte.py --config configs/fase1.yaml --rutas configs/rutas.yaml
"""
import argparse

import pandas as pd
from PIL import ImageFont

from comun import lado_a_lado, leer_rutas, leer_yaml, panel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rev = cfg["revision_baker"]
    rutas = leer_rutas(args.rutas)

    pares = pd.read_csv(rutas["data"] / cfg["pares"])
    pares = pares[(pares.vuelo == rev["vuelo"])].set_index("posicion")
    salida = rutas["reports"] / rev["salida"]
    salida.mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(rev["fuente"], 18)

    for k in range(rev["desde"], rev["hasta"] + 1, rev["paso"]):
        p = pares.loc[k]
        rgb, n_rgb = panel(rutas["dataset"] / p.ruta_rgb, rev["alto_panel"], rev["fov_termica_en_rgb"])
        ter, n_ter = panel(rutas["dataset"] / p.ruta_termica, rev["alto_panel"])
        excl = "EXCLUIDO" if p.excluido else "conservado"
        lienzo = lado_a_lado([rgb, ter], [f"pos {k} | RGB {n_rgb} cajas (amarillo: zona que ve la térmica)",
                                          f"térmica {n_ter} cajas | {excl}"], fuente)
        destino = salida / f"baker_{k:05d}.jpg"
        lienzo.save(destino, quality=90)
        print(f"{destino.name}: RGB {n_rgb}, térmica {n_ter}, {excl}")


if __name__ == "__main__":
    main()
