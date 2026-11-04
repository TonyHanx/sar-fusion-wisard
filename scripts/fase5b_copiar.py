"""Fase 5b: copia los archivos de una corrida a reports/<resumen_5b.carpeta>/<corrida>/, para git.

Copia los de `resumen_5b.archivos_corrida` (configs/fase5.yaml) desde runs/<base.carpeta>/<corrida>/ y escribe
bitacora_<corrida>.csv con la cabecera y la última fila de la bitácora de esa corrida. No copia pesos ni imágenes.
Sale con 1 si falta resumen.json (la corrida no terminó) o no hay fila en la bitácora.

Uso: python scripts/fase5b_copiar.py --config configs/fase5.yaml --rutas configs/rutas.yaml --corrida rgb_100ep
"""
import argparse
import csv
import shutil
import sys

from comun import leer_rutas, leer_yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--corrida", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    r5 = cfg["resumen_5b"]
    origen = rutas["runs"] / cfg["base"]["carpeta"] / args.corrida
    destino = rutas["reports"] / r5["carpeta"] / args.corrida
    if not (origen / "resumen.json").exists():
        sys.exit(f"No hay {origen / 'resumen.json'}: la corrida no terminó.")
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in r5["archivos_corrida"]:
        if (origen / nombre).exists():
            shutil.copy2(origen / nombre, destino / nombre)
            print(f"copiado {nombre}")
        else:
            print(f"falta {nombre}", file=sys.stderr)

    with open(rutas["bitacora"], newline="", encoding="utf-8") as f:
        filas = list(csv.reader(f))
    propias = [r for r in filas[1:] if f"corrida {args.corrida};" in r[3]]
    if not propias:
        sys.exit(f"No hay fila de {args.corrida} en la bitácora.")
    with open(destino / f"bitacora_{args.corrida}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(filas[0])
        w.writerow(propias[-1])
    print(f"Archivos en {destino}")


if __name__ == "__main__":
    main()
