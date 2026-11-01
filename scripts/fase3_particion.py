r"""Fase 3a: partición por vuelo, etiquetas sin cajas repetidas y datasets de Ultralytics de los tres modelos.

1. Lee la partición (`particion`) y comprueba que cada vuelo con pares finales esté en una sola división.
2. Cajas repetidas: líneas idénticas (misma clase y mismas coordenadas) dentro de un mismo .txt de WiSARD. Se cuentan
   por vuelo y modalidad, en los pares finales y en los excluidos. Las etiquetas de los pares finales se escriben sin
   ellas (se queda la primera) en data/<etiquetas>/{rgb,termica}/<vuelo>/<vuelo>_<pos>.txt; el dataset original no se
   toca. Los pares excluidos no entran en ningún dataset, así que sus repetidas no se escriben.
3. Para cada modelo, data/<carpeta>/<modelo>/images/<división>/<vuelo>_<pos>.<ext> (enlace duro a data/alineados) y
   labels/<división>/<vuelo>_<pos>.txt (las etiquetas térmicas sin repetidas, las mismas para los tres modelos), y el
   yaml de Ultralytics (path, train, val, test, channels, names). Las carpetas de los datasets y de las etiquetas se
   rehacen enteras en cada corrida.
4. Resumen por vuelo y división: pares, pares con persona, personas (cajas térmicas, por fotograma), pares "solo
   térmica", pares sin persona (fondo) y episodios.
5. Verificación con Ultralytics: check_det_dataset de cada yaml; YOLODataset de cada división (imágenes, etiquetas,
   fondo, corruptas, instancias); y en `muestras_verificacion` imágenes al azar (seed) de la prueba, el tensor que
   recibe el modelo comparado con los PNG de data/alineados.
6. Agrega una fila a la bitácora. No entrena nada.

Uso:
    .venv\Scripts\python.exe scripts\fase3_particion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import os
import shutil
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, pares_anotados
from conteo_particion import episodios

RUTA_ETIQUETA = {"rgb": "ruta_rgb", "termica": "ruta_termica"}


def sin_repetidas(ruta_txt):
    """Líneas de un .txt YOLO sin las repetidas (se queda la primera) y cuántas se quitaron."""
    vistas, lineas, total = set(), [], 0
    for linea in Path(ruta_txt).read_text().splitlines():
        partes = linea.split()
        if not partes:
            continue
        if len(partes) != 5 or partes[0] != "0":
            raise SystemExit(f"{ruta_txt}: línea inesperada {linea!r} (se esperaba 'clase cx cy w h' con clase 0)")
        total += 1
        clave = tuple(map(float, partes[1:]))
        if clave not in vistas:
            vistas.add(clave)
            lineas.append(" ".join(partes))
    return lineas, total - len(lineas)


def vaciar(carpeta, data):
    """Borra una carpeta generada por este script, solo si está dentro de data/."""
    carpeta = Path(carpeta).resolve()
    if data.resolve() not in carpeta.parents:
        raise SystemExit(f"No se borra {carpeta}: no está dentro de {data}")
    if carpeta.exists():
        shutil.rmtree(carpeta)


def enlazar(origen, destino, modo):
    if modo == "duro":
        os.link(origen, destino)
    elif modo == "copia":
        shutil.copy2(origen, destino)
    else:
        raise SystemExit(f"enlace desconocido: {modo}")


def leer_division(ruta):
    part = leer_yaml(ruta)
    division = {}
    for d, vuelos in part.items():
        for v in vuelos:
            if v in division:
                raise SystemExit(f"{v} está en dos divisiones: {division[v]} y {d}")
            division[v] = d
    return division


def verificar(cfg_modelos, divisiones, salida, rutas_yaml, n, seed, alineados, indice):
    """Lee cada dataset con Ultralytics como lo hará el entrenamiento y compara algunos tensores con los PNG."""
    from ultralytics.data.dataset import YOLODataset
    from ultralytics.data.utils import check_det_dataset, load_dataset_cache_file

    filas, muestras = [], []
    por_nombre = {Path(r.rgb).stem: r for r in indice.itertuples()}
    for modelo, m in cfg_modelos.items():
        datos = check_det_dataset(str(rutas_yaml[modelo]))
        if datos.get("channels", 3) != m["channels"]:
            raise SystemExit(f"{modelo}: Ultralytics leyó channels {datos.get('channels')}, se esperaba {m['channels']}")
        for d in divisiones.values():
            ds = YOLODataset(img_path=datos[d], imgsz=640, augment=False, data=datos, task="detect")
            cache = load_dataset_cache_file(Path(ds.label_files[0]).parent.with_suffix(".cache"))
            nf, nm, ne, nc, _ = cache["results"]
            filas.append({"modelo": modelo, "division": d, "channels": datos.get("channels", 3), "imagenes": len(ds),
                          "con_etiqueta": nf, "sin_archivo_etiqueta": nm, "fondo": ne, "corruptas": nc,
                          "instancias": int(sum(len(lb["cls"]) for lb in ds.labels)), "avisos": len(cache["msgs"])})
            if d != divisiones["prueba"]:
                continue
            for i in sorted(np.random.default_rng(seed).choice(len(ds), n, replace=False)):
                item = ds[int(i)]
                stem = Path(item["im_file"]).stem
                fila = por_nombre[stem]
                rgb = cv2.imread(str(alineados / fila.rgb), cv2.IMREAD_COLOR)[..., ::-1]  # R, G, B
                ter = cv2.imread(str(alineados / fila.termica), cv2.IMREAD_UNCHANGED)
                t = item["img"].numpy()  # C, H, W después de LetterBox y Format, como entra al modelo
                y0, x0 = (t.shape[1] - ter.shape[0]) // 2, (t.shape[2] - ter.shape[1]) // 2
                t = t[:, y0:y0 + ter.shape[0], x0:x0 + ter.shape[1]].transpose(1, 2, 0).astype(int)
                esperado = {"fusion": np.dstack([rgb, ter]), "rgb": rgb, "termico": np.dstack([ter] * 3)}[modelo]
                muestras.append({"modelo": modelo, "imagen": stem, "forma_tensor": tuple(item["img"].shape),
                                 "dif_max_con_png": int(np.abs(t - esperado).max()),
                                 "canales_iguales": bool((t == t[..., :1]).all()),
                                 "instancias": len(item["cls"])})
    return pd.DataFrame(filas), pd.DataFrame(muestras)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    c = cfg["datasets"]
    rutas = leer_rutas(args.rutas)
    D, data = rutas["dataset"], rutas["data"]
    alineados = data / c["alineados"]
    division = leer_division(RAIZ / cfg["particion"])
    divisiones = c["divisiones"]  # nombre en la partición -> nombre de Ultralytics

    anotados = pares_anotados(data / cfg["pares"])
    indice = pd.read_csv(alineados / "indice.csv")
    finales = set(zip(anotados.vuelo[~anotados.excluido], anotados.posicion[~anotados.excluido]))
    if set(zip(indice.vuelo, indice.posicion)) != finales:
        raise SystemExit("data/alineados/indice.csv no coincide con los pares finales de data/pares.csv")
    faltan = sorted(set(indice.vuelo) - set(division))
    sobran = sorted(set(division) - set(indice.vuelo))
    if faltan or sobran:
        raise SystemExit(f"Partición: vuelos sin división {faltan}; vuelos sin pares finales {sobran}")
    if set(division.values()) != set(divisiones):
        raise SystemExit(f"Partición: se esperaban las divisiones {list(divisiones)}")

    # 1. etiquetas sin repetidas
    etq = data / c["etiquetas"]
    for carpeta in [data / c["carpeta"] / mo for mo in c["modelos"]] + [etq / mod for mod in RUTA_ETIQUETA]:
        vaciar(carpeta, data)
    rep = []
    for p in anotados.itertuples():
        for mod, col in RUTA_ETIQUETA.items():
            lineas, quitadas = sin_repetidas((D / getattr(p, col)).with_suffix(".txt"))
            rep.append({"vuelo": p.vuelo, "modalidad": mod, "excluido": p.excluido, "repetidas": quitadas,
                        "cajas": len(lineas) + quitadas})
            if not p.excluido:
                destino = etq / mod / p.vuelo / f"{p.vuelo}_{p.posicion:04d}.txt"
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text("".join(f"{x}\n" for x in lineas))
    rep = pd.DataFrame(rep)
    tabla_rep = (rep.assign(par=np.where(rep.excluido, "excluido", "final"), con_repetidas=rep.repetidas > 0)
                 .groupby(["vuelo", "modalidad", "par"])
                 .agg(pares=("cajas", "size"), cajas=("cajas", "sum"), repetidas=("repetidas", "sum"),
                      pares_con_repetidas=("con_repetidas", "sum"))
                 .reset_index())
    tabla_rep = tabla_rep[tabla_rep.repetidas > 0]
    tabla_rep.to_csv(rutas["reports"] / c["repetidas"], index=False, encoding="utf-8")
    print(f"Cajas repetidas: {int(rep.repetidas.sum())}")
    print(tabla_rep.to_string(index=False))

    # 2. datasets de Ultralytics
    rutas_yaml = {}
    for modelo, m in c["modelos"].items():
        base = data / c["carpeta"] / modelo
        for d in divisiones.values():
            (base / "images" / d).mkdir(parents=True)
            (base / "labels" / d).mkdir(parents=True)
        for f in indice.itertuples():
            d = divisiones[division[f.vuelo]]
            img = Path(getattr(f, m["imagenes"]))
            enlazar(alineados / img, base / "images" / d / img.name, c["enlace"])
            enlazar(etq / "termica" / f.vuelo / f"{f.vuelo}_{f.posicion:04d}.txt",
                    base / "labels" / d / f"{img.stem}.txt", c["enlace"])
        contenido = {"path": base.resolve().as_posix(), **{d: f"images/{d}" for d in divisiones.values()},
                     "channels": m["channels"], "names": c["nombres"]}
        rutas_yaml[modelo] = RAIZ / m["yaml"]
        rutas_yaml[modelo].write_text(
            f"# Dataset de Ultralytics del modelo '{modelo}'. Generado por scripts/fase3_particion.py con "
            f"{args.config}: no editar a mano.\n# Imágenes: data/{c['alineados']}/{m['imagenes']} (enlaces duros). "
            f"Etiquetas: las térmicas sin cajas repetidas.\n"
            + yaml.safe_dump(contenido, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"{modelo}: {base} -> {rutas_yaml[modelo].relative_to(RAIZ)}")

    # 3. resumen por vuelo y división
    filas = []
    for vuelo, g in anotados.groupby("vuelo"):
        fin = indice[indice.vuelo == vuelo].sort_values("posicion")
        if not len(fin):
            continue
        cuenta = {mod: np.array([len((etq / mod / vuelo / f"{vuelo}_{p:04d}.txt").read_text().splitlines())
                                 for p in fin.posicion]) for mod in RUTA_ETIQUETA}
        personas, rgb = cuenta["termica"], cuenta["rgb"]
        solo = (personas > 0) & (rgb == 0)
        estado = pd.Series("excluido", index=g.sort_values("posicion").posicion.to_numpy(), dtype=object)
        estado.loc[fin.posicion.to_numpy()] = np.where(personas > 0, "persona", "sin persona")
        estrictos, unidos = episodios(estado)
        filas.append({"division": division[vuelo], "vuelo": vuelo, "pares": len(fin),
                      "pares_con_persona": int((personas > 0).sum()), "pares_fondo": int((personas == 0).sum()),
                      "personas": int(personas.sum()), "pares_solo_termica": int(solo.sum()),
                      "personas_en_pares_solo_termica": int(personas[solo].sum()), "episodios": len(estrictos),
                      "episodios_si_excluidos_no_cortan": len(unidos)})
    resumen = pd.DataFrame(filas)
    orden = {d: k for k, d in enumerate(divisiones)}
    resumen = resumen.sort_values(["division", "vuelo"], key=lambda s: s.map(orden) if s.name == "division" else s)
    tot = resumen.groupby("division", sort=False).sum(numeric_only=True).reset_index().assign(vuelo="TOTAL")
    resumen = pd.concat([resumen, tot], ignore_index=True)
    resumen = resumen.sort_values("division", key=lambda s: s.map(orden), kind="stable")
    resumen.to_csv(rutas["reports"] / c["resumen"], index=False, encoding="utf-8")
    pd.set_option("display.width", 250)
    print(resumen.to_string(index=False))

    # 4. verificación con Ultralytics
    ver, muestras = verificar(c["modelos"], divisiones, data / c["carpeta"], rutas_yaml, c["muestras_verificacion"],
                              cfg["seed"], alineados, indice)
    print(ver.to_string(index=False))
    print(muestras.to_string(index=False))
    esperado = resumen[resumen.vuelo == "TOTAL"].set_index("division")
    ok = True
    for v in ver.itertuples():
        e = esperado.loc[next(k for k, d in divisiones.items() if d == v.division)]
        ok &= (v.imagenes == e.pares and v.instancias == e.personas and v.fondo == e.pares_fondo and v.corruptas == 0
               and v.sin_archivo_etiqueta == 0)
    ok &= bool((muestras.dif_max_con_png == 0).all())
    ok &= bool(muestras[muestras.modelo == "termico"].canales_iguales.all())
    ok &= bool((muestras[muestras.modelo == "fusion"].forma_tensor.map(lambda s: s[0]) == 4).all())
    print("Verificación correcta" if ok else "AVISO: la verificación encontró diferencias")
    pd.concat([ver.assign(tipo="division"), muestras.assign(tipo="muestra")], ignore_index=True).to_csv(
        rutas["reports"] / c["verificacion"], index=False, encoding="utf-8")

    t = esperado
    agregar_a_bitacora(
        rutas["bitacora"], "3a", "partición y datasets de Ultralytics (fusion, rgb, termico); sin entrenar",
        f"{cfg['particion']}; etiquetas térmicas sin cajas repetidas; enlace {c['enlace']}; seed={cfg['seed']}",
        "; ".join(f"{d}: {int(t.loc[d].pares)} pares, {int(t.loc[d].personas)} personas" for d in divisiones)
        + f"; {int(rep.repetidas.sum())} cajas repetidas quitadas; verificación con Ultralytics "
        + ("correcta" if ok else "con diferencias"))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
