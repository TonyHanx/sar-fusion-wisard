"""Fase 10: resumen entre semillas de la evaluación en la prueba (configs/fase10.yaml), con las reglas fijadas antes de
predecir. Lee reports/fase10/resultados.csv y mcnemar.csv (src/evaluacion/evaluar_prueba.py) y no vuelve a predecir.

- Por modelo (fusión, solo térmica y solo RGB), subconjunto y dudosas: cada semilla, y el promedio y la desviación
  estándar (ddof = 1) entre las semillas, de recall, precisión, F2 y mAP@0.5 -> resumen_modelos.csv.
- Por comparación de `comparaciones.entre_semillas.familias` (fusión contra térmica, la principal, y fusión contra RGB),
  en baja y severa sin las dudosas: el resultado de cada semilla (McNemar con Bonferroni e IC por episodios, criterio de
  evaluar_prueba) y el de las tres juntas. DEMOSTRADA solo si las tres semillas son "demostrada" con el mismo signo; si
  lo son una o dos, "no concluyente"; si ninguna, "no demostrada" -> resumen_comparaciones.csv.
- RGB contra térmica, solo con el IC de la diferencia de recall por semilla -> en resumen_comparaciones.csv.
Una fila en la bitácora.

Uso: .venv\\Scripts\\python.exe -m src.evaluacion.fase10_resumen --config configs\\fase10.yaml --rutas configs\\rutas.yaml
"""
import argparse

import numpy as np
import pandas as pd

from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml

METRICAS = ["recall", "precision", "f2", "map50"]


def main():
    """Escribe los resúmenes entre semillas."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    salidas = RAIZ / cfg["salidas"]
    res = pd.read_csv(salidas / "resultados.csv")
    mc = pd.read_csv(salidas / "mcnemar.csv")
    es = cfg["comparaciones"]["entre_semillas"]
    semillas = es["semillas"]
    peso = next(iter(cfg["pesos"]["archivos"]))

    # por modelo
    mod = res[res.tipo == "modelo"].copy()
    mod["modalidad"] = mod.nombre.str.rsplit("_s", n=1).str[0]
    mod["semilla"] = mod.nombre.str.rsplit("_s", n=1).str[1].astype(int)
    filas = []
    for (sub, dud, modalidad), d in mod.groupby(["subconjunto", "dudosas", "modalidad"], sort=False):
        d = d.set_index("semilla").loc[semillas]
        fila = {"subconjunto": sub, "dudosas": dud, "modelo": modalidad, "n_personas": int(d.n_personas.iloc[0])}
        for m in METRICAS:
            for s in semillas:
                fila[f"{m}_s{s}"] = d.at[s, m]
            fila[f"{m}_media"], fila[f"{m}_de"] = d[m].mean(), d[m].std(ddof=1)
        fila["umbrales"] = " / ".join(f"{u:g}" for u in d.umbral)
        filas.append(fila)
    modelos = pd.DataFrame(filas)
    modelos.to_csv(salidas / "resumen_modelos.csv", index=False, float_format="%.4f")

    # comparaciones
    filas = []
    for nombre, f in es["familias"].items():
        for sub, d in mc.groupby("subconjunto", sort=False):
            por = []
            for s in semillas:
                a, b = f"{f['a']}_s{s}_{peso}", f"{f['b']}_s{s}_{peso}"
                fila_s = d[(d.modelo_a == a) & (d.modelo_b == b)]
                if len(fila_s) != 1:
                    raise SystemExit(f"Falta McNemar de {a} contra {b} en {sub}")
                por.append(fila_s.iloc[0])
            cumplen = [r.resultado == "demostrada" for r in por]
            signos = {np.sign(r.diferencia_recall) for r, c in zip(por, cumplen) if c}
            n = sum(cumplen)
            if n == len(semillas) and len(signos) == 1:
                total = "demostrada"
            elif n >= 1:
                total = "no concluyente"
            else:
                total = "no demostrada"
            fila = {"comparacion": nombre, "principal": f["principal"], "subconjunto": sub, "dudosas": por[0].dudosas,
                    "n_personas": int(por[0].n_personas), "semillas_que_cumplen": n, "resultado_tres_semillas": total}
            for s, r in zip(semillas, por):
                fila.update({f"dif_s{s}": r.diferencia_recall, f"ic_inf_s{s}": r.dif_ic_inf, f"ic_sup_s{s}": r.dif_ic_sup,
                             f"p_bonf_s{s}": r.p_bonferroni, f"solo_a_s{s}": int(r.solo_a), f"solo_b_s{s}": int(r.solo_b),
                             f"resultado_s{s}": r.resultado})
            fila["dif_media"] = float(np.mean([r.diferencia_recall for r in por]))
            filas.append(fila)
    dif = res[(res.tipo == "diferencia") & (res.dudosas == cfg_dudosas(cfg))]
    for nombre, f in es["descriptiva"].items():
        for sub in mc.subconjunto.unique():
            fila = {"comparacion": nombre, "principal": False, "subconjunto": sub, "dudosas": cfg_dudosas(cfg),
                    "resultado_tres_semillas": "solo IC"}
            vals = []
            for s in semillas:
                r = dif[(dif.modelo == f"{f['a']}_s{s}_{peso} - {f['b']}_s{s}_{peso}") & (dif.subconjunto == sub)].iloc[0]
                fila.update({f"dif_s{s}": r.recall, f"ic_inf_s{s}": r.recall_ic_inf, f"ic_sup_s{s}": r.recall_ic_sup})
                vals.append(r.recall)
            fila["n_personas"] = int(r.n_personas)
            fila["dif_media"] = float(np.mean(vals))
            filas.append(fila)
    comp = pd.DataFrame(filas)
    comp.to_csv(salidas / "resumen_comparaciones.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    principal = modelos[(modelos.dudosas == "sin") & modelos.subconjunto.isin(comp.subconjunto.unique())]
    print(principal[["subconjunto", "modelo", "n_personas", *[f"recall_s{s}" for s in semillas], "recall_media",
                     "recall_de", "umbrales"]].round(3).to_string(index=False))
    print(comp.round(4).to_string(index=False))
    texto = "; ".join(f"{r.comparacion} {r.subconjunto}: {r.resultado_tres_semillas}"
                      + (f" ({int(r.semillas_que_cumplen)} de {len(semillas)})" if pd.notna(r.semillas_que_cumplen) else "")
                      + f", dif media {r.dif_media:+.3f}" for r in comp.itertuples()) + "; " + "; ".join(
        f"{r.modelo} {r.subconjunto}: recall {r.recall_media:.3f} ± {r.recall_de:.3f}" for r in principal.itertuples())
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "resumen entre semillas (fase 10)",
                       "prueba, segundo uso; reglas de configs/fase10.yaml fijadas antes de predecir; demostrada solo si "
                       "se cumple en las 3 semillas; reports/fase10/resumen_*.csv", texto)


def cfg_dudosas(cfg):
    """Modo de dudosas de las comparaciones: el de McNemar de la base (sin)."""
    return leer_yaml(RAIZ / cfg["base"])["mcnemar"]["dudosas"]


if __name__ == "__main__":
    main()
