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
  entre_anotadores  concordancia entre el primer anotador y el segundo sobre las dos clases: se ve en la RGB (baja) o
                 no (severa), en la ronda `--ronda` (por omisión, oclusion.modo_simple.ronda_actual). El segundo
                 responde en modo simple (data/<modo_simple.rondas[N].segundo>). El primero, en modo simple si la ronda
                 tiene su archivo (data/<modo_simple.rondas[N].primero>, desde la ronda 2); si no (ronda 1), su
                 anotación con cajas. Los archivos deben tener las 75. Las "no es persona" de cualquiera de los dos (y
                 las "fuera de cuadro" de las cajas del primero) van aparte. Kappa de Cohen con IC 95 % (el que
                 decide), matriz de confusión, tabla completa con las "no es persona", desacuerdos con sus imágenes (en
                 <entre_anotadores.carpeta>/ronda<N>/, también las "no es persona" de uno solo) y respuestas más rápidas
                 que `tiempo_rapido_s`. Con el primero en modo simple, además:
                 - el nivel automático contra el primero en modo simple, sobre las personas que el primero no marca "no
                   es persona" (automatico.csv, automatico_matriz.csv, automatico_desacuerdos.csv e
                   imagenes_automatico/);
                 - las respuestas del primero que cambian entre su anotación con cajas y el modo simple
                   (cambios_primero.csv, cambios_primero_tabla.csv e imagenes_cambios_primero/).
                 Desde la ronda 2, las respuestas del segundo que cambian respecto de la ronda anterior
                 (cambios_segundo.csv) y el kappa entre anotadores de cada ronda (rondas.csv). Agrega una fila a la
                 bitácora.

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
NOMBRE_ANOTADOR = {"primero": "primer", "segundo": "segundo"}


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
def respuestas_simple(cfg, rutas, ronda, quien, ids):
    """Respuestas de `quien` ("primero" o "segundo") en modo simple en la ronda `ronda`, pasadas a las clases (columna
    `clase`); exige las de todas las `ids`. (None, None) si la ronda no tiene archivo de ese anotador."""
    va, ms = cfg["validacion_auto"], cfg["oclusion"]["modo_simple"]
    baja, severa = va["niveles"]
    if ronda not in ms["rondas"]:
        raise SystemExit(f"La ronda {ronda} no está en oclusion.modo_simple.rondas ({sorted(ms['rondas'])})")
    archivo = ms["rondas"][ronda].get(quien)
    if archivo is None:
        return None, None
    ruta = rutas["data"] / archivo
    nombre = NOMBRE_ANOTADOR[quien]
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}: la ronda {ronda} del {nombre} anotador no está hecha (anotar_oclusion.py "
                         f"--{quien}-simple, con modo_simple.ronda_actual = {ronda})")
    df = pd.read_csv(ruta, dtype={"id": str}).set_index("id")
    faltan = [i for i in ids if i not in df.index]
    if faltan:
        raise SystemExit(f"La ronda {ronda} del {nombre} anotador no está completa: faltan {len(faltan)} de {len(ids)} "
                         f"personas en {ruta} (la primera: {faltan[0]})")
    if set(df.anotador) != {f"{quien}_simple"}:
        raise SystemExit(f"{ruta}: anotaciones de {sorted(set(df.anotador))}, se esperaba {quien}_simple")
    df = df.loc[list(ids)]
    df["clase"] = df.respuesta.map({"se_ve_rgb": baja, "no_se_ve_rgb": severa, "no_es_persona": "no_es_persona"})
    if df.clase.isna().any():
        raise SystemExit(f"{ruta}: respuestas desconocidas {sorted(set(df.respuesta[df.clase.isna()]))}")
    return df, ruta


def clase_cajas(man, baja, severa):
    """Clase del primer anotador según su anotación con cajas: baja si tiene visible RGB, severa si es "no visible"."""
    return pd.Series(np.select([man.no_es_persona, man.fuera_de_cuadro, man.rgb_estado == "no_visible",
                                man.rgb_estado == "caja"], ["no_es_persona", "fuera_de_cuadro", severa, baja],
                               "sin_resolver"), index=man.index)


