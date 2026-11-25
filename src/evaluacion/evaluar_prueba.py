r"""Fase 8: evaluación en la prueba (FHL 0405), con las reglas confirmadas en configs/fase8.yaml.

Usa las funciones de scripts/evaluar.py (fase 6) sin cambiar sus reglas: predicciones con el validador de Ultralytics
(confianza >= 0.001, save_json), pycocotools a IoU 0.5 y maxDets 100.

Partes (cada una se detiene y espera al usuario):
- umbrales (paso 2): fija el umbral de confianza de cada modelo y peso en la validación (FHL 0134 y MtErie 0007), sin
  leer la prueba.
  - Regla: el umbral con el mayor F2, con todas las personas de WiSARD y todos los fotogramas, en la rejilla ampliada
    (`umbral.rejilla_baja` y luego `umbral.rejilla`); si hay empate, el más alto.
  - Las variantes con la RGB en 0 usan el umbral del mismo modelo y peso con la RGB real.
  - Además, el umbral de la rejilla anterior (solo `umbral.rejilla`), para la sensibilidad descriptiva de la prueba.
  - Reutiliza las predicciones de validación que ya existen (`umbral.validacion`) y hace las que faltan (rgb_base).
  - Escribe `umbral.umbrales` (una fila por modelo y peso, con el sha256 de los pesos y de las predicciones) y
    `umbral.rejilla_completa`, y una fila por modelo y peso en la bitácora. Si `umbral.umbrales` ya existe, no hace
    nada: los umbrales se fijan una sola vez.
- verificar (paso 3): comprueba la prueba sin predecir.
  - Los umbrales están en GitHub (el archivo es igual al de la rama remota) y los pesos son los mismos con que se
    fijaron (sha256).
  - Cada modelo recibe los canales con que entrenó (primera capa de los pesos contra `channels` del dataset).
  - Las etiquetas de los tres datasets de la prueba son las mismas, y los fotogramas, las personas, los niveles, las
    dudosas y los bloques coinciden con `comprobar` de configs/fase6.yaml.
  - No existe ninguna salida de la prueba.
- prueba (paso 4): repite `verificar`, predice la prueba con todos los modelos (también las fusiones con la RGB en 0) y
  la mide una sola vez.
  - Por modelo y subconjunto (los de la fase 6, con y sin las dudosas): recall, precisión y F2 con su umbral, y mAP@0.5,
    con IC por bootstrap de episodios (13 bloques).
  - Diferencias de `comparaciones.descriptivas` con IC, con el mismo peso a cada lado.
  - McNemar de `comparaciones.mcnemar` con el peso principal, en baja y severa sin las dudosas, con Bonferroni, y el
    criterio: demostrada solo si McNemar y el IC de la diferencia de recall coinciden.
  - Sensibilidad, sin IC: las mismas cifras con el umbral de la rejilla anterior y con 0.5.
  - Salidas en `salidas`: resultados.csv, mcnemar.csv, sensibilidad.csv, prediccion.csv y recall_por_nivel.png. Una
    fila por modelo en la bitácora y una con McNemar y el criterio.

Uso:
  .venv\Scripts\python.exe scripts\fase8_evaluar.py --config configs\fase8.yaml --rutas configs\rutas.yaml --parte umbrales
  .venv\Scripts\python.exe scripts\fase8_evaluar.py --config configs\fase8.yaml --rutas configs\rutas.yaml --parte verificar
  .venv\Scripts\python.exe scripts\fase8_evaluar.py --config configs\fase8.yaml --rutas configs\rutas.yaml --parte prueba
"""
import argparse
import copy
import hashlib
import subprocess
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from statsmodels.stats.contingency_tables import mcnemar  # noqa: E402

import src.evaluacion.evaluar as e6  # noqa: E402
from src.comun import RAIZ, agregar_a_bitacora, fijar_semilla, leer_rutas, leer_yaml  # noqa: E402

VALIDACION = "validacion"
PRUEBA = "prueba"
COLOR = {"fusion": "#2a78d6", "termico": "#1baf7a", "rgb": "#eb6834"}  # los de configs/fase6.yaml
SALIDAS = ["resultados.csv", "mcnemar.csv", "sensibilidad.csv", "prediccion.csv", "recall_por_nivel.png"]


