"""Fase 9: entrena una corrida de la segunda versión (configs/fase9.yaml) con el entrenamiento de la fase 7 y aplica R1.

El entrenamiento, las comprobaciones previas (prueba fuera, carpeta nueva, aplicaciones, potencia), el monitor,
resumen.json y la fila de la bitácora son los de src/entrenamiento/entrenar_fase7.py, sin cambiarlo. La receta pide
`save_period: 1`, así que quedan los pesos de cada época (weights/epoch{N-1}.pt para la época N de results.csv).

R1 (reports/diagnostico_sobreajuste/informe.md): la época elegida es la de mayor media móvil centrada de
`seleccion.ventana` épocas de `seleccion.metrica` (mAP@0.5 de validación), solo entre las épocas con la ventana completa;
si hay empate, la primera. Sus pesos se copian a weights/elegida.pt, y la elección se agrega a resumen.json
(`r1`) y a la bitácora.

Uso:
  .venv\\Scripts\\python.exe -m src.entrenamiento.entrenar_fase9 --config configs\\fase9.yaml --rutas configs\\rutas.yaml --corrida control_fusion_base
  .venv\\Scripts\\python.exe -m src.entrenamiento.entrenar_fase9 --config configs\\fase9.yaml --rutas configs\\rutas.yaml --corrida r2_fusion_base --semilla 1
  .venv\\Scripts\\python.exe -m src.entrenamiento.entrenar_fase9 --config configs\\fase9.yaml --rutas configs\\rutas.yaml --solo-r1 control_fusion_base

Con --semilla N (una de c3.semillas), la corrida usa seed = N y va en runs/fase9/<corrida>_sN/.
"""
import argparse
import copy
import json
import shutil
from pathlib import Path

import pandas as pd

import src.entrenamiento.entrenar_fase7 as fase7
from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml


def elegir_epoca(resultados, metrica, ventana):
    """Época (como en results.csv, desde 1) de mayor media móvil centrada, con la ventana completa, y la tabla."""
    suave = resultados[metrica].rolling(ventana, center=True, min_periods=ventana).mean()
    if suave.isna().all():
        raise SystemExit(f"R1: hacen falta al menos {ventana} épocas")
    i = int(suave.idxmax())  # la primera, si hay empate
    return int(resultados.loc[i, "epoch"]), float(suave[i]), suave


def aplicar_r1(cfg, rutas, nombre):
    """Elige la época por R1, copia sus pesos a weights/elegida.pt y lo agrega a resumen.json y a la bitácora."""
    sel = cfg["seleccion"]
    carpeta = rutas["runs"] / cfg["c3"]["carpeta"] / nombre
    resultados = pd.read_csv(carpeta / "results.csv")
    resultados.columns = [c.strip() for c in resultados.columns]
    epoca, valor_suave, _ = elegir_epoca(resultados, sel["metrica"], sel["ventana"])
    origen = carpeta / "weights" / f"epoch{epoca - 1}.pt"
    if not origen.exists():
        raise SystemExit(f"R1: no están los pesos de la época {epoca} ({origen})")
    shutil.copy2(origen, carpeta / "weights" / "elegida.pt")
    fila = resultados.loc[resultados["epoch"] == epoca].iloc[0]
    r1 = {"criterio": f"media móvil centrada de {sel['ventana']} épocas de {sel['metrica']}", "epoca": epoca,
          "media_movil": valor_suave, "pesos": f"weights/epoch{epoca - 1}.pt -> weights/elegida.pt",
          **{k: float(fila[k]) for k in fase7.CLAVES}}
    ruta_resumen = carpeta / "resumen.json"
    resumen = json.loads(ruta_resumen.read_text(encoding="utf-8"))
    resumen["r1"] = r1
    ruta_resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    texto = (f"R1: época {epoca} (media móvil de {sel['ventana']} del mAP50 {valor_suave:.4f}); en esa época mAP50 "
             f"{fila['metrics/mAP50(B)']:.4f}, mAP50-95 {fila['metrics/mAP50-95(B)']:.4f}, "
             f"P {fila['metrics/precision(B)']:.3f}, R {fila['metrics/recall(B)']:.3f}; weights/elegida.pt")
    corrida_cfg = cfg["c3"]["corridas"][nombre]
    agregar_a_bitacora(rutas["bitacora"], cfg["c3"]["base"]["fase"], f"YOLO26s {nombre} (R1)",
                       f"elección de época R1; {carpeta.relative_to(RAIZ).as_posix()}; datos {corrida_cfg['datos']}", texto)
    print(texto)


def main():
    """Entrena la corrida pedida y aplica R1 (--corrida), o solo R1 sobre una corrida terminada (--solo-r1)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--corrida")
    g.add_argument("--solo-r1", metavar="CORRIDA")
    ap.add_argument("--semilla", type=int, help="semilla de c3.semillas; la corrida va en <corrida>_s<semilla>")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.semilla is not None:
        if args.semilla not in cfg["c3"]["semillas"]:
            raise SystemExit(f"La semilla {args.semilla} no está en c3.semillas ({cfg['c3']['semillas']})")
        base = args.corrida or args.solo_r1
        if base not in cfg["c3"]["corridas"]:
            raise SystemExit(f"No existe la corrida {base}")
        entrada = copy.deepcopy(cfg["c3"]["corridas"][base])
        entrada.setdefault("ultralytics", {})["seed"] = args.semilla
        nombre = f"{base}_s{args.semilla}"
        cfg["c3"]["corridas"][nombre] = entrada
        if args.corrida:
            args.corrida = nombre
        else:
            args.solo_r1 = nombre
    if args.corrida:
        if cfg["c3"]["base"]["ultralytics"].get("save_period") != 1:
            raise SystemExit("R1 pide save_period: 1 en c3.base.ultralytics")
        fase7.entrenar(cfg, rutas, args.corrida)
        aplicar_r1(cfg, rutas, args.corrida)
    else:
        aplicar_r1(cfg, rutas, args.solo_r1)


if __name__ == "__main__":
    main()