def fila_kappa(nombre, x, a, b, niveles):
    """Kappa de dos columnas sobre las filas de `x`, con su matriz."""
    m = matriz(x, a, b, niveles, (a, b))
    k = kappa(m)
    return {"comparacion": nombre, "comparables": len(x), "kappa": k[0], "ic95_bajo": k[1], "ic95_alto": k[2],
            "acuerdo": (x[a] == x[b]).mean(), "desacuerdos": int((x[a] != x[b]).sum())}, m


def entre_anotadores(cfg, rutas, carpeta, ronda=None):
    """Concordancia entre el primer anotador y el segundo en la ronda `ronda` (por omisión, `modo_simple.ronda_actual`).
    El segundo responde en modo simple. El primero, también en modo simple si la ronda tiene su archivo (ronda 2); si
    no (ronda 1), su anotación con cajas. Salidas en <entre_anotadores.carpeta>/ronda<N>/. Con el primero en modo
    simple, además: el automático contra el primero en modo simple y qué respuestas del primero cambian respecto de su
    anotación con cajas. Desde la ronda 2, qué respuestas del segundo cambian respecto de la ronda anterior."""
    o, va = cfg["oclusion"], cfg["validacion_auto"]
    ea = va["entre_anotadores"]
    ms = o["modo_simple"]
    ronda = ms["ronda_actual"] if ronda is None else ronda
    regla = ms["rondas"].get(ronda, {}).get("regla", "?")
    baja, severa = va["niveles"]
    niveles = [baja, severa]
    texto = {baja: "se ve", severa: "no se ve", "no_es_persona": "no es persona", "fuera_de_cuadro": "fuera de cuadro"}
    man = leer_muestra(cfg, rutas)
    seg, ruta_s = respuestas_simple(cfg, rutas, ronda, "segundo", man.index)
    if seg is None:
        raise SystemExit(f"La ronda {ronda} no tiene archivo del segundo anotador en oclusion.modo_simple")
    pri, ruta_p = respuestas_simple(cfg, rutas, ronda, "primero", man.index)
    simple1 = pri is not None
    fuente = "modo simple" if simple1 else "cajas"
    print(f"Ronda {ronda} (regla {regla}). Segundo: {ruta_s}. Primero: " + (str(ruta_p) if simple1 else
                                                                          f"anotación con cajas ({o['anotaciones']})"))
    x = man[["n_muestra", "posicion", "indice_caja"]].copy()
    x["primero_cajas"] = clase_cajas(man, baja, severa)
    x["segundo"], x["tiempo_segundo_s"] = seg.clase, seg.tiempo_s
    if simple1:
        x["primero_simple"], x["tiempo_primero_s"] = pri.clase, pri.tiempo_s
    x["primero"] = x.primero_simple if simple1 else x.primero_cajas
    if (x.primero_cajas == "sin_resolver").any():
        raise SystemExit("Hay respuestas sin resolver en la anotación con cajas del primero")
    auto = pd.read_csv(rutas["data"] / cfg["oclusion_auto"]["salida"], dtype={"id": str}).set_index("id")
    auto_todas = pd.Series(np.where(auto.loc[x.index, "sin_caja_rgb_cerca"].astype(bool), severa, baja), index=x.index)

    # Primero contra segundo (el que decide), sin las "no es persona" de ninguno ni las "fuera de cuadro".
    x["aparte"] = x.primero.isin(["no_es_persona", "fuera_de_cuadro"]) | (x.segundo == "no_es_persona")
    x["desacuerdo"] = x.primero != x.segundo
    comp = x[~x.aparte]
    m = matriz(comp, "primero", "segundo", niveles, ("primero", "segundo"))
    k = kappa(m)
    todas = [baja, severa, "no_es_persona", "fuera_de_cuadro"]
    completa = matriz(x, "primero", "segundo", todas, ("primero", "segundo"))
    completa = completa.loc[completa.sum(axis=1) > 0, completa.sum(axis=0) > 0]
    des = comp[comp.desacuerdo]
    uno_solo = x[x.aparte & x.desacuerdo]  # "no es persona" para uno solo de los dos
    res = pd.DataFrame([{"comparacion": "primero contra segundo", "comparables": len(comp), "kappa": k[0],
                         "ic95_bajo": k[1], "ic95_alto": k[2], "acuerdo": (~comp.desacuerdo).mean(),
                         "desacuerdos": len(des)}])
    # Informativo: cada anotador contra el nivel automático, en las mismas personas comparables.
    comp = comp.assign(automatico=auto_todas[comp.index])
    matrices_auto = {}
    for quien in ("primero", "segundo"):
        fila, matrices_auto[quien] = fila_kappa(f"{quien} contra automático (informativo)", comp, quien, "automatico",
                                                niveles)
        res.loc[len(res)] = fila
    if simple1:  # informativo: la anotación con cajas del primero contra el segundo, en las mismas personas
        c2 = x[~x.primero_cajas.isin(["no_es_persona", "fuera_de_cuadro"]) & (x.segundo != "no_es_persona")]
        res.loc[len(res)], _ = fila_kappa("primero (cajas) contra segundo (informativo)", c2, "primero_cajas",
                                          "segundo", niveles)
    res = res.round(4)

    sub = carpeta / ea["carpeta"] / f"ronda{ronda}"
    sub.mkdir(parents=True, exist_ok=True)
    cols = ["n_muestra", "posicion", "indice_caja", "primero", "segundo", "aparte", "desacuerdo", "tiempo_segundo_s"]
    if simple1:
        cols += ["primero_cajas", "tiempo_primero_s"]
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
          f"comparables {len(comp)}; primero: {fuente}")
    print(res.to_string(index=False))
    print(f"\nDos clases (filas: primero; columnas: segundo)\n{m}\n\nTabla completa\n{completa}")
    for quien, mq in matrices_auto.items():
        print(f"\n{quien} contra automático (informativo)\n{mq}")
    print(f"\n'No es persona' de alguno: {int(x.aparte.sum())}; de uno solo: {len(uno_solo)}")
    print(f"\nDesacuerdos en las dos clases:\n{des[cols].to_string()}")
    print(f"\n'No es persona' de uno solo:\n{uno_solo[cols].to_string()}")
    for quien in ("primero", "segundo") if simple1 else ("segundo",):
        t = x[f"tiempo_{quien}_s"]
        rapidas = x[t < ea["tiempo_rapido_s"]]
        print(f"\nTiempo del {quien} por persona (s): mediana {t.median():.1f}, menos de {ea['tiempo_rapido_s']} s: "
              f"{len(rapidas)} ({', '.join(map(str, rapidas.n_muestra))})")

    extra = ""
    if simple1:
        extra += automatico_contra_primero_simple(cfg, rutas, sub, x, auto_todas, texto)
        extra += cambios_primero(cfg, rutas, sub, x, auto_todas, texto)
    if ronda - 1 in ms["rondas"]:
        extra += cambios_entre_rondas(cfg, rutas, carpeta, ronda, x)
    agregar_a_bitacora(
        rutas["bitacora"], "4", f"concordancia entre anotadores (muestra, dos clases, ronda {ronda})",
        f"primero ({'modo simple' if simple1 else 'anotación con cajas, visible RGB'}) contra segundo (modo simple); "
        f"ronda {ronda}, regla {regla}; {len(x)} personas, aparte {int(x.aparte.sum())} ('no es persona' de alguno o "
        f"'fuera de cuadro')",
        f"kappa {k[0]:.3f} (IC {k[1]:.3f}-{k[2]:.3f}), acuerdo {(~comp.desacuerdo).mean():.1%}, {len(des)} "
        f"desacuerdos en {len(comp)}; 'no es persona' de uno solo: {len(uno_solo)}; informativo, contra el automático: "
        f"primero {res.kappa.iloc[1]:.3f}, segundo {res.kappa.iloc[2]:.3f}" + extra)
    return x, res, m


