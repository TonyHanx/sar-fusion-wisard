r"""Fase 3b: λ RGB automático de las personas del vuelo de prueba, y su comparación con la anotación manual.

Calcular (por omisión), para cada persona térmica de los pares finales del vuelo de prueba (las 1 501 de FHL 0405):
- la caja RGB de WiSARD (sin repetidas, data/etiquetas) llevada a la térmica con la semejanza congelada cuyo centro
  esté más cerca del centro de la caja térmica, si está a `radio_alturas` alturas de la caja térmica o menos (la misma
  regla que la precarga de la herramienta; dos personas térmicas pueden quedarse con la misma caja RGB);
- λ = 1 − área(caja RGB) / área(caja térmica), recortado a [0, 1]; sin caja RGB cerca, λ = 1;
- el nivel con los límites de `limites_nivel` (baja, moderada, severa).
Guarda data/<salida> (ids iguales a los de data/<oclusion.personas>) y agrega una fila a la bitácora.

--comparar: compara el automático con la anotación manual de la muestra (data/<oclusion.anotaciones>, primer
anotador, las personas de data/<oclusion.muestra_segundo>). Necesita las personas de la muestra terminadas. Las
marcadas "no es persona" o "fuera de cuadro" se cuentan aparte y no entran en la comparación. Calcula el kappa de
Cohen sobre el nivel (sin pesos; IC 95 % asintótico de statsmodels), la matriz de confusión y la diferencia de λ
(automático − manual). Si kappa >= `kappa_minimo` se usa el automático; si no, se vuelve a la anotación manual.
Escribe reports/<comparacion>.md y .csv y agrega una fila a la bitácora.

Uso:
    .venv\Scripts\python.exe scripts\oclusion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
    .venv\Scripts\python.exe scripts\oclusion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --comparar
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from comun import RAIZ, agregar_a_bitacora, leer_cajas_yolo, leer_rutas, leer_yaml
from fase2_homografias_cajas import cajas_llevadas, centros

NIVELES = ["baja", "moderada", "severa"]
CAJA = ["x0", "y0", "x1", "y1"]


def nivel(lam, limites):
    lam = np.asarray(lam, float)
    return np.where(lam <= limites["baja"], "baja", np.where(lam <= limites["moderada"], "moderada", "severa"))


def cajas_px(ruta, tam):
    """Cajas (x0, y0, x1, y1) en px, en el orden del archivo (el índice identifica a la persona)."""
    w, h = tam
    return np.array([[(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]
                     for _, cx, cy, bw, bh in leer_cajas_yolo(ruta)], np.float64).reshape(-1, 4)


def resumen_niveles(df, columna_lambda, columna_nivel):
    return {"personas": len(df), "lambda_mediana": round(float(df[columna_lambda].median()), 3),
            **{n: int((df[columna_nivel] == n).sum()) for n in NIVELES}}


def calcular(cfg, rutas):
    o, a, d = cfg["oclusion"], cfg["oclusion_auto"], cfg["datasets"]
    data = rutas["data"]
    v = o["vuelo"]
    Hs = yaml.safe_load((RAIZ / cfg["transformaciones"]).read_text(encoding="utf-8"))
    H = np.array(Hs[v]["H_rgb_a_termica"], np.float64)
    tam_rgb, tam_ter = tuple(Hs[v]["tam_rgb"]), tuple(cfg["tam_termica"])
    indice = pd.read_csv(data / d["alineados"] / "indice.csv")
    sel = indice[indice.vuelo == v].sort_values("posicion")
    etq = data / d["etiquetas"]
    muestra = set(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).id)

    filas = []
    for f in sel.itertuples():
        nombre = f"{v}_{f.posicion:04d}.txt"
        ct = cajas_px(etq / "termica" / v / nombre, tam_ter)
        cr = cajas_px(etq / "rgb" / v / nombre, tam_rgb)
        crl = cajas_llevadas(H, cr) if len(cr) else cr
        for k, b in enumerate(ct):
            area_t = (b[2] - b[0]) * (b[3] - b[1])
            fila = {"id": f"{v}_{f.posicion:04d}_{k}", "vuelo": v, "posicion": f.posicion, "indice_caja": k,
                    **{f"ter_{c}": round(float(x), 3) for c, x in zip(CAJA, b)}, "area_termica": round(area_t, 3),
                    "cajas_rgb_en_par": len(cr), "rgb_dist_alturas": np.nan, "caja_rgb_indice": np.nan,
                    **{f"rgb_{c}": np.nan for c in CAJA}, "area_rgb": np.nan}
            if len(crl):
                dist = np.linalg.norm(centros(crl) - centros(b[None])[0], axis=1) / (b[3] - b[1])
                j = int(dist.argmin())
                fila["rgb_dist_alturas"] = round(float(dist[j]), 3)
                if dist[j] <= a["radio_alturas"]:
                    r = crl[j]
                    fila.update({f"rgb_{c}": round(float(x), 3) for c, x in zip(CAJA, r)})
                    fila["caja_rgb_indice"] = j
                    fila["area_rgb"] = round(float((r[2] - r[0]) * (r[3] - r[1])), 3)
            filas.append(fila)
    df = pd.DataFrame(filas)
    sin = df.area_rgb.isna()
    df["sin_caja_rgb_cerca"] = sin
    df["lambda_rgb_auto"] = np.where(sin, 1.0, np.clip(1 - df.area_rgb / df.area_termica, 0, 1)).round(4)
    df["nivel_auto"] = nivel(df.lambda_rgb_auto, a["limites_nivel"])
    df["anotado_1de3"] = df.posicion % o["paso"] == 0
    df["en_muestra"] = df.id.isin(muestra)

    # misma caja RGB para más de una persona térmica del mismo par
    con = df[~sin]
    veces = con.groupby(["posicion", "caja_rgb_indice"]).id.transform("size")
    compartidas = int((veces > 1).sum())

    # coherencia con la precarga de la herramienta (misma regla) en las personas de 1 de cada 3
    per = pd.read_csv(data / o["personas"], dtype={"id": str})
    m = per.merge(df, on="id", suffixes=("_p", ""))
    if len(m) != len(per) or not all(np.allclose(m[f"rgb_{c}_p"].fillna(-1), m[f"rgb_{c}"].fillna(-1), atol=1e-3)
                                     for c in CAJA):
        raise SystemExit(f"La caja RGB no coincide con la precarga de {o['personas']}")
    if len(muestra - set(df.id)):
        raise SystemExit("Hay personas de la muestra que no están en el cálculo automático")

    df.to_csv(data / a["salida"], index=False, encoding="utf-8")
    grupos = {"todas": df, "1 de cada 3": df[df.anotado_1de3], "muestra": df[df.en_muestra]}
    res = pd.DataFrame([{"grupo": g, **resumen_niveles(x, "lambda_rgb_auto", "nivel_auto"),
                         "sin_caja_rgb_cerca": int(x.sin_caja_rgb_cerca.sum()),
                         "lambda_0": int((x.lambda_rgb_auto == 0).sum())} for g, x in grupos.items()])
    pd.set_option("display.width", 200)
    print(f"{v}: {len(df)} personas en {sel.posicion.size} pares -> {data / a['salida']}")
    print(res.to_string(index=False))
    print(f"Personas que comparten la caja RGB con otra persona del mismo par: {compartidas}")
    t = res.set_index("grupo").loc["todas"]
    agregar_a_bitacora(
        rutas["bitacora"], "3b", "lambda RGB automático (prueba)",
        f"{v}; caja RGB más cercana a {a['radio_alturas']} alturas; λ = 1 − área RGB / área térmica, recortado; "
        f"límites {a['limites_nivel']}",
        f"{len(df)} personas: baja {int(t.baja)}, moderada {int(t.moderada)}, severa {int(t.severa)}; sin caja RGB "
        f"cerca {int(t.sin_caja_rgb_cerca)}; {compartidas} comparten caja RGB")
    return df, res, compartidas


def comparar(cfg, rutas, manual=None, carpeta=None, bitacora=True):
    from statsmodels.stats.inter_rater import cohens_kappa

    o, a = cfg["oclusion"], cfg["oclusion_auto"]
    data = rutas["data"]
    manual = Path(manual) if manual else data / o["anotaciones"]
    carpeta = Path(carpeta) if carpeta else rutas["reports"]
    auto = pd.read_csv(data / a["salida"], dtype={"id": str})
    muestra = pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).id
    man = pd.read_csv(manual, dtype={"id": str})
    man = man[man.id.isin(set(muestra))]
    hechas = set(man.id[man.terminada.astype(bool)])
    faltan = [i for i in muestra if i not in hechas]
    if faltan:
        raise SystemExit(f"Faltan {len(faltan)} de {len(muestra)} personas de la muestra por terminar en {manual} "
                         f"(la primera: {faltan[0]})")
    aparte = man[man.no_es_persona.astype(bool) | man.fuera_de_cuadro.astype(bool)]
    comp = man[~man.id.isin(set(aparte.id))][["id", "lambda_rgb"]].merge(
        auto[["id", "lambda_rgb_auto", "nivel_auto", "sin_caja_rgb_cerca"]], on="id")
    comp = comp.rename(columns={"lambda_rgb": "lambda_rgb_manual"})
    comp["nivel_manual"] = nivel(comp.lambda_rgb_manual, a["limites_nivel"])
    comp["diferencia"] = (comp.lambda_rgb_auto - comp.lambda_rgb_manual).round(4)

    def matriz_de(x):
        m = pd.crosstab(pd.Categorical(x.nivel_manual, NIVELES), pd.Categorical(x.nivel_auto, NIVELES), dropna=False)
        m.index.name, m.columns.name = "manual", "automático"
        return m

    def kappa_de(x):
        """Kappa e IC 95 %; NaN si no se puede calcular (p. ej. un solo nivel en los dos)."""
        t = matriz_de(x).to_numpy()
        pe = (t.sum(1) * t.sum(0)).sum() / t.sum() ** 2 if t.sum() else 1.0
        if pe >= 1:
            return np.nan, np.nan, np.nan
        k = cohens_kappa(t)
        return float(k.kappa), float(k.kappa_low), float(k.kappa_upp)

    matriz = matriz_de(comp)
    kappa, bajo, alto = kappa_de(comp)
    acuerdo = float((comp.nivel_manual == comp.nivel_auto).mean())
    # El acuerdo de las personas sin caja RGB cerca (automático = 1) es casi seguro si la RGB tampoco se ve a mano:
    # se reporta aparte el de las que sí tienen caja RGB cerca. La decisión usa el kappa de todas.
    sub = []
    for nombre, x in (("con caja RGB cerca", comp[~comp.sin_caja_rgb_cerca]),
                      ("sin caja RGB cerca (λ automático = 1)", comp[comp.sin_caja_rgb_cerca])):
        ks = kappa_de(x)
        sub.append(f"| {nombre} | {len(x)} | "
                   + ("no se puede calcular" if np.isnan(ks[0]) else f"{ks[0]:.3f} ({ks[1]:.3f} a {ks[2]:.3f})")
                   + f" | {(x.nivel_manual == x.nivel_auto).mean():.1%} | "
                   + f"{(x.lambda_rgb_auto - x.lambda_rgb_manual).mean():+.3f} |")
    dif = comp.diferencia
    usar = "automático" if kappa >= a["kappa_minimo"] else "manual"

    carpeta.mkdir(parents=True, exist_ok=True)
    comp.to_csv(carpeta / f"{a['comparacion']}.csv", index=False, encoding="utf-8")
    filas_md = "\n".join(f"| {n} | " + " | ".join(str(int(matriz.loc[n, c])) for c in NIVELES)
                         + f" | {int(matriz.loc[n].sum())} |" for n in NIVELES)
    texto = f"""# λ RGB automático contra la anotación manual

