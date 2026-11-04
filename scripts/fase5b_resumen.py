"""Fase 5b: resumen de los entrenamientos de 100 épocas (curvas, mejor modelo, tiempo, potencia y temperatura).

Solo lee runs/<carpeta>/<corrida>/ (results.csv, resumen.json, monitor.csv y args.yaml). No evalúa nada, y menos en
la partición de prueba.

Escribe en reports/<resumen_5b.carpeta>/:
- perdidas.png: pérdidas de entrenamiento y de validación por época, una línea por modelo;
- metricas_validacion.png: precisión, recall, mAP@0.5 y mAP@0.5:0.95 de validación por época, con la época de best.pt;
- resumen.csv: por modelo, el mejor modelo (best.pt), la última época, el tiempo, la potencia y la temperatura;
- resultados_<corrida>.csv y resultados_<corrida>.png: copias de results.csv y results.png de Ultralytics.

Uso: python scripts/fase5b_resumen.py --config configs/fase5.yaml --rutas configs/rutas.yaml
"""
import argparse
import json
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from comun import leer_rutas, leer_yaml  # noqa: E402

PERDIDAS = [("box_loss", "Pérdida de caja"), ("cls_loss", "Pérdida de clase"), ("l1_loss", "Pérdida L1")]
METRICAS = [("metrics/precision(B)", "Precisión"), ("metrics/recall(B)", "Recall"), ("metrics/mAP50(B)", "mAP@0.5"),
            ("metrics/mAP50-95(B)", "mAP@0.5:0.95")]
FITNESS = "metrics/mAP50-95(B)"  # Ultralytics guarda best.pt en la primera época con el mayor mAP@0.5:0.95