def automatico_contra_primero_simple(cfg, rutas, sub, x, auto_todas, texto):
    """Nivel automático contra el primero en modo simple, sobre todas las personas que el primero no marca "no es
    persona" (como la comparación con su anotación con cajas, que dio el kappa de la decisión). Escribe automatico.csv,
    automatico_matriz.csv, automatico_desacuerdos.csv e imagenes_automatico/."""
    va = cfg["validacion_auto"]
    niveles = va["niveles"]
    a = x[x.primero_simple.isin(niveles)].assign(automatico=auto_todas)
    fila, m = fila_kappa("automático contra primero (modo simple)", a, "primero_simple", "automatico", niveles)
    r = pd.DataFrame([fila]).round(4)
    r["kappa_minimo"] = va["kappa_minimo"]
    r.to_csv(sub / "automatico.csv", index=False, encoding="utf-8")
    m.to_csv(sub / "automatico_matriz.csv", encoding="utf-8")
    des = a[a.primero_simple != a.automatico]
    des[["n_muestra", "posicion", "indice_caja", "primero_simple", "automatico", "primero_cajas", "segundo"]].to_csv(
        sub / "automatico_desacuerdos.csv", encoding="utf-8")
    if len(des):
        crit = {int(f.n_muestra): f"primero (simple): {texto[f.primero_simple]} / automatico: {texto[f.automatico]}"
                for f in des.itertuples()}
        revisar(cfg, rutas, personas=sorted(crit), nombre="imagenes_automatico", base=sub, criterio=crit)
    print(f"\nAutomático contra el primero en modo simple ({len(a)} personas sin 'no es persona' del primero)\n"
          f"{r.to_string(index=False)}\n{m}\nDesacuerdos: {', '.join(map(str, des.n_muestra)) or 'ninguno'}")
    return (f"; automático contra primero (modo simple): kappa {fila['kappa']:.3f} (IC {fila['ic95_bajo']:.3f}-"
            f"{fila['ic95_alto']:.3f}), {fila['desacuerdos']} desacuerdos en {len(a)}")