Fecha: {date.today().isoformat()}. Muestra de {len(muestra)} personas de {o['vuelo']} (seed={cfg['seed']}),
anotadas a mano por el primer anotador. Se generó con `scripts/oclusion_auto.py --comparar`.

- Comparadas: **{len(comp)}**. Aparte: {int(aparte.no_es_persona.astype(bool).sum())} "no es persona" y
  {int(aparte.fuera_de_cuadro.astype(bool).sum())} "fuera de cuadro"; no entran en la comparación.
- Niveles con λ RGB: baja si λ <= {a['limites_nivel']['baja']:.2f}, moderada si λ <= {a['limites_nivel']['moderada']:.2f},
  severa si es mayor.

## Resultado

| | Valor |
|---|---|
| **Kappa de Cohen (nivel)** | **{kappa:.3f}** (IC 95 % {bajo:.3f} a {alto:.3f}) |
| Acuerdo en el nivel | {acuerdo:.1%} |
| Diferencia media de λ (automático − manual) | {dif.mean():+.3f} (desviación estándar {dif.std():.3f}) |
| Diferencia absoluta media de λ | {dif.abs().mean():.3f} |
| Mediana de la diferencia | {dif.median():+.3f} |

- **Decisión:** {'el kappa es de' if usar == 'automático' else 'el kappa no llega a'} {a['kappa_minimo']}{' o más' if usar == 'automático' else ''}, así que
  **se usa el {'λ automático' if usar == 'automático' else 'λ de la anotación manual (se vuelve a anotar a mano)'}**.
