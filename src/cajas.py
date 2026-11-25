"""Geometría de las cajas de personas: leerlas en píxeles, llevarlas de la RGB a la térmica y sus centros.

Las usan la alineación (fase 2), la partición, la anotación de oclusión y la fase 7. Estaban en el script de la
semejanza por vuelo (src/alineacion/semejanza_por_vuelo.py, antes scripts/fase2_homografias_cajas.py) y se movieron
aquí sin cambiar su código.
"""
import cv2
import numpy as np

from src.comun import leer_cajas_yolo


def llevar(H, puntos):
    """Lleva puntos (x, y) con la transformación H de 3 x 3 (de la RGB a la térmica, o al revés)."""
    return cv2.perspectiveTransform(np.asarray(puntos, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


def cajas_px_sin_repetidas(ruta_txt, tam):
    """Cajas (x0, y0, x1, y1) en píxeles, sin repetidas.

    Quita las líneas repetidas y las ordena, así que el índice de una caja no es el de su línea en el .txt. Cuando el
    índice tiene que identificar a la persona, se usa oclusion_auto.cajas_px_en_orden."""
    w, h = tam
    unicas = sorted(set(leer_cajas_yolo(ruta_txt)))
    return np.array([[(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]
                     for _, cx, cy, bw, bh in unicas], dtype=np.float64).reshape(-1, 4)


def centros(cajas):
    """Centro (x, y) de cada caja (x0, y0, x1, y1)."""
    return np.column_stack([(cajas[:, 0] + cajas[:, 2]) / 2, (cajas[:, 1] + cajas[:, 3]) / 2])


def cajas_llevadas(H, cajas):
    """Rectángulo que encierra cada caja RGB llevada a la térmica."""
    esquinas = llevar(H, cajas[:, [0, 1, 2, 1, 2, 3, 0, 3]].reshape(-1, 2)).reshape(-1, 4, 2)
    return np.column_stack([esquinas[..., 0].min(1), esquinas[..., 1].min(1),
                            esquinas[..., 0].max(1), esquinas[..., 1].max(1)])


def dentro(cajas, tam_ter, margen):
    """Cajas (en px térmicos) que no tocan el borde de la térmica."""
    tw, th = tam_ter
    return (cajas[:, 0] >= margen) & (cajas[:, 1] >= margen) & (cajas[:, 2] <= tw - margen) & (cajas[:, 3] <= th - margen)