def cambios_primero(cfg, rutas, sub, x, auto_todas, texto):
    """Respuestas del primero que cambian entre su anotación con cajas y el modo simple. Escribe cambios_primero.csv
    (con el segundo y el automático), cambios_primero_tabla.csv (cajas contra modo simple) e imagenes_cambios_primero/."""
    niveles = cfg["validacion_auto"]["niveles"]
    c = x[["n_muestra", "posicion", "indice_caja", "primero_cajas", "primero_simple", "segundo"]].assign(
        automatico=auto_todas)
    c["cambio"] = c.primero_cajas != c.primero_simple
    antes, ahora = c.primero_cajas == c.automatico, c.primero_simple == c.automatico
    c["con_el_automatico"] = np.select([antes & ~ahora, ~antes & ahora], ["deja de coincidir", "pasa a coincidir"], "")
    cam = c[c.cambio]
    cam.to_csv(sub / "cambios_primero.csv", encoding="utf-8")
    filas = niveles + ["no_es_persona", "fuera_de_cuadro"]
    tabla = matriz(c, "primero_cajas", "primero_simple", filas, ("cajas", "modo_simple"))
    tabla = tabla.loc[tabla.sum(axis=1) > 0, tabla.sum(axis=0) > 0]
    tabla.to_csv(sub / "cambios_primero_tabla.csv", encoding="utf-8")
    dos = c[c.primero_cajas.isin(niveles) & c.primero_simple.isin(niveles)]
    kk = kappa(matriz(dos, "primero_cajas", "primero_simple", niveles, ("cajas", "modo_simple")))
    if len(cam):
        crit = {int(f.n_muestra): f"primero, cajas: {texto[f.primero_cajas]} / simple: {texto[f.primero_simple]}"
                for f in cam.itertuples()}
        revisar(cfg, rutas, personas=sorted(crit), nombre="imagenes_cambios_primero", base=sub, criterio=crit)
    tipos = cam.groupby(["primero_cajas", "primero_simple"]).size()
    print(f"\nRespuestas del primero que cambian entre su anotación con cajas y el modo simple: {len(cam)} de {len(c)}\n"
          f"{tabla}\n{cam.to_string()}\nEl primero contra sí mismo en las dos clases (informativo): kappa {kk[0]:.3f} "
          f"en {len(dos)}")
    detalle = ", ".join(f"{texto[a]} -> {texto[b]}: {n}" for (a, b), n in tipos.items())
    return (f"; respuestas del primero que cambian de cajas a modo simple: {len(cam)} de {len(c)}"
            + (f" ({detalle})" if detalle else "") + f", el primero contra sí mismo kappa {kk[0]:.3f}")


