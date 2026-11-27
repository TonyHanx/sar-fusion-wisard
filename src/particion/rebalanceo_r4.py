"""Fase 9, R4: datasets de Ultralytics con los vuelos de entrenamiento rebalanceados (sección `r4` de configs/fase9.yaml).

Para cada modelo (fusión, solo RGB y solo térmica) arma data/datasets/r4_<modelo>/ a partir del dataset base
(configs/<modelo>.yaml), solo con enlaces duros: no copia ni cambia ninguna imagen ni etiqueta, y no toca el dataset base
ni el WiSARD original.

- Entrenamiento:
  - del vuelo de `submuestrear.vuelo` (Baker) quedan solo los fotogramas cuya posición (el número del final del nombre)
    cumple `posicion % cada == resto`: con cada 2 y resto 0, las posiciones pares, sin azar;
  - cada fotograma del vuelo de `duplicar.vuelo` (FHL 0401) va `veces` veces: el original con su nombre y las copias
    como enlaces duros con el sufijo `<sufijo><k>` (k = 2, 3, ...), para que Ultralytics las cuente como imágenes
    distintas;
  - los demás vuelos, igual que en la base.
- Validación: la misma carpeta de la base (`val` del yaml apunta a ../<modelo base>/images/val), así que también usa
  las mismas etiquetas y la misma caché de etiquetas.
- No se escribe la prueba (`test`).

Escribe configs/r4_<modelo>.yaml y la tabla de pares y personas por vuelo, antes y después (`r4.tabla`). Si la carpeta
del dataset ya existe, se detiene: no la sobrescribe.

Uso: .venv\\Scripts\\python.exe -m src.particion.rebalanceo_r4 --config configs\\fase9.yaml --rutas configs\\rutas.yaml
"""
import argparse
import os
import re
from pathlib import Path

import pandas as pd
import yaml

from src.comun import RAIZ, leer_rutas, leer_yaml, ruta_del_dataset, ruta_para_yaml

PATRON = re.compile(r"^(?P<vuelo>.+)_(?P<pos>\d+)$")


def vuelo_y_posicion(stem):
    """Vuelo y posición de un nombre de imagen del dataset (<vuelo>_<posición>)."""
    m = PATRON.match(stem)
    if not m:
        raise SystemExit(f"Nombre de imagen inesperado: {stem}")
    return m["vuelo"], int(m["pos"])


def personas(etiqueta):
    """Cajas (líneas no vacías) de una etiqueta YOLO."""
    return sum(1 for linea in Path(etiqueta).read_text().splitlines() if linea.strip())


def armar(modelo, origen_yaml, r4, rutas):
    """Arma el dataset R4 de `modelo` y devuelve la tabla de pares y personas por vuelo, antes y después."""
    base = leer_yaml(RAIZ / origen_yaml)
    raiz_base = ruta_del_dataset(base)
    destino = Path(rutas["data"]) / r4["destino"] / f"{r4['prefijo']}{modelo}"
    if destino.exists():
        raise SystemExit(f"Ya existe {destino}: no se sobrescribe. Muévelo antes si hay que rearmarlo.")
    img_base, lbl_base = raiz_base / base["train"], raiz_base / base["train"].replace("images", "labels", 1)
    img_dst, lbl_dst = destino / "images" / "train", destino / "labels" / "train"
    img_dst.mkdir(parents=True)
    lbl_dst.mkdir(parents=True)
    sub, dup = r4["submuestrear"], r4["duplicar"]
    filas = []
    for imagen in sorted(img_base.iterdir()):
        vuelo, pos = vuelo_y_posicion(imagen.stem)
        etiqueta = lbl_base / f"{imagen.stem}.txt"
        if not etiqueta.exists():
            raise SystemExit(f"Falta la etiqueta {etiqueta}")
        n_personas = personas(etiqueta)
        if vuelo == sub["vuelo"] and pos % sub["cada"] != sub["resto"]:
            veces = 0
        elif vuelo == dup["vuelo"]:
            veces = dup["veces"]
        else:
            veces = 1
        for k in range(1, veces + 1):
            stem = imagen.stem if k == 1 else f"{imagen.stem}{dup['sufijo']}{k}"
            os.link(imagen, img_dst / f"{stem}{imagen.suffix}")
            os.link(etiqueta, lbl_dst / f"{stem}.txt")
        filas.append({"modelo": modelo, "vuelo": vuelo, "veces": veces, "personas": n_personas})

    datos = {"path": ruta_para_yaml(destino), "train": "images/train",
             "val": f"../{raiz_base.name}/{base['val']}", "channels": base.get("channels", 3), "names": base["names"]}
    texto = (f"# Dataset de Ultralytics R4 del modelo '{modelo}' (fase 9, rebalanceo de vuelos). Generado por "
             f"src/particion/rebalanceo_r4.py con la sección r4 de configs/fase9.yaml: no editar a mano.\n"
             f"# Entrenamiento: el de {origen_yaml} con {sub['vuelo']} en las posiciones con posición % {sub['cada']} == "
             f"{sub['resto']} y {dup['vuelo']} {dup['veces']} veces (enlaces duros). Validación: la misma de "
             f"{origen_yaml}. Sin prueba.\n")
    ruta_yaml = RAIZ / r4["yaml"] / f"{r4['prefijo']}{modelo}.yaml"
    ruta_yaml.write_text(texto + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")

    df = pd.DataFrame(filas)
    df["personas_despues"] = df["personas"] * df["veces"]
    tabla = df.groupby(["modelo", "vuelo"]).agg(pares_antes=("veces", "size"), pares_despues=("veces", "sum"),
                                                personas_antes=("personas", "sum"),
                                                personas_despues=("personas_despues", "sum")).reset_index()
    n_img = sum(1 for _ in img_dst.iterdir())
    n_lbl = sum(1 for _ in lbl_dst.iterdir())
    if not (n_img == n_lbl == tabla["pares_despues"].sum()):
        raise SystemExit(f"{destino}: {n_img} imágenes y {n_lbl} etiquetas, se esperaban {tabla['pares_despues'].sum()}")
    print(f"{modelo}: {n_img} imágenes de entrenamiento en {destino}; {ruta_yaml.relative_to(RAIZ)}")
    return tabla


def main():
    """Arma los datasets R4 de los tres modelos y escribe la tabla por vuelo."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    r4 = leer_yaml(args.config)["r4"]
    rutas = leer_rutas(args.rutas)
    tablas = [armar(modelo, origen, r4, rutas) for modelo, origen in r4["origen"].items()]
    tabla = pd.concat(tablas, ignore_index=True)
    for modelo in tabla["modelo"].unique():  # los tres modelos tienen las mismas imágenes y etiquetas
        a = tabla[tabla["modelo"] == modelo].drop(columns="modelo").reset_index(drop=True)
        b = tablas[0].drop(columns="modelo").reset_index(drop=True)
        if not a.equals(b):
            raise SystemExit(f"La tabla de {modelo} no coincide con la de {tablas[0]['modelo'].iloc[0]}")
    t = tablas[0].drop(columns="modelo")
    total = t.drop(columns="vuelo").sum()
    t = pd.concat([t, pd.DataFrame([{"vuelo": "total", **total.to_dict()}])], ignore_index=True)
    for c in ("pares", "personas"):
        t[f"{c}_pct_queda"] = (100 * t[f"{c}_despues"] / t[f"{c}_antes"]).round(1)
    salida = RAIZ / r4["tabla"]
    salida.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(salida, index=False)
    print(t.to_string(index=False))
    print(f"Tabla en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
