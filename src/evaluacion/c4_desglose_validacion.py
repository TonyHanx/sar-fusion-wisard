r"""Fase 7, C4: desglose descriptivo de la evaluación en validación, por vuelo y por bloque del bootstrap.

No cambia ninguna cifra ni agrega pruebas: usa las predicciones de C4, los umbrales elegidos (umbrales.csv de
src/evaluacion/c4_evaluar_validacion.py) y el mismo emparejamiento de pycocotools. Sirve para leer los IC y McNemar de
C4:
- bloques.csv: los bloques (episodios) del bootstrap, con sus fotogramas y sus personas por nivel;
- alto_por_nivel.csv: alto de la caja térmica (px) por vuelo y nivel (oclusión y tamaño);
- recall_por_vuelo.csv: personas detectadas por vuelo y subconjunto (sin las cajas dudosas), los 12 modelos;
- discordantes_por_bloque.csv: para los pares de McNemar (last.pt), las personas que detecta solo uno, por bloque;
- remuestreos.csv: en cuántos remuestreos del bootstrap falta cada bloque (los mismos de la evaluación, seed=0).
Una fila en la bitácora.

Uso (después de src/evaluacion/c4_evaluar_validacion.py):
  .venv\Scripts\python.exe -m src.evaluacion.c4_desglose_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml
"""
import argparse

import numpy as np
import pandas as pd

import src.evaluacion.evaluar as evaluar_fase6
import src.evaluacion.c4_evaluar_validacion as c4_evaluar
from src.comun import agregar_a_bitacora, leer_rutas, leer_yaml

PARTICION = c4_evaluar.PARTICION


def corto(vuelo):
    """210924_FHL_Enterprise_0134 -> FHL 0134."""
    p = vuelo.split("_")
    return f"{p[1]} {p[-1]}"


