"""Utilidades compartidas: lectura de configuración, semilla y bitácora."""
import csv
import math
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS_BITACORA = ["fecha", "fase", "modelo", "configuracion", "resultado"]
ROJO, AMARILLO = (255, 0, 0), (255, 220, 0)


def leer_yaml(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def leer_rutas(ruta):
    """Lee configs/rutas.yaml y devuelve rutas absolutas."""
    return {k: (RAIZ / v if not Path(v).is_absolute() else Path(v)) for k, v in leer_yaml(ruta).items()}


def fijar_semilla(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def agregar_a_bitacora(ruta, fase, modelo, configuracion, resultado):
    ruta = Path(ruta)
    nueva = not ruta.exists()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nueva:
            w.writerow(COLUMNAS_BITACORA)
        w.writerow([datetime.now().isoformat(timespec="seconds"), fase, modelo, configuracion, resultado])


def leer_cajas_yolo(ruta_txt):
    """Devuelve lista de (clase, cx, cy, w, h). Un .txt vacío es 0 cajas."""
    cajas = []
    for linea in Path(ruta_txt).read_text().splitlines():
        partes = linea.split()
        if partes:
            cajas.append((int(partes[0]), *map(float, partes[1:5])))
    return cajas


def pares_anotados(ruta_csv):
    """Pares de data/pares.csv con las dos imágenes anotadas, incluidos los excluidos (columna `excluido`)."""
    pares = pd.read_csv(ruta_csv, dtype={"cajas_rgb": "Int64", "cajas_termica": "Int64"})
    return pares[pares.anotado].reset_index(drop=True)


def pares_utilizables(ruta_csv):
    """Pares anotados y no excluidos de data/pares.csv."""
    pares = pares_anotados(ruta_csv)
    return pares[~pares.excluido].reset_index(drop=True)


def fotogramas_clave(posiciones):
    """Posiciones de inicio, mitad y final de una lista de posiciones."""
    posiciones = sorted(posiciones)
    return {"inicio": posiciones[0], "mitad": posiciones[len(posiciones) // 2], "final": posiciones[-1]}


def panel(ruta, alto, fov=None):
    """Imagen reducida a `alto` px con sus cajas en rojo y, opcionalmente, un rectángulo amarillo normalizado."""
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


def panel_franja(ruta, franja, tam):
    """RGB recortada a la franja normalizada que ve la térmica y llevada a `tam` (ancho, alto), con sus cajas en rojo.
    Sirve para comparar a simple vista con la térmica: si el zoom o la alineación cambian, deja de coincidir."""
    (x0, x1), (y0, y1) = franja["x"], franja["y"]
    W, H = tam
    img = Image.open(ruta)
    img.draft("RGB", (math.ceil(W / (x1 - x0)), math.ceil(H / (y1 - y0))))  # decodifica ya reducida, sin bajar de tam
    img = img.convert("RGB")
    w, h = img.size
    img = img.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))).resize((W, H))
    d = ImageDraw.Draw(img)
    cajas = leer_cajas_yolo(ruta.with_suffix(".txt"))
    for _, cx, cy, bw, bh in cajas:
        d.rectangle([(cx - bw / 2 - x0) / (x1 - x0) * W, (cy - bh / 2 - y0) / (y1 - y0) * H,
                     (cx + bw / 2 - x0) / (x1 - x0) * W, (cy + bh / 2 - y0) / (y1 - y0) * H], outline=ROJO, width=2)
    return img, len(cajas)


def lado_a_lado(paneles, rotulos, fuente, banda=30, separacion=10):
    """Pega los paneles en fila, con un rótulo encima de cada uno."""
    alto = max(p.height for p in paneles)
    lienzo = Image.new("RGB", (sum(p.width for p in paneles) + separacion * (len(paneles) - 1), alto + banda),
                       (255, 255, 255))
    d = ImageDraw.Draw(lienzo)
    x = 0
    for p, r in zip(paneles, rotulos):
        lienzo.paste(p, (x, banda))
        d.text((x + 6, 5), r, fill=(0, 0, 0), font=fuente)
        x += p.width + separacion
    return lienzo