- El IC del kappa es asintótico: con {len(comp)} personas es ancho.

## Por grupo (solo informativo; la decisión usa todas)

| Grupo | Personas | Kappa (IC 95 %) | Acuerdo | Diferencia media de λ |
|---|---:|---|---:|---:|
{chr(10).join(sub)}

## Matriz de confusión (filas: manual; columnas: automático)

| Manual \\ automático | {' | '.join(NIVELES)} | Total |
|---|{'---:|' * (len(NIVELES) + 1)}
{filas_md}

Detalle por persona: `reports/{a['comparacion']}.csv`.
"""
    (carpeta / f"{a['comparacion']}.md").write_text(texto, encoding="utf-8")
    print(texto)
    if bitacora:
        agregar_a_bitacora(rutas["bitacora"], "3b", "lambda RGB automático contra manual (muestra)",
                           f"{len(comp)} personas; kappa mínimo {a['kappa_minimo']}",
                           f"kappa {kappa:.3f} (IC {bajo:.3f}-{alto:.3f}); acuerdo {acuerdo:.1%}; diferencia media "
                           f"de λ {dif.mean():+.3f}; se usa el {usar}")
    return {"kappa": kappa, "acuerdo": acuerdo, "matriz": matriz, "diferencia_media": float(dif.mean()),
            "usar": usar, "comparadas": comp}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--comparar", action="store_true", help="compara con la anotación manual de la muestra")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # λ en consolas cp1252
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.comparar:
        comparar(cfg, rutas)
    else:
        calcular(cfg, rutas)


if __name__ == "__main__":
    main()