def ruta(p):
    return e6.ruta(p)


def rel(p):
    return e6.rel(p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leer_config(args):
    cfg = leer_yaml(args.config)
    if cfg.get("estado") != "confirmada":
        raise SystemExit(f"{args.config}: estado '{cfg.get('estado')}'; las reglas tienen que estar confirmadas.")
    base = copy.deepcopy(leer_yaml(ruta(cfg["base"])))
    val, prueba = base["particiones"][VALIDACION], base["particiones"]["prueba"]
    if set(val["vuelos"]) & set(prueba["vuelos"]):
        raise SystemExit(f"La validación incluye un vuelo de la prueba: {val['vuelos']}")
    return cfg, base


def rejillas(u):
    r = u["rejilla"]
    anterior = [float(x) for x in np.round(np.arange(r["desde"], r["hasta"] + r["paso"] / 2, r["paso"]), 2)]
    baja = [float(x) for x in u["rejilla_baja"]]
    if not baja or max(baja) >= min(anterior) or baja != sorted(baja):
        raise SystemExit("umbral.rejilla_baja tiene que ir en orden y por debajo de umbral.rejilla.")
    return baja + anterior, anterior


def armar_modelos(cfg, particion=VALIDACION):
    """Un modelo por nombre y peso (más las variantes con la RGB en 0), con dónde van sus predicciones: en la
    validación, las de `umbral.validacion`; en la prueba, runs/<carpeta>/prueba/<modelo>_<peso>[_rgb0]/ con el dataset
    `datos_prueba`."""
    modelos = {}
    val = cfg["umbral"]["validacion"]
    for m, info in cfg["modelos"].items():
        if m not in val:
            raise SystemExit(f"umbral.validacion no dice dónde están las predicciones de validación de {m}.")
        for peso, archivo in cfg["pesos"]["archivos"].items():
            k = f"{m}_{peso}"
            base = {"modelo": m, "corrida": info["corrida"], "corridas": info["corridas"], "pesos": archivo,
                    "peso": peso, "fase": info["fase"], "principal": cfg["pesos"]["principal"][info["fase"]] == peso,
                    "modalidad": info["modalidad"], "rgb0": False}
            if particion == VALIDACION:
                base.update({"datos": val[m]["datos"], "carpeta": val[m]["carpeta"],
                             "pred": val[m].get("nombres", {}).get(peso, k)})
            else:
                base.update({"datos": info["datos_prueba"], "carpeta": cfg["carpeta"], "pred": k})
            modelos[k] = base
            if m in cfg["rgb_cero"]:
                modelos[f"{k}_rgb0"] = {**base, "rgb0": True, "umbral_de": k}
    return modelos


def clave(nombre, peso):
    """Nombre de `comparaciones` (p. ej. fusion_base_rgb0) -> clave del modelo con ese peso."""
    return f"{nombre[:-5]}_{peso}_rgb0" if nombre.endswith("_rgb0") else f"{nombre}_{peso}"


def rotulo(k, info):
    return (f"{info['modelo']}" + (" con la RGB en 0" if info["rgb0"] else "")
            + ("" if info["fase"] == "7" else f" ({info['peso']}.pt)"))


def umbrales(cfg, base, rutas):
    u = cfg["umbral"]
    destino, completa = ruta(u["umbrales"]), ruta(u["rejilla_completa"])
    if destino.exists():
        raise SystemExit(f"{rel(destino)} ya existe: los umbrales se fijan una sola vez.")
    rejilla, anterior = rejillas(u)
    modelos = armar_modelos(cfg)
    reales = {k: i for k, i in modelos.items() if not i["rgb0"]}
    part = base["particiones"][VALIDACION]
    print(f"Validación: {', '.join(part['vuelos'])}. La prueba no se lee en esta parte.")
    print(f"Rejilla ({len(rejilla)} umbrales): {', '.join(f'{t:g}' for t in rejilla)}")

    datos = e6.preparar(base, rutas, VALIDACION, reales)
    e6.verificar(datos, VALIDACION)
    ev = base["evaluacion"]
    gt = e6.coco_gt(datos, np.zeros(len(datos["per"]), bool))  # todas las personas de WiSARD

    filas, resumen, t0 = [], [], time.time()
    for k, info in reales.items():
        cfg_pred = {**base, "carpeta": info["carpeta"], "corridas": info["corridas"]}
        carpeta = rutas["runs"] / info["carpeta"] / VALIDACION / info["pred"]
        hecha = not (carpeta / "predictions.json").exists()
        preds, ultra = e6.predecir(info["pred"], info, cfg_pred, rutas, VALIDACION, part)
        pesos = rutas["runs"] / info["corridas"] / info["corrida"] / info["pesos"]
        if Path(ultra["pesos"]) != Path(rel(pesos)):
            raise SystemExit(f"{k}: las predicciones de {rel(carpeta)} son de {ultra['pesos']}, no de {rel(pesos)}.")
        dt = e6.coco_dt(gt, preds, datos, ev["max_dets"])
        r0 = None
        for t in rejilla:
            r = e6.evaluar(gt, dt, datos["fot"].img_id, datos, {**ev, "conf": t})
            p = r["punto"]
            filas.append({"modelo": k, "umbral": t, "en_rejilla_anterior": t in anterior, "f2": p["f2"],
                          "recall": p["recall"], "precision": p["precision"], "tp": r["tp_conf"], "fp": r["fp_conf"]})
            r0 = r0 or r
        resumen.append({"k": k, "info": info, "preds": preds, "ultra": ultra, "hecha": hecha, "pesos": pesos,
                        "pj": carpeta / "predictions.json", "map50": r0["punto"]["map50"],
                        "n_personas": r0["n_personas"], "n_fotogramas": r0["n_fotogramas"]})
        print(f"{k}: {len(preds)} predicciones ({'hechas ahora' if hecha else 'reutilizadas'}, {rel(carpeta)}); "
              f"mAP@0.5 propio {r0['punto']['map50']:.4f}", flush=True)
    tabla = pd.DataFrame(filas)

    def mejor(d):
        """La de mayor F2 (redondeado a 12 decimales); si hay empate, la de umbral más alto."""
        f2 = d.f2.fillna(-1.0).round(12)
        return d[f2 == f2.max()].sort_values("umbral").iloc[-1]

    elegido, elegido_ant = {}, {}
    for k in reales:
        d = tabla[tabla.modelo == k]
        elegido[k], elegido_ant[k] = mejor(d), mejor(d[d.en_rejilla_anterior])
    tabla["elegido"] = [elegido[m].umbral == t for m, t in zip(tabla.modelo, tabla.umbral)]
    tabla["elegido_rejilla_anterior"] = [elegido_ant[m].umbral == t for m, t in zip(tabla.modelo, tabla.umbral)]

    fijado = datetime.now().isoformat(timespec="seconds")
    salida = []
    for k, info in modelos.items():
        kr = info.get("umbral_de", k)
        e, ea = elegido[kr], elegido_ant[kr]
        s = next(x for x in resumen if x["k"] == kr)
        salida.append({
            "modelo": k, "nombre": info["modelo"], "corrida": info["corrida"], "fase": info["fase"],
            "peso": info["peso"], "principal": info["principal"], "modalidad": info["modalidad"],
            "rgb_cero": info["rgb0"], "umbral_de": kr if info["rgb0"] else "",
            "umbral": e.umbral, "en_el_piso": e.umbral == rejilla[0], "en_el_techo": e.umbral == rejilla[-1],
            "f2": e.f2, "recall": e.recall, "precision": e.precision, "tp": int(e.tp), "fp": int(e.fp),
            "umbral_rejilla_anterior": ea.umbral, "f2_rejilla_anterior": ea.f2, "recall_rejilla_anterior": ea.recall,
            "precision_rejilla_anterior": ea.precision,
            "map50_validacion": s["map50"], "n_personas": s["n_personas"], "n_fotogramas": s["n_fotogramas"],
            "pesos": rel(s["pesos"]), "pesos_sha256": sha256(s["pesos"]),
            "predicciones_validacion": rel(s["pj"]), "predicciones_sha256": sha256(s["pj"]),
            "n_predicciones": len(s["preds"]), "fijado": fijado})
    out = pd.DataFrame(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(completa, index=False)
    out.to_csv(destino, index=False)

    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.precision", 3):
        print(out[["modelo", "umbral", "en_el_piso", "f2", "recall", "precision", "umbral_rejilla_anterior",
                   "f2_rejilla_anterior", "recall_rejilla_anterior", "map50_validacion"]].to_string(index=False))
    print(f"Escrito {rel(destino)} y {rel(completa)} ({time.time() - t0:.0f} s). La prueba no se ha leído.")

    for s in resumen:
        k, info, e, ea = s["k"], s["info"], elegido[s["k"]], elegido_ant[s["k"]]
        variantes = [v for v, i in modelos.items() if i.get("umbral_de") == k]
        agregar_a_bitacora(
            rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {k}",
            f"Fase 8, paso 2: umbral en validación ({', '.join(part['vuelos'])}); pesos {rel(s['pesos'])}; "
            f"predicciones {rel(s['pj'])} ({'hechas en este paso' if s['hecha'] else 'reutilizadas'}, confianza >= "
            f"{base['prediccion']['conf']}); mayor F2 (beta {ev['beta']}) con las {s['n_personas']} personas, IoU "
            f"{ev['iou']}, maxDets {ev['max_dets']}, rejilla {rejilla[0]:g} a {rejilla[-1]:g} ({len(rejilla)} "
            f"umbrales), empate al más alto",
            f"umbral {e.umbral:g}{' (el piso de la rejilla)' if e.umbral == rejilla[0] else ''}: F2 {e.f2:.3f}, "
            f"recall {e.recall:.3f}, P {e.precision:.3f}; rejilla anterior (0.05 a 0.95): {ea.umbral:g}, F2 "
            f"{ea.f2:.3f}, recall {ea.recall:.3f}; mAP50 propio {s['map50']:.3f}"
            + (f"; también para {', '.join(variantes)}" if variantes else "")
            + f"; en {rel(destino)}")


def git(*a):
    r = subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def canales_de_pesos(p):
    """Canales de entrada de la primera capa de unos pesos de Ultralytics."""
    import torch
    import ultralytics  # noqa: F401  (las clases del modelo, para cargar el checkpoint)

    ck = torch.load(p, map_location="cpu", weights_only=False)
    m = ck["ema"] if ck.get("ema") is not None else ck["model"]
    return int(next(m.parameters()).shape[1])


def verificar_prueba(cfg, base, rutas):
    """Paso 3: todo lo que se puede comprobar sin predecir. Devuelve los modelos, los umbrales y los datos."""
    salidas = ruta(cfg["salidas"])
    hay = [s for s in SALIDAS if (salidas / s).exists()]
    if cfg["una_sola_vez"] and hay:
        raise SystemExit(f"La prueba ya se evaluó (existen {', '.join(hay)} en {rel(salidas)}). Se evalúa una sola vez.")

    # umbrales: en GitHub y con los mismos pesos
    pu = ruta(cfg["umbral"]["umbrales"])
    if not pu.exists():
        raise SystemExit(f"No existe {rel(pu)}: corre antes --parte umbrales.")
    rama = git("rev-parse", "--abbrev-ref", "@{upstream}")
    local, remoto = git("hash-object", Path(rel(pu)).as_posix()), git("rev-parse", f"{rama}:{Path(rel(pu)).as_posix()}")
    if not rama or not local or local != remoto:
        raise SystemExit(f"{rel(pu)} no está en GitHub tal como está aquí (rama {rama or '?'}): súbelo antes de predecir.")
    u = pd.read_csv(pu).set_index("modelo")
    modelos = armar_modelos(cfg, PRUEBA)
    if set(u.index) != set(modelos):
        raise SystemExit(f"{rel(pu)} no tiene los mismos modelos que configs: faltan {sorted(set(modelos) - set(u.index))}"
                         f", sobran {sorted(set(u.index) - set(modelos))}.")
    umbral, umbral_ant = u.umbral.astype(float).to_dict(), u.umbral_rejilla_anterior.astype(float).to_dict()
    print(f"Umbrales de {rel(pu)}: en GitHub ({rama}, blob {local[:10]}).")

    # pesos y canales
    for k, info in modelos.items():
        if info["rgb0"]:
            continue
        pesos = rutas["runs"] / info["corridas"] / info["corrida"] / info["pesos"]
        if sha256(pesos) != u.at[k, "pesos_sha256"]:
            raise SystemExit(f"{k}: {rel(pesos)} no son los pesos con que se fijó el umbral.")
        c_pesos, c_datos = canales_de_pesos(pesos), int(leer_yaml(ruta(info["datos"])).get("channels", 3))
        esperado = 4 if info["modalidad"] == "fusion" else 3
        if not c_pesos == c_datos == esperado:
            raise SystemExit(f"{k}: la primera capa tiene {c_pesos} canales, el dataset {c_datos}; se esperaban {esperado}.")
        print(f"{k}: pesos iguales a los del umbral ({umbral[k]:g}); {c_pesos} canales en los pesos y en "
              f"{info['datos']}")

    # etiquetas, niveles, dudosas y bloques (sin leer imágenes)
    datos = e6.preparar(base, rutas, PRUEBA, {k: i for k, i in modelos.items() if not i["rgb0"]})
    e6.verificar(datos, PRUEBA)
    pred = rutas["runs"] / cfg["carpeta"] / PRUEBA
    print(f"Predicciones de la prueba que ya existen en {rel(pred)}: "
          + (", ".join(sorted(p.name for p in pred.iterdir())) if pred.exists() else "ninguna"))
    return modelos, umbral, umbral_ant, datos


def grafico_prueba(res, modelos, base, part, ruta_png, B, nb):
    """Recall de los modelos del peso principal por subconjunto, sin las dudosas, con su IC."""
    f = base["figura"]
    scs = part["subconjuntos"]
    claves = [k for k, i in modelos.items() if i["principal"]]
    fig, ejes = plt.subplots(1, len(scs), figsize=(11.5, 4.6), sharey=True, facecolor=f["fondo"])
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
        titulo = sc.get("rotulo", sc["nombre"].replace("_", " ")).replace(chr(10), " ")
        ax.set_title(f"{titulo}\n{n} personas", fontsize=9, color=f["texto"], loc="left")
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.grid(axis="x", color=f["rejilla"], linewidth=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(f["rejilla"])
        ax.tick_params(colors=f["texto_secundario"], labelsize=8, length=0)
        ax.set_xlabel("Recall (umbral de F2 en validación)", fontsize=8, color=f["texto_secundario"])
    ejes[0].set_yticks(y, [rotulo(k, modelos[k]) for k in claves])
    leyenda = [Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["fusion"], label="Fusión"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["fusion"],
                      markerfacecolor=f["fondo"], markeredgewidth=2, label="Fusión con la RGB en 0"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["termico"], label="Solo térmica"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=COLOR["rgb"], label="Solo RGB")]
    fig.legend(handles=leyenda, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=4, frameon=False, fontsize=8,
               labelcolor=f["texto"])
    fig.suptitle("Recall en la prueba (FHL 0405) por subconjunto (last.pt en la fase 7, best.pt en la fase 6; sin las "
                 "cajas dudosas)", x=0.01, y=0.99, ha="left", va="top", fontsize=10, color=f["texto"])
    fig.text(0.01, 0.01, f"Barras: IC del {int(base['bootstrap']['confianza'] * 100)} % por bootstrap de episodios "
             f"({B:,} remuestreos de {nb} bloques).".replace(",", " "), fontsize=7, color=f["texto_secundario"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.90))
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_png, dpi=f["dpi"], facecolor=f["fondo"])
    plt.close(fig)


def criterio(p_b, alfa, dif, ic_inf, ic_sup):
    """Demostrada solo si McNemar con Bonferroni y el IC por episodios de la diferencia de recall coinciden."""
    mc = p_b < alfa
    ic = (ic_inf > 0 and dif > 0) or (ic_sup < 0 and dif < 0)
    if mc and ic:
        return "demostrada"
    if mc or ic:
        return "no concluyente (solo McNemar)" if mc else "no concluyente (solo el IC)"
    return "no demostrada"


def prueba(cfg, base, rutas):
    """Paso 4: predice la prueba con todos los modelos y la mide una sola vez."""
    modelos, umbral, umbral_ant, datos = verificar_prueba(cfg, base, rutas)
    part = base["particiones"][PRUEBA]
    ev = base["evaluacion"]
    salidas = ruta(cfg["salidas"])
    salidas.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    preds, ultra, filas_p = {}, {}, []
    for k, info in modelos.items():
        cfg_pred = {**base, "carpeta": info["carpeta"], "corridas": info["corridas"]}
        preds[k], ultra[k] = e6.predecir(info["pred"], info, cfg_pred, rutas, PRUEBA, part, rgb_cero=info["rgb0"])
        filas_p.append({"modelo": k, "pesos": ultra[k]["pesos"], "rgb_cero": info["rgb0"], "datos": info["datos"],
                        "n_predicciones": len(preds[k]), "segundos": ultra[k].get("segundos"),
                        **{f"ultralytics_{m}": ultra[k].get(m) for m in ("map50", "map50_95", "precision", "recall")}})
        print(f"{k}: {len(preds[k])} predicciones; Ultralytics: mAP@0.5 {ultra[k].get('map50', float('nan')):.4f}",
              flush=True)
    print(f"Predicción: {time.time() - t0:.0f} s", flush=True)

    B = base["bootstrap"]["remuestreos"]
    rng = np.random.default_rng(base["bootstrap"]["seed"])
    nb = datos["nb"]
    cuentas_b = np.stack([np.bincount(rng.integers(0, nb, nb), minlength=nb) for _ in range(B)])
    conf_ic = base["bootstrap"]["confianza"]
    per = datos["per"]
    pares_d = cfg["comparaciones"]["descriptivas"]
    pares_mc = cfg["comparaciones"]["mcnemar"]["pares"]
    alfa, dud_mc = base["mcnemar"]["alfa"], base["mcnemar"]["dudosas"]
    filas, filas_s, filas_mc = [], [], []
    for sc in part["subconjuntos"]:
        imgs = datos["fot"] if sc["fotogramas"] == "todos" else datos["fot"][datos["fot"].anotado]
        for dud in ("con", "sin"):
            cuenta = pd.Series(True, index=per.index) if sc["personas"] == "todas" else (per.nivel == sc["personas"])
            if dud == "sin":
                cuenta &= ~per.dudosa
            gt = e6.coco_gt(datos, ~cuenta.to_numpy())
            evals, boot = {}, {}
            t = time.time()
            for k, info in modelos.items():
                dt = e6.coco_dt(gt, preds[k], datos, ev["max_dets"])
                r = e6.evaluar(gt, dt, imgs.img_id, datos, {**ev, "conf": umbral[k]})
                evals[k], boot[k] = r, e6.bootstrap(r, cuentas_b)
                fila = {"particion": PRUEBA, "subconjunto": sc["nombre"], "dudosas": dud, "tipo": "modelo", "modelo": k,
                        "nombre": info["modelo"], "peso": info["peso"], "principal": info["principal"],
                        "rgb_cero": info["rgb0"], "umbral": umbral[k], "n_fotogramas": r["n_fotogramas"],
                        "n_personas": r["n_personas"], "tp": r["tp_conf"], "fp": r["fp_conf"],
                        "fn": r["n_personas"] - r["tp_conf"]}
                for mt in e6.METRICAS:
                    fila[mt] = r["punto"][mt]
                    fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = e6.intervalo(boot[k][mt], conf_ic)
                fila["remuestreos"] = B
                fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[k][mt]).sum() for mt in e6.METRICAS))
                filas.append(fila)
                for nombre_u, tu in (("rejilla_anterior", umbral_ant[k]), ("0.5", ev["conf"])):
                    rs = r if tu == umbral[k] else e6.evaluar(gt, dt, imgs.img_id, datos, {**ev, "conf": tu})
                    filas_s.append({"subconjunto": sc["nombre"], "dudosas": dud, "modelo": k, "umbral_tipo": nombre_u,
                                    "umbral": tu, "umbral_principal": umbral[k], "n_personas": rs["n_personas"],
                                    "tp": rs["tp_conf"], "fp": rs["fp_conf"],
                                    **{mt: rs["punto"][mt] for mt in ("recall", "precision", "f2")}})
            for a0, b0 in pares_d:
                for peso in cfg["pesos"]["archivos"]:
                    a, b = clave(a0, peso), clave(b0, peso)
                    fila = {"particion": PRUEBA, "subconjunto": sc["nombre"], "dudosas": dud, "tipo": "diferencia",
                            "modelo": f"{a} - {b}", "peso": peso, "umbral": np.nan,
                            "n_fotogramas": evals[a]["n_fotogramas"], "n_personas": evals[a]["n_personas"]}
                    for mt in e6.METRICAS:
                        fila[mt] = evals[a]["punto"][mt] - evals[b]["punto"][mt]
                        fila[f"{mt}_ic_inf"], fila[f"{mt}_ic_sup"] = e6.intervalo(boot[a][mt] - boot[b][mt], conf_ic)
                    fila["remuestreos"] = B
                    fila["remuestreos_sin_valor"] = int(max(np.isnan(boot[a][mt] - boot[b][mt]).sum()
                                                            for mt in e6.METRICAS))
                    filas.append(fila)
            if sc.get("mcnemar") and dud == dud_mc:
                for a0, b0 in pares_mc:
                    a, b = (f"{n}_{cfg['pesos']['principal'][cfg['modelos'][n]['fase']]}" for n in (a0, b0))
                    da, db = evals[a]["detectada"], evals[b]["detectada"]
                    if set(da) != set(db):
                        raise SystemExit(f"McNemar: no son las mismas personas en {a} y {b} ({sc['nombre']}).")
                    ids = sorted(da)
                    xa, xb = np.array([da[i] for i in ids]), np.array([db[i] for i in ids])
                    tabla = [[int((xa & xb).sum()), int((xa & ~xb).sum())],
                             [int((~xa & xb).sum()), int((~xa & ~xb).sum())]]
                    res = mcnemar(tabla, exact=base["mcnemar"]["exacta"])
                    p_b = min(1.0, float(res.pvalue) * len(pares_mc))
                    dif = float(xa.mean() - xb.mean())
                    ic_inf, ic_sup = e6.intervalo(boot[a]["recall"] - boot[b]["recall"], conf_ic)
                    filas_mc.append({"particion": PRUEBA, "subconjunto": sc["nombre"], "dudosas": dud, "modelo_a": a,
                                     "modelo_b": b, "umbral_a": umbral[a], "umbral_b": umbral[b], "n_personas": len(ids),
                                     "ambos": tabla[0][0], "solo_a": tabla[0][1], "solo_b": tabla[1][0],
                                     "ninguno": tabla[1][1], "recall_a": float(xa.mean()), "recall_b": float(xb.mean()),
                                     "diferencia_recall": dif, "dif_ic_inf": ic_inf, "dif_ic_sup": ic_sup,
                                     "estadistico": float(res.statistic), "p": float(res.pvalue),
                                     "comparaciones": len(pares_mc), "p_bonferroni": p_b, "alfa": alfa,
                                     "mcnemar_significativo": p_b < alfa,
                                     "ic_excluye_0": bool((ic_inf > 0 and dif > 0) or (ic_sup < 0 and dif < 0)),
                                     "resultado": criterio(p_b, alfa, dif, ic_inf, ic_sup)})
            print(f"{sc['nombre']} ({dud} dudosas): listo ({time.time() - t:.0f} s)", flush=True)

    res, sens, mc, pr = pd.DataFrame(filas), pd.DataFrame(filas_s), pd.DataFrame(filas_mc), pd.DataFrame(filas_p)
    res.to_csv(salidas / "resultados.csv", index=False)
    sens.to_csv(salidas / "sensibilidad.csv", index=False)
    mc.to_csv(salidas / "mcnemar.csv", index=False)
    pr.to_csv(salidas / "prediccion.csv", index=False)
    grafico_prueba(res, modelos, base, part, salidas / "recall_por_nivel.png", B, nb)
    with pd.option_context("display.width", 250, "display.max_columns", 40, "display.precision", 3):
        d = res[(res.tipo == "modelo") & (res.dudosas == "sin")]
        print(d[["subconjunto", "modelo", "umbral", "n_personas", "recall", "recall_ic_inf", "recall_ic_sup",
                 "precision", "f2", "map50", "map50_ic_inf", "map50_ic_sup"]].to_string(index=False))
        print(mc[["subconjunto", "modelo_a", "modelo_b", "n_personas", "solo_a", "solo_b", "diferencia_recall",
                  "dif_ic_inf", "dif_ic_sup", "p_bonferroni", "resultado"]].to_string(index=False))
    print(f"Salidas en {rel(salidas)} ({time.time() - t0:.0f} s)")

    for k, info in modelos.items():
        resumen = []
        for sc in part["subconjuntos"]:
            d = res[(res.tipo == "modelo") & (res.modelo == k) & (res.subconjunto == sc["nombre"])
                    & (res.dudosas == "sin")].iloc[0]
            resumen.append(f"{sc['nombre']} (sin dudosas, {d.n_personas}): recall {d.recall:.3f} "
                           f"[{d.recall_ic_inf:.3f}, {d.recall_ic_sup:.3f}], P {d.precision:.3f}, F2 {d.f2:.3f}, "
                           f"mAP50 {d.map50:.3f} [{d.map50_ic_inf:.3f}, {d.map50_ic_sup:.3f}]")
        agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], f"YOLO26s {k}",
                           f"Fase 8, prueba ({', '.join(part['vuelos'])}, split {part['split']}); pesos "
                           f"{ultra[k]['pesos']}" + ("; RGB en 0 (los 3 canales de color)" if info["rgb0"] else "")
                           + f"; umbral {umbral[k]:g} (F2 en validación, {rel(ruta(cfg['umbral']['umbrales']))})"
                           f", IoU {ev['iou']}, maxDets {ev['max_dets']}; bootstrap {B} remuestreos de {nb} bloques, "
                           f"seed={base['bootstrap']['seed']}; una sola vez; salidas en {rel(salidas)}",
                           "; ".join(resumen) + f"; Ultralytics (su AP) mAP50 {ultra[k].get('map50', float('nan')):.4f}")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "McNemar y criterio (fase 8)",
                       f"Prueba; pares {', '.join(f'{a}-{b}' for a, b in pares_mc)} con el peso principal, sin las "
                       f"dudosas, Bonferroni x{len(pares_mc)}; demostrada solo si McNemar (p_bonf < {alfa}) y el IC del "
                       f"95 % por episodios de la diferencia de recall coinciden; {rel(salidas / 'mcnemar.csv')}",
                       "; ".join(f"{m.subconjunto} {m.modelo_a}-{m.modelo_b}: {m.diferencia_recall:+.3f} "
                                 f"[{m.dif_ic_inf:+.3f}, {m.dif_ic_sup:+.3f}], solo_a {m.solo_a}, solo_b {m.solo_b}, "
                                 f"p_bonf {m.p_bonferroni:.2g} -> {m.resultado}" for m in mc.itertuples()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["umbrales", "verificar", "prueba"])
    args = ap.parse_args()
    cfg, base = leer_config(args)
    rutas = leer_rutas(args.rutas)
    fijar_semilla(base["bootstrap"]["seed"])
    if args.parte == "umbrales":
        umbrales(cfg, base, rutas)
    elif args.parte == "verificar":
        verificar_prueba(cfg, base, rutas)
        print("Prueba verificada sin predecir.")
    else:
        prueba(cfg, base, rutas)


if __name__ == "__main__":
    main()
