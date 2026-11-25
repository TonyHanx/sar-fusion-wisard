"""Dropout de modalidad para la fusión temprana (fase 7, C2): pone en 0 los 3 canales de color de una imagen de 4.

Actúa al leer cada imagen (`load_image` del dataset de Ultralytics), antes de las transformaciones. Con mosaico, cada
una de las 4 imágenes del mosaico se decide por separado. Las imágenes leídas antes y guardadas en el búfer del mosaico
no se modifican: se pone en 0 una copia, y cada lectura vuelve a decidir.

- En el entrenamiento, cada imagen pierde la RGB con probabilidad p (`random.random()`, que Ultralytics siembra en cada
  proceso de lectura con la semilla de la corrida). Con p = 0 no se cambia el dataset ni se gasta ningún número al azar,
  así que la corrida es igual a la de Ultralytics sin dropout.
- En la evaluación con la RGB en 0 (`evaluar.py --rgb-cero`), p = 1: todas las imágenes, sin azar.

Uso:
  from modalidad import quitar_rgb
  ds = quitar_rgb(ds, p)    # ds: YOLODataset de 4 canales; devuelve el mismo objeto
"""
import random

from ultralytics.data.dataset import YOLODataset


class DatasetSinRGB(YOLODataset):
    """YOLODataset de 4 canales (R, G, B y térmica al leer) que pone la RGB en 0 con probabilidad `p_sin_rgb`."""
    p_sin_rgb = 0.0

    def load_image(self, i, rect_mode=True, resize_short=False):
        """Carga la imagen como Ultralytics y, con probabilidad `p_sin_rgb`, pone en 0 los 3 canales de color, así el
        modelo aprende a detectar solo con la térmica."""
        imagen, hw0, hw = super().load_image(i, rect_mode, resize_short)
        if self.p_sin_rgb >= 1 or (self.p_sin_rgb > 0 and random.random() < self.p_sin_rgb):
            imagen = imagen.copy()  # el original puede estar en el búfer del mosaico
            imagen[..., :3] = 0
        return imagen, hw0, hw


def quitar_rgb(dataset, p):
    """Convierte `dataset` (un YOLODataset de 4 canales recién creado) en DatasetSinRGB con probabilidad p."""
    if not 0 <= p <= 1:
        raise ValueError(f"p tiene que estar entre 0 y 1: {p}")
    if p == 0:
        return dataset
    if type(dataset) is not YOLODataset:
        raise TypeError(f"El dropout de modalidad espera un YOLODataset, no {type(dataset).__name__}")
    if dataset.channels != 4:
        raise ValueError(f"El dropout de modalidad pide 4 canales; el dataset tiene {dataset.channels}")
    dataset.__class__ = DatasetSinRGB
    dataset.p_sin_rgb = float(p)
    return dataset
