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
VERDE = (0, 230, 0)


def leer_yaml(ruta):
    """Lee un archivo yaml y devuelve su contenido (diccionario o lista)."""
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def leer_rutas(ruta):
    """Lee configs/rutas.yaml y devuelve rutas absolutas."""
    return {k: (RAIZ / v if not Path(v).is_absolute() else Path(v)) for k, v in leer_yaml(ruta).items()}


def ruta_del_dataset(datos):
    """Carpeta raíz de un dataset de Ultralytics (la clave `path` de su yaml), como ruta absoluta.

    Los yaml guardan `path` relativo a la raíz del repositorio, para que no dependan de la laptop."""
    p = Path(datos["path"])
    return p if p.is_absolute() else RAIZ / p


def ruta_para_yaml(carpeta):
    """La clave `path` que se escribe en el yaml de un dataset: relativa a la raíz del repositorio si la carpeta está
    dentro (data/ por omisión), o absoluta si `data` de configs/rutas.yaml apunta fuera. Es la inversa de
    ruta_del_dataset."""
    p = Path(carpeta).resolve()
    return (p.relative_to(RAIZ) if p.is_relative_to(RAIZ) else p).as_posix()


def yaml_para_ultralytics(ruta_yaml, rutas):
    """Copia del yaml de un dataset con `path` absoluto (ruta_del_dataset), en runs/_datos/, para pasársela a
    Ultralytics. Devuelve la ruta de la copia.

    Ultralytics resuelve un `path` relativo contra la carpeta desde donde se lanza el comando (y, si no existe, contra
    su DATASETS_DIR), no contra la raíz del repositorio. Con la copia, el resultado no depende de esa carpeta ni de la
    máquina, y el yaml de git sigue sin rutas de ninguna máquina. La copia se reescribe en cada llamada."""
    ruta_yaml = Path(ruta_yaml).resolve()
    datos = leer_yaml(ruta_yaml)
    datos["path"] = ruta_del_dataset(datos).as_posix()
    origen = ruta_para_yaml(ruta_yaml)
    destino = Path(rutas["runs"]) / "_datos" / origen.replace(":", "").replace("/", "__")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(f"# Copia de {origen} con path absoluto (src/comun.py, yaml_para_ultralytics): no editar.\n"
                       + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino


def fijar_semilla(seed):
    """Fija la semilla de random, NumPy y PyTorch (CPU y GPU), para que lo aleatorio salga igual en cada corrida (seed=0
    en todo el proyecto)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def agregar_a_bitacora(ruta, fase, modelo, configuracion, resultado):
    """Agrega una fila a la bitácora (reports/bitacora.csv): fecha, fase, modelo, configuración y resultado. Si el
    archivo no existe, lo crea con el encabezado. La llaman todos los entrenamientos y evaluaciones al terminar."""
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


def homografia_franja(franja, tam_rgb, tam_termica):
    """Homografía inicial RGB -> térmica a partir de la franja normalizada de CLAUDE.md."""
    (x0, x1), (y0, y1) = franja["x"], franja["y"]
    (w, h), (tw, th) = tam_rgb, tam_termica
    return np.array([[tw / ((x1 - x0) * w), 0, -x0 / (x1 - x0) * tw],
                     [0, th / ((y1 - y0) * h), -y0 / (y1 - y0) * th],
                     [0, 0, 1]])


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


def apilar(filas, sep=8):
    """Pega las imágenes una debajo de otra, sobre fondo blanco y con `sep` px entre ellas. Arma las hojas de ejemplos
    de los reportes."""
    lienzo = Image.new("RGB", (max(f.width for f in filas), sum(f.height for f in filas) + sep * (len(filas) - 1)),
                       (255, 255, 255))
    y = 0
    for f in filas:
        lienzo.paste(f, (0, y))
        y += f.height + sep
    return lienzo
