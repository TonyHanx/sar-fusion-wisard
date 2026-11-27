"""Fase 9: R1 por receta, semilla y vuelo de validación (sección `evaluacion` de configs/fase9.yaml). Sin la prueba.

Para cada corrida de cada receta (semillas de c3.semillas):
- R1 de results.csv: la época elegida, su media móvil de 5 y el mAP@0.5 de esa época (validación de Ultralytics);
- predicciones de validación de weights/elegida.pt (validador de Ultralytics con save_json, como src/evaluacion/evaluar.py),
  y con ellas el mAP@0.5 propio en total y por vuelo (funciones de experimentos/diagnostico_sobreajuste.py).

Los modelos de `evaluacion.modelos` (solo térmica y solo RGB con la receta final) se evalúan igual, como grupos aparte.
La columna `posible_colapso` marca las corridas con la época de R1 en las primeras `decision_r4.colapso_hasta_epoca`.
Solo las comparaciones de `comparaciones_a_bitacora` (si está) agregan su fila a la bitácora.

Por receta: promedio y desviación estándar entre semillas. Por comparación (a − b): diferencia de promedios, su error
típico entre semillas (Welch), la t de Welch y si supera el `minimo_relevante` del diagnóstico.

Uso: .venv\\Scripts\\python.exe -m src.evaluacion.fase9_validacion --config configs\\fase9.yaml --rutas configs\\rutas.yaml
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

from experimentos.diagnostico_sobreajuste import ap50, cajas_gt, emparejar, vuelo_y_posicion
from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from src.entrenamiento.entrenar_fase9 import elegir_epoca
from src.evaluacion import evaluar


def nombre_corrida(base, semilla, ev):
    """Carpeta de la corrida de `base` con `semilla` (la semilla 0 del control no lleva sufijo)."""
    return base if semilla == 0 and base in ev["semilla0_sin_sufijo"] else f"{base}_s{semilla}"


def main():
    """Evalúa las corridas terminadas y escribe las tablas en `evaluacion.salidas`."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    ev, c3, sel = cfg["evaluacion"], cfg["c3"], cfg["seleccion"]
    rc = leer_yaml(RAIZ / ev["ruido"])["ruido"]
    gt = cajas_gt(RAIZ / rc["etiquetas"], rc["tam_imagen"])
    vuelos = sorted({vuelo_y_posicion(i)[0] for i in gt})
    salidas = RAIZ / ev["salidas"]
    salidas.mkdir(parents=True, exist_ok=True)

    filas = []
    # Los modelos de solo térmica y solo RGB (paso 3) van como grupos aparte, con su corrida base (`evaluacion.modelos`).
    for receta, base in (ev["recetas"] | (ev.get("modelos") or {})).items():
        for semilla in c3["semillas"]:
            nombre = nombre_corrida(base, semilla, ev)
            carpeta = rutas["runs"] / c3["carpeta"] / nombre
            if not (carpeta / "weights" / "elegida.pt").exists():
                raise SystemExit(f"Falta {carpeta / 'weights' / 'elegida.pt'}")
            res = pd.read_csv(carpeta / "results.csv")
            res.columns = [c.strip() for c in res.columns]
            epoca, suave, _ = elegir_epoca(res, sel["metrica"], sel["ventana"])
            imgsz = leer_yaml(carpeta / "args.yaml")["imgsz"]
            cfg_pred = {"carpeta": ev["carpeta"], "corridas": c3["carpeta"], "pesos": "weights/elegida.pt",
                        "prediccion": ev["prediccion"] | {"imgsz": imgsz}}
            info = {"corrida": nombre, "datos": c3["corridas"][base]["datos"]}
            preds, ultra = evaluar.predecir(nombre, info, cfg_pred, rutas, "val", {"split": "val"})
            emp = emparejar(gt, preds, rc["iou"], rc["max_det"])
            fila = {"receta": receta, "semilla": semilla, "corrida": nombre, "imgsz": imgsz, "epocas": len(res),
                    "epoca_r1": epoca, "posible_colapso": epoca <= cfg["decision_r4"]["colapso_hasta_epoca"],
                    "r1_media_movil": suave,
                    "map50_epoca_r1": float(res.loc[res["epoch"] == epoca, "metrics/mAP50(B)"].iloc[0]),
                    "map50_ultralytics_elegida": ultra.get("map50"), "map50_propio": ap50([emp[i] for i in gt])}
            for v in vuelos:
                fila[f"map50_{v}"] = ap50([emp[i] for i in gt if vuelo_y_posicion(i)[0] == v])
            filas.append(fila)
            print(f"{nombre}: época R1 {epoca}, media móvil {suave:.4f}, mAP50 propio {fila['map50_propio']:.4f}", flush=True)
    corridas = pd.DataFrame(filas)
    corridas.to_csv(salidas / "r1_corridas.csv", index=False, float_format="%.4f")

    metricas = ["r1_media_movil", "map50_propio", *[f"map50_{v}" for v in vuelos]]
    recetas = corridas.groupby("receta", sort=False)[metricas].agg(["mean", "std", "count"])
    recetas.columns = [f"{m}_{a}" for m, a in recetas.columns]
    recetas.to_csv(salidas / "r1_recetas.csv", float_format="%.4f")

    comparaciones = []
    for a, b in ev["comparaciones"]:
        for m in metricas:
            xa = corridas.loc[corridas["receta"] == a, m].to_numpy()
            xb = corridas.loc[corridas["receta"] == b, m].to_numpy()
            dif = xa.mean() - xb.mean()
            ee = np.sqrt(xa.var(ddof=1) / len(xa) + xb.var(ddof=1) / len(xb))
            t = stats.ttest_ind(xa, xb, equal_var=False)
            comparaciones.append({"a": a, "b": b, "metrica": m, "dif": dif, "ee_semillas": ee,
                                  "t_welch": t.statistic, "p_welch": t.pvalue,
                                  "supera_2ee": bool(dif > 2 * ee), "supera_minimo": bool(dif > ev["minimo_relevante"])})
    comp = pd.DataFrame(comparaciones)
    comp.to_csv(salidas / "r1_comparaciones.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(corridas.to_string(index=False))
    print(recetas.to_string())
    print(comp.to_string(index=False))
    a_bitacora = {tuple(p) for p in ev.get("comparaciones_a_bitacora", ev["comparaciones"])}
    for _, c in comp[comp["metrica"] == "r1_media_movil"].iterrows():
        if (c["a"], c["b"]) not in a_bitacora:  # ya está en la bitácora de una evaluación anterior
            continue
        agregar_a_bitacora(rutas["bitacora"], c3["base"]["fase"], f"{c['a']} vs {c['b']} (R1, {len(c3['semillas'])} semillas)",
                           "validación; media móvil de 5 del mAP@0.5 en la época R1",
                           f"diferencia {c['dif']:+.4f}, error típico entre semillas {c['ee_semillas']:.4f}, "
                           f"t de Welch {c['t_welch']:.2f} (p {c['p_welch']:.3f}); supera 2 EE: {c['supera_2ee']}; "
                           f"supera {ev['minimo_relevante']}: {c['supera_minimo']}")


if __name__ == "__main__":
    main()
