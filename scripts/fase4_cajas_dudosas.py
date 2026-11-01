r"""Fase 4: cajas dudosas de la prueba para el cálculo "sin ellas" de la fase 6 (decidido el 2026-11-01).

Cajas dudosas anotadas: todas las personas sin nivel de data/<nivel_final.salida> (las "no es persona" del primer
anotador y las de los dos en la ronda 2). Las etiquetas de prueba no se tocan.

Seguimiento por los fotogramas no anotados del vuelo de prueba (`oclusion.vuelo`; anotados = posición múltiplo de
`oclusion.paso`): desde cada caja anotada (dudosa o con nivel), hacia adelante y hacia atrás, fotograma a fotograma,
hasta el fotograma anotado siguiente, sin incluirlo. En cada paso, la caja térmica de WiSARD (data/etiquetas/termica/)
más cercana por el centro, mutua y a `cajas_dudosas.max_dist_alturas` alturas o menos (la mayor de las dos alturas). Se
corta si falta un fotograma (par excluido). Cada caja de un fotograma no anotado queda:
  seguida       enlazada solo con cajas dudosas: es dudosa;
  en conflicto  enlazada con una caja dudosa y con una persona con nivel (el mismo objeto se respondió distinto en dos
                fotogramas anotados): va aparte, sin decidir;
  (si solo se enlaza con personas con nivel, o con nada, no es dudosa).

Escribe `oclusion.cajas_dudosas` (yaml generado: no editar a mano) con las tres listas; por caja, su archivo de
etiquetas (dentro de data/etiquetas/), la línea (`indice_caja`, desde 0), el texto exacto de la línea (comprobado
igual en las etiquetas de prueba de los tres datasets) y la caja en px. Y en reports/<cajas_dudosas.carpeta>/:
  cajas.csv        las cajas dudosas (anotadas, seguidas y en conflicto);
  resumen.csv      cuántas hay de cada tipo, con el umbral y con los de `sensibilidad_alturas`;
  conflictos.csv   los pares (caja dudosa, persona con nivel) unidos por cajas en conflicto;
  conflictos.jpg   por par, los fotogramas de uno al otro: térmica y RGB alineada alrededor de la caja (rojo: la caja
                   dudosa anotada; verde: la persona con nivel; amarillo: las cajas seguidas en medio).
No modifica data/ ni el dataset original.

Uso:
    .venv\Scripts\python.exe scripts\fase4_cajas_dudosas.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import sys

import cv2
import numpy as np
import pandas as pd

from comun import RAIZ, leer_cajas_yolo, leer_rutas, leer_yaml
from fase4_validacion_auto import respuestas_simple

ROJO, VERDE, AMARILLO = (40, 40, 230), (60, 200, 60), (0, 220, 255)


def cargar_cajas(carpeta, vuelo, tam):
    """{posición: (array N x 4 con cx, cy, w, h en px, líneas no vacías del .txt)} de las etiquetas térmicas."""
    w, h = tam
    cajas = {}
    for f in sorted(carpeta.glob(f"{vuelo}_*.txt")):
        lineas = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        c = np.array([[cx * w, cy * h, bw * w, bh * h] for _, cx, cy, bw, bh in leer_cajas_yolo(f)]).reshape(-1, 4)
        assert len(c) == len(lineas), f
        cajas[int(f.stem[-4:])] = (c, lineas)
    return cajas


def emparejar(cajas, p, k, q, umbral):
    """Caja de q que corresponde a la caja k de p, con su distancia en alturas, o None."""
    if q not in cajas or not len(cajas[q][0]) or not len(cajas[p][0]):
        return None
    a, b = cajas[p][0], cajas[q][0]
    d = np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])
    j = int(d[k].argmin())
    if int(d[:, j].argmin()) != k:
        return None
    dist = float(d[k, j] / max(a[k, 3], b[j, 3]))
    return (j, dist) if dist <= umbral else None


def seguir(cajas, anotadas, paso, umbral):
    """{(q, j): [(id anotada, dudosa, pasos con signo, distancia del último paso)]} de las cajas de fotogramas no
    anotados a las que llega alguna cadena desde una caja anotada."""
    llega = {}
    for (p, k), (i, dudosa) in anotadas.items():
        for s in (1, -1):
            pp, kk = p, k
            for n in range(1, paso):
                q = p + s * n
                e = emparejar(cajas, pp, kk, q, umbral)
                if e is None:
                    break
                llega.setdefault((q, e[0]), []).append((i, dudosa, s * n, round(e[1], 3)))
                pp, kk = q, e[0]
    return llega


def clasificar(llega):
    seguidas = {qj: v for qj, v in llega.items() if all(x[1] for x in v)}
    conflicto = {qj: v for qj, v in llega.items() if any(x[1] for x in v) and not all(x[1] for x in v)}
    return seguidas, conflicto


def caja_px(c):
    cx, cy, w, h = c
    return [round(float(v), 1) for v in (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)]


def recorte(img, c, lado, escala, color, otras=()):
    """Zona de `lado` px alrededor del centro de la caja `c`, ampliada, con la caja (y `otras`) dibujadas."""
    cx, cy = c[0], c[1]
    x0, y0 = int(round(cx - lado / 2)), int(round(cy - lado / 2))
    pad = lado
    grande = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    zona = grande[y0 + pad:y0 + pad + lado, x0 + pad:x0 + pad + lado]
    zona = cv2.resize(zona, (round(lado * escala), round(lado * escala)), interpolation=cv2.INTER_NEAREST)
    for cc, col in list(otras) + [(c, color)]:
        b = caja_px(cc)
        p0 = (round((b[0] - x0) * escala), round((b[1] - y0) * escala))
        p1 = (round((b[2] - x0) * escala), round((b[3] - y0) * escala))
        cv2.rectangle(zona, p0, p1, col, 1)
    return zona


def mosaico(pares, cajas, alineados, vuelo, cfg_m, ruta):
    lado, escala = cfg_m["lado_px"], cfg_m["escala"]
    t = round(lado * escala)
    filas = []
    for par in pares:
        crops_t, crops_r = [], []
        for q, k, color in par["cadena"]:
            nombre = f"{vuelo}_{q:04d}.png"
            ter = cv2.imread(str(alineados / "termica" / vuelo / nombre), cv2.IMREAD_GRAYSCALE)
            ter = cv2.cvtColor(ter, cv2.COLOR_GRAY2BGR)
            rgb = cv2.imread(str(alineados / "rgb" / vuelo / nombre), cv2.IMREAD_COLOR)
            c = cajas[q][0][k]
            otras = [(cajas[q][0][m], (150, 150, 150)) for m in range(len(cajas[q][0])) if m != k]
            for img, lista in ((ter, crops_t), (rgb, crops_r)):
                z = recorte(img, c, lado, escala, color, otras)
                cv2.putText(z, str(q), (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
                lista.append(z)
        sep = np.full((t, 4, 3), 255, np.uint8)
        gran = np.full((t, 16, 3), 255, np.uint8)
        fila = np.hstack(sum(([z, sep] for z in crops_t), [])[:-1] + [gran] + sum(([z, sep] for z in crops_r), [])[:-1])
        rot = np.full((24, fila.shape[1], 3), 255, np.uint8)
        cv2.putText(rot, par["texto"], (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        filas.append(np.vstack([rot, fila, np.full((8, fila.shape[1], 3), 255, np.uint8)]))
    if not filas:
        return
    ancho = max(f.shape[1] for f in filas)
    filas = [np.hstack([f, np.full((f.shape[0], ancho - f.shape[1], 3), 255, np.uint8)]) for f in filas]
    cab = np.full((26, ancho, 3), 255, np.uint8)
    cv2.putText(cab, "termica (izq.) y RGB alineada (der.); rojo: caja dudosa anotada; verde: persona con nivel; "
                     "amarillo: seguidas", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(str(ruta), np.vstack([cab] + filas), [cv2.IMWRITE_JPEG_QUALITY, 90])


def linea_yaml(d):
    partes = []
    for k, v in d.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        elif isinstance(v, list):
            v = "[" + ", ".join(str(x) for x in v) + "]"
        elif isinstance(v, str) and (" " in v or ":" in v):
            v = f'"{v}"'
        partes.append(f"{k}: {v}")
    return "{" + ", ".join(partes) + "}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    o, cd, data = cfg["oclusion"], cfg["cajas_dudosas"], rutas["data"]
    vuelo, paso = o["vuelo"], o["paso"]
    carpeta = rutas["reports"] / cd["carpeta"]
    carpeta.mkdir(parents=True, exist_ok=True)

    niv = pd.read_csv(data / cfg["nivel_final"]["salida"], dtype={"id": str})
    niv["dudosa"] = niv.nivel.isna() | (niv.nivel.astype(str) == "")
    muestra = list(pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).sort_values("orden").id)
    ronda = o["modo_simple"]["resto"]["ronda"]
    r1, _ = respuestas_simple(cfg, rutas, ronda, "primero", muestra)
    r2, _ = respuestas_simple(cfg, rutas, ronda, "segundo", muestra)
    los_dos = set(r1.index[(r1.respuesta == "no_es_persona") & (r2.respuesta == "no_es_persona")])
    faltan = los_dos - set(niv.id[niv.dudosa])
    if faltan:
        raise SystemExit(f"Las 'no es persona' de los dos tienen nivel en el nivel final: {sorted(faltan)}")

    rel = f"termica/{vuelo}"
    cajas = cargar_cajas(data / cfg["datasets"]["etiquetas"] / rel, vuelo, cfg["tam_termica"])
    pruebas = [data / cfg["datasets"]["carpeta"] / m / "labels" / cfg["datasets"]["divisiones"]["prueba"]
               for m in cfg["datasets"]["modelos"]]
    anotadas = {}
    for f in niv.itertuples():
        p, k = int(f.posicion), int(f.indice_caja)
        if p % paso or p not in cajas or k >= len(cajas[p][0]):
            raise SystemExit(f"{f.id}: no es una caja de un fotograma anotado")
        cx, cy, w, h = cajas[p][0][k]
        if max(abs(a - b) for a, b in zip((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                                          (f.ter_x0, f.ter_y0, f.ter_x1, f.ter_y1))) > 0.01:
            raise SystemExit(f"{f.id}: la caja de la etiqueta no coincide con la del nivel final")
        anotadas[(p, k)] = (f.id, bool(f.dudosa))
    n_anot = sum(len(c[0]) for p, c in cajas.items() if p % paso == 0)
    if n_anot != len(anotadas):
        raise SystemExit(f"Los fotogramas anotados tienen {n_anot} cajas y el nivel final {len(anotadas)} personas")

    def comprobar_linea(q, j):
        linea = cajas[q][1][j]
        for d in pruebas:
            lt = [l.strip() for l in (d / f"{vuelo}_{q:04d}.txt").read_text(encoding="utf-8").splitlines()
                  if l.strip()]
            if lt[j] != linea:
                raise SystemExit(f"{d}: la línea {j} de {q} no coincide con data/etiquetas")
        return linea

    # ---- seguimiento con el umbral y, solo para reportar, con los de sensibilidad
    resumen = []
    n_no_anot = sum(len(c[0]) for p, c in cajas.items() if p % paso)
    for u in sorted({cd["max_dist_alturas"], *cd["sensibilidad_alturas"]}):
        s, c = clasificar(seguir(cajas, anotadas, paso, u))
        resumen.append({"max_dist_alturas": u, "usado": u == cd["max_dist_alturas"],
                        "anotadas": int(niv.dudosa.sum()), "seguidas": len(s), "en_conflicto": len(c),
                        "total_sin_conflicto": int(niv.dudosa.sum()) + len(s),
                        "total_con_conflicto": int(niv.dudosa.sum()) + len(s) + len(c),
                        "cajas_en_fotogramas_no_anotados": n_no_anot,
                        "cajas_del_vuelo": n_no_anot + n_anot})
    resumen = pd.DataFrame(resumen)
    resumen.to_csv(carpeta / "resumen.csv", index=False, encoding="utf-8")
    print(resumen.to_string(index=False))
    seguidas, conflicto = clasificar(seguir(cajas, anotadas, paso, cd["max_dist_alturas"]))

    # ---- listas
    filas, yaml_anot, yaml_seg, yaml_conf = [], [], [], []
    for f in niv[niv.dudosa].itertuples():
        p, k = int(f.posicion), int(f.indice_caja)
        linea = comprobar_linea(p, k)
        d = {"id": f.id, "posicion": p, "indice_caja": k, "etiqueta": f"{rel}/{vuelo}_{p:04d}.txt", "linea": linea,
             "caja_px": caja_px(cajas[p][0][k]), "en_muestra": bool(f.en_muestra), "los_dos": f.id in los_dos}
        yaml_anot.append(d)
        filas.append({"tipo": "anotada", **d, "sigue_a": "", "con_nivel": ""})
    for tipo, grupo, lista in (("seguida", seguidas, yaml_seg), ("en_conflicto", conflicto, yaml_conf)):
        for (q, j), v in sorted(grupo.items()):
            linea = comprobar_linea(q, j)
            d = {"posicion": q, "indice_caja": j, "etiqueta": f"{rel}/{vuelo}_{q:04d}.txt", "linea": linea,
                 "caja_px": caja_px(cajas[q][0][j]), "sigue_a": sorted({x[0] for x in v if x[1]})}
            if tipo == "en_conflicto":
                d["con_nivel"] = sorted({x[0] for x in v if not x[1]})
            lista.append(d)
            filas.append({"tipo": tipo, "id": "", **{k: (";".join(x) if isinstance(x, list) and k in
                                                             ("sigue_a", "con_nivel") else x) for k, x in d.items()}})
    pd.DataFrame(filas).to_csv(carpeta / "cajas.csv", index=False, encoding="utf-8")

    r0 = resumen[resumen.usado].iloc[0]
    cab = f"""# Cajas térmicas de WiSARD dudosas de la prueba ({vuelo}). GENERADO por scripts/fase4_cajas_dudosas.py a partir
