r"""Fase 4: validación del nivel de oclusión automático con la muestra anotada a mano (decidida el 2026-11-01).

Como en la muestra no hay ninguna persona moderada (0 de 68), el nivel pasa a dos clases: severa = la persona no se ve
en la RGB; baja = se ve.
- Manual (primer anotador, data/<oclusion.anotaciones>, personas de data/<oclusion.muestra_segundo>): severa si la
  visible RGB es "no visible"; baja si tiene caja.
- Automático (data/<oclusion_auto.salida>): severa si no hay caja RGB de WiSARD a `oclusion_auto.radio_alturas` alturas
  o menos; baja si la hay.

Partes (por omisión, todas), con salidas en reports/<validacion_auto.carpeta>/:
  comparar       kappa de Cohen binario (sin pesos, IC 95 % asintótico de statsmodels), matriz de confusión y lista de
                 desacuerdos con sus imágenes (las de oclusion_auto.revisar, en desacuerdos/). Se usa el automático si
                 el kappa binario es de `kappa_minimo` o más. Aparte, solo para reportar, el kappa de 3 niveles con λ por
                 áreas (`oclusion_auto.limites_nivel`) y la diferencia de λ. Las "no es persona" y "fuera de cuadro" no
                 entran. Agrega una fila a la bitácora.
  no_es_persona  mosaico de las "no es persona" de la muestra: RGB alineada, térmica, térmica con el realce de la
                 herramienta (CLAHE, tecla e), térmica con el contraste estirado en la zona (percentiles) y esta última
                 con las cajas térmicas de WiSARD. Misma vista inicial que la herramienta.
  fondo          medida del fondo de la fase 2 (desplazamiento de la RGB alineada respecto de la térmica, correlación de
                 fase de los gradientes, con la semejanza congelada) y distancia de cada persona térmica a la caja RGB
                 más cercana, en `revision_fondo.desde`-`hasta` del vuelo de prueba más `contexto` posiciones a cada lado
                 (también los pares excluidos). Como en el bosque esa medida no es fiable, también el movimiento
                 desde el fotograma anterior dentro de cada cámara (RGB con RGB, térmica con térmica) y su diferencia
                 (salto): un desfase solo en p da un salto en p y el contrario en p + 1. Imagen de inspección como las
                 de la revisión de desfases de la fase 2, con `detalle` entero. Agrega una fila a la bitácora.
  entre_anotadores  concordancia entre el primer anotador y el segundo (modo simple) sobre las dos clases: se ve en la
                 RGB (baja) o no (severa), en la ronda `--ronda` del segundo (por omisión, oclusion.segundo_simple.
                 ronda_actual; su archivo, en data/<segundo_simple.rondas[N].archivo>, debe tener las 75). Las "no es
                 persona" de cualquiera de los dos (y las "fuera de cuadro" del primero) van aparte. Kappa de Cohen con
                 IC 95 %, matriz de confusión, tabla completa con las "no es persona", desacuerdos con sus imágenes (en
                 <entre_anotadores.carpeta>/ronda<N>/, también las "no es persona" de uno solo) y respuestas del segundo
                 más rápidas que `tiempo_rapido_s`. Desde la ronda 2, además, las respuestas del segundo que cambian
                 respecto de la ronda anterior (ronda<N>/cambios.csv) y el kappa de cada ronda (rondas.csv). Agrega una
                 fila a la bitácora.

No modifica data/ ni el dataset original (lo lee para la medida del fondo, como en la fase 2).

Uso:
    .venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
    .venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --partes fondo
    .venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 2
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from oclusion_auto import NIVELES, _ascii, hashlib_md5, nivel, revisar

PARTES = ["comparar", "no_es_persona", "fondo", "entre_anotadores"]


def leer_muestra(cfg, rutas):
    """Anotaciones del primer anotador de las personas de la muestra, en su orden, con su número (desde 1)."""
    o, data = cfg["oclusion"], rutas["data"]
    muestra = list(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).sort_values("orden").id)
    man = pd.read_csv(data / o["anotaciones"], dtype={"id": str}).set_index("id").reindex(muestra)
    if man.terminada.isna().any() or not man.terminada.astype(bool).all():
        raise SystemExit(f"La muestra no está terminada en {data / o['anotaciones']}")
    man.insert(0, "n_muestra", range(1, len(muestra) + 1))
    man["no_es_persona"] = man.no_es_persona.astype(bool)
    man["fuera_de_cuadro"] = man.fuera_de_cuadro.astype(bool)
    return man


def matriz(x, col_manual, col_auto, niveles, nombres=("manual", "automatico")):
    m = pd.crosstab(pd.Categorical(x[col_manual], niveles), pd.Categorical(x[col_auto], niveles), dropna=False)
    m.index.name, m.columns.name = nombres
    return m


def kappa(m):
    """Kappa de Cohen sin pesos e IC 95 % asintótico; NaN si no se puede calcular (un solo nivel en los dos)."""
    from statsmodels.stats.inter_rater import cohens_kappa
    t = np.asarray(m, float)
    pe = (t.sum(1) * t.sum(0)).sum() / t.sum() ** 2
    if pe >= 1:
        return np.nan, np.nan, np.nan
    k = cohens_kappa(t)
    return float(k.kappa), float(k.kappa_low), float(k.kappa_upp)


# ---------------------------------------------------------------------------------------------------- comparar
def comparar(cfg, rutas, carpeta):
    o, a, va = cfg["oclusion"], cfg["oclusion_auto"], cfg["validacion_auto"]
    baja, severa = va["niveles"]
    man = leer_muestra(cfg, rutas)
    auto = pd.read_csv(rutas["data"] / a["salida"], dtype={"id": str}).set_index("id")
    aparte = man[man.no_es_persona | man.fuera_de_cuadro]
    comp = man[~man.index.isin(aparte.index)].copy()
    raros = set(comp.rgb_estado) - {"caja", "no_visible"}
    if raros:
        raise SystemExit(f"Visible RGB sin resolver en personas comparables: {raros}")
    comp = comp.join(auto[["lambda_rgb_auto", "sin_caja_rgb_cerca", "rgb_dist_alturas", "cajas_rgb_en_par"]])
    comp["nivel2_manual"] = np.where(comp.rgb_estado == "no_visible", severa, baja)
    comp["nivel2_auto"] = np.where(comp.sin_caja_rgb_cerca.astype(bool), severa, baja)
    comp["nivel3_manual"] = nivel(comp.lambda_rgb, a["limites_nivel"])
    comp["nivel3_auto"] = nivel(comp.lambda_rgb_auto, a["limites_nivel"])
    comp["diferencia_lambda"] = (comp.lambda_rgb_auto - comp.lambda_rgb).round(4)
    comp["desacuerdo2"] = comp.nivel2_manual != comp.nivel2_auto
    comp["desacuerdo3"] = comp.nivel3_manual != comp.nivel3_auto

    m2 = matriz(comp, "nivel2_manual", "nivel2_auto", [baja, severa])
    m3 = matriz(comp, "nivel3_manual", "nivel3_auto", NIVELES)
    k2, k3 = kappa(m2), kappa(m3)
    usar = "automático" if k2[0] >= va["kappa_minimo"] else "manual"
    dif = comp.diferencia_lambda
    res = pd.DataFrame([
        {"comparacion": "dos niveles (decide)", "personas": len(comp), "kappa": k2[0], "ic95_bajo": k2[1],
         "ic95_alto": k2[2], "acuerdo": (~comp.desacuerdo2).mean(), "desacuerdos": int(comp.desacuerdo2.sum())},
        {"comparacion": "tres niveles, λ por áreas (solo se reporta)", "personas": len(comp), "kappa": k3[0],
         "ic95_bajo": k3[1], "ic95_alto": k3[2], "acuerdo": (~comp.desacuerdo3).mean(),
         "desacuerdos": int(comp.desacuerdo3.sum())}]).round(4)

    cols = ["n_muestra", "posicion", "indice_caja", "rgb_estado", "lambda_rgb", "nivel2_manual", "nivel3_manual",
            "sin_caja_rgb_cerca", "rgb_dist_alturas", "cajas_rgb_en_par", "lambda_rgb_auto", "nivel2_auto",
            "nivel3_auto", "diferencia_lambda", "desacuerdo2", "desacuerdo3"]
    comp[cols].to_csv(carpeta / "comparacion.csv", encoding="utf-8")
    res.to_csv(carpeta / "kappa.csv", index=False, encoding="utf-8")
    m2.to_csv(carpeta / "matriz_dos_niveles.csv", encoding="utf-8")
    m3.to_csv(carpeta / "matriz_tres_niveles.csv", encoding="utf-8")
    des = comp[comp.desacuerdo2]
    des[cols].to_csv(carpeta / "desacuerdos_dos_niveles.csv", encoding="utf-8")
    if len(des):  # imágenes de los desacuerdos, como las de la revisión de la muestra
        revisar(cfg, rutas, personas=[int(n) for n in des.n_muestra], nombre="desacuerdos", base=carpeta,
                criterio="desacuerdo en dos niveles")

    pd.set_option("display.width", 220)
    print(f"Muestra: {len(man)} personas; aparte {int(man.no_es_persona.sum())} 'no es persona' y "
          f"{int(man.fuera_de_cuadro.sum())} 'fuera de cuadro'; comparables {len(comp)}")
    print(res.to_string(index=False))
    print(f"\nDos niveles (filas: manual; columnas: automático)\n{m2}\n\nTres niveles\n{m3}")
    print(f"\nDiferencia de λ (automático − manual): media {dif.mean():+.3f}, absoluta media {dif.abs().mean():.3f}, "
          f"mediana {dif.median():+.3f}")
    print(f"\nDesacuerdos en dos niveles:\n{des[cols].to_string()}")
    print(f"\nDesacuerdos en tres niveles:\n{comp[comp.desacuerdo3][cols].to_string()}")
    print(f"\nKappa binario {k2[0]:.3f} {'>=' if usar == 'automático' else '<'} {va['kappa_minimo']}: se usa el {usar}")
    agregar_a_bitacora(
        rutas["bitacora"], "4", "nivel de oclusión automático contra manual (muestra, dos niveles)",
        f"{len(comp)} comparables de {len(man)} ({o['vuelo']}); severa = no se ve en la RGB (manual: visible RGB "
        f"'no visible'; automático: sin caja RGB de WiSARD a {a['radio_alturas']} alturas); kappa mínimo "
        f"{va['kappa_minimo']}",
        f"kappa binario {k2[0]:.3f} (IC {k2[1]:.3f}-{k2[2]:.3f}), acuerdo {(~comp.desacuerdo2).mean():.1%}, "
        f"{int(comp.desacuerdo2.sum())} desacuerdos; kappa 3 niveles {k3[0]:.3f} (IC {k3[1]:.3f}-{k3[2]:.3f}, solo se "
        f"reporta); diferencia media de λ {dif.mean():+.3f}; se usa el {usar}")
    return comp, res, m2, m3


# ---------------------------------------------------------------------------------------------------- no es persona
def no_es_persona(cfg, rutas, carpeta):
    from anotar_oclusion import CAJA_WISARD, OTRAS, crear_anotador

    o, a = cfg["oclusion"], cfg["oclusion_auto"]
    cn = cfg["validacion_auto"]["no_es_persona"]
    man = leer_muestra(cfg, rutas)
    sel = man[man.no_es_persona]
    auto = pd.read_csv(rutas["data"] / a["salida"], dtype={"id": str}).set_index("id")
    corr = {c["id"]: c.get("motivo", "") for c in leer_yaml(RAIZ / o["correcciones"])["correcciones"]}
    titulos = ["RGB alineada", "termica", "termica con realce (CLAHE, tecla e)",
               f"termica estirada (p{cn['percentiles_estirado'][0]}-p{cn['percentiles_estirado'][1]} de la zona)",
               "estirada + cajas termicas de WiSARD (verde: esta; gris: otras)"]
    filas, losetas = [], []
    with tempfile.TemporaryDirectory() as tmp:  # la herramienta trabaja sobre una copia: no toca las anotaciones
        copia = Path(tmp) / "oclusion.csv"
        shutil.copy(rutas["data"] / o["anotaciones"], copia)
        huella = hashlib_md5(copia)
        an = crear_anotador(cfg, rutas, segundo=False, salida=copia, muestra=True)
        for i, f in sel.iterrows():
            an.i = an.ids.index(i)
            an.abrir()
            p = an.p
            an.realce = False
            an.preparar_imagenes()
            rgb, ter = an.fondo_panel("rgb"), an.fondo_panel("ter")
            an.realce = True
            an.preparar_imagenes()
            clahe = an.fondo_panel("ter")
            an.realce = False
            an.preparar_imagenes()
            g = ter[..., 0].astype(np.float64)
            lo, hi = np.percentile(g, cn["percentiles_estirado"])
            est = np.clip((g - lo) * 255 / max(hi - lo, 1e-6), 0, 255).astype(np.uint8)
            est = cv2.cvtColor(est, cv2.COLOR_GRAY2BGR)
            cajas = est.copy()
            for q in an.todas[an.todas.posicion == p.posicion].itertuples():
                if q.id != i:
                    an.rect(cajas, [q.ter_x0, q.ter_y0, q.ter_x1, q.ter_y1], OTRAS, 1)
            an.rect(cajas, [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1], CAJA_WISARD, 1)
            paneles = [rgb, ter, clahe, est, cajas]
            for img in paneles:
                an.senalar(img)
            h = cn["alto_panel_px"]
            paneles = [cv2.resize(x, (round(x.shape[1] * h / x.shape[0]), h), interpolation=cv2.INTER_AREA)
                       for x in paneles]
            sep = np.full((h, 6, 3), 255, np.uint8)
            fila = np.hstack(sum(([x, sep] for x in paneles), [])[:-1])
            ad = auto.loc[i]
            motivo = corr.get(i, "")
            texto = (f"{f.n_muestra} de {len(man)} | fotograma {p.posicion}, caja {p.indice_caja + 1} de "
                     f"{p.cajas_en_fotograma} | automatico: " + ("sin caja RGB cerca" if ad.sin_caja_rgb_cerca else
                                                                 f"caja RGB a {ad.rgb_dist_alturas:.2f} alturas")
                     + (f" | {motivo}" if motivo else ""))
            rot = np.full((30, fila.shape[1], 3), 255, np.uint8)
            cv2.putText(rot, _ascii(texto)[:170], (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
            losetas.append(np.vstack([rot, fila]))
            filas.append({"n_muestra": int(f.n_muestra), "id": i, "posicion": int(p.posicion),
                          "indice_caja": int(p.indice_caja), "cajas_en_fotograma": int(p.cajas_en_fotograma),
                          "alto_caja_termica_px": round(float(p.ter_y1 - p.ter_y0), 1),
                          "rgb_estado_manual": f.rgb_estado, "termica_estado_manual": f.termica_estado,
                          "sin_caja_rgb_cerca": bool(ad.sin_caja_rgb_cerca), "rgb_dist_alturas": ad.rgb_dist_alturas,
                          "nivel_auto_dos": "severa" if ad.sin_caja_rgb_cerca else "baja", "motivo": motivo})
        if hashlib_md5(copia) != huella:
            raise SystemExit("El mosaico cambió la copia de las anotaciones: revisar el código")
    ancho = losetas[0].shape[1]
    cab = np.full((30, ancho, 3), 255, np.uint8)
    x = 0
    for t, w in zip(titulos, [pan.shape[1] for pan in paneles]):
        cv2.putText(cab, t, (x + 4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        x += w + 6
    blanco = np.full((10, ancho, 3), 255, np.uint8)
    mosaico = np.vstack([cab] + sum(([t, blanco] for t in losetas), [])[:-1])
    cv2.imwrite(str(carpeta / "no_es_persona.jpg"), mosaico, [cv2.IMWRITE_JPEG_QUALITY, 92])
    lista = pd.DataFrame(filas)
    lista.to_csv(carpeta / "no_es_persona.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 220)
    print(lista.drop(columns="motivo").to_string(index=False))
    print(f"{len(lista)} 'no es persona' -> {carpeta / 'no_es_persona.jpg'}")
    return lista


# ---------------------------------------------------------------------------------------------------- fondo
def fondo(cfg, rutas, carpeta):
    from types import SimpleNamespace

    from PIL import ImageFont

    from comun import pares_anotados
    from fase2_revision_desfases import desplazamiento_fondo, imagen_tramo, personas_de, preparar

    rf = cfg["validacion_auto"]["revision_fondo"]
    cfg2 = leer_yaml(RAIZ / rf["config_fase2"])
    c, cr = cfg2["homografias_cajas"], cfg2["revision_desfases"]
    v = cfg["oclusion"]["vuelo"]
    Hs = yaml.safe_load((RAIZ / cfg["transformaciones"]).read_text(encoding="utf-8"))
    H = np.array(Hs[v]["H_rgb_a_termica"], np.float64)
    tam_rgb, tam_ter = tuple(Hs[v]["tam_rgb"]), tuple(cfg["tam_termica"])
    D = rutas["dataset"]
    pares = pares_anotados(rutas["data"] / cfg["pares"])
    g = pares[pares.vuelo == v].set_index("posicion")  # incluidos los excluidos
    a, b, k = rf["desde"], rf["hasta"], rf["contexto"]
    sigma, minimo = cr["fondo_sigma"], cr["fondo_respuesta_min"]
    ventana = cv2.createHanningWindow(tam_ter, cv2.CV_64F)
    filas, imgs = [], {}
    for p in range(a - k, b + k + 1):
        if p not in g.index:
            continue
        par = g.loc[p]
        imgs[p] = preparar(par, D, H, tam_ter)  # (RGB alineada, térmica)
        dx, dy, resp = desplazamiento_fondo(*imgs[p], sigma, ventana)
        _, ct, per = personas_de(par, D, H, tam_rgb, tam_ter, c)
        cuentan = [x for x in per if x["cuenta"]]
        orden = sorted(per, key=lambda x: x["x_termica"])
        fila = {"posicion": p, "en_revision": a <= p <= b, "excluido": bool(par.excluido),
                "motivo_exclusion": "" if pd.isna(par.motivo_exclusion) else str(par.motivo_exclusion)[:60],
                "fondo_dx_px": round(dx, 1), "fondo_dy_px": round(dy, 1), "fondo_px": round(float(np.hypot(dx, dy)), 1),
                "respuesta": round(resp, 3), "fiable": resp >= minimo,
                "personas_termica": len(ct), "personas_cuentan": len(cuentan),
                "mediana_relativa": round(float(np.median([x["relativa"] for x in cuentan])), 2) if cuentan else np.nan,
                "relativas": " ".join(f"{x['relativa']:.2f}" for x in orden),
                "personas_dxy_px": " ".join(f"({x['dx_px']:+.0f},{x['dy_px']:+.0f})" for x in orden)}
        # Movimiento desde el fotograma anterior dentro de cada cámara (misma modalidad: la correlación de fase sí es
        # fiable en el bosque). salto = movimiento RGB − movimiento térmico = cuánto cambia el corrimiento de la RGB
        # respecto de la térmica entre p − 1 y p. Un desfase solo en p da un salto en p y el contrario en p + 1.
        if p - 1 in imgs:
            mr = desplazamiento_fondo(imgs[p][0], imgs[p - 1][0], sigma, ventana)
            mt = desplazamiento_fondo(imgs[p][1], imgs[p - 1][1], sigma, ventana)
            fila.update({"mov_rgb_dx": round(mr[0], 1), "mov_rgb_dy": round(mr[1], 1), "resp_rgb": round(mr[2], 3),
                         "mov_ter_dx": round(mt[0], 1), "mov_ter_dy": round(mt[1], 1), "resp_ter": round(mt[2], 3),
                         "salto_dx": round(mr[0] - mt[0], 1), "salto_dy": round(mr[1] - mt[1], 1),
                         "salto_fiable": min(mr[2], mt[2]) >= minimo})
        filas.append(fila)
    t = pd.DataFrame(filas)
    t.to_csv(carpeta / f"fondo_{a:04d}-{b:04d}.csv", index=False, encoding="utf-8")
    detalle = rf["detalle"]
    estado = {p: ("excluido" if g.loc[p].excluido else "final") for p in (a - 1, b + 1) if p in g.index}
    tr = SimpleNamespace(tramo=0, vuelo=v, desde=a, hasta=b, peor=detalle, cabecera=(
        f"{v} {a}-{b} (pares finales) | " + ", ".join(f"{p}: {e}" for p, e in estado.items())
        + f" | abajo, el {detalle} en detalle"))
    fuente = ImageFont.truetype(cfg2["fuente"], 16)
    fuente_t = ImageFont.truetype(cfg2["fuente"], 13)
    img, _, _ = imagen_tramo(tr, g, D, H, tam_rgb, tam_ter, c, {**cr, "max_posiciones_por_tramo": b - a + 1}, fuente,
                             fuente_t)
    img.save(carpeta / f"fondo_{a:04d}-{b:04d}.jpg", quality=cr["calidad_jpg"])

    pd.set_option("display.width", 250)
    print(t.drop(columns="motivo_exclusion").to_string(index=False))
    print(f"-> {carpeta / f'fondo_{a:04d}-{b:04d}.jpg'}")
    r = t[t.en_revision | t.posicion.eq(b + 1)]
    agregar_a_bitacora(
        rutas["bitacora"], "4", f"revisión del desfase por el fondo ({v} {a}-{b})",
        f"correlación de fase de los gradientes (sigma {sigma}, fiable si respuesta >= {minimo}), semejanza "
        f"congelada; posiciones {t.posicion.min()}-{t.posicion.max()}; además, salto = movimiento RGB − movimiento "
        f"térmico desde el fotograma anterior",
        "fondo RGB-térmica (dx, dy) px: " + ", ".join(
            f"{int(x.posicion)}: ({x.fondo_dx_px:+.0f}, {x.fondo_dy_px:+.0f})" + ("" if x.fiable else " no fiable")
            for x in r[r.en_revision].itertuples())
        + "; salto (dx, dy) px: " + ", ".join(
            f"{int(x.posicion)}: ({x.salto_dx:+.0f}, {x.salto_dy:+.0f})" + ("" if x.salto_fiable else " no fiable")
            for x in r.itertuples() if not pd.isna(x.salto_dx))
        + "; mediana relativa de personas: " + ", ".join(f"{int(x.posicion)}: {x.mediana_relativa:.2f}"
                                                         for x in r[r.en_revision].itertuples()))
    return t


# ---------------------------------------------------------------------------------------------------- entre anotadores
def respuestas_segundo(cfg, rutas, ronda, ids):
    """Respuestas del segundo anotador (modo simple) de una ronda, pasadas a las clases; exige las de todas las `ids`."""
    va, ss = cfg["validacion_auto"], cfg["oclusion"]["segundo_simple"]
    baja, severa = va["niveles"]
    if ronda not in ss["rondas"]:
        raise SystemExit(f"La ronda {ronda} no está en oclusion.segundo_simple.rondas ({sorted(ss['rondas'])})")
    ruta = rutas["data"] / ss["rondas"][ronda]["archivo"]
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}: la ronda {ronda} del segundo anotador no está hecha (anotar_oclusion.py "
                         f"--segundo-simple, con segundo_simple.ronda_actual = {ronda})")
    seg = pd.read_csv(ruta, dtype={"id": str}).set_index("id")
    faltan = [i for i in ids if i not in seg.index]
    if faltan:
        raise SystemExit(f"La ronda {ronda} no está completa: faltan {len(faltan)} de {len(ids)} personas en {ruta} "
                         f"(la primera: {faltan[0]})")
    seg = seg.loc[list(ids)]
    seg["segundo"] = seg.respuesta.map({"se_ve_rgb": baja, "no_se_ve_rgb": severa, "no_es_persona": "no_es_persona"})
    return seg, ruta


def entre_anotadores(cfg, rutas, carpeta, ronda=None):
    """Concordancia del primer anotador con la ronda `ronda` del segundo (por omisión, `segundo_simple.ronda_actual`).
    Salidas en <entre_anotadores.carpeta>/ronda<N>/; desde la ronda 2, además, qué cambió respecto de la anterior."""
    o, va = cfg["oclusion"], cfg["validacion_auto"]
    ea = va["entre_anotadores"]
    ss = o["segundo_simple"]
    ronda = ss["ronda_actual"] if ronda is None else ronda
    regla = ss["rondas"].get(ronda, {}).get("regla", "?")
    baja, severa = va["niveles"]
    texto = {baja: "se ve", severa: "no se ve", "no_es_persona": "no es persona", "fuera_de_cuadro": "fuera de cuadro"}
    man = leer_muestra(cfg, rutas)
    seg, ruta2 = respuestas_segundo(cfg, rutas, ronda, man.index)
    print(f"Ronda {ronda} (regla {regla}): {ruta2}")
    x = man[["n_muestra", "posicion", "indice_caja", "rgb_estado", "no_es_persona", "fuera_de_cuadro"]].join(
        seg[["respuesta", "segundo", "tiempo_s"]].rename(columns={"respuesta": "respuesta_segundo",
                                                                  "tiempo_s": "tiempo_segundo_s"}))
    x["primero"] = np.select([x.no_es_persona, x.fuera_de_cuadro, x.rgb_estado == "no_visible", x.rgb_estado == "caja"],
                             ["no_es_persona", "fuera_de_cuadro", severa, baja], "sin_resolver")
    if (x.primero == "sin_resolver").any() or x.segundo.isna().any():
        raise SystemExit("Hay respuestas sin resolver o desconocidas")
    x["aparte"] = x.primero.isin(["no_es_persona", "fuera_de_cuadro"]) | (x.segundo == "no_es_persona")
    x["desacuerdo"] = x.primero != x.segundo
    comp = x[~x.aparte]
    m = matriz(comp, "primero", "segundo", [baja, severa], ("primero", "segundo"))
    k = kappa(m)
    todas = [baja, severa, "no_es_persona", "fuera_de_cuadro"]
    completa = matriz(x, "primero", "segundo", todas, ("primero", "segundo"))
    completa = completa.loc[completa.sum(axis=1) > 0, completa.sum(axis=0) > 0]
    des = comp[comp.desacuerdo]
    uno_solo = x[x.aparte & x.desacuerdo]  # "no es persona" para uno solo de los dos
    rapidas = x[x.tiempo_segundo_s < ea["tiempo_rapido_s"]]
    res = pd.DataFrame([{"comparacion": "primero contra segundo", "comparables": len(comp), "kappa": k[0],
                         "ic95_bajo": k[1], "ic95_alto": k[2], "acuerdo": (~comp.desacuerdo).mean(),
                         "desacuerdos": len(des)}])
    # Informativo: cada anotador contra el nivel automático, en las mismas personas comparables.
    auto = pd.read_csv(rutas["data"] / cfg["oclusion_auto"]["salida"], dtype={"id": str}).set_index("id")
    comp = comp.assign(automatico=np.where(auto.loc[comp.index, "sin_caja_rgb_cerca"].astype(bool), severa, baja))
    matrices_auto = {}
    for quien in ("primero", "segundo"):
        mq = matrices_auto[quien] = matriz(comp, quien, "automatico", [baja, severa], (quien, "automatico"))
        kq = kappa(mq)
        res.loc[len(res)] = {"comparacion": f"{quien} contra automático (informativo)", "comparables": len(comp),
                             "kappa": kq[0], "ic95_bajo": kq[1], "ic95_alto": kq[2],
                             "acuerdo": (comp[quien] == comp.automatico).mean(),
                             "desacuerdos": int((comp[quien] != comp.automatico).sum())}
    res = res.round(4)

    sub = carpeta / ea["carpeta"] / f"ronda{ronda}"
    sub.mkdir(parents=True, exist_ok=True)
    cols = ["n_muestra", "posicion", "indice_caja", "primero", "segundo", "aparte", "desacuerdo", "tiempo_segundo_s"]
    x = x.join(comp[["automatico"]])
    x[cols + ["automatico"]].to_csv(sub / "respuestas.csv", encoding="utf-8")
    res.to_csv(sub / "kappa.csv", index=False, encoding="utf-8")
    m.to_csv(sub / "matriz.csv", encoding="utf-8")
    completa.to_csv(sub / "tabla_completa.csv", encoding="utf-8")
    pd.concat([des, uno_solo])[cols].to_csv(sub / "desacuerdos.csv", encoding="utf-8")
    personas = [int(n) for n in pd.concat([des, uno_solo]).sort_values("n_muestra").n_muestra]
    if personas:
        crit = {int(f.n_muestra): f"primero: {texto[f.primero]} / segundo: {texto[f.segundo]}"
                for f in pd.concat([des, uno_solo]).itertuples()}
        revisar(cfg, rutas, personas=personas, nombre="imagenes", base=sub, criterio=crit)

    pd.set_option("display.width", 220)
    print(f"{len(x)} personas; aparte {int(x.aparte.sum())} ('no es persona' de alguno o 'fuera de cuadro'); "
          f"comparables {len(comp)}")
    print(res.to_string(index=False))
    print(f"\nDos clases (filas: primero; columnas: segundo)\n{m}\n\nTabla completa\n{completa}")
    for quien, mq in matrices_auto.items():
        print(f"\n{quien} contra automático (informativo)\n{mq}")
    print(f"\n'No es persona' de alguno: {int(x.aparte.sum())}; de uno solo: {len(uno_solo)}; respuestas del segundo en "
          f"menos de {ea['tiempo_rapido_s']} s: {len(rapidas)}")
    print(f"\nDesacuerdos en las dos clases:\n{des[cols].to_string()}")
    print(f"\n'No es persona' de uno solo:\n{uno_solo[cols].to_string()}")
    print(f"\nTiempo del segundo por persona (s): mediana {x.tiempo_segundo_s.median():.1f}, "
          f"menos de {ea['tiempo_rapido_s']} s: {len(rapidas)} ({', '.join(map(str, rapidas.n_muestra))})")
    cambios_txt = ""
    if ronda - 1 in ss["rondas"]:
        cambios_txt = cambios_entre_rondas(cfg, rutas, carpeta, ronda, x)
    agregar_a_bitacora(
        rutas["bitacora"], "4", f"concordancia entre anotadores (muestra, dos clases, ronda {ronda})",
        f"primero (visible RGB) contra segundo (modo simple, ronda {ronda}, regla {regla}); {len(x)} personas, aparte "
        f"{int(x.aparte.sum())} ('no es persona' de alguno)",
        f"kappa {k[0]:.3f} (IC {k[1]:.3f}-{k[2]:.3f}), acuerdo {(~comp.desacuerdo).mean():.1%}, {len(des)} "
        f"desacuerdos en {len(comp)}; 'no es persona' de uno solo: {len(uno_solo)}; informativo, contra el automático: "
        f"primero {res.kappa.iloc[1]:.3f}, segundo {res.kappa.iloc[2]:.3f}" + cambios_txt)
    return x, res, m


def cambios_entre_rondas(cfg, rutas, carpeta, ronda, x):
    """Compara la ronda `ronda` con la anterior: kappa entre anotadores de las dos (de sus kappa.csv) y respuestas del
    segundo que cambiaron, con la del primero. Escribe <entre_anotadores.carpeta>/ronda<N>/cambios.csv y rondas.csv."""
    ea = cfg["validacion_auto"]["entre_anotadores"]
    ss = cfg["oclusion"]["segundo_simple"]
    previa = ronda - 1
    sub = carpeta / ea["carpeta"]
    ruta_k = sub / f"ronda{previa}" / "kappa.csv"
    if not ruta_k.exists():
        raise SystemExit(f"No existe {ruta_k}: calcula antes la ronda {previa} (--ronda {previa})")
    prev, _ = respuestas_segundo(cfg, rutas, previa, x.index)
    c = x[["n_muestra", "posicion", "indice_caja", "primero", "segundo"]].join(
        prev[["segundo"]].rename(columns={"segundo": f"segundo_ronda{previa}"}))
    c = c.rename(columns={"segundo": f"segundo_ronda{ronda}"})[
        ["n_muestra", "posicion", "indice_caja", "primero", f"segundo_ronda{previa}", f"segundo_ronda{ronda}"]]
    a, b = c[f"segundo_ronda{previa}"], c[f"segundo_ronda{ronda}"]
    c["cambio"] = a != b
    c["con_el_primero"] = np.select([a.eq(c.primero) & b.ne(c.primero), a.ne(c.primero) & b.eq(c.primero)],
                                    ["deja de coincidir", "pasa a coincidir"], "")
    c[c.cambio].to_csv(sub / f"ronda{ronda}" / "cambios.csv", encoding="utf-8")
    filas = []
    for r in sorted(ss["rondas"]):
        rk = sub / f"ronda{r}" / "kappa.csv"
        if r <= ronda and rk.exists():
            kr = pd.read_csv(rk).iloc[0]
            filas.append({"ronda": r, "regla": ss["rondas"][r]["regla"], **kr.drop("comparacion").to_dict()})
    rondas = pd.DataFrame(filas)
    rondas.to_csv(sub / "rondas.csv", index=False, encoding="utf-8")
    # El segundo contra sí mismo (dos clases, sin las "no es persona" de ninguna de sus dos rondas), informativo.
    dos = c[a.isin(cfg["validacion_auto"]["niveles"]) & b.isin(cfg["validacion_auto"]["niveles"])]
    kk = kappa(matriz(dos, f"segundo_ronda{previa}", f"segundo_ronda{ronda}", cfg["validacion_auto"]["niveles"],
                      (f"ronda{previa}", f"ronda{ronda}")))
    n_pasa = int((c.con_el_primero == "pasa a coincidir").sum())
    n_deja = int((c.con_el_primero == "deja de coincidir").sum())
    print(f"\nRondas (primero contra segundo)\n{rondas.to_string(index=False)}")
    print(f"\nRespuestas del segundo que cambian de la ronda {previa} a la {ronda}: {int(c.cambio.sum())} de {len(c)} "
          f"(pasan a coincidir con el primero: {n_pasa}; dejan de coincidir: {n_deja}); segundo contra sí mismo en las "
          f"dos clases (informativo): kappa {kk[0]:.3f} en {len(dos)}")
    print(c[c.cambio].to_string())
    return (f"; respecto de la ronda {previa}: {int(c.cambio.sum())} respuestas del segundo cambian (pasan a coincidir "
            f"con el primero: {n_pasa}; dejan de coincidir: {n_deja}; el segundo contra sí mismo, kappa {kk[0]:.3f})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--partes", nargs="+", choices=PARTES, default=PARTES)
    ap.add_argument("--ronda", type=int, default=None,
                    help="ronda del segundo anotador para entre_anotadores (por omisión, segundo_simple.ronda_actual)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    carpeta = rutas["reports"] / cfg["validacion_auto"]["carpeta"]
    carpeta.mkdir(parents=True, exist_ok=True)
    for parte in PARTES:
        if parte in args.partes:
            print(f"\n===== {parte}")
            if parte == "entre_anotadores":
                entre_anotadores(cfg, rutas, carpeta, args.ronda)
            else:
                {"comparar": comparar, "no_es_persona": no_es_persona, "fondo": fondo}[parte](cfg, rutas, carpeta)


if __name__ == "__main__":
    main()
