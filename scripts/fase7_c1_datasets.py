"""Fase 7, parte C1: datasets termico_ampliado y fusion_ampliado (sección `c1` de configs/fase7.yaml).

Partes:
  - componer: elige las imágenes nuevas de entrenamiento y cuenta la composición, sin escribir imágenes:
      * las de C0 que quedan tras la clasificación (runs/<carpeta>/c0/clasificacion/fotogramas.csv);
      * los pares anotados y excluidos de los vuelos de entrenamiento, salvo `excluidos_entrenamiento.salvo`;
      * las vacías nuevas, con el tope de `vacias.fraccion_maxima` del total de entrenamiento, al azar (seed) y
        repartidas por carpeta en proporción a sus vacías.
    Escribe runs/<carpeta>/c1/composicion.csv (una fila por imagen candidata) y las tablas por sitio y por carpeta,
    con el tiempo estimado por época.

Uso:
  .venv\\Scripts\\python.exe scripts\\fase7_c1_datasets.py --config configs\\fase7.yaml --rutas configs\\rutas.yaml --parte componer
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from comun import RAIZ, leer_cajas_yolo, leer_rutas, leer_yaml


def ruta(p):
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def md(df, dec=1):
    cols = list(df.columns)
    filas = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        filas.append("| " + " | ".join(f"{v:.{dec}f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(filas)


def lados_txt(txt, tam):
    """Lado mayor (px de la térmica) de las cajas de un .txt, sin las líneas repetidas (como la fase 3a)."""
    tw, th = tam
    cajas = list(dict.fromkeys(leer_cajas_yolo(txt))) if Path(txt).exists() else []
    return [max(w * tw, h * th) for _, _, _, w, h in cajas]


def tramos(lados, bordes, etiquetas):
    cuenta = np.histogram(lados, bins=bordes)[0] if len(lados) else np.zeros(len(etiquetas), int)
    return {f"tramo {e}": int(c) for e, c in zip(etiquetas, cuenta)}


def sitio(nombre):
    return nombre.split("_")[1]


def cupos(disponibles, total):
    """Reparto proporcional con restos mayores: {carpeta: vacías disponibles} -> {carpeta: cupo}."""
    n = sum(disponibles.values())
    if n <= total:
        return dict(disponibles)
    exacto = {k: total * v / n for k, v in disponibles.items()}
    cupo = {k: int(np.floor(x)) for k, x in exacto.items()}
    resto = total - sum(cupo.values())
    for k in sorted(exacto, key=lambda k: (-(exacto[k] - cupo[k]), k))[:resto]:
        cupo[k] += 1
    return cupo


def componer(cfg, rutas, out):
    c = cfg["c1"]
    D = rutas["dataset"]
    tam = cfg["tam_termica"]
    bordes = [0] + cfg["tramos_px"] + [np.inf]
    etiquetas = [f"<{bordes[1]}"] + [f"{a}-{b}" for a, b in zip(bordes[1:-2], bordes[2:-1])] + [f">={bordes[-2]}"]
    part = leer_yaml(ruta(c["particion"]))
    pares = pd.read_csv(rutas["data"] / cfg["pares"])

    # base: el entrenamiento actual (mismas imágenes en termico y fusion)
    base = leer_yaml(ruta(c["base"]["termico"]))
    lab = Path(base["path"]) / "labels" / "train"
    img = sorted((Path(base["path"]) / base["train"]).iterdir())
    filas_base = []
    for f in img:
        lados = lados_txt(lab / f"{f.stem}.txt", tam)
        vuelo = f.stem.rsplit("_", 1)[0]
        filas_base.append({"stem": f.stem, "sitio": sitio(vuelo), "carpeta": vuelo, "cajas": len(lados), "lados": lados})
    base_df = pd.DataFrame(filas_base)

    # nuevas 1: las de C0 que quedan tras la clasificación
    f0 = pd.read_csv(out / "c0" / "clasificacion" / "fotogramas.csv")
    f0 = f0[f0.usar]
    n1 = pd.DataFrame({"fuente": "c0", "carpeta": f0.carpeta, "posicion": f0.posicion,
                       "ruta_termica": f0.carpeta + "/" + f0.archivo, "cajas": f0.cajas,
                       "lados": [[float(x) for x in str(l).split(";")] if isinstance(l, str) and l else []
                                 for l in f0.lados]})
    # nuevas 2: pares anotados y excluidos de los vuelos de entrenamiento
    g = pares[pares.vuelo.isin(part["entrenamiento"]) & pares.anotado & pares.excluido]
    for v, tr in c["excluidos_entrenamiento"]["salvo"].items():
        for a, b in tr:
            g = g[~((g.vuelo == v) & g.posicion.between(a, b))]
    lados2 = [lados_txt((D / r).with_suffix(".txt"), tam) for r in g.ruta_termica]
    n2 = pd.DataFrame({"fuente": "excluido de entrenamiento", "carpeta": g.carpeta_termica.to_numpy(),
                       "posicion": g.posicion.to_numpy(), "ruta_termica": g.ruta_termica.to_numpy(),
                       "cajas": [len(l) for l in lados2], "lados": lados2})
    nuevas = pd.concat([n1, n2], ignore_index=True)
    nuevas["sitio"] = nuevas.carpeta.map(sitio)
    nuevas["stem"] = nuevas.carpeta + "_" + nuevas.posicion.map("{:04d}".format)
    nuevas["persona"] = nuevas.cajas > 0

    # nada de validación ni de prueba, ni repetidas con la base
    otras = pares[pares.vuelo.isin(part["validacion"] + part["prueba"])]
    malas = set(nuevas.carpeta) & (set(otras.carpeta_termica) | set(cfg["prohibidas"]))
    if malas:
        raise SystemExit(f"Carpetas de validación o prueba entre las nuevas: {sorted(malas)}")
    if nuevas.stem.duplicated().any() or set(nuevas.stem) & set(base_df.stem):
        raise SystemExit("Nombres repetidos entre las nuevas o con la base")
    rutas_base = set(pares[pares.vuelo.isin(part["entrenamiento"]) & pares.anotado & ~pares.excluido].ruta_termica)
    if set(nuevas.ruta_termica) & rutas_base:
        raise SystemExit("Imágenes nuevas que ya están en la base")

    # pares reales aprobados (RGB real en la fusión)
    pr = c["pares_reales"]
    aprob = {pr["candidatos"][v] for v in pr["aprobados"]}
    nuevas["rgb_real"] = nuevas.carpeta.isin(aprob)
    nuevas["ruta_rgb"] = None
    if aprob:
        m = pares.set_index("ruta_termica").ruta_rgb
        sel = nuevas.rgb_real
        nuevas.loc[sel, "ruta_rgb"] = nuevas.loc[sel, "ruta_termica"].map(m)
        if nuevas.loc[sel, "ruta_rgb"].isna().any():
            raise SystemExit("Pares reales sin RGB en pares.csv")

    # tope de vacías nuevas: E <= f (N_base + P + E)  ->  E <= f / (1 - f) (N_base + P)
    fv = c["vacias"]["fraccion_maxima"]
    P = int(nuevas.persona.sum())
    e_max = int(np.floor(fv / (1 - fv) * (len(base_df) + P)))
    vac = nuevas[~nuevas.persona]
    cupo = cupos(vac.groupby("carpeta").size().to_dict(), e_max)
    nuevas["elegida"] = nuevas.persona
    for carpeta, k in cupo.items():
        idx = vac[vac.carpeta == carpeta].sort_values("posicion").index.to_numpy()
        rng = np.random.default_rng(c["vacias"]["seed"])
        nuevas.loc[rng.choice(idx, k, replace=False), "elegida"] = True
    nuevas["motivo"] = np.where(nuevas.elegida, "", "vacía fuera del cupo")

    destino = out / "c1"
    destino.mkdir(parents=True, exist_ok=True)
    guardar = nuevas.copy()
    guardar["lados"] = guardar.lados.map(lambda l: ";".join(f"{x:.2f}" for x in l))
    guardar[["stem", "fuente", "sitio", "carpeta", "posicion", "ruta_termica", "ruta_rgb", "rgb_real", "cajas",
             "persona", "elegida", "motivo", "lados"]].to_csv(destino / "composicion.csv", index=False)

    # tablas
    def resumen(df, clave):
        filas = []
        for k, g in df.groupby(clave, sort=True):
            lados = [x for l in g.lados for x in l]
            filas.append({clave: k, "imagenes": len(g), "con_persona": int((g.cajas > 0).sum()),
                          "vacias": int((g.cajas == 0).sum()), "personas": len(lados), **tramos(lados, bordes, etiquetas)})
        return pd.DataFrame(filas)

    el = nuevas[nuevas.elegida]
    por_carpeta = resumen(el, "carpeta").merge(
        nuevas[~nuevas.persona].groupby("carpeta").size().rename("vacias_disponibles").reset_index(), how="left")
    por_carpeta["vacias_disponibles"] = por_carpeta.vacias_disponibles.fillna(0).astype(int)
    s_base = resumen(base_df, "sitio")
    s_base.insert(0, "parte", "base")
    s_new = resumen(el, "sitio")
    s_new.insert(0, "parte", "nuevas")
    tot = []
    for nombre, df in (("base", base_df), ("nuevas", el), ("total", pd.concat([base_df, el], ignore_index=True))):
        r = resumen(df.assign(todo="todo"), "todo").drop(columns="todo")
        r.insert(0, "parte", nombre)
        tot.append(r)
    tot = pd.concat(tot, ignore_index=True)
    por_sitio = pd.concat([s_base, s_new], ignore_index=True)
    n_total = len(base_df) + len(el)

    # tiempo por época, con las medidas de epocas.csv
    t = []
    for modelo, corrida in c["tiempo"]["corridas"].items():
        e = pd.read_csv(ruta(corrida) / "epocas.csv")
        e = e[e.epoca > 1]
        s_img = e.s_entrenamiento.median() / len(base_df)
        s_val = e.s_validacion_y_guardado.median()
        s = s_img * n_total + s_val
        t.append({"modelo": modelo, "medido_en": Path(corrida).name, "ms_por_imagen": 1000 * s_img,
                  "s_validacion": s_val, "imagenes": n_total, "s_por_epoca": s,
                  f"h_{c['tiempo']['epocas']}_epocas": s * c["tiempo"]["epocas"] / 3600})
    t = pd.DataFrame(t)
    por_carpeta.to_csv(destino / "por_carpeta.csv", index=False)
    por_sitio.to_csv(destino / "por_sitio.csv", index=False)
    tot.to_csv(destino / "total.csv", index=False)
    t.to_csv(destino / "tiempo.csv", index=False)
    texto = (f"Tope de vacías nuevas: {e_max} (base {len(base_df)}, nuevas con persona {P}, "
             f"vacías disponibles {len(vac)}; fracción {fv})\n\n" + md(tot) + "\n\n" + md(por_sitio) + "\n\n"
             + md(por_carpeta) + "\n\n" + md(t, 2) + "\n")
    (destino / "tablas.md").write_text(texto, encoding="utf-8")
    print(texto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["componer"])
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    globals()[args.parte](cfg, rutas, rutas["runs"] / cfg["carpeta"])


if __name__ == "__main__":
    main()
