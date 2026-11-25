"""Fase 7, antes de fusion_base: de qué vuelo viene cada imagen de los datasets ampliados, comprobado con los archivos.

No decide con composicion.csv ni con los nombres de los archivos (sección `origen` de configs/fase7.yaml):
  1. Enlace duro: el identificador de archivo (os.stat) de cada imagen de los datasets se busca entre los de
     data/alineados/{termica,fusion}/ (la base de la fase 2) y data/<c1.salida>/{termica,fusion}/ (las nuevas de C1).
     De ahí salen la parte (base o nueva) y la carpeta a la que enlaza. Solo se miran metadatos, no píxeles.
  2. Contenido: hash de los píxeles de la térmica de cada imagen (el PNG en gris o la cuarta muestra del TIFF) contra
     el de todas las térmicas originales del dataset WiSARD, pasadas a gris como en la fase 2 y en C1 (cv2, BGR a gris).
     Las carpetas `prohibidas` (FHL 0405/0406) no se leen.
  3. Fusión: la térmica de cada TIFF es igual al PNG del mismo nombre del dataset térmico, y las nuevas sin pareja real
     tienen la RGB en 0.
Escribe en runs/<carpeta>/<origen.carpeta>/ las tablas origen_por_vuelo.csv y origen_comprobaciones.csv, y el detalle por
imagen en origen/origen_imagenes.csv. Solo lee el dataset original y data/.

Uso:
  .venv\\Scripts\\python.exe -m src.ampliacion.origen_imagenes --config configs\\fase7.yaml --rutas configs\\rutas.yaml
"""
# Solo importaciones livianas arriba: en Windows cada proceso hijo vuelve a importar este módulo (comun importa torch).
import argparse
import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import tifffile


def huella(a):
    """Huella de una imagen por su contenido (forma, tipo y hash de los píxeles), para encontrar de qué térmica original
    viene."""
    a = np.ascontiguousarray(a)
    return f"{a.shape}:{a.dtype}:" + hashlib.blake2b(a.tobytes(), digest_size=16).hexdigest()


def original(ruta):
    """Térmica original en gris, como src/alineacion/alinear.py y la parte construir de C1."""
    im = cv2.imread(ruta, cv2.IMREAD_COLOR)
    return ruta, (huella(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)) if im is not None else None)


def imagen(ruta):
    """Imagen de un dataset: (ruta, huella de la térmica, máximo de la RGB o None)."""
    if ruta.lower().endswith((".tif", ".tiff")):
        a = tifffile.imread(ruta)  # muestras del archivo: B, G, R, térmica
        if a.ndim != 3 or a.shape[2] != 4:
            raise RuntimeError(f"{ruta}: forma {a.shape}, se esperaban 4 muestras")
        return ruta, huella(a[..., 3]), int(a[..., :3].max())
    g = cv2.imread(ruta, cv2.IMREAD_UNCHANGED)
    if g is None or g.ndim != 2:
        raise RuntimeError(f"{ruta}: no es una imagen en gris")
    return ruta, huella(g), None


def ident(p):
    """Identificador del archivo en el disco (dispositivo e i-nodo). Dos enlaces duros al mismo archivo tienen el mismo.
    """
    s = os.stat(p)
    return s.st_dev, s.st_ino


def md(df):
    """Tabla de pandas como tabla de Markdown."""
    cols = list(df.columns)
    filas = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    filas += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(filas)


