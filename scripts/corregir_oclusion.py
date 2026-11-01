r"""Fase 3b: aplica a data/<oclusion.anotaciones> las correcciones de configs/<oclusion.correcciones> y arma la lista
de personas para ajustar la visible RGB.

1. Correcciones (decididas a ojo por el primer anotador): visible "no visible", visible = caja térmica de WiSARD,
   visible borrada, "no es persona" o completa centrada en la caja térmica de WiSARD (mismo tamaño; la completa RGB se
   mueve lo mismo). Usa las mismas funciones que la herramienta (la completa RGB vuelve a la
   semejanza si la RGB queda "no visible", λ recalculado). Aplicarlas de nuevo no cambia nada. Antes de escribir guarda
   una copia en data/<respaldos>/. Las demás filas (la persona 1 y las de la muestra sin corrección) no cambian.
2. Lista de ajuste (data/<oclusion.lista_ajuste>): personas de la muestra con visible RGB (dibujada o precargada),
   sin "no es persona" ni "fuera de cuadro", ordenadas de mayor a menor según la fracción del área de la visible RGB que
   queda fuera de la completa RGB. La herramienta la abre con --ajuste. Se arma una sola vez (si no existe); con
   --rehacer-lista se vuelve a armar con el estado actual.

Uso:
    .venv\Scripts\python.exe scripts\corregir_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import shutil
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from anotar_oclusion import (COLUMNAS, a_fila, area, centro, con_centro, desde_fila, interseccion, normalizar,
                             terminada, vacia)
from comun import RAIZ, leer_rutas, leer_yaml


def aplicar(r, p, c):
    """Aplica la corrección `c` al registro `r` de la persona `p` (fila de la lista de personas)."""
    for lado, clave in (("rgb", "rgb"), ("ter", "termica")):
        accion = c.get(clave)
        if accion is None:
            continue
        if accion == "no_visible":
            r[lado] = {"estado": "no_visible", "caja": None, "guardada": None}
        elif accion == "borrar":
            r[lado] = vacia()
        elif accion == "wisard" and lado == "ter":
            r[lado] = {"estado": "caja", "caja": [float(p.ter_x0), float(p.ter_y0), float(p.ter_x1), float(p.ter_y1)],
                       "guardada": None}
        else:
            raise SystemExit(f"{c['id']}: corrección desconocida {clave}: {accion}")
    if "no_es_persona" in c:
        r["no_es_persona"] = bool(c["no_es_persona"])
    if c.get("completa") is not None:
        if c["completa"] != "centrar_en_wisard" or r["completa"] is None:
            raise SystemExit(f"{c['id']}: corrección de la completa no aplicable ({c['completa']})")
        (xt, yt), (xr, yr) = centro(r["completa"]["ter"]), centro(r["completa"]["rgb"])
        cx, cy = (float(p.ter_x0) + float(p.ter_x1)) / 2, (float(p.ter_y0) + float(p.ter_y1)) / 2
        r["completa"] = {"ter": con_centro(r["completa"]["ter"], cx, cy),
                         "rgb": con_centro(r["completa"]["rgb"], cx + xr - xt, cy + yr - yt)}
    normalizar(r)
    return r


def fuera_de_completa(f):
    """Fracción del área de la visible RGB fuera de la completa RGB."""
    v = [f[f"rgb_{c}"] for c in ("x0", "y0", "x1", "y1")]
    comp = [f[f"completa_rgb_{c}"] for c in ("x0", "y0", "x1", "y1")]
    return 1 - interseccion(v, comp) / area(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--rehacer-lista", action="store_true", help="vuelve a armar la lista de ajuste aunque exista")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    o, data = cfg["oclusion"], rutas["data"]
    ruta = data / o["anotaciones"]
    correcciones = leer_yaml(RAIZ / o["correcciones"])["correcciones"]
    muestra = list(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).id)
    personas = pd.read_csv(data / o["personas"], dtype={"id": str}).set_index("id", drop=False)
    df = pd.read_csv(ruta, dtype={"id": str})
    filas = df.set_index("id", drop=False)

    nuevas = {}
    for c in correcciones:
        i = c["id"]
        if i not in filas.index:
            raise SystemExit(f"{i} no está en {ruta}")
        if i not in muestra or muestra.index(i) + 1 != c["n"]:
            raise SystemExit(f"{i}: no es la persona {c['n']} de la muestra")
        f = filas.loc[i]
        antes = a_fila(personas.loc[i], desde_fila(f), f.anotador)
        r = aplicar(desde_fila(f), personas.loc[i], c)
        if not terminada(r):
            raise SystemExit(f"{i}: queda sin terminar con la corrección")
        despues = a_fila(personas.loc[i], r, f.anotador)
        if despues != antes:
            despues["guardado"] = datetime.now().isoformat(timespec="seconds")
            nuevas[i] = despues
            cambios = [k for k in COLUMNAS if k != "guardado"
                       and not (pd.isna(antes.get(k)) and pd.isna(despues.get(k)))
                       and antes.get(k) != despues.get(k)]
            print(f"  {c['n']:2d} {i}: {', '.join(cambios)}")
        else:
            print(f"  {c['n']:2d} {i}: ya estaba corregida")

    if nuevas:
        respaldo = data / o["respaldos"] / f"{ruta.stem}_{datetime.now():%Y%m%d_%H%M%S}.csv"
        respaldo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, respaldo)
        salida = pd.DataFrame([nuevas.get(f["id"], f) for f in df.to_dict("records")], columns=COLUMNAS)
        tmp = ruta.with_name(ruta.name + ".tmp")
        salida.to_csv(tmp, index=False, encoding="utf-8")
        # las filas sin corrección quedan idénticas, texto por texto
        viejas = ruta.read_text(encoding="utf-8").splitlines()
        nuevas_lineas = tmp.read_text(encoding="utf-8").splitlines()
        distintas = [i for i, (a, b) in enumerate(zip(viejas, nuevas_lineas)) if a != b]
        ids_distintos = {df.id.iloc[k - 1] for k in distintas}
        if len(viejas) != len(nuevas_lineas) or not ids_distintos <= set(nuevas):
            tmp.unlink()
            raise SystemExit(f"Cambiarían filas sin corrección: {sorted(ids_distintos - set(nuevas))}")
        tmp.replace(ruta)
        print(f"{len(nuevas)} personas corregidas en {ruta} (respaldo: {respaldo})")
    else:
        print(f"Nada que corregir en {ruta}")

    # lista para ajustar la visible RGB (una sola vez, para que no cambie el orden con que se ajustó)
    if (data / o["lista_ajuste"]).exists() and not args.rehacer_lista:
        print(f"La lista de ajuste ya existe ({data / o['lista_ajuste']}); no se rehace")
        return
    df = pd.read_csv(ruta, dtype={"id": str})
    m = df[df.id.isin(set(muestra)) & (df.rgb_estado == "caja") & ~df.no_es_persona.astype(bool)
           & ~df.fuera_de_cuadro.astype(bool)].copy()
    m["n_muestra"] = [muestra.index(i) + 1 for i in m.id]
    m["fuera_de_completa"] = [round(fuera_de_completa(f), 4) for f in m.to_dict("records")]
    m = m.sort_values(["fuera_de_completa", "n_muestra"], ascending=[False, True])
    m.insert(0, "orden", range(1, len(m) + 1))
    lista = m[["orden", "id", "n_muestra", "posicion", "indice_caja", "fuera_de_completa", "lambda_rgb"]]
    lista.to_csv(data / o["lista_ajuste"], index=False, encoding="utf-8")
    print(f"Lista de ajuste: {len(lista)} personas con visible RGB -> {data / o['lista_ajuste']}")
    print(f"  fuera de la completa: máximo {lista.fuera_de_completa.max():.0%}, mediana "
          f"{lista.fuera_de_completa.median():.0%}, mínimo {lista.fuera_de_completa.min():.0%}; "
          f"con λ RGB = 0: {int((lista.lambda_rgb == 0).sum())}")


if __name__ == "__main__":
    main()