def cambios_entre_rondas(cfg, rutas, carpeta, ronda, x):
    """Compara la ronda `ronda` con la anterior: kappa entre anotadores de cada ronda (de sus kappa.csv, en rondas.csv)
    y respuestas del segundo que cambian, con la del primero en cada ronda (ronda<N>/cambios_segundo.csv)."""
    va, ea = cfg["validacion_auto"], cfg["validacion_auto"]["entre_anotadores"]
    ms = cfg["oclusion"]["modo_simple"]
    niveles = va["niveles"]
    previa = ronda - 1
    sub = carpeta / ea["carpeta"]
    ruta_k = sub / f"ronda{previa}" / "kappa.csv"
    if not ruta_k.exists():
        raise SystemExit(f"No existe {ruta_k}: calcula antes la ronda {previa} (--ronda {previa})")
    prev, _ = respuestas_simple(cfg, rutas, previa, "segundo", x.index)
    prim_prev, _ = respuestas_simple(cfg, rutas, previa, "primero", x.index)
    c = x[["n_muestra", "posicion", "indice_caja"]].copy()
    c[f"primero_ronda{previa}"] = x.primero_cajas if prim_prev is None else prim_prev.clase
    c[f"primero_ronda{ronda}"] = x.primero
    c[f"segundo_ronda{previa}"] = prev.clase
    c[f"segundo_ronda{ronda}"] = x.segundo
    a, b = c[f"segundo_ronda{previa}"], c[f"segundo_ronda{ronda}"]
    c["cambio"] = a != b
    c[c.cambio].to_csv(sub / f"ronda{ronda}" / "cambios_segundo.csv", encoding="utf-8")
    filas = []
    for r in sorted(ms["rondas"]):
        rk = sub / f"ronda{r}" / "kappa.csv"
        if r <= ronda and rk.exists():
            kr = pd.read_csv(rk).iloc[0]
            filas.append({"ronda": r, "regla": ms["rondas"][r]["regla"],
                          "primero": "modo simple" if "primero" in ms["rondas"][r] else "cajas",
                          **kr.drop("comparacion").to_dict()})
    rondas = pd.DataFrame(filas)
    rondas.to_csv(sub / "rondas.csv", index=False, encoding="utf-8")
    # El segundo contra sí mismo (dos clases, sin las "no es persona" de ninguna de sus dos rondas), informativo.
    dos = c[a.isin(niveles) & b.isin(niveles)]
    kk = kappa(matriz(dos, f"segundo_ronda{previa}", f"segundo_ronda{ronda}", niveles,
                      (f"ronda{previa}", f"ronda{ronda}")))
    print(f"\nRondas (primero contra segundo)\n{rondas.to_string(index=False)}")
    print(f"\nRespuestas del segundo que cambian de la ronda {previa} a la {ronda}: {int(c.cambio.sum())} de {len(c)}; "
          f"el segundo contra sí mismo en las dos clases (informativo): kappa {kk[0]:.3f} en {len(dos)}")
    print(c[c.cambio].to_string())
    return (f"; respuestas del segundo que cambian respecto de la ronda {previa}: {int(c.cambio.sum())} de {len(c)}, "
            f"el segundo contra sí mismo kappa {kk[0]:.3f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--partes", nargs="+", choices=PARTES, default=PARTES)
    ap.add_argument("--ronda", type=int, default=None,
                    help="ronda para entre_anotadores (por omisión, oclusion.modo_simple.ronda_actual)")
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