# de data/{cfg['nivel_final']['salida']}: no editar a mano. Decidido el 2026-11-01.
# - Las etiquetas de prueba NO se tocan: estas cajas siguen en data/etiquetas/termica/ y en
#   data/datasets/<modelo>/labels/test/ (enlaces duros), como las dejó WiSARD (sin cajas repetidas).
# - `cajas`: las personas sin nivel de los fotogramas anotados ("no es persona" del primer anotador; `los_dos` = también
#   del segundo en la ronda {ronda}). No entran en ningún nivel.
# - `seguidas`: cajas de los fotogramas no anotados enlazadas solo con cajas dudosas (seguimiento fotograma a
#   fotograma, caja más cercana, mutua y a {cd['max_dist_alturas']} alturas o menos; ver configs/fase3.yaml, cajas_dudosas).
# - `en_conflicto`: cajas de fotogramas no anotados enlazadas con una caja dudosa (`sigue_a`) y con una persona con
#   nivel (`con_nivel`): el mismo objeto se respondió distinto en dos fotogramas anotados. Falta decidir qué se hace.
# - Fase 6: las métricas se calculan con y sin las cajas dudosas ("sin ellas" = esas cajas se marcan como ignoradas).
# Por caja: `etiqueta` (dentro de data/etiquetas/), `indice_caja` (línea, desde 0, sin contar líneas vacías), `linea`
# (texto exacto: clase cx cy w h, YOLO normalizado) y `caja_px` (x0, y0, x1, y1 en px de la térmica, 640 x 512).
fuente: data/{cfg['nivel_final']['salida']}
max_dist_alturas: {cd['max_dist_alturas']}
resumen: {{anotadas: {int(r0.anotadas)}, de_los_dos: {len(los_dos)}, seguidas: {int(r0.seguidas)}, en_conflicto: \
{int(r0.en_conflicto)}, total_sin_conflicto: {int(r0.total_sin_conflicto)}, total_con_conflicto: \
{int(r0.total_con_conflicto)}, cajas_del_vuelo: {int(r0.cajas_del_vuelo)}}}
"""
    texto = cab
    for nombre, lista in (("cajas", yaml_anot), ("seguidas", yaml_seg), ("en_conflicto", yaml_conf)):
        texto += f"{nombre}:" + (" []\n" if not lista else "\n" + "".join(f"  - {linea_yaml(d)}\n" for d in lista))
    ruta_yaml = RAIZ / o["cajas_dudosas"]
    ruta_yaml.write_text(texto, encoding="utf-8")
    leido = leer_yaml(ruta_yaml)
    assert len(leido["cajas"]) == len(yaml_anot) and len(leido["en_conflicto"] or []) == len(yaml_conf)
    print(f"{ruta_yaml}: {len(yaml_anot)} anotadas, {len(yaml_seg)} seguidas, {len(yaml_conf)} en conflicto")

    # ---- pares en conflicto y mosaico
    pares = {}
    for (q, j), v in conflicto.items():
        for a in (x for x in v if x[1]):
            for b in (x for x in v if not x[1]):
                pares.setdefault((a[0], b[0]), []).append((q, j))
    por_id = niv.set_index("id")
    filas_p, mos = [], []
    for (a, b), medio in sorted(pares.items(), key=lambda kv: int(por_id.posicion[kv[0][0]])):
        pa, pb = int(por_id.posicion[a]), int(por_id.posicion[b])
        ka, kb = int(por_id.indice_caja[a]), int(por_id.indice_caja[b])
        cadena = sorted([(pa, ka, ROJO), (pb, kb, VERDE)] + [(q, j, AMARILLO) for q, j in sorted(set(medio))])
        filas_p.append({"dudosa": a, "posicion_dudosa": pa, "respuesta_dudosa": por_id.respuesta[a],
                        "con_nivel": b, "posicion_con_nivel": pb, "nivel": por_id.nivel[b],
                        "cajas_en_medio": len(set(medio))})
        mos.append({"cadena": cadena, "texto": f"{pa} (no es persona, caja {ka + 1})  <->  {pb} ({por_id.nivel[b]}, "
                                               f"caja {kb + 1})"})
    conf = pd.DataFrame(filas_p)
    conf.to_csv(carpeta / "conflictos.csv", index=False, encoding="utf-8")
    mosaico(mos, cajas, data / cfg["datasets"]["alineados"], vuelo, cd["mosaico"], carpeta / "conflictos.jpg")
    if len(conf):
        print(f"{len(conf)} pares en conflicto (dudosa <-> persona con nivel):")
        print(conf.to_string(index=False))
    print(f"Tablas e imagen en {carpeta}")


if __name__ == "__main__":
    main()
