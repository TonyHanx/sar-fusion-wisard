"""Fase 9: aplica la regla `decision_r4` de configs/fase9.yaml y escribe qué receta queda como final. Sin la prueba.

La regla la fijó el usuario el 27 de noviembre de 2026, antes de ver R4: la candidata (R4) gana solo si su R1 promedio
entre semillas supera al del control por `minimo` o más **y** por más de `errores_tipicos` errores típicos entre
semillas. El error típico es el de fase9_validacion.py (Welch: raíz de var_a/n_a + var_b/n_b, con ddof = 1). Si no gana,
la receta final es el control.

R1 sale de results.csv de cada corrida (entrenar_fase9.elegir_epoca), sin predecir nada. Escribe `decision_r4.salida`
(JSON con las cifras, la receta y las corridas del paso 3) y una fila en la bitácora.

Uso: .venv\\Scripts\\python.exe -m src.evaluacion.fase9_decidir --config configs\\fase9.yaml --rutas configs\\rutas.yaml
"""
import argparse
import json

import numpy as np
import pandas as pd

from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from src.entrenamiento.entrenar_fase9 import elegir_epoca
from src.evaluacion.fase9_validacion import nombre_corrida


def r1_de_receta(receta, cfg, rutas):
    """R1 (media móvil de la época elegida) de cada semilla de `receta`, desde results.csv."""
    ev, c3, sel = cfg["evaluacion"], cfg["c3"], cfg["seleccion"]
    filas = []
    for semilla in c3["semillas"]:
        nombre = nombre_corrida(ev["recetas"][receta], semilla, ev)
        res = pd.read_csv(rutas["runs"] / c3["carpeta"] / nombre / "results.csv")
        res.columns = [c.strip() for c in res.columns]
        if len(res) != c3["base"]["ultralytics"]["epochs"]:
            raise SystemExit(f"{nombre}: {len(res)} épocas en results.csv, no {c3['base']['ultralytics']['epochs']}")
        epoca, valor, _ = elegir_epoca(res, sel["metrica"], sel["ventana"])
        filas.append({"corrida": nombre, "semilla": semilla, "epoca_r1": epoca, "r1": valor})
    return filas


def main():
    """Aplica la regla y escribe la decisión."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    d = cfg["decision_r4"]
    a, b = r1_de_receta(d["candidata"], cfg, rutas), r1_de_receta(d["control"], cfg, rutas)
    xa, xb = np.array([f["r1"] for f in a]), np.array([f["r1"] for f in b])
    dif = float(xa.mean() - xb.mean())
    ee = float(np.sqrt(xa.var(ddof=1) / len(xa) + xb.var(ddof=1) / len(xb)))
    supera_minimo = dif >= d["minimo"]
    supera_ee = dif > d["errores_tipicos"] * ee
    gana = bool(supera_minimo and supera_ee)
    receta = d["candidata"] if gana else d["control"]
    decision = {
        "regla": f"{d['candidata']} gana si su R1 promedio supera al de {d['control']} por {d['minimo']} o más y por más "
                 f"de {d['errores_tipicos']} errores típicos entre semillas (Welch); si no, {d['control']}",
        "candidata": {"receta": d["candidata"], "corridas": a, "media": float(xa.mean()), "de": float(xa.std(ddof=1))},
        "control": {"receta": d["control"], "corridas": b, "media": float(xb.mean()), "de": float(xb.std(ddof=1))},
        "diferencia": dif, "error_tipico": ee, "supera_minimo": bool(supera_minimo), "supera_errores_tipicos": bool(supera_ee),
        "gana_candidata": gana, "receta_final": receta, "datos": "base",
        "corridas_paso3": d["modelos"][receta],
    }
    salida = RAIZ / d["salida"]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    texto = (f"{d['candidata']} {xa.mean():.4f} ± {xa.std(ddof=1):.4f} contra {d['control']} {xb.mean():.4f} ± "
             f"{xb.std(ddof=1):.4f}: diferencia {dif:+.4f}, error típico {ee:.4f}; supera {d['minimo']}: {supera_minimo}; "
             f"supera {d['errores_tipicos']} EE: {supera_ee}. Receta final: {receta} (datos base). Paso 3: "
             f"{', '.join(d['modelos'][receta])}")
    agregar_a_bitacora(rutas["bitacora"], cfg["c3"]["base"]["fase"], f"decisión {d['candidata']} contra {d['control']}",
                       f"regla fijada antes de ver {d['candidata']}: {decision['regla']}; R1 desde results.csv", texto)
    print(texto)
    print(f"Decisión en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