def main():
    """Comprueba de qué vuelo viene cada imagen de los datasets ampliados, por enlace duro y por contenido, y escribe
    las tablas de origen."""
    from src.comun import leer_rutas, leer_yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    o = cfg["origen"]
    D, data = Path(rutas["dataset"]), Path(rutas["data"])
    salida = data / cfg["c1"]["salida"]
    destino = rutas["runs"] / cfg["carpeta"] / o["carpeta"]
    (destino / "origen").mkdir(parents=True, exist_ok=True)
    prohibidas = set(cfg["prohibidas"])
    ext = tuple(cfg["extensiones"])

    pares = pd.read_csv(data / cfg["pares"])
    vuelo_de = dict(zip(pares.carpeta_termica, pares.vuelo))  # carpeta IR -> vuelo; las sin pareja, ellas mismas
    vigilar = list(o["vigilar"])
    if set(vigilar) - set(pares.vuelo):
        raise SystemExit(f"Vuelos de `vigilar` que no están en pares.csv: {sorted(set(vigilar) - set(pares.vuelo))}")

    # 1. enlaces duros: identificador de archivo de las imágenes de origen (solo metadatos)
    origenes = {}
    for parte, raiz in (("base", data / "alineados"), ("nueva", salida)):
        for sub in ("termica", "fusion"):
            for f in (raiz / sub).glob("*/*"):
                if f.is_file():
                    origenes[ident(f)] = (parte, f.parent.name, f)
    filas = []
    for ds in o["datasets"]:
        for split in ("train", "val"):
            for f in sorted((salida / "datasets" / ds / "images" / split).iterdir()):
                parte, carpeta, fuente = origenes.get(ident(f), (None, None, None))
                filas.append({"dataset": ds, "split": split, "archivo": f.name, "ruta": str(f), "parte": parte,
                              "carpeta_enlace": carpeta, "enlace": str(fuente.relative_to(data)) if fuente else None})
    df = pd.DataFrame(filas)
    df["vuelo_enlace"] = [vuelo_de.get(c, c) if p == "nueva" else c for p, c in zip(df.parte, df.carpeta_enlace)]
    print(f"{len(df)} imágenes en {o['datasets']}; sin enlace conocido: {int(df.parte.isna().sum())}", flush=True)

    # 2. contenido: térmicas originales (sin las prohibidas) y térmica de cada imagen de los datasets
    carpetas_ir = sorted(c for c in D.iterdir() if c.is_dir() and "_IR" in c.name and c.name not in prohibidas)
    rutas_orig = [str(f) for c in carpetas_ir for f in sorted(c.iterdir()) if f.suffix.lower() in ext]
    with ProcessPoolExecutor(o["procesos"]) as ex:
        h_orig = list(ex.map(original, rutas_orig, chunksize=64))
        print(f"{len(h_orig)} térmicas originales leídas, de {len(carpetas_ir)} carpetas IR "
              f"(sin leer {sorted(prohibidas)})", flush=True)
        h_ds = list(ex.map(imagen, df.ruta.tolist(), chunksize=32))
    ilegibles = [r for r, h in h_orig if h is None]
    por_huella = {}
    for r, h in h_orig:
        if h is not None:
            por_huella.setdefault(h, []).append(Path(r))
    df["huella"] = [h for _, h, _ in h_ds]
    df["max_rgb"] = [m for _, _, m in h_ds]
    coinc = [por_huella.get(h, []) for h in df.huella]
    df["originales_iguales"] = [len(c) for c in coinc]
    df["carpetas_contenido"] = [";".join(sorted({p.parent.name for p in c})) for c in coinc]
    df["original"] = [";".join(sorted(f"{p.parent.name}/{p.name}" for p in c)) for c in coinc]
    df["vuelo_contenido"] = [";".join(sorted({vuelo_de.get(p.parent.name, p.parent.name) for p in c})) for c in coinc]

    # 3. fusión: la térmica del TIFF es la del PNG del mismo nombre; RGB en 0 en las nuevas sin pareja real
    ter = df[df.dataset == o["datasets"][0]].assign(stem=lambda x: x.archivo.map(lambda a: Path(a).stem))
    fus = df[df.dataset == o["datasets"][1]].assign(stem=lambda x: x.archivo.map(lambda a: Path(a).stem))
    cruce = fus.merge(ter[["split", "stem", "huella"]], on=["split", "stem"], how="left", suffixes=("", "_png"))
    aprob = {cfg["c1"]["pares_reales"]["candidatos"][v] for v in cfg["c1"]["pares_reales"]["aprobados"]}
    nuevas_fus = cruce[cruce.parte == "nueva"]
    nuevas_rgb_real = nuevas_fus.carpeta_enlace.isin(aprob)

    unico = df.vuelo_contenido.str.count(";") == 0
    comprob = [
        ("imágenes de los dos datasets", len(df), ""),
        ("con enlace a data/alineados o a las nuevas de C1", int(df.parte.notna().sum()), f"de {len(df)}"),
        ("con su térmica igual a una original", int((df.originales_iguales > 0).sum()), f"de {len(df)}"),
        ("con originales iguales en más de un vuelo", int((~unico & (df.originales_iguales > 0)).sum()), "tiene que ser 0"),
        ("vuelo por contenido distinto del vuelo del enlace", int((unico & (df.vuelo_contenido != df.vuelo_enlace)).sum()),
         "tiene que ser 0"),
        ("térmicas originales ilegibles", len(ilegibles), ""),
        ("TIFF con la térmica distinta del PNG del mismo nombre", int((cruce.huella != cruce.huella_png).sum()),
         f"de {len(cruce)}; tiene que ser 0"),
        ("TIFF nuevos sin pareja real con RGB distinta de 0", int((nuevas_fus.max_rgb[~nuevas_rgb_real] > 0).sum()),
         f"de {int((~nuevas_rgb_real).sum())}; tiene que ser 0"),
    ]
    for v in vigilar:
        for parte in ("nueva", "base"):
            for split in ("train", "val"):
                n = int(((df.parte == parte) & (df.split == split) &
                         ((df.vuelo_contenido == v) | (df.vuelo_enlace == v))).sum())
                comprob.append((f"{v}: imágenes {parte}s en {split} (los dos datasets)", n,
                                "tiene que ser 0" if parte == "nueva" else "de la partición por vuelo"))
    comprob = pd.DataFrame(comprob, columns=["comprobacion", "valor", "nota"])

    por_vuelo = (df.groupby(["dataset", "split", "parte", "vuelo_contenido", "carpetas_contenido"], dropna=False)
                 .size().rename("imagenes").reset_index())
    df.drop(columns=["ruta"]).to_csv(destino / "origen" / "origen_imagenes.csv", index=False)
    por_vuelo.to_csv(destino / "origen_por_vuelo.csv", index=False)
    comprob.to_csv(destino / "origen_comprobaciones.csv", index=False)
    print(md(comprob))
    print()
    print(md(por_vuelo))
    malas = comprob[comprob.nota.str.contains("tiene que ser 0") & (comprob.valor != 0)]
    if len(malas) or df.parte.isna().any() or (df.originales_iguales == 0).any():
        raise SystemExit("Hay comprobaciones que no se cumplen (arriba)")


if __name__ == "__main__":
    main()
