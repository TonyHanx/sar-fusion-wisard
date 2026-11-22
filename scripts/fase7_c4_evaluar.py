r"""Fase 7, C4: evaluación de las cuatro corridas de C3 en validación, con el evaluador propio.

Usa las funciones de scripts/evaluar.py (fase 6) sin cambiar sus reglas: predicciones con el validador de Ultralytics
(confianza >= 0.001, save_json), pycocotools a IoU 0.5, maxDets 100, bootstrap por episodios (10 bloques en la
validación, 10 000 remuestreos, seed=0) y McNemar exacta. Las reglas propias de C4 están en `c4` de configs/fase7.yaml
(fijadas por el usuario el 21 de noviembre de 2026, antes de evaluar):
- modelos: cada corrida con last.pt (época 50, la cifra principal) y con best.pt (secundaria); las fusiones, además,
  con la RGB en 0 (`rgb_cero`);
- umbral de confianza por modelo y peso: el de mayor F2 en la validación (rejilla de 0.05 a 0.95, paso 0.05; si hay
  empate, el más alto), con todas las personas de WiSARD; las variantes con la RGB en 0 usan el del mismo peso con la
  RGB real;
- subconjuntos: todas las personas y los niveles de oclusión de la validación (a mano, scripts/fase7_c4_oclusion.py):
  baja (se ve en la RGB) y severa (no se ve). Las "no es persona" no tienen nivel: son cajas dudosas, y se evalúa con y
  sin ellas, como en la prueba;
- diferencias con IC por bootstrap (los mismos remuestreos para los dos modelos) y McNemar (solo last.pt) para los
  pares de `c4.pares`, con Bonferroni por el número de pares dentro de cada subconjunto.
Además junta, por corrida, la cifra de results.csv (última época y promedio de las 5 últimas, validación de
Ultralytics, sin IC) desde resumen.json.

Salidas en <c4.salidas>: umbrales.csv (F2 de cada umbral de la rejilla), resultados.csv, mcnemar.csv,
corridas.csv y recall_por_nivel.png. Una fila por modelo en la bitácora.

Uso:
  .venv\Scripts\python.exe scripts\fase7_c4_evaluar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --solo-predecir
  .venv\Scripts\python.exe scripts\fase7_c4_evaluar.py --config configs\fase7.yaml --rutas configs\rutas.yaml
"""
import argparse
import copy
import json
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from statsmodels.stats.contingency_tables import mcnemar  # noqa: E402

import evaluar as e6  # noqa: E402
from comun import RAIZ, agregar_a_bitacora, fijar_semilla, leer_rutas, leer_yaml  # noqa: E402

PARTICION = "validacion"
METRICAS = e6.METRICAS
COLOR = {"fusion": "#2a78d6", "termico": "#1baf7a"}  # los de configs/fase6.yaml


def ruta(p):
    return e6.ruta(p)


def rel(p):
    return e6.rel(p)


def clave(nombre, peso):
    """Nombre de c4.pares (p. ej. fusion_ampliado_rgb0) -> clave del modelo con ese peso."""
    return f"{nombre[:-5]}_{peso}_rgb0" if nombre.endswith("_rgb0") else f"{nombre}_{peso}"


def armar_modelos(cfg):
    c4, c3 = cfg["c4"], cfg["c3"]
    modelos = {}
    for peso, archivo in c4["pesos"].items():
        for corrida in c4["corridas"]:
            base = {"corrida": corrida, "pesos": archivo, "datos": c3["corridas"][corrida]["datos"], "peso": peso,
                    "rgb0": False, "pred": f"{corrida}_{peso}", "nombre": f"{corrida} ({peso}.pt)",
                    "modalidad": "fusion" if corrida.startswith("fusion") else "termico"}
            modelos[f"{corrida}_{peso}"] = base
            if corrida in c4["rgb_cero"]:
                modelos[f"{corrida}_{peso}_rgb0"] = {**base, "rgb0": True, "umbral_de": f"{corrida}_{peso}",
                                                    "nombre": f"{corrida} con la RGB en 0 ({peso}.pt)"}
    for a, b in c4["pares"]:
        for peso in c4["pesos"]:
            for n in (a, b):
                if clave(n, peso) not in modelos:
                    raise SystemExit(f"c4.pares: {n} no es un modelo de C4")
    return modelos


