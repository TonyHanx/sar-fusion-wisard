r"""Fase 4, cierre: nivel binario de oclusión de las 498 personas de los 310 fotogramas anotados (2026-11-01).

El nivel automático no pasó la validación de la ronda 2 (kappa 0.427, menor que `validacion_auto.kappa_minimo`), así
que el nivel es el del primer anotador en modo simple, con la regla aclarada:
- personas de la muestra (data/<oclusion.muestra_segundo>): sus respuestas de la ronda `oclusion.modo_simple.resto.ronda`
  (data/<modo_simple.rondas[ronda].primero>);
- las demás de la lista (data/<oclusion.personas>): data/<oclusion.modo_simple.resto.archivo>
  (anotar_oclusion.py --primero-simple-resto).
- reanotaciones (`oclusion.modo_simple.reanotaciones`, anotar_oclusion.py --primero-simple-reanotar NOMBRE): sus
  respuestas reemplazan las anteriores de las personas con fotograma entre `desde` y `hasta` (decidido el 2026-11-01
  para la escena en sombra). Tienen que estar completas; si falta el archivo, se detiene. La respuesta anterior queda
  en `respuesta_anterior` (y en su archivo, que no se toca).
"Se ve en la RGB" = baja y "no se ve en la RGB" = severa (`validacion_auto.niveles`); "no es persona" = sin nivel
(columna `nivel` vacía). También quedan sin nivel, por decisión, las "no es persona" de los dos anotadores en la ronda 2
(columna `los_dos_no_es_persona`), aunque una reanotación las cambie (lo avisa). `caja_dudosa` = sin nivel: son las cajas
que scripts/fase4_cajas_dudosas.py pasa a `oclusion.cajas_dudosas`. Las fuentes tienen que estar completas y no
solaparse.

Escribe data/<nivel_final.salida>, el nivel que usa la fase 6: una fila por persona, en el orden de la lista, con su
caja térmica de WiSARD (`posicion`, `indice_caja` = línea de data/etiquetas/termica/<vuelo>/<vuelo>_<posicion>.txt, y
`ter_*` en px), `respuesta`, `nivel`, `no_es_persona`, `caja_dudosa`, `en_muestra`, el archivo de la respuesta y el
tiempo. Si el archivo ya existía y cambia, guarda antes una copia en data/<oclusion.respaldos>/. Y en
reports/<nivel_final.carpeta>/:
  niveles.csv              personas por nivel (muestra, resto y total) y fotogramas con alguna persona de cada nivel;
  tiempos.csv              tiempo por persona (cuantiles) y respuestas más rápidas que
                           `validacion_auto.entre_anotadores.tiempo_rapido_s`, de la muestra, del resto y del total;
  automatico.csv           informativo: kappa de Cohen (IC 95 % asintótico) del nivel a mano contra el automático
                           (data/<oclusion_auto.salida>: severa si no hay caja RGB de WiSARD cerca), sin las "no es
                           persona" (sin nivel); en las 498 y por separado en la muestra y en el resto;
  automatico_matriz.csv    matriz de confusión de las 498 (filas: a mano, con las "no es persona" aparte; columnas:
                           automático);
  automatico_por_tramo.csv informativo: respuestas y kappa contra el automático dentro y fuera de cada tramo de
                           `nivel_final.tramos`, en la muestra y en el resto por separado;
  no_es_persona.csv        las personas sin nivel (cajas dudosas), con su fotograma, el nivel automático y su respuesta;
  reanotacion_<NOMBRE>.csv respuesta anterior y nueva de cada persona de la reanotación, y
  reanotacion_<NOMBRE>_tabla.csv la tabla de cambios (filas: anterior; columnas: nueva).
Agrega una fila a la bitácora. Solo lee las respuestas y no toca el dataset original.

Uso:
    .venv\Scripts\python.exe scripts\fase4_nivel.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import os
import shutil
import sys
import tempfile
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

from comun import agregar_a_bitacora, leer_rutas, leer_yaml
from fase4_validacion_auto import fila_kappa, matriz, respuestas_simple

COLUMNAS = ["orden", "id", "vuelo", "posicion", "indice_caja", "cajas_en_fotograma", "ter_x0", "ter_y0", "ter_x1",
            "ter_y1", "en_muestra", "respuesta", "nivel", "no_es_persona", "los_dos_no_es_persona", "caja_dudosa",
            "archivo_respuesta", "reanotacion", "respuesta_anterior", "tiempo_s"]


def respuestas_archivo(ruta, ids, falta):
    """Respuestas del primero en modo simple de `ruta`; exige todas las `ids` y solo esas."""
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}: {falta}")
    df = pd.read_csv(ruta, dtype={"id": str})
    if df.id.duplicated().any():
        raise SystemExit(f"{ruta}: personas repetidas")
    df = df.set_index("id")
    faltan, sobran = [i for i in ids if i not in df.index], sorted(set(df.index) - set(ids))
    if faltan or sobran:
        raise SystemExit(f"{ruta}: faltan {len(faltan)} de {len(ids)} personas y sobran {len(sobran)} "
                         f"({(faltan or sobran)[0]})")
    if set(df.anotador) != {"primero_simple"}:
        raise SystemExit(f"{ruta}: anotaciones de {sorted(set(df.anotador))}, se esperaba primero_simple")
    return df.loc[list(ids)], ruta


def escribir_atomico(df, ruta, respaldos):
    """Escribe el CSV en un temporal de la misma carpeta y lo reemplaza; si cambia, antes copia el anterior a
    `respaldos`. Dice qué pasó."""
    antes = ruta.read_bytes() if ruta.exists() else None
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    os.close(fd)
    df.to_csv(tmp, index=False, encoding="utf-8")
    nuevo = Path(tmp).read_bytes()
    if antes is None:
        os.replace(tmp, ruta)
        return "nuevo"
    if antes == nuevo:
        os.remove(tmp)
        return "sin cambios"
    respaldos.mkdir(parents=True, exist_ok=True)
    copia = respaldos / f"{ruta.stem}_{datetime.now():%Y%m%d-%H%M%S}{ruta.suffix}"
    shutil.copy2(ruta, copia)
    os.replace(tmp, ruta)
    return f"actualizado; el anterior quedó en {copia}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    o, va, nf = cfg["oclusion"], cfg["validacion_auto"], cfg["nivel_final"]
    data = rutas["data"]
    baja, severa = va["niveles"]
    carpeta = rutas["reports"] / nf["carpeta"]
    carpeta.mkdir(parents=True, exist_ok=True)

    personas = pd.read_csv(data / o["personas"], dtype={"id": str}).sort_values("orden").set_index("id", drop=False)
    muestra = list(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).sort_values("orden").id)
    resto = [i for i in personas.id if i not in set(muestra)]
    ronda = o["modo_simple"]["resto"]["ronda"]
    r_mu, ruta_mu = respuestas_simple(cfg, rutas, ronda, "primero", muestra)
    if r_mu is None:
        raise SystemExit(f"La ronda {ronda} no tiene archivo del primer anotador")
    r_re, ruta_re = respuestas_archivo(data / o["modo_simple"]["resto"]["archivo"], resto,
                                       "falta anotar el resto (anotar_oclusion.py --primero-simple-resto)")
    r = pd.concat([r_mu.assign(archivo_respuesta=ruta_mu.name), r_re.assign(archivo_respuesta=ruta_re.name)])
    r = r.reindex(personas.id)
    if r.respuesta.isna().any() or len(r) != len(personas):
        raise SystemExit("Las respuestas no cubren la lista de personas")
    r["reanotacion"], r["respuesta_anterior"] = "", ""

    # ---- reanotaciones: reemplazan la respuesta de las personas de su tramo
    reanot = o["modo_simple"].get("reanotaciones", {})
    ya = set()
    for nombre_r, rr in reanot.items():
        ids_r = list(personas.id[personas.posicion.between(rr["desde"], rr["hasta"])])
        if ya & set(ids_r):
            raise SystemExit(f"La reanotación {nombre_r} se solapa con otra")
        ya |= set(ids_r)
        df, ruta = respuestas_archivo(data / rr["archivo"], ids_r,
                                      f"falta la reanotación {nombre_r} (anotar_oclusion.py --primero-simple-reanotar "
                                      f"{nombre_r})")
        r.loc[ids_r, "respuesta_anterior"] = r.loc[ids_r, "respuesta"]
        r.loc[ids_r, "respuesta"] = df.respuesta
        r.loc[ids_r, "tiempo_s"] = df.tiempo_s
        r.loc[ids_r, "archivo_respuesta"] = ruta.name
        r.loc[ids_r, "reanotacion"] = nombre_r
    clase = {"se_ve_rgb": baja, "no_se_ve_rgb": severa, "no_es_persona": ""}
    malas = sorted(set(r.respuesta) - set(clase))
    if malas:
        raise SystemExit(f"Respuestas desconocidas: {malas}")

    # ---- "no es persona" de los dos en la ronda 2: sin nivel por decisión
    r_se, _ = respuestas_simple(cfg, rutas, ronda, "segundo", muestra)
    los_dos = set() if r_se is None else set(
        r_mu.index[(r_mu.respuesta == "no_es_persona") & (r_se.respuesta == "no_es_persona")])
    for i in sorted(los_dos):
        if r.respuesta[i] != "no_es_persona":
            print(f"AVISO: {i} era 'no es persona' para los dos en la ronda {ronda} y ahora es '{r.respuesta[i]}'; "
                  "queda sin nivel por decisión")

    niv = personas[COLUMNAS[:10]].copy()
    niv["en_muestra"] = niv.id.isin(muestra)
    niv["respuesta"] = r.respuesta
    niv["no_es_persona"] = niv.respuesta == "no_es_persona"
    niv["los_dos_no_es_persona"] = niv.id.isin(los_dos)
    niv["nivel"] = niv.respuesta.map(clase).where(~niv.los_dos_no_es_persona, "")
    niv["caja_dudosa"] = niv.nivel == ""
    niv["archivo_respuesta"] = r.archivo_respuesta
    niv["reanotacion"] = r.reanotacion
    niv["respuesta_anterior"] = r.respuesta_anterior
    niv["tiempo_s"] = r.tiempo_s.astype(float).round(1)
    niv = niv[COLUMNAS].reset_index(drop=True)
    estado = escribir_atomico(niv, data / nf["salida"], data / o["respaldos"])
    print(f"Nivel final -> {data / nf['salida']} ({estado}): {len(niv)} personas")

    # ---- reanotaciones: qué cambió
    for nombre_r in reanot:
        x = niv[niv.reanotacion == nombre_r]
        x[["orden", "id", "posicion", "indice_caja", "en_muestra", "respuesta_anterior", "respuesta", "nivel"]].assign(
            cambia=x.respuesta_anterior != x.respuesta).to_csv(carpeta / f"reanotacion_{nombre_r}.csv", index=False,
                                                               encoding="utf-8")
        resp = ["se_ve_rgb", "no_se_ve_rgb", "no_es_persona"]
        tab = pd.crosstab([pd.Categorical(x.en_muestra.map({True: "muestra", False: "resto"}), ["muestra", "resto"]),
                           pd.Categorical(x.respuesta_anterior, resp)], pd.Categorical(x.respuesta, resp),
                          dropna=False)
        tab.index.names, tab.columns.name = ["personas", "anterior"], "nueva"
        tab.to_csv(carpeta / f"reanotacion_{nombre_r}_tabla.csv", encoding="utf-8")
        print(f"Reanotación {nombre_r}: {len(x)} personas, cambian {int((x.respuesta_anterior != x.respuesta).sum())}")
        print(tab.to_string())

    # ---- personas y fotogramas por nivel
    nombre = {baja: baja, severa: severa, "": "sin_nivel"}
    niv["grupo"] = niv.nivel.map(nombre)
    grupos = [baja, severa, "sin_nivel"]
    filas = []
    for g in grupos + ["total"]:
        x = niv if g == "total" else niv[niv.grupo == g]
        filas.append({"nivel": g, "muestra": int(x.en_muestra.sum()), "resto": int((~x.en_muestra).sum()),
                      "total": len(x), "porcentaje": round(100 * len(x) / len(niv), 1),
                      "fotogramas_con_alguna": int(x.posicion.nunique()),
                      "cajas_dudosas": int(x.caja_dudosa.sum())})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(carpeta / "niveles.csv", index=False, encoding="utf-8")
    print(tabla.to_string(index=False))

    # ---- tiempos
    rapido = va["entre_anotadores"]["tiempo_rapido_s"]
    filas = []
    for g, x in [("muestra", niv[niv.en_muestra]), ("resto", niv[~niv.en_muestra]), ("total", niv)]:
        q = x.tiempo_s.quantile([0.25, 0.5, 0.75, 0.9])
        filas.append({"personas": g, "n": len(x), "mediana_s": round(q[0.5], 2), "p25_s": round(q[0.25], 2),
                      "p75_s": round(q[0.75], 2), "p90_s": round(q[0.9], 2), "maximo_s": x.tiempo_s.max(),
                      "id_maximo": x.id[x.tiempo_s.idxmax()], f"menos_de_{rapido}_s": int((x.tiempo_s < rapido).sum()),
                      "rapidas_se_ve": int(((x.tiempo_s < rapido) & (x.nivel == baja)).sum()),
                      "rapidas_no_se_ve": int(((x.tiempo_s < rapido) & (x.nivel == severa)).sum())})
    tiempos = pd.DataFrame(filas)
    tiempos.to_csv(carpeta / "tiempos.csv", index=False, encoding="utf-8")
    print(tiempos.to_string(index=False))

    # ---- informativo: contra el automático
    auto = pd.read_csv(data / cfg["oclusion_auto"]["salida"], dtype={"id": str}).set_index("id")
    faltan = sorted(set(niv.id) - set(auto.index))
    if faltan:
        raise SystemExit(f"{len(faltan)} personas sin nivel automático ({faltan[0]})")
    niv["automatico"] = niv.id.map(auto.sin_caja_rgb_cerca.astype(bool)).map({True: severa, False: baja})
    filas = []
    for g, x in [("498 personas", niv), ("muestra", niv[niv.en_muestra]), ("resto", niv[~niv.en_muestra])]:
        x = x[~x.caja_dudosa]
        f, _ = fila_kappa(f"a mano contra automático ({g})", x, "nivel", "automatico", [baja, severa])
        f["a_mano_baja_auto_severa"] = int(((x.nivel == baja) & (x.automatico == severa)).sum())
        f["a_mano_severa_auto_baja"] = int(((x.nivel == severa) & (x.automatico == baja)).sum())
        filas.append(f)
    ka = pd.DataFrame(filas)
    ka.to_csv(carpeta / "automatico.csv", index=False, encoding="utf-8")
    m = matriz(niv.assign(fila=niv.grupo), "fila", "automatico", grupos, ("a_mano", "automatico"))
    m = m[[baja, severa]]
    m.loc["total"] = m.sum()
    m["total"] = m.sum(axis=1)
    m.to_csv(carpeta / "automatico_matriz.csv", encoding="utf-8")
    print(ka.to_string(index=False))
    print(m.to_string())

    # ---- informativo: por tramo de fotogramas (dentro y fuera), en la muestra y en el resto
    filas = []
    for tramo, (a, b) in nf.get("tramos", {}).items():
        dentro = niv.posicion.between(a, b)
        for lugar, sel in [(f"{tramo} ({a}-{b})", dentro), (f"fuera de {tramo}", ~dentro)]:
            for g, s2 in [("muestra", niv.en_muestra), ("resto", ~niv.en_muestra)]:
                x = niv[sel & s2]
                c = x[~x.caja_dudosa]
                with warnings.catch_warnings():  # con un solo nivel en el automático, kappa 0 y sin z (statsmodels)
                    warnings.simplefilter("ignore", RuntimeWarning)
                    fk, _ = fila_kappa("", c, "nivel", "automatico", [baja, severa])
                filas.append({"tramo": lugar, "personas": g, "n": len(x), "se_ve": int((x.nivel == baja).sum()),
                              "no_se_ve": int((x.nivel == severa).sum()), "sin_nivel": int(x.caja_dudosa.sum()),
                              "automatico_severa": int((x.automatico == severa).sum()), "comparables": len(c),
                              "kappa": fk["kappa"], "se_ve_y_auto_severa":
                                  int(((c.nivel == baja) & (c.automatico == severa)).sum())})
    if filas:
        tr = pd.DataFrame(filas)
        tr.to_csv(carpeta / "automatico_por_tramo.csv", index=False, encoding="utf-8")
        print(tr.to_string(index=False))

    # ---- "no es persona"
    nep = niv[niv.caja_dudosa][["orden", "id", "posicion", "indice_caja", "cajas_en_fotograma", "en_muestra",
                                "respuesta", "los_dos_no_es_persona", "automatico", "archivo_respuesta"]]
    nep.to_csv(carpeta / "no_es_persona.csv", index=False, encoding="utf-8")
    print(f"Sin nivel: {len(nep)} (de los dos en la ronda {ronda}: {int(nep.los_dos_no_es_persona.sum())}); "
          f"fotogramas {nep.posicion.min()} a {nep.posicion.max()}")

    k0 = ka.iloc[0]
    t0 = tiempos.set_index("personas")
    agregar_a_bitacora(
        rutas["bitacora"], "4", "nivel de oclusión final (a mano, 498 personas de los 310 fotogramas anotados)",
        f"primer anotador en modo simple, regla aclarada: muestra ({len(muestra)}) de la ronda {ronda} "
        f"({ruta_mu.name}) + resto ({len(resto)}) ({ruta_re.name}); se ve = {baja}, no se ve = {severa}, "
        f"no es persona = sin nivel; reanotaciones: "
        + (", ".join(f"{k} ({v['desde']}-{v['hasta']}, {v['archivo']})" for k, v in reanot.items()) or "ninguna")
        + f"; salida data/{nf['salida']}",
        f"{baja} {int(tabla.total[0])}, {severa} {int(tabla.total[1])}, sin nivel {int(tabla.total[2])} "
        f"(de los dos {len(los_dos)}); reanotadas {int((niv.reanotacion != '').sum())}, cambian "
        f"{int(((niv.reanotacion != '') & (niv.respuesta != niv.respuesta_anterior)).sum())}; mediana por persona {t0.mediana_s['total']} s (muestra "
        f"{t0.mediana_s['muestra']} s, resto {t0.mediana_s['resto']} s); informativo, contra el automático: kappa "
        f"{k0.kappa:.3f} (IC {k0.ic95_bajo:.3f}-{k0.ic95_alto:.3f}), acuerdo {100 * k0.acuerdo:.1f}%, "
        f"{k0.desacuerdos} desacuerdos en {k0.comparables}")
    print(f"Tablas en {carpeta}; fila nueva en la bitácora")


if __name__ == "__main__":
    main()
