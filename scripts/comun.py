"""Utilidades compartidas: lectura de configuración, semilla y bitácora."""
import csv
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import yaml

RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS_BITACORA = ["fecha", "fase", "modelo", "configuracion", "resultado"]


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