def config_base(cfg, rutas, con_nivel):
    """configs/fase6.yaml con las corridas de la fase 7, la carpeta de C4 y, si existe, el nivel de la validación."""
    c4 = cfg["c4"]
    b = copy.deepcopy(leer_yaml(ruta(c4["base"])))
    b["corridas"] = cfg["c3"]["carpeta"]
    b["carpeta"] = c4["carpeta"]
    part = b["particiones"][PARTICION]
    prohibidos = set(cfg["prohibidas"]) | set(leer_yaml(ruta(cfg["c1"]["particion"]))["prueba"])
    if any(x in v for v in part["vuelos"] for x in prohibidos):
        raise SystemExit(f"La validación incluye un vuelo de la prueba: {part['vuelos']}")
    if con_nivel:
        nivel = rutas["data"] / c4["oclusion"]["nivel"]
        if not nivel.exists():
            raise SystemExit(f"No existe {nivel}: anota la oclusión de la validación (scripts/fase7_c4_oclusion.py "
                             f"--parte anotar y --parte nivel)")
        part["niveles"] = str(nivel)
    return b


def elegir_umbrales(cfg, modelos, preds, datos, ev):
    """Por cada modelo con la RGB real, el umbral de mayor F2 (todas las personas, todos los fotogramas)."""
    u = cfg["c4"]["umbral"]
    rejilla = np.round(np.arange(u["desde"], u["hasta"] + u["paso"] / 2, u["paso"]), 2)
    gt = e6.coco_gt(datos, np.zeros(len(datos["per"]), bool))
    filas, umbral = [], {}
    for k, info in modelos.items():
        if info["rgb0"]:
            continue
        dt = e6.coco_dt(gt, preds[k], datos, ev["max_dets"])
        mejor = None
        for t in rejilla:
            r = e6.evaluar(gt, dt, datos["fot"].img_id, datos, {**ev, "conf": float(t)})
            p = r["punto"]
            f2 = round(float(p["f2"]), 12) if not np.isnan(p["f2"]) else -1.0
            filas.append({"modelo": k, "umbral": float(t), "f2": p["f2"], "recall": p["recall"],
                          "precision": p["precision"], "tp": r["tp_conf"], "fp": r["fp_conf"]})
            if mejor is None or f2 >= mejor[1]:  # recorre de menor a mayor: con >=, el empate se queda con el más alto
                mejor = (float(t), f2)
        umbral[k] = mejor[0]
    for k, info in modelos.items():
        if info["rgb0"]:
            umbral[k] = umbral[info["umbral_de"]]
    tabla = pd.DataFrame(filas)
    tabla["elegido"] = [umbral[m] == t for m, t in zip(tabla.modelo, tabla.umbral)]
    return umbral, tabla