def main():
    """Desglosa la evaluación de C4 en validación por vuelo y por bloque del bootstrap, sin cambiar ninguna cifra, y
    escribe sus tablas y la fila de la bitácora."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    c4 = cfg["c4"]
    base = c4_evaluar.config_base(cfg, rutas, con_nivel=True)
    part = base["particiones"][PARTICION]
    ev = base["evaluacion"]
    modelos = c4_evaluar.armar_modelos(cfg)
    salidas = c4_evaluar.ruta(c4["salidas"])

    datos = evaluar_fase6.preparar(base, rutas, PARTICION, modelos)
    evaluar_fase6.verificar(datos, PARTICION)
    per, fot, nb = datos["per"], datos["fot"], datos["nb"]
    per["dudosa"] = per.nivel == "sin_nivel"
    per["vuelo_corto"] = per.vuelo.map(corto)
    per["bloque"] = per.img_id.map(dict(zip(fot.img_id, fot.bloque)))

    u = pd.read_csv(salidas / "umbrales.csv")
    umbral = dict(u[u.elegido].groupby("modelo").umbral.first())
    for k, info in modelos.items():
        if info["rgb0"]:
            umbral[k] = umbral[info["umbral_de"]]
    if set(umbral) != set(modelos):
        raise SystemExit("umbrales.csv no tiene todos los modelos: corre antes src/evaluacion/c4_evaluar_validacion.py")

    # bloques del bootstrap
    bl = fot.groupby("bloque").agg(vuelo=("vuelo", "first"), fotogramas=("img_id", "size"),
                                   posicion_desde=("posicion", "min"), posicion_hasta=("posicion", "max"))
    bl["vuelo"] = bl.vuelo.map(corto)
    bl = bl.join(per.groupby(["bloque", "nivel"]).size().unstack(fill_value=0)).fillna(0)
    bl["personas_sin_dudosas"] = per[~per.dudosa].groupby("bloque").size()
    bl = bl.fillna(0).reset_index()
    bl.to_csv(salidas / "bloques.csv", index=False)

    # remuestreos: los mismos de src/evaluacion/c4_evaluar_validacion.py (mismo generador y seed)
    B = base["bootstrap"]["remuestreos"]
    rng = np.random.default_rng(base["bootstrap"]["seed"])
    cuentas_b = np.stack([np.bincount(rng.integers(0, nb, nb), minlength=nb) for _ in range(B)])
    rem = pd.DataFrame({"bloque": range(nb), "remuestreos_sin_el_bloque": (cuentas_b == 0).sum(0),
                        "fraccion": (cuentas_b == 0).mean(0)})
    rem.to_csv(salidas / "remuestreos.csv", index=False)

    # tamaño por vuelo y nivel
    alto = per.groupby(["vuelo_corto", "nivel"]).h.describe(percentiles=[.1, .5, .9])
    alto = alto[["count", "10%", "50%", "90%"]].rename(columns={"count": "personas", "10%": "alto_p10",
                                                                "50%": "alto_mediana", "90%": "alto_p90"})
    alto.round(1).reset_index().to_csv(salidas / "alto_por_nivel.csv", index=False)

    # detectadas por persona, con el umbral de cada modelo
    preds = {k: evaluar_fase6.predecir(info["pred"], info, base, rutas, PARTICION, part, rgb_cero=info["rgb0"])[0]
             for k, info in modelos.items()}
    det = {}
    for nivel in ("todas", "baja", "severa"):
        cuenta = ~per.dudosa if nivel == "todas" else (per.nivel == nivel)
        gt = evaluar_fase6.coco_gt(datos, ~cuenta.to_numpy())
        for k in modelos:
            dt = evaluar_fase6.coco_dt(gt, preds[k], datos, ev["max_dets"])
            r = evaluar_fase6.evaluar(gt, dt, fot.img_id, datos, {**ev, "conf": umbral[k]})
            det[(nivel, k)] = pd.Series(r["detectada"])

    pg = per.set_index("gt_id")
    filas = []
    for (nivel, k), d in det.items():
        s = pg.loc[d.index].assign(det=d.to_numpy())
        for v, g in s.groupby("vuelo_corto"):
            filas.append({"subconjunto": nivel, "modelo": k, "peso": modelos[k]["peso"], "vuelo": v,
                          "umbral": umbral[k], "personas": len(g), "detectadas": int(g.det.sum()),
                          "recall": g.det.mean()})
    rv = pd.DataFrame(filas)
    rv.to_csv(salidas / "recall_por_vuelo.csv", index=False)

    filas = []
    for a0, b0 in c4["pares"]:
        a, b = c4_evaluar.clave(a0, c4["principal"]), c4_evaluar.clave(b0, c4["principal"])
        for nivel in ("todas", "baja", "severa"):
            da, db = det[(nivel, a)], det[(nivel, b)]
            s = pg.loc[da.index].assign(sa=(da & ~db.loc[da.index]).to_numpy(), sb=(db.loc[da.index] & ~da).to_numpy())
            for blq, g in s.groupby("bloque"):
                filas.append({"subconjunto": nivel, "modelo_a": a, "modelo_b": b, "bloque": blq,
                              "vuelo": g.vuelo_corto.iloc[0], "personas": len(g), "solo_a": int(g.sa.sum()),
                              "solo_b": int(g.sb.sum())})
    dis = pd.DataFrame(filas)
    dis.to_csv(salidas / "discordantes_por_bloque.csv", index=False)

    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(bl.to_string(index=False))
        print(rem.to_string(index=False))
        print(alto.round(1).to_string())
        print(rv[rv.peso == c4["principal"]].pivot_table(index=["subconjunto", "vuelo", "personas"], columns="modelo",
                                                         values="recall").round(3).to_string())
        print(dis.groupby(["subconjunto", "modelo_a", "modelo_b", "vuelo"])[["personas", "solo_a", "solo_b"]]
              .sum().to_string())

    grande = bl.loc[bl.personas_sin_dudosas.idxmax()]
    sin_grande = rem.loc[rem.bloque == grande.bloque, "fraccion"].iloc[0]
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "YOLO26s (12 modelos de C4)",
                       f"C4, desglose descriptivo en validación (src/evaluacion/c4_desglose_validacion.py): "
                       f"por vuelo y por bloque "
                       f"del bootstrap, con los umbrales de umbrales.csv; sin pruebas nuevas; salidas en "
                       f"{c4_evaluar.rel(salidas)}",
                       f"{nb} bloques; el más grande ({grande.vuelo}, bloque {grande.bloque}) tiene "
                       f"{int(grande.personas_sin_dudosas)} de {int(bl.personas_sin_dudosas.sum())} personas y falta en "
                       f"{sin_grande:.1%} de los remuestreos; recall last.pt por vuelo en recall_por_vuelo.csv")


if __name__ == "__main__":
    main()
