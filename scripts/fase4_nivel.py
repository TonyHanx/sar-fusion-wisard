r"""Fase 4, cierre: nivel binario de oclusión de las 498 personas de los 310 fotogramas anotados (2026-11-01).

El nivel automático no pasó la validación de la ronda 2 (kappa 0.427, menor que `validacion_auto.kappa_minimo`), así
que el nivel es el del primer anotador en modo simple, con la regla aclarada:
- personas de la muestra (data/<oclusion.muestra_segundo>): sus respuestas de la ronda `oclusion.modo_simple.resto.ronda`
  (data/<modo_simple.rondas[ronda].primero>);
- las demás de la lista (data/<oclusion.personas>): data/<oclusion.modo_simple.resto.archivo>
  (anotar_oclusion.py --primero-simple-resto).
"Se ve en la RGB" = baja y "no se ve en la RGB" = severa (`validacion_auto.niveles`); "no es persona" = sin nivel
(columna `nivel` vacía). Las cajas de `oclusion.cajas_dudosas` tienen que ser "no es persona": si no, se detiene. Las dos
fuentes tienen que estar completas y no solaparse.

Escribe data/<nivel_final.salida>, el nivel que usa la fase 6: una fila por persona, en el orden de la lista, con su
caja térmica de WiSARD (`posicion`, `indice_caja` = línea de data/etiquetas/termica/<vuelo>/<vuelo>_<posicion>.txt, y
`ter_*` en px), `respuesta`, `nivel`, `no_es_persona`, `caja_dudosa`, `en_muestra`, el archivo de la respuesta y el
tiempo. Y en reports/<nivel_final.carpeta>/:
  niveles.csv              personas por nivel (muestra, resto y total) y fotogramas con alguna persona de cada nivel;
  tiempos.csv              tiempo por persona (cuantiles) y respuestas más rápidas que
                           `validacion_auto.entre_anotadores.tiempo_rapido_s`, de la muestra, del resto y del total;
  automatico.csv           informativo: kappa de Cohen (IC 95 % asintótico) del nivel a mano contra el automático
                           (data/<oclusion_auto.salida>: severa si no hay caja RGB de WiSARD cerca), sin las "no es
                           persona"; en las 498 y por separado en la muestra y en el resto;
  automatico_matriz.csv    matriz de confusión de las 498 (filas: a mano, con las "no es persona" aparte; columnas:
                           automático);
  automatico_por_tramo.csv informativo: respuestas y kappa contra el automático dentro y fuera de cada tramo de
                           `nivel_final.tramos`, en la muestra y en el resto por separado;
  no_es_persona.csv        las "no es persona", con su fotograma, el nivel automático y si están en las cajas dudosas.
Agrega una fila a la bitácora. Solo lee las respuestas y no toca el dataset original.

Uso:
    .venv\Scripts\python.exe scripts\fase4_nivel.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import os
import sys
import tempfile
import warnings
from pathlib import Path

import pandas as pd

from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from fase4_validacion_auto import fila_kappa, matriz, respuestas_simple

COLUMNAS = ["orden", "id", "vuelo", "posicion", "indice_caja", "cajas_en_fotograma", "ter_x0", "ter_y0", "ter_x1",
            "ter_y1", "en_muestra", "respuesta", "nivel", "no_es_persona", "caja_dudosa", "archivo_respuesta",
            "tiempo_s"]


def respuestas_resto(cfg, rutas, ids):
    """Respuestas del primero en modo simple de las personas que no son de la muestra; exige todas y solo esas."""
    ms = cfg["oclusion"]["modo_simple"]
    ruta = rutas["data"] / ms["resto"]["archivo"]
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}: falta anotar el resto (anotar_oclusion.py --primero-simple-resto)")
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


def escribir_atomico(df, ruta):
    """Escribe el CSV en un temporal de la misma carpeta y lo reemplaza; dice si cambió."""
    antes = ruta.read_bytes() if ruta.exists() else None
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    os.close(fd)
    df.to_csv(tmp, index=False, encoding="utf-8")
    nuevo = Path(tmp).read_bytes()
    os.replace(tmp, ruta)
    return "nuevo" if antes is None else "sin cambios" if antes == nuevo else "actualizado"


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
    r_re, ruta_re = respuestas_resto(cfg, rutas, resto)
    r = pd.concat([r_mu.assign(archivo_respuesta=ruta_mu.name), r_re.assign(archivo_respuesta=ruta_re.name)])
    r = r.reindex(personas.id)
    if r.respuesta.isna().any() or len(r) != len(personas):
        raise SystemExit("Las respuestas no cubren la lista de personas")
    clase = {"se_ve_rgb": baja, "no_se_ve_rgb": severa, "no_es_persona": ""}
    malas = sorted(set(r.respuesta) - set(clase))
    if malas:
        raise SystemExit(f"Respuestas desconocidas: {malas}")

    dudosas = {c["id"]: c for c in leer_yaml(RAIZ / o["cajas_dudosas"])["cajas"]}
    for i, c in dudosas.items():
        q = personas.loc[i]
        if (int(q.posicion), int(q.indice_caja)) != (c["posicion"], c["indice_caja"]):
            raise SystemExit(f"{o['cajas_dudosas']}: {i} no coincide con la lista de personas")
        if r.respuesta[i] != "no_es_persona":
            raise SystemExit(f"{o['cajas_dudosas']}: {i} es '{r.respuesta[i]}' para el primero, no 'no es persona'")

    niv = personas[COLUMNAS[:10]].copy()
    niv["en_muestra"] = niv.id.isin(muestra)
    niv["respuesta"] = r.respuesta
    niv["nivel"] = niv.respuesta.map(clase)
    niv["no_es_persona"] = niv.respuesta == "no_es_persona"
    niv["caja_dudosa"] = niv.id.isin(dudosas)
    niv["archivo_respuesta"] = r.archivo_respuesta
    niv["tiempo_s"] = r.tiempo_s.astype(float).round(1)
    niv = niv[COLUMNAS].reset_index(drop=True)
    estado = escribir_atomico(niv, data / nf["salida"])
    print(f"Nivel final -> {data / nf['salida']} ({estado}): {len(niv)} personas")

    # ---- personas y fotogramas por nivel
    nombre = {baja: baja, severa: severa, "": "no_es_persona"}
    niv["grupo"] = niv.nivel.map(nombre)
    grupos = [baja, severa, "no_es_persona"]
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
        x = x[~x.no_es_persona]
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
                c = x[~x.no_es_persona]
                with warnings.catch_warnings():  # con un solo nivel en el automático, kappa 0 y sin z (statsmodels)
                    warnings.simplefilter("ignore", RuntimeWarning)
                    fk, _ = fila_kappa("", c, "nivel", "automatico", [baja, severa])
                filas.append({"tramo": lugar, "personas": g, "n": len(x), "se_ve": int((x.nivel == baja).sum()),
                              "no_se_ve": int((x.nivel == severa).sum()), "no_es_persona": int(x.no_es_persona.sum()),
                              "automatico_severa": int((x.automatico == severa).sum()), "comparables": len(c),
                              "kappa": fk["kappa"], "se_ve_y_auto_severa":
                                  int(((c.nivel == baja) & (c.automatico == severa)).sum())})
    if filas:
        tr = pd.DataFrame(filas)
        tr.to_csv(carpeta / "automatico_por_tramo.csv", index=False, encoding="utf-8")
        print(tr.to_string(index=False))

    # ---- "no es persona"
    nep = niv[niv.no_es_persona][["orden", "id", "posicion", "indice_caja", "cajas_en_fotograma", "en_muestra",
                                  "caja_dudosa", "automatico", "archivo_respuesta"]]
    nep.to_csv(carpeta / "no_es_persona.csv", index=False, encoding="utf-8")
    print(f"'No es persona': {len(nep)} (cajas dudosas: {int(nep.caja_dudosa.sum())}); fotogramas "
          f"{nep.posicion.min()} a {nep.posicion.max()}")

    k0 = ka.iloc[0]
    t0 = tiempos.set_index("personas")
    agregar_a_bitacora(
        rutas["bitacora"], "4", "nivel de oclusión final (a mano, 498 personas de los 310 fotogramas anotados)",
        f"primer anotador en modo simple, regla aclarada: muestra ({len(muestra)}) de la ronda {ronda} "
        f"({ruta_mu.name}) + resto ({len(resto)}) ({ruta_re.name}); se ve = {baja}, no se ve = {severa}, "
        f"no es persona = sin nivel; salida data/{nf['salida']}",
        f"{baja} {int(tabla.total[0])}, {severa} {int(tabla.total[1])}, no es persona {int(tabla.total[2])} "
        f"(cajas dudosas {len(dudosas)}); mediana por persona {t0.mediana_s['total']} s (muestra "
        f"{t0.mediana_s['muestra']} s, resto {t0.mediana_s['resto']} s); informativo, contra el automático: kappa "
        f"{k0.kappa:.3f} (IC {k0.ic95_bajo:.3f}-{k0.ic95_alto:.3f}), acuerdo {100 * k0.acuerdo:.1f}%, "
        f"{k0.desacuerdos} desacuerdos en {k0.comparables}")
    print(f"Tablas en {carpeta}; fila nueva en la bitácora")


if __name__ == "__main__":
    main()