def grafico(res, modelos, cfg, base, ruta_png, B):
    """Recall de los modelos de last.pt por subconjunto, con su IC (un panel por subconjunto)."""
    f = base["figura"]
    c4 = cfg["c4"]
    scs = c4["subconjuntos"]
    claves = [k for k, i in modelos.items() if i["peso"] == c4["principal"]]
    fig, ejes = plt.subplots(1, len(scs), figsize=(9.2, 3.9), sharey=True, facecolor=f["fondo"])
    y = np.arange(len(claves))[::-1]
    for ax, sc in zip(ejes, scs):
        ax.set_facecolor(f["fondo"])
        d = res[(res.tipo == "modelo") & (res.subconjunto == sc["nombre"]) & (res.dudosas == "sin")].set_index("modelo")
        for yy, k in zip(y, claves):
            info, fila = modelos[k], d.loc[k]
            col = COLOR[info["modalidad"]]
            ax.plot([fila.recall_ic_inf, fila.recall_ic_sup], [yy, yy], color=col, linewidth=2, solid_capstyle="round",
                    zorder=2)
            ax.plot(fila.recall, yy, "o", markersize=8, color=col, markerfacecolor=f["fondo"] if info["rgb0"] else col,
                    markeredgecolor=col, markeredgewidth=2 if info["rgb0"] else 1.5, zorder=3)
        n = int(d.n_personas.iloc[0])
        ax.set_title(f"{sc['rotulo'].replace(chr(10), ' ')}\n{n} personas", fontsize=9, color=f["texto"], loc="left")
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.grid(axis="x", color=f["rejilla"], linewidth=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(f["rejilla"])
        ax.tick_params(colors=f["texto_secundario"], labelsize=8, length=0)
        ax.set_xlabel("Recall (umbral de F2 de cada modelo)", fontsize=8, color=f["texto_secundario"])
    ejes[0].set_yticks(y, [modelos[k]["nombre"].replace(f" ({c4['principal']}.pt)", "") for k in claves])
    leyenda = [Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["fusion"], label="Fusión"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["fusion"],
                      markerfacecolor=f["fondo"], markeredgewidth=2, label="Fusión con la RGB en 0"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["termico"], label="Solo térmica")]
    fig.legend(handles=leyenda, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=3, frameon=False, fontsize=8,
               labelcolor=f["texto"])
    fig.suptitle(f"Recall en validación por nivel de oclusión ({c4['principal']}.pt, sin las cajas dudosas)", x=0.01,
                 y=0.99, ha="left", va="top", fontsize=10, color=f["texto"])
    fig.text(0.01, 0.01, f"Barras: IC del {int(base['bootstrap']['confianza'] * 100)} % por bootstrap de episodios "
             f"({B:,} remuestreos de 10 bloques).".replace(",", " "), fontsize=7, color=f["texto_secundario"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.90))
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_png, dpi=f["dpi"], facecolor=f["fondo"])
    plt.close(fig)


