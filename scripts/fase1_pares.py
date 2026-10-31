"""Fase 1: reconstruye los pares RGB-térmicos de WiSARDv1. Solo lee el dataset.

Reglas (CLAUDE.md):
  - Carpetas: la VIS con número N va con la IR con número N+1 del mismo fecha_sitio_dron. El número es el sufijo
    de 4 dígitos de la carpeta o, si no lo tiene (220109_Baker), el DJI_NNNN del primer archivo.
  - Fotogramas: por posición en orden natural, hasta la longitud mínima.
  - Un .txt vacío es 0 cajas; una imagen sin .txt no está anotada.

Uso: python scripts/fase1_pares.py --config configs/fase1.yaml --rutas configs/rutas.yaml
"""
import argparse
import re
import sys

import pandas as pd

from comun import leer_rutas, leer_yaml

COLUMNAS = ["vuelo", "sitio", "fecha", "posicion", "carpeta_rgb", "carpeta_termica", "ruta_rgb", "ruta_termica",
            "cajas_rgb", "cajas_termica", "anotado", "excluido", "motivo_exclusion"]


def clave_natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def leer_txt(ruta):
    """Devuelve (número de cajas, líneas mal formadas) o (None, 0) si no hay .txt."""
    if not ruta.exists():
        return None, 0
    n, malas = 0, 0
    for linea in ruta.read_text().splitlines():
        partes = linea.split()
        if not partes:
            continue
        n += 1
        if len(partes) != 5 or partes[0] != "0":
            malas += 1
    return n, malas


def inventario(dataset, extensiones):
    carpetas = {}
    for d in sorted(p for p in dataset.iterdir() if p.is_dir()):
        imagenes = sorted((f.name for f in d.iterdir() if f.suffix.lower() in extensiones), key=clave_natural)
        m = re.search(r"_(\d{4})$", d.name) or (re.match(r"DJI_(\d{4})", imagenes[0]) if imagenes else None)
        carpetas[d.name] = dict(
            imagenes=imagenes,
            modalidad="IR" if "_IR" in d.name else "VIS",
            numero=int(m.group(1)) if m else None,
            grupo="_".join(d.name.split("_")[:3]),  # fecha_sitio_dron
        )
    return carpetas


def parejas_de_carpetas(carpetas):
    parejas = []
    for c_vis, v in carpetas.items():
        if v["modalidad"] != "VIS" or v["numero"] is None:
            continue
        for c_ir, i in carpetas.items():
            if i["modalidad"] == "IR" and i["grupo"] == v["grupo"] and i["numero"] == v["numero"] + 1:
                parejas.append((c_vis, c_ir))
    return sorted(parejas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    dataset = rutas["dataset"]

    carpetas = inventario(dataset, set(cfg["extensiones_imagen"]))
    parejas = parejas_de_carpetas(carpetas)
    print(f"carpetas: {len(carpetas)} | parejas de carpetas: {len(parejas)}")

    filas, malas = [], 0
    for c_vis, c_ir in parejas:  # una pareja a la vez; solo se leen los .txt
        vis, ir = carpetas[c_vis]["imagenes"], carpetas[c_ir]["imagenes"]
        p = c_vis.split("_")
        vuelo, sitio, fecha = c_vis.replace("_VIS", ""), p[1], f"20{p[0][:2]}-{p[0][2:4]}-{p[0][4:6]}"
        for k in range(min(len(vis), len(ir))):
            n_rgb, m_rgb = leer_txt((dataset / c_vis / vis[k]).with_suffix(".txt"))
            n_ir, m_ir = leer_txt((dataset / c_ir / ir[k]).with_suffix(".txt"))
            malas += m_rgb + m_ir
            filas.append(dict(vuelo=vuelo, sitio=sitio, fecha=fecha, posicion=k, carpeta_rgb=c_vis,
                              carpeta_termica=c_ir, ruta_rgb=f"{c_vis}/{vis[k]}", ruta_termica=f"{c_ir}/{ir[k]}",
                              cajas_rgb=n_rgb, cajas_termica=n_ir,
                              anotado=n_rgb is not None and n_ir is not None))
        print(f"  {c_vis} ({len(vis)}) <-> {c_ir} ({len(ir)})")

    pares = pd.DataFrame(filas)
    pares[["cajas_rgb", "cajas_termica"]] = pares[["cajas_rgb", "cajas_termica"]].astype("Int64")
    pares["excluido"] = False
    pares["motivo_exclusion"] = ""
    for e in cfg["exclusiones"]:
        m = ((pares.carpeta_rgb == e["carpeta_rgb"]) & (pares.carpeta_termica == e["carpeta_termica"])
             & pares.posicion.between(e["desde"], e["hasta"]))
        pares.loc[m, ["excluido", "motivo_exclusion"]] = [True, e["motivo"]]
        print(f"exclusión {e['carpeta_rgb']} {e['desde']}-{e['hasta']}: {m.sum()} pares")

    destino = rutas["data"] / cfg["pares"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    pares[COLUMNAS].to_csv(destino, index=False, encoding="utf-8")

    usables = pares[pares.anotado & ~pares.excluido]
    solo_termica = usables[(usables.cajas_termica > 0) & (usables.cajas_rgb == 0)]
    tabla = (pares.groupby(["vuelo", "sitio", "carpeta_rgb", "carpeta_termica"])
             .agg(pares=("posicion", "size"), pares_anotados=("anotado", "sum"), pares_excluidos=("excluido", "sum"))
             .join(usables.groupby("vuelo").size().rename("pares_anotados_sin_excluidos"), on="vuelo")
             .join(solo_termica.groupby("vuelo").size().rename("pares_solo_termica"), on="vuelo")
             .fillna(0).astype({"pares_anotados_sin_excluidos": int, "pares_solo_termica": int})
             .reset_index())
    tabla = tabla[tabla.pares_anotados_sin_excluidos > 0]
    total = tabla.select_dtypes("number").sum()
    tabla = pd.concat([tabla, pd.DataFrame([{"vuelo": "TOTAL", **total}])], ignore_index=True)
    tabla.to_csv(rutas["reports"] / cfg["tabla_por_vuelo"], index=False, encoding="utf-8")

    print(f"\nlíneas de etiqueta mal formadas en los pares: {malas}")
    print(tabla.to_string(index=False))
    obtenido = dict(pares=len(pares), pares_anotados=int(pares.anotado.sum()),
                    pares_anotados_sin_excluidos=len(usables))
    print("\n            obtenido  esperado  diferencia")
    ok = True
    for k, esperado in cfg["esperado"].items():
        print(f"{k:>30}: {obtenido[k]:>6}  {esperado:>8}  {obtenido[k] - esperado:>+10}")
        ok &= obtenido[k] == esperado
    print(f"pares con persona solo en la térmica: {len(solo_termica)}")
    if not ok:
        print("LOS TOTALES NO COINCIDEN", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
