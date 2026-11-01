r"""Fase 3b: λ RGB automático de las personas del vuelo de prueba, y su comparación con la anotación manual.

Calcular (por omisión), para cada persona térmica de los pares finales del vuelo de prueba (las 1 501 de FHL 0405):
- la caja RGB de WiSARD (sin repetidas, data/etiquetas) llevada a la térmica con la semejanza congelada cuyo centro
  esté más cerca del centro de la caja térmica, si está a `radio_alturas` alturas de la caja térmica o menos (la misma
  regla que la precarga de la herramienta; dos personas térmicas pueden quedarse con la misma caja RGB);
- λ = 1 − área(caja RGB) / área(caja térmica), recortado a [0, 1]; sin caja RGB cerca, λ = 1;
- el nivel con los límites de `limites_nivel` (baja, moderada, severa).
Guarda data/<salida> (ids iguales a los de data/<oclusion.personas>) y agrega una fila a la bitácora.

La comparación con la anotación manual de la muestra (antes --comparar, con 3 niveles) está en
scripts/fase4_validacion_auto.py: desde el 2026-11-01 el nivel tiene dos clases (se ve o no en la RGB) y el kappa de 3
niveles solo se reporta.

--revisar: antes de comparar, lista las personas de la muestra anotada con la completa RGB corrida más de
`revision.mover_completa_px` respecto de la térmica (distancia entre centros), o con una visible RGB dibujada en un par
"solo térmica" (sin ninguna caja RGB de WiSARD). Por persona guarda en reports/<revision.carpeta>/ la vista de la
herramienta (con las cajas) y, debajo, los mismos paneles sin cajas; además un mosaico y lista.csv. No toca
data/<oclusion.anotaciones> (la herramienta se arma sobre una copia temporal).

Uso:
    .venv\Scripts\python.exe scripts\oclusion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
    .venv\Scripts\python.exe scripts\oclusion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --revisar
"""
import argparse
import sys
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