def resumen_corridas(cfg, rutas, ultra):
    filas = []
    for corrida in cfg["c4"]["corridas"]:
        r = json.loads((rutas["runs"] / cfg["c3"]["carpeta"] / corrida / "resumen.json").read_text(encoding="utf-8"))
        u, p, e = r["val_ultima_epoca"], r["val_promedio_ultimas"], r["val_elegida"]
        filas.append({"corrida": corrida, "results_ultima_epoca": u["epoca"], "results_map50_ultima": u["metrics/mAP50(B)"],
                      "results_recall_ultima": u["metrics/recall(B)"],
                      "results_epocas_promedio": "-".join(str(x) for x in (p["epocas"][0], p["epocas"][-1])),
                      "results_map50_promedio": p["metrics/mAP50(B)"], "results_recall_promedio": p["metrics/recall(B)"],
                      "results_best_epoca": e["epoca"], "results_map50_best": e["metrics/mAP50(B)"],
                      "ultralytics_map50_last_pt": ultra[f"{corrida}_last"].get("map50"),
                      "ultralytics_map50_best_pt": ultra[f"{corrida}_best"].get("map50")})
    return pd.DataFrame(filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--solo-predecir", action="store_true",
                    help="solo las predicciones de los modelos (no necesita el nivel de oclusión)")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    c4 = cfg["c4"]
    base = config_base(cfg, rutas, con_nivel=not args.solo_predecir)
    fijar_semilla(base["bootstrap"]["seed"])
    part = base["particiones"][PARTICION]
    modelos = armar_modelos(cfg)

    datos = e6.preparar(base, rutas, PARTICION, modelos)
    e6.verificar(datos, PARTICION)
    per = datos["per"]
    if not args.solo_predecir:
        per["dudosa"] = per.nivel == "sin_nivel"  # "no es persona": sin nivel, caja dudosa (como en la prueba)
        print(f"Niveles: {per.nivel.value_counts().to_dict()}; dudosas {int(per.dudosa.sum())}")

    preds, ultra = {}, {}
    for k, info in modelos.items():
        preds[k], ultra[k] = e6.predecir(info["pred"], info, base, rutas, PARTICION, part, rgb_cero=info["rgb0"])
        print(f"{k}: {len(preds[k])} predicciones; Ultralytics: mAP@0.5 {ultra[k].get('map50', float('nan')):.4f}")
    if args.solo_predecir:
        for k, info in modelos.items():
            agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {k}",
                               f"C4: predicciones en validación ({', '.join(part['vuelos'])}); pesos {ultra[k]['pesos']}"
                               + ("; RGB en 0 (los 3 canales de color)" if info["rgb0"] else "")
                               + f"; confianza >= {base['prediccion']['conf']}, validador de Ultralytics con save_json",
                               f"{len(preds[k])} predicciones en runs/{c4['carpeta']}/{PARTICION}/"
                               f"{info['pred'] + ('_rgb0' if info['rgb0'] else '')}/predictions.json; sin métricas propias")
        return

    t0 = time.time()
    ev = base["evaluacion"]
    salidas = ruta(c4["salidas"])
    salidas.mkdir(parents=True, exist_ok=True)
    umbral, tabla_u = elegir_umbrales(cfg, modelos, preds, datos, ev)
    tabla_u.to_csv(salidas / "umbrales.csv", index=False)
    print("Umbrales (F2 en validación): " + ", ".join(f"{k} {v:.2f}" for k, v in umbral.items()))

    B = base["bootstrap"]["remuestreos"]
    rng = np.random.default_rng(base["bootstrap"]["seed"])
    nb = datos["nb"]
    cuentas_b = np.stack([np.bincount(rng.integers(0, nb, nb), minlength=nb) for _ in range(B)])
    conf_ic = base["bootstrap"]["confianza"]
    filas, filas_mc, evals = [], [], {}
    for sc in c4["subconjuntos"]:
        for dud in ("con", "sin"):
            cuenta = pd.Series(True, index=per.index) if sc["personas"] == "todas" else (per.nivel == sc["personas"])
            if dud == "sin":
                cuenta &= ~per.dudosa
            gt = e6.coco_gt(datos, ~cuenta.to_numpy())
            boot = {}
            for k, info in modelos.items():
                dt = e6.coco_dt(gt, preds[k], datos, ev["max_dets"])
                r = e6.evaluar(gt, dt, datos["fot"].img_id, datos, {**ev, "conf": umbral[k]})
                evals[(sc["nombre"], dud, k)] = r
                boot[k] = e6.bootstrap(r, cuentas_b)
                fila = {"particion": PARTICION, "subconjunto": sc["nombre"], "dudosas": dud, "tipo": "modelo",
                        "modelo": k, "corrida": info["corrida"], "peso": info["peso"], "rgb_cero": info["rgb0"],
                        "umbral": umbral[k], "n_fotogramas": r["n_fotogramas"], "n_personas": r["n_personas"],
                        "tp": r["tp_conf"], "fp": r["fp_conf"], "fn": r["n_personas"] - r["tp_conf"]}
                for mt in METRICAS:
                    fila[mt] = r["punto"][mt]
                    fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = e6.intervalo(boot[k][mt], conf_ic)
                fila["remuestreos"] = B
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[k][mt]).sum() for mt in METRICAS))
                filas.append(fila)
            for peso in c4["pesos"]:
                for a0, b0 in c4["pares"]:
                    a, b = clave(a0, peso), clave(b0, peso)
                    fila = {"particion": PARTICION, "subconjunto": sc["nombre"], "dudosas": dud, "tipo": "diferencia",
                            "modelo": f"{a} - {b}", "peso": peso, "n_fotogramas": evals[(sc["nombre"], dud, a)]["n_fotogramas"],
                            "n_personas": evals[(sc["nombre"], dud, a)]["n_personas"]}
                    for mt in METRICAS:
                        fila[mt] = evals[(sc["nombre"], dud, a)]["punto"][mt] - evals[(sc["nombre"], dud, b)]["punto"][mt]
                        fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = e6.intervalo(boot[a][mt] - boot[b][mt], conf_ic)
                    fila["remuestreos"] = B
                    fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[a][mt] - boot[b][mt]).sum() for mt in METRICAS))
                    filas.append(fila)
            print(f"{sc['nombre']} ({dud} dudosas): listo", flush=True)

        dud = base["mcnemar"]["dudosas"]
        peso = c4["principal"]
        pares = [(clave(a, peso), clave(b, peso)) for a, b in c4["pares"]]
        for a, b in pares:
            da, db = evals[(sc["nombre"], dud, a)]["detectada"], evals[(sc["nombre"], dud, b)]["detectada"]
            if set(da) != set(db):
                raise SystemExit(f"McNemar: no son las mismas personas en {a} y {b} ({sc['nombre']}).")
            ids = sorted(da)
            xa, xb = np.array([da[i] for i in ids]), np.array([db[i] for i in ids])
            tabla = [[int((xa & xb).sum()), int((xa & ~xb).sum())], [int((~xa & xb).sum()), int((~xa & ~xb).sum())]]
            res = mcnemar(tabla, exact=base["mcnemar"]["exacta"])
            p_b = min(1.0, float(res.pvalue) * len(pares))
            filas_mc.append({"particion": PARTICION, "subconjunto": sc["nombre"], "dudosas": dud, "modelo_a": a,
                             "modelo_b": b, "umbral_a": umbral[a], "umbral_b": umbral[b], "n_personas": len(ids),
                             "ambos": tabla[0][0], "solo_a": tabla[0][1], "solo_b": tabla[1][0],
                             "ninguno": tabla[1][1], "recall_a": float(xa.mean()), "recall_b": float(xb.mean()),
                             "estadistico": float(res.statistic), "p": float(res.pvalue), "comparaciones": len(pares),
                             "p_bonferroni": p_b, "alfa": base["mcnemar"]["alfa"],
                             "significativo": p_b < base["mcnemar"]["alfa"]})

    res = pd.DataFrame(filas)
    mc = pd.DataFrame(filas_mc)
    corr = resumen_corridas(cfg, rutas, ultra)
    res.to_csv(salidas / "resultados.csv", index=False)
    mc.to_csv(salidas / "mcnemar.csv", index=False)
    corr.to_csv(salidas / "corridas.csv", index=False)
    grafico(res, modelos, cfg, base, salidas / "recall_por_nivel.png", B)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.precision", 3):
        print(corr.to_string(index=False))
        print(res[res.dudosas == "sin"][["subconjunto", "modelo", "umbral", "n_personas", "recall", "recall_ic_inf",
                                         "recall_ic_sup", "precision", "f2", "map50", "map50_ic_inf",
                                         "map50_ic_sup"]].to_string(index=False))
        print(mc[["subconjunto", "modelo_a", "modelo_b", "n_personas", "solo_a", "solo_b", "recall_a", "recall_b", "p",
                  "p_bonferroni", "significativo"]].to_string(index=False))
    print(f"Salidas en {rel(salidas)} ({time.time() - t0:.0f} s)")

    for k, info in modelos.items():
        resumen = []
        for sc in c4["subconjuntos"]:
            d = res[(res.tipo == "modelo") & (res.modelo == k) & (res.subconjunto == sc["nombre"])
                    & (res.dudosas == "sin")].iloc[0]
            resumen.append(f"{sc['nombre']} (sin dudosas, {d.n_personas}): recall {d.recall:.3f} "
                           f"[{d.recall_ic_inf:.3f}, {d.recall_ic_sup:.3f}], P {d.precision:.3f}, F2 {d.f2:.3f}, "
                           f"mAP50 {d.map50:.3f} [{d.map50_ic_inf:.3f}, {d.map50_ic_sup:.3f}]")
        agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {k}",
                           f"C4, validación ({', '.join(part['vuelos'])}); pesos {ultra[k]['pesos']}"
                           + ("; RGB en 0 (los 3 canales de color)" if info["rgb0"] else "")
                           + f"; umbral {umbral[k]:.2f} (F2 en validación"
                           + (f", el de {info['umbral_de']})" if info["rgb0"] else ")")
                           + f", IoU {ev['iou']}, maxDets {ev['max_dets']}; nivel a mano "
                           f"({c4['oclusion']['nivel']}); bootstrap {B} remuestreos de {nb} bloques, seed="
                           f"{base['bootstrap']['seed']}; salidas en {rel(salidas)}",
                           "; ".join(resumen) + f"; Ultralytics (su AP) mAP50 {ultra[k].get('map50', float('nan')):.4f}")


if __name__ == "__main__":
    main()