def estilo(ax, f):
    ax.set_facecolor(f["fondo"])
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(f["rejilla"])
    ax.grid(axis="y", color=f["rejilla"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=f["texto_secundario"], labelsize=8)
    ax.title.set_color(f["texto"])


def figura(paneles, filas, cols, datos, corridas, f, cierre, mejores, ruta, titulo):
    fig, axs = plt.subplots(filas, cols, figsize=(3.6 * cols, 2.7 * filas), sharex=True, facecolor=f["fondo"],
                            squeeze=False)
    for ax, (col, rotulo) in zip(axs.flat, paneles):
        estilo(ax, f)
        for c, info in corridas.items():
            d = datos[c]
            ax.plot(d["epoch"], d[col], color=info["color"], linewidth=1.4, label=info["nombre"])
            if mejores is not None:
                e = mejores[c]
                ax.plot([e], [d.loc[d["epoch"] == e, col].iloc[0]], "o", color=info["color"], markersize=6,
                        markeredgecolor=f["fondo"], markeredgewidth=1.5, zorder=3)
        if cierre is not None:
            ax.axvline(cierre + 0.5, color=f["texto_secundario"], linewidth=0.8, linestyle=(0, (3, 3)))
        ax.set_title(rotulo, fontsize=9, loc="left")
    for ax in axs[-1]:
        ax.set_xlabel("Época", fontsize=8, color=f["texto_secundario"])
    h, l = axs.flat[0].get_legend_handles_labels()
    nota = "Línea punteada: desde ahí, sin mosaico." if cierre is not None else ""
    if mejores is not None:
        nota += " Punto: época de best.pt."
    fig.suptitle(titulo, x=0.01, y=0.99, ha="left", va="top", fontsize=10, color=f["texto"])
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.005, 0.95), ncol=len(l), frameon=False, fontsize=8,
               labelcolor=f["texto"])
    fig.text(0.01, 0.005, nota.strip(), fontsize=7, color=f["texto_secundario"])
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    fig.savefig(ruta, dpi=f["dpi"], facecolor=f["fondo"])
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    r5 = cfg["resumen_5b"]
    f = r5["figura"]
    corridas = r5["corridas"]
    salida = rutas["reports"] / r5["carpeta"]
    salida.mkdir(parents=True, exist_ok=True)

    datos, mejores, filas, cierres = {}, {}, [], set()
    for c, info in corridas.items():
        carpeta = rutas["runs"] / cfg["base"]["carpeta"] / c
        d = pd.read_csv(carpeta / "results.csv")
        d.columns = [k.strip() for k in d.columns]
        datos[c] = d
        r = json.load(open(carpeta / "resumen.json", encoding="utf-8"))
        a = leer_yaml(carpeta / "args.yaml")
        cierres.add(a["epochs"] - a["close_mosaic"] if a["close_mosaic"] else None)
        fila_mejor = d.loc[d[FITNESS].idxmax()]
        mejores[c] = int(fila_mejor["epoch"])
        mon = pd.read_csv(carpeta / "monitor.csv")
        carga = mon[mon["utilization_gpu"] >= 50]
        ultima = d.iloc[-1]
        bp = r["val_best_pt"]
        filas.append({
            "modelo": info["nombre"], "corrida": c, "canales": r["canales"], "epocas": int(ultima["epoch"]),
            "lote": r["lote_final"], "inicio_cuarto_canal": r["configuracion"]["inicio_cuarto_canal"]
            if r["canales"] == 4 else "",
            "mejor_epoca": mejores[c],
            "best_map50": bp["metrics/mAP50(B)"], "best_map50_95": bp["metrics/mAP50-95(B)"],
            "best_precision": bp["metrics/precision(B)"], "best_recall": bp["metrics/recall(B)"],
            "ultima_map50": ultima["metrics/mAP50(B)"], "ultima_map50_95": ultima["metrics/mAP50-95(B)"],
            "ultima_precision": ultima["metrics/precision(B)"], "ultima_recall": ultima["metrics/recall(B)"],
            "max_map50": d["metrics/mAP50(B)"].max(), "epoca_max_map50": int(d.loc[d["metrics/mAP50(B)"].idxmax(),
                                                                                   "epoch"]),
            "s_corrida": r["s_total_corrida"], "min_corrida": round(r["s_total_corrida"] / 60, 1),
            "s_epoca_mediana": pd.Series([e["s_total"] for e in r["epocas"]]).median(),
            "potencia_previa_w": r["potencia_antes"]["limite_mediana_w"],
            "limite_entrenando_mediana_w": round(carga["enforced_power_limit"].median(), 1),
            "limite_entrenando_p10_w": round(carga["enforced_power_limit"].quantile(0.1), 1),
            "limite_entrenando_p90_w": round(carga["enforced_power_limit"].quantile(0.9), 1),
            "consumo_mediana_w": round(carga["power_draw"].median(), 1),
            "uso_gpu_mediana_pct": carga["utilization_gpu"].median(),
            "temperatura_max_c": mon["temperature_gpu"].max(),
            "gpu_pico_mib": r["gpu_pico_memoria_mib"], "ram_pico_pct": r["ram_pico_pct"],
            "optimizador": r["optimizador"], "lr0": r["lr0"],
        })
        shutil.copyfile(carpeta / "results.csv", salida / f"resultados_{c}.csv")
        if (carpeta / "results.png").exists():
            shutil.copyfile(carpeta / "results.png", salida / f"resultados_{c}.png")

    cierre = cierres.pop() if len(cierres) == 1 else None
    paneles = [(f"train/{k}", f"{t}, entrenamiento") for k, t in PERDIDAS] + \
              [(f"val/{k}", f"{t}, validación") for k, t in PERDIDAS]
    figura(paneles, 2, 3, datos, corridas, f, cierre, None, salida / "perdidas.png",
           "Pérdidas por época (entrenamiento arriba, validación abajo)")
    figura(METRICAS, 2, 2, datos, corridas, f, cierre, mejores, salida / "metricas_validacion.png",
           "Métricas de validación por época (FHL 0134 y MtErie 0007)")
    tabla = pd.DataFrame(filas)
    tabla.to_csv(salida / "resumen.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 50):
        print(tabla.T.to_string())
    print(f"Salidas en {salida}")


if __name__ == "__main__":
    main()