def revisar(cfg, rutas, personas=None, nombre=None, base=None, criterio="pedida para revisar"):
    """Sin `personas`: las de los criterios de `revision`, en reports/<carpeta>/. Con `personas` (números en la
    muestra): esas, en <base>/<nombre>/ (por omisión base = reports/<carpeta>), con `criterio` como motivo (un texto, o
    un diccionario número -> texto); si hay dos o más del mismo fotograma, también la superposición de sus cajas
    térmicas de WiSARD y de sus completas (superposicion.csv) y la secuencia de térmicas vecinas."""
    import shutil
    import tempfile

    import cv2
    from anotar_oclusion import crear_anotador

    o, a, rv = cfg["oclusion"], cfg["oclusion_auto"], cfg["oclusion_auto"]["revision"]
    data = rutas["data"]
    carpeta = rutas["reports"] / rv["carpeta"]
    muestra = list(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).id)
    per = pd.read_csv(data / o["personas"], dtype={"id": str}).set_index("id")
    auto = pd.read_csv(data / a["salida"], dtype={"id": str}).set_index("id")
    man = pd.read_csv(data / o["anotaciones"], dtype={"id": str})
    man = man[man.id.isin(set(muestra))].set_index("id")
    if len(man) != len(muestra) or not man.terminada.astype(bool).all():
        raise SystemExit(f"La muestra no está terminada en {data / o['anotaciones']}")

    x = man.reindex([i for i in muestra if i in man.index]).copy()
    x["n_muestra"] = [muestra.index(i) + 1 for i in x.index]
    x["corrimiento_px"] = np.hypot(x.completa_rgb_dx, x.completa_rgb_dy).round(2)
    x["par_solo_termica"] = per.loc[x.index, "par_solo_termica"].astype(bool).to_numpy()
    corrida = x.corrimiento_px > rv["mover_completa_px"]
    dibujada = x.par_solo_termica & (x.rgb_estado == "caja")
    x["criterio"] = np.select([corrida & dibujada, corrida, dibujada],
                              [f"completa RGB corrida > {rv['mover_completa_px']} px y visible RGB en par solo térmica",
                               f"completa RGB corrida > {rv['mover_completa_px']} px",
                               "visible RGB dibujada en par solo térmica"], "")
    x["lambda_rgb_auto"] = auto.loc[x.index, "lambda_rgb_auto"].to_numpy()
    x["nivel_auto"] = auto.loc[x.index, "nivel_auto"].to_numpy()
    x["nivel_manual"] = nivel(x.lambda_rgb, a["limites_nivel"])
    sel = x[corrida | dibujada]
    if personas:
        if not nombre:
            raise SystemExit("--personas necesita --nombre (subcarpeta de la revisión)")
        faltan = sorted(set(personas) - set(x.n_muestra))
        if faltan:
            raise SystemExit(f"No están en la muestra: {faltan}")
        por_n = {int(n): i for i, n in x.n_muestra.items()}
        sel = x.loc[[por_n[n] for n in personas]].copy()
        sel["criterio"] = ([criterio[int(n)] for n in sel.n_muestra] if isinstance(criterio, dict) else criterio)
        carpeta = (Path(base) if base else carpeta) / nombre
    cols = ["n_muestra", "posicion", "indice_caja", "criterio", "completa_rgb_dx", "completa_rgb_dy",
            "corrimiento_px", "rgb_estado", "termica_estado", "no_es_persona", "fuera_de_cuadro", "lambda_rgb",
            "lambda_termica", "nivel_manual", "lambda_rgb_auto", "nivel_auto"]
    if carpeta.exists():  # solo lo que generó esta revisión
        for f in list(carpeta.glob("*.jpg")) + list(carpeta.glob("lista.csv")) + list(carpeta.glob("superposicion.csv")):
            f.unlink()
    carpeta.mkdir(parents=True, exist_ok=True)
    sel[cols].to_csv(carpeta / "lista.csv", encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:  # la herramienta trabaja sobre una copia: no toca las anotaciones
        copia = Path(tmp) / "oclusion.csv"
        shutil.copy(data / o["anotaciones"], copia)
        an = crear_anotador(cfg, rutas, segundo=False, salida=copia, muestra=True)
        hc = hashlib_md5(copia)
        losetas = []
        for i, f in sel.iterrows():
            an.i = an.ids.index(i)
            an.abrir()
            # la vista de la herramienta, agrandada si hace falta para que entren todas las cajas de la persona
            r, p = an.r, an.p
            completas = (r["completa"]["rgb"], r["completa"]["ter"]) if r["completa"] is not None else ()
            cajas = [[p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1]] + [
                c for c in (*completas, r["rgb"]["caja"], r["ter"]["caja"]) if c is not None]
            cx, cy = (p.ter_x0 + p.ter_x1) / 2, (p.ter_y0 + p.ter_y1) / 2
            asp = an.ph / an.pw
            ext = max(max(2 * max(cy - c[1], c[3] - cy), 2 * max(cx - c[0], c[2] - cx) * asp) for c in cajas)
            z = min(an.vista[2], an.ph / (o["recorte_factor_union"] * ext))
            an.vista = an.limitar(cx, cy, z)
            lienzo = an.dibujar()
            an.ver_cajas = False
            sin = {l: an.panel(l) for l in ("rgb", "ter")}
            an.realce = True  # RGB con el realce de contraste de la herramienta (tecla e): ayuda en la sombra
            an.preparar_imagenes()
            sin["realce"] = an.panel("rgb")
            an.realce = False
            an.preparar_imagenes()
            an.ver_cajas = True
            con = {l: lienzo[:an.ph, an.x_panel[l]:an.x_panel[l] + an.pw] for l in ("rgb", "ter")}
            k = rv["escala_sin_cajas"]
            hueco = np.zeros((round(an.ph * k), an.sep, 3), np.uint8)
            fila = np.hstack(sum(([cv2.resize(sin[l], None, fx=k, fy=k, interpolation=cv2.INTER_AREA), hueco]
                                  for l in ("rgb", "ter", "realce")), [])[:-1])
            fila = np.hstack([fila, np.zeros((fila.shape[0], lienzo.shape[1] - fila.shape[1], 3), np.uint8)])
            lineas = [f"{f.n_muestra} de {len(muestra)} | {i} | fotograma {f.posicion}, caja {f.indice_caja + 1}",
                      _ascii(f.criterio) + f" | completa RGB corrida dx {f.completa_rgb_dx:+.1f}, dy "
                      f"{f.completa_rgb_dy:+.1f} ({f.corrimiento_px:.1f} px)",
                      f"lambda RGB manual {f.lambda_rgb:.3f} ({_ascii(f.nivel_manual)}) | lambda RGB automatico "
                      f"{f.lambda_rgb_auto:.3f} ({_ascii(f.nivel_auto)}) | lambda termica manual {f.lambda_termica:.3f} "
                      f"| visible RGB: {f.rgb_estado} | visible termica: {f.termica_estado}"
                      + (" | NO ES PERSONA" if f.no_es_persona else "") + (" | FUERA DE CUADRO" if f.fuera_de_cuadro else ""),
                      "celeste: completa de la imagen (oscuro: la de la otra imagen) | verde: visible | gris: otras "
                      "personas de WiSARD | abajo, sin cajas: RGB, termica y RGB con realce de contraste"]
            cab = np.zeros((26 * len(lineas) + 10, lienzo.shape[1], 3), np.uint8)
            for j, t in enumerate(lineas):
                cv2.putText(cab, t, (10, 26 * (j + 1)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            img = np.vstack([cab, lienzo, fila])
            nombre = f"{f.n_muestra:02d}_{f.posicion:04d}_{f.indice_caja}.jpg"
            cv2.imwrite(str(carpeta / nombre), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            # loseta del mosaico: paneles con cajas y sin cajas, RGB y térmica
            par = np.hstack([con["rgb"], con["ter"], sin["rgb"], sin["realce"], sin["ter"]])
            h = rv["alto_mosaico_px"]
            par = cv2.resize(par, (round(par.shape[1] * h / par.shape[0]), h), interpolation=cv2.INTER_AREA)
            rot = np.zeros((28, par.shape[1], 3), np.uint8)
            cv2.putText(rot, f"{f.n_muestra} de {len(muestra)} | fot. {f.posicion} caja {f.indice_caja + 1} | "
                             f"{_ascii(f.criterio) if personas else _motivo(f, corrida[i], dibujada[i])}"
                             f" | manual {f.lambda_rgb:.2f} / auto {f.lambda_rgb_auto:.2f}",
                        (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            losetas.append(np.vstack([rot, par]))
            print(f"  {f.n_muestra:2d} de {len(muestra)}  {i}  {f.criterio}  -> {nombre}")
        if hashlib_md5(copia) != hc:
            raise SystemExit("La revisión cambió la copia de las anotaciones: revisar el código")
    if losetas:
        c = rv["columnas_mosaico"]
        losetas += [np.zeros_like(losetas[0])] * (-len(losetas) % c)
        sep = 8
        filas = [np.hstack(sum(([t, np.zeros((t.shape[0], sep, 3), np.uint8)] for t in losetas[j:j + c]), [])[:-1])
                 for j in range(0, len(losetas), c)]
        mosaico = np.vstack(sum(([fl, np.zeros((sep, fl.shape[1], 3), np.uint8)] for fl in filas), [])[:-1])
        cv2.imwrite(str(carpeta / "mosaico.jpg"), mosaico, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if personas:
        superposicion(cfg, rutas, sel, per, carpeta)
        print(f"{len(sel)} personas pedidas -> {carpeta}")
    else:
        print(f"{len(sel)} personas a revisar ({int(corrida.sum())} con la completa RGB corrida más de "
              f"{rv['mover_completa_px']} px, {int(dibujada.sum())} con visible RGB en par solo térmica) -> {carpeta}")
    return sel[cols]


def _motivo(f, corrida, dibujada):
    if corrida:
        return f"corrida {f.corrimiento_px:.1f} px"
    return "solo termica" if dibujada else "pedida"


def _sup(a, b):
    """IoU e intersección sobre el área de la caja más chica."""
    from anotar_oclusion import area, interseccion
    i = interseccion(a, b)
    return i / (area(a) + area(b) - i), i / min(area(a), area(b))


def superposicion(cfg, rutas, sel, per, carpeta):
    """Personas pedidas del mismo fotograma: superposición de sus cajas y secuencia de térmicas vecinas."""
    import itertools

    import cv2

    o, sq = cfg["oclusion"], cfg["oclusion_auto"]["revision"]["secuencia"]
    data, alineados = rutas["data"], rutas["data"] / cfg["datasets"]["alineados"]
    filas = []
    for pos, g in sel.groupby("posicion"):
        if len(g) < 2:
            continue
        cajas = {i: [float(per.loc[i, f"ter_{c}"]) for c in CAJA] for i in g.index}
        comp = {i: [float(g.loc[i, f"completa_termica_{c}"]) for c in CAJA] for i in g.index}
        for i, j in itertools.combinations(g.index, 2):
            na, nb = int(g.loc[i, "n_muestra"]), int(g.loc[j, "n_muestra"])
            fila = {"posicion": pos, "persona_a": na, "persona_b": nb}
            for clave, d in (("wisard", cajas), ("completas", comp)):
                if not any(np.isnan(d[i] + d[j])):
                    iou, menor = _sup(d[i], d[j])
                    fila[f"iou_{clave}"], fila[f"inter_sobre_menor_{clave}"] = round(iou, 3), round(menor, 3)
            # qué fracción de la completa de cada una cae sobre la caja de WiSARD propia y sobre la de la otra
            for u, nu, w, nw in ((i, na, j, nb), (j, nb, i, na)):
                if not any(np.isnan(comp[u])):
                    from anotar_oclusion import area, interseccion
                    fila[f"completa_{nu}_sobre_wisard_{nu}"] = round(interseccion(comp[u], cajas[u]) / area(comp[u]), 3)
                    fila[f"completa_{nu}_sobre_wisard_{nw}"] = round(interseccion(comp[u], cajas[w]) / area(comp[u]), 3)
            filas.append(fila)
        # secuencia de térmicas vecinas con las cajas de WiSARD, alrededor de las cajas de estas personas
        v = o["vuelo"]
        u = np.array(list(cajas.values()), float)
        cx, cy = (u[:, 0].min() + u[:, 2].max()) / 2, (u[:, 1].min() + u[:, 3].max()) / 2
        lado, k = sq["lado_px"], sq["escala"]
        x0, y0 = int(round(cx - lado / 2)), int(round(cy - lado / 2))
        indice = pd.read_csv(alineados / "indice.csv")
        vecinos = indice[(indice.vuelo == v) & ((indice.posicion - pos).abs() <= sq["posiciones"])]
        teselas = []
        for q in vecinos.sort_values("posicion").itertuples():
            ter = cv2.imread(str(alineados / q.termica), cv2.IMREAD_GRAYSCALE)
            ter = cv2.copyMakeBorder(ter, lado, lado, lado, lado, cv2.BORDER_CONSTANT, value=0)
            rec = cv2.cvtColor(ter[y0 + lado:y0 + 2 * lado, x0 + lado:x0 + 2 * lado], cv2.COLOR_GRAY2BGR)
            rec = cv2.resize(rec, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
            etq = data / cfg["datasets"]["etiquetas"] / "termica" / v / f"{v}_{q.posicion:04d}.txt"
            dentro = 0
            for b in cajas_px(etq, tuple(cfg["tam_termica"])):
                if b[2] < x0 or b[0] > x0 + lado or b[3] < y0 or b[1] > y0 + lado:
                    continue
                dentro += 1
                cv2.rectangle(rec, (int(round((b[0] - x0) * k)), int(round((b[1] - y0) * k))),
                              (int(round((b[2] - x0) * k)) - 1, int(round((b[3] - y0) * k)) - 1), (0, 255, 0), 1)
            actual = q.posicion == pos
            rec = cv2.copyMakeBorder(rec, 26, 3, 3, 3, cv2.BORDER_CONSTANT,
                                     value=(0, 220, 255) if actual else (60, 60, 60))
            texto = f"{q.posicion}: {dentro} caja" + ("" if dentro == 1 else "s")
            cv2.putText(rec, texto, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 0, 0) if actual else (255, 255, 255), 1, cv2.LINE_AA)
            teselas.append(rec)
        c = sq["columnas"]
        teselas += [np.zeros_like(teselas[0])] * (-len(teselas) % c)
        img = np.vstack([np.hstack(teselas[j:j + c]) for j in range(0, len(teselas), c)])
        cab = np.zeros((36, img.shape[1], 3), np.uint8)
        cv2.putText(cab, f"Termica, posiciones {vecinos.posicion.min()} a {vecinos.posicion.max()} (pares finales), "
                         f"zona de {lado} x {lado} px alrededor de las cajas | verde: cajas de WiSARD | amarillo: "
                         f"fotograma {pos}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(carpeta / f"secuencia_{pos:04d}.jpg"), np.vstack([cab, img]), [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"  secuencia de {len(vecinos)} fotogramas -> secuencia_{pos:04d}.jpg")
    if filas:
        t = pd.DataFrame(filas)
        t.to_csv(carpeta / "superposicion.csv", index=False, encoding="utf-8")
        print(t.T.to_string(header=False))


def hashlib_md5(ruta):
    import hashlib
    return hashlib.md5(Path(ruta).read_bytes()).hexdigest()


def _ascii(t):
    """cv2.putText solo dibuja ASCII."""
    import unicodedata
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--revisar", action="store_true", help="imágenes de las personas de la muestra a revisar")
    ap.add_argument("--personas", type=int, nargs="+", help="con --revisar: estas personas (número en la muestra)")
    ap.add_argument("--nombre", help="con --personas: subcarpeta de la revisión")
    args = ap.parse_args()
    if args.personas and not args.revisar:
        ap.error("--personas va con --revisar")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # λ en consolas cp1252
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.revisar:
        revisar(cfg, rutas, args.personas, args.nombre)
    else:
        calcular(cfg, rutas)


if __name__ == "__main__":
    main()
