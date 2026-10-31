"""Fase 0: carga yolo26s.pt y predice sobre una imagen térmica de WiSARD.

Uso: python scripts/fase0_prueba_prediccion.py --config configs/fase0.yaml --rutas configs/rutas.yaml
"""
import argparse
import time

import cv2
import torch
from ultralytics import YOLO

from comun import RAIZ, agregar_a_bitacora, fijar_semilla, leer_cajas_yolo, leer_rutas, leer_yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()

    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    fijar_semilla(cfg["seed"])

    imagen = rutas["dataset"] / cfg["imagen"]
    salida = rutas["runs"] / cfg["salida"]
    salida.mkdir(parents=True, exist_ok=True)

    modelo = YOLO(str(RAIZ / cfg["pesos"]))
    pred = dict(device=cfg["dispositivo"], imgsz=cfg["imgsz"], conf=cfg["conf"], classes=cfg["clases"], verbose=False)
    modelo.predict(str(imagen), **pred)  # calentamiento
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    r = modelo.predict(str(imagen), **pred)[0]
    torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) * 1000

    h, w = r.orig_shape
    referencia = leer_cajas_yolo(imagen.with_suffix(".txt"))
    print(f"imagen: {imagen} ({w}x{h})")
    print(f"dispositivo: {r.boxes.data.device}  ({torch.cuda.get_device_name(0)})")
    print(f"tiempo de predicción: {ms:.1f} ms")
    print(f"cajas de referencia: {len(referencia)}")
    print(f"detecciones de persona (conf >= {cfg['conf']}): {len(r.boxes)}")
    for (x1, y1, x2, y2), c in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist()):
        print(f"  conf {c:.3f}  caja [{x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f}]")

    # Superposición: predicciones (de Ultralytics) + referencia en verde.
    lienzo = r.plot()
    for _, cx, cy, bw, bh in referencia:
        p1 = (round((cx - bw / 2) * w), round((cy - bh / 2) * h))
        p2 = (round((cx + bw / 2) * w), round((cy + bh / 2) * h))
        cv2.rectangle(lienzo, p1, p2, (0, 255, 0), 1)
    destino = salida / f"{imagen.stem}_prediccion.jpg"
    cv2.imwrite(str(destino), lienzo)
    print(f"superposición guardada en: {destino}")

    agregar_a_bitacora(
        rutas["bitacora"], fase=0, modelo=cfg["pesos"],
        configuracion=f"prueba de predicción; {cfg['imagen']}; imgsz={cfg['imgsz']}; conf={cfg['conf']}",
        resultado=f"{len(r.boxes)} detecciones de persona, {len(referencia)} de referencia; {ms:.1f} ms en GPU",
    )


if __name__ == "__main__":
    main()
