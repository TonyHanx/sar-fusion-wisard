"""Fase 9: tiempo por imagen en inferencia a cada tamaño de entrada (sección `tiempo_inferencia` de configs/fase9.yaml).

Usa el validador de Ultralytics con lote 1 sobre la validación (las mismas imágenes de 4 canales y la misma lectura que
en el entrenamiento), en fp32 y fp16, y guarda los ms por imagen de preprocesado, inferencia y posprocesado que reporta
Ultralytics. Cada combinación se pasa `repeticiones` veces y se guarda la última (la primera calienta la GPU). Correr
con la GPU libre. No usa la prueba.

Uso: .venv\\Scripts\\python.exe -m src.evaluacion.fase9_tiempo_inferencia --config configs\\fase9.yaml --rutas configs\\rutas.yaml
"""
import argparse
import tempfile

import pandas as pd
from ultralytics import YOLO

from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, yaml_para_ultralytics
from src.entorno.entorno import nvidia_smi


def main():
    """Mide y escribe el csv de `tiempo_inferencia.salida` y una fila de la bitácora."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    ti = cfg["tiempo_inferencia"]
    pesos = rutas["runs"] / cfg["c3"]["carpeta"] / ti["corrida"] / ti["pesos"]
    datos = str(yaml_para_ultralytics(RAIZ / ti["datos"], rutas))
    gpu = nvidia_smi("name")[0]
    filas = []
    with tempfile.TemporaryDirectory() as tmp:
        for imgsz in ti["tamanos"]:
            for precision in ti["precisiones"]:
                for rep in range(ti["repeticiones"]):
                    modelo = YOLO(str(pesos))
                    m = modelo.val(data=datos, split="val", imgsz=imgsz, half=precision == "fp16", project=tmp,
                                   name=f"{imgsz}_{precision}_{rep}", verbose=False, **ti["prediccion"])
                v = m.speed
                filas.append({"gpu": gpu, "imgsz": imgsz, "precision": precision, "lote": ti["prediccion"]["batch"],
                              "preproceso_ms": v["preprocess"], "inferencia_ms": v["inference"],
                              "posproceso_ms": v["postprocess"],
                              "total_ms": v["preprocess"] + v["inference"] + v["postprocess"]})
                print(filas[-1], flush=True)
    df = pd.DataFrame(filas)
    base = df[df["imgsz"] == min(ti["tamanos"])].set_index("precision")["inferencia_ms"]
    df["razon_inferencia_vs_menor"] = [r.inferencia_ms / base[r.precision] for r in df.itertuples()]
    salida = RAIZ / ti["salida"]
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(salida, index=False, float_format="%.3f")
    print(df.to_string(index=False))
    texto = "; ".join(f"{r.imgsz} px {r.precision}: inferencia {r.inferencia_ms:.2f} ms/imagen (total {r.total_ms:.2f})"
                      for r in df.itertuples())
    agregar_a_bitacora(rutas["bitacora"], cfg["c3"]["base"]["fase"], "YOLO26s fusión, tiempo de inferencia",
                       f"{gpu}; lote 1; validación (442 imágenes, 4 canales); pesos {ti['corrida']}/{ti['pesos']}",
                       texto)


if __name__ == "__main__":
    main()
