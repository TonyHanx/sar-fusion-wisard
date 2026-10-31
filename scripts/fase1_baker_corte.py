"""Fase 1: imágenes lado a lado (RGB y térmica, con sus cajas) del inicio del tramo excluido de Baker.

En la RGB se dibuja en amarillo la zona aproximada que ve la térmica, para distinguir personas fuera del encuadre
térmico de personas sin caja. Una imagen a la vez.

Uso: python scripts/fase1_baker_corte.py --config configs/fase1.yaml --rutas configs/rutas.yaml
"""
import argparse

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from comun import leer_cajas_yolo, leer_rutas, leer_yaml

ROJO, AMARILLO = (255, 0, 0), (255, 220, 0)


def panel(ruta, alto, fov=None):
    img = Image.open(ruta)
    img.draft("RGB", (img.width * alto // img.height, alto))  # decodifica la RGB grande ya reducida
    img = img.convert("RGB")
    img = img.resize((round(img.width * alto / img.height), alto))
    w, h = img.size
    d = ImageDraw.Draw(img)
    if fov:
        d.rectangle([fov["x"][0] * w, fov["y"][0] * h, fov["x"][1] * w, fov["y"][1] * h], outline=AMARILLO, width=2)
    cajas = leer_cajas_yolo(ruta.with_suffix(".txt"))
    for _, cx, cy, bw, bh in cajas:
        d.rectangle([(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h], outline=ROJO, width=2)
    return img, len(cajas)


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
    banda = 30

    for k in range(rev["desde"], rev["hasta"] + 1, rev["paso"]):
        p = pares.loc[k]
        rgb, n_rgb = panel(rutas["dataset"] / p.ruta_rgb, rev["alto_panel"], rev["fov_termica_en_rgb"])
        ter, n_ter = panel(rutas["dataset"] / p.ruta_termica, rev["alto_panel"])
        lienzo = Image.new("RGB", (rgb.width + 10 + ter.width, rev["alto_panel"] + banda), (255, 255, 255))
        lienzo.paste(rgb, (0, banda))
        lienzo.paste(ter, (rgb.width + 10, banda))
        d = ImageDraw.Draw(lienzo)
        excl = "EXCLUIDO" if p.excluido else "conservado"
        d.text((6, 5), f"pos {k} | RGB {n_rgb} cajas (amarillo: zona que ve la térmica)", fill=(0, 0, 0), font=fuente)
        d.text((rgb.width + 16, 5), f"térmica {n_ter} cajas | {excl}", fill=(0, 0, 0), font=fuente)
        destino = salida / f"baker_{k:05d}.jpg"
        lienzo.save(destino, quality=90)
        print(f"{destino.name}: RGB {n_rgb}, térmica {n_ter}, {excl}")


if __name__ == "__main__":
    main()
