"""Fase 7, parte C1: datasets termico_ampliado y fusion_ampliado (sección `c1` de configs/fase7.yaml).

Partes:
  - componer: elige las imágenes nuevas de entrenamiento y cuenta la composición, sin escribir imágenes:
      * las de C0 que quedan tras la clasificación (runs/<carpeta>/c0/clasificacion/fotogramas.csv);
      * los pares anotados y excluidos de los vuelos de entrenamiento, salvo `excluidos_entrenamiento.salvo`;
      * las vacías nuevas, con el tope de `vacias.fraccion_maxima` del total de entrenamiento, al azar (seed) y
        repartidas por carpeta en proporción a sus vacías.
    Escribe runs/<carpeta>/c1/composicion.csv (una fila por imagen candidata) y las tablas por sitio y por carpeta,
    con el tiempo estimado por época.
  - construir: escribe las imágenes nuevas elegidas (térmica en gris, TIFF B, G, R, T con la RGB en 0 si no hay pareja
    real, y las etiquetas sin repetidas) en data/<salida>/, arma los dos datasets de Ultralytics con enlaces duros
    (la base y la validación enlazan a los datasets actuales, sin tocarlos) y los verifica: cuentas, lectura de todas
    las etiquetas con Ultralytics y `verificacion` TIFF y PNG al azar leídos como los recibe el modelo.

Uso:
  .venv\\Scripts\\python.exe -m src.ampliacion.c1_datasets_ampliados --config configs\\fase7.yaml --rutas configs\\rutas.yaml --parte componer
  .venv\\Scripts\\python.exe -m src.ampliacion.c1_datasets_ampliados --config configs\\fase7.yaml --rutas configs\\rutas.yaml --parte construir
"""
# Solo importaciones livianas arriba: en Windows cada proceso hijo vuelve a importar este módulo (comun importa torch).
import argparse
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import tifffile

# Raíz del repositorio (este archivo está en src/ampliacion/). Se calcula aquí y no se importa de src.comun porque
# src.comun importa torch, y los procesos de ProcessPoolExecutor importan este módulo al arrancar.
RAIZ = Path(__file__).resolve().parents[2]


def ruta(p):
    """Ruta absoluta: si es relativa, desde la raíz del repositorio."""
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def md(df, dec=1):
    """Tabla de pandas como tabla de Markdown, con `dec` decimales en los números con coma."""
    cols = list(df.columns)
    filas = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        filas.append("| " + " | ".join(f"{v:.{dec}f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(filas)


def lados_txt(txt, tam):
    """Lado mayor (px de la térmica) de las cajas de un .txt, sin las líneas repetidas (como la fase 3a)."""
    from src.comun import leer_cajas_yolo

    tw, th = tam
    cajas = list(dict.fromkeys(leer_cajas_yolo(txt))) if Path(txt).exists() else []
    return [max(w * tw, h * th) for _, _, _, w, h in cajas]


def tramos(lados, bordes, etiquetas):
    """Cuántas personas caen en cada tramo de tamaño (lado mayor en px)."""
    cuenta = np.histogram(lados, bins=bordes)[0] if len(lados) else np.zeros(len(etiquetas), int)
    return {f"tramo {e}": int(c) for e, c in zip(etiquetas, cuenta)}


def sitio(nombre):
    """Sitio de un vuelo, sacado de su nombre (AAMMDD_Sitio_...)."""
    return nombre.split("_")[1]


def cupos(disponibles, total):
    """Reparto proporcional con restos mayores: {carpeta: vacías disponibles} -> {carpeta: cupo}."""
    n = sum(disponibles.values())
    if n <= total:
        return dict(disponibles)
    exacto = {k: total * v / n for k, v in disponibles.items()}
    cupo = {k: int(np.floor(x)) for k, x in exacto.items()}
    resto = total - sum(cupo.values())
    for k in sorted(exacto, key=lambda k: (-(exacto[k] - cupo[k]), k))[:resto]:
        cupo[k] += 1
    return cupo


def componer(cfg, rutas, out):
    """Elige las imágenes nuevas de entrenamiento (las de C0 que quedan, los pares excluidos de los vuelos de
    entrenamiento y las vacías con su tope) y escribe la composición, sin escribir imágenes."""
    from src.comun import leer_yaml

    c = cfg["c1"]
    D = rutas["dataset"]
    tam = cfg["tam_termica"]
    bordes = [0] + cfg["tramos_px"] + [np.inf]
    etiquetas = [f"<{bordes[1]}"] + [f"{a}-{b}" for a, b in zip(bordes[1:-2], bordes[2:-1])] + [f">={bordes[-2]}"]
    part = leer_yaml(ruta(c["particion"]))
    pares = pd.read_csv(rutas["data"] / cfg["pares"])

    # base: el entrenamiento actual (mismas imágenes en termico y fusion)
    base = leer_yaml(ruta(c["base"]["termico"]))
    lab = ruta(base["path"]) / "labels" / "train"
    img = sorted((ruta(base["path"]) / base["train"]).iterdir())
    filas_base = []
    for f in img:
        lados = lados_txt(lab / f"{f.stem}.txt", tam)
        vuelo = f.stem.rsplit("_", 1)[0]
        filas_base.append({"stem": f.stem, "sitio": sitio(vuelo), "carpeta": vuelo, "cajas": len(lados), "lados": lados})
    base_df = pd.DataFrame(filas_base)

    # nuevas 1: las de C0 que quedan tras la clasificación
    f0 = pd.read_csv(out / "c0" / "clasificacion" / "fotogramas.csv")
    f0 = f0[f0.usar]
    n1 = pd.DataFrame({"fuente": "c0", "carpeta": f0.carpeta, "posicion": f0.posicion,
                       "ruta_termica": f0.carpeta + "/" + f0.archivo, "cajas": f0.cajas,
                       "lados": [[float(x) for x in str(l).split(";")] if isinstance(l, str) and l else []
                                 for l in f0.lados]})
    # nuevas 2: pares anotados y excluidos de los vuelos de entrenamiento
    g = pares[pares.vuelo.isin(part["entrenamiento"]) & pares.anotado & pares.excluido]
    for v, tr in c["excluidos_entrenamiento"]["salvo"].items():
        for a, b in tr:
            g = g[~((g.vuelo == v) & g.posicion.between(a, b))]
    lados2 = [lados_txt((D / r).with_suffix(".txt"), tam) for r in g.ruta_termica]
    n2 = pd.DataFrame({"fuente": "excluido de entrenamiento", "carpeta": g.carpeta_termica.to_numpy(),
                       "posicion": g.posicion.to_numpy(), "ruta_termica": g.ruta_termica.to_numpy(),
                       "cajas": [len(l) for l in lados2], "lados": lados2})
    nuevas = pd.concat([n1, n2], ignore_index=True)
    nuevas["sitio"] = nuevas.carpeta.map(sitio)
    nuevas["stem"] = nuevas.carpeta + "_" + nuevas.posicion.map("{:04d}".format)
    nuevas["persona"] = nuevas.cajas > 0

    # nada de validación ni de prueba, ni repetidas con la base
    otras = pares[pares.vuelo.isin(part["validacion"] + part["prueba"])]
    malas = set(nuevas.carpeta) & (set(otras.carpeta_termica) | set(cfg["prohibidas"]))
    if malas:
        raise SystemExit(f"Carpetas de validación o prueba entre las nuevas: {sorted(malas)}")
    if nuevas.stem.duplicated().any() or set(nuevas.stem) & set(base_df.stem):
        raise SystemExit("Nombres repetidos entre las nuevas o con la base")
    rutas_base = set(pares[pares.vuelo.isin(part["entrenamiento"]) & pares.anotado & ~pares.excluido].ruta_termica)
    if set(nuevas.ruta_termica) & rutas_base:
        raise SystemExit("Imágenes nuevas que ya están en la base")

    # pares reales aprobados (RGB real en la fusión)
    pr = c["pares_reales"]
    aprob = {pr["candidatos"][v] for v in pr["aprobados"]}
    nuevas["rgb_real"] = nuevas.carpeta.isin(aprob)
    nuevas["ruta_rgb"] = None
    if aprob:
        m = pares.set_index("ruta_termica").ruta_rgb
        sel = nuevas.rgb_real
        nuevas.loc[sel, "ruta_rgb"] = nuevas.loc[sel, "ruta_termica"].map(m)
        if nuevas.loc[sel, "ruta_rgb"].isna().any():
            raise SystemExit("Pares reales sin RGB en pares.csv")

    # tope de vacías nuevas: E <= f (N_base + P + E)  ->  E <= f / (1 - f) (N_base + P)
    fv = c["vacias"]["fraccion_maxima"]
    P = int(nuevas.persona.sum())
    e_max = int(np.floor(fv / (1 - fv) * (len(base_df) + P)))
    vac = nuevas[~nuevas.persona]
    cupo = cupos(vac.groupby("carpeta").size().to_dict(), e_max)
    nuevas["elegida"] = nuevas.persona
    for carpeta, k in cupo.items():
        idx = vac[vac.carpeta == carpeta].sort_values("posicion").index.to_numpy()
        rng = np.random.default_rng(c["vacias"]["seed"])
        nuevas.loc[rng.choice(idx, k, replace=False), "elegida"] = True
    nuevas["motivo"] = np.where(nuevas.elegida, "", "vacía fuera del cupo")

    destino = out / "c1"
    destino.mkdir(parents=True, exist_ok=True)
    guardar = nuevas.copy()
    guardar["lados"] = guardar.lados.map(lambda l: ";".join(f"{x:.2f}" for x in l))
    guardar[["stem", "fuente", "sitio", "carpeta", "posicion", "ruta_termica", "ruta_rgb", "rgb_real", "cajas",
             "persona", "elegida", "motivo", "lados"]].to_csv(destino / "composicion.csv", index=False)

    # tablas
    def resumen(df, clave):
        """Resumen de la composición agrupada por `clave`: imágenes, con persona, vacías, personas y tramos de tamaño.
        """
        filas = []
        for k, g in df.groupby(clave, sort=True):
            lados = [x for l in g.lados for x in l]
            filas.append({clave: k, "imagenes": len(g), "con_persona": int((g.cajas > 0).sum()),
                          "vacias": int((g.cajas == 0).sum()), "personas": len(lados), **tramos(lados, bordes, etiquetas)})
        return pd.DataFrame(filas)

    el = nuevas[nuevas.elegida]
    por_carpeta = resumen(el, "carpeta").merge(
        nuevas[~nuevas.persona].groupby("carpeta").size().rename("vacias_disponibles").reset_index(), how="left")
    por_carpeta["vacias_disponibles"] = por_carpeta.vacias_disponibles.fillna(0).astype(int)
    s_base = resumen(base_df, "sitio")
    s_base.insert(0, "parte", "base")
    s_new = resumen(el, "sitio")
    s_new.insert(0, "parte", "nuevas")
    tot = []
    for nombre, df in (("base", base_df), ("nuevas", el), ("total", pd.concat([base_df, el], ignore_index=True))):
        r = resumen(df.assign(todo="todo"), "todo").drop(columns="todo")
        r.insert(0, "parte", nombre)
        tot.append(r)
    tot = pd.concat(tot, ignore_index=True)
    por_sitio = pd.concat([s_base, s_new], ignore_index=True)
    n_total = len(base_df) + len(el)

    # tiempo por época, con las medidas de epocas.csv
    t = []
    for modelo, corrida in c["tiempo"]["corridas"].items():
        e = pd.read_csv(ruta(corrida) / "epocas.csv")
        e = e[e.epoca > 1]
        s_img = e.s_entrenamiento.median() / len(base_df)
        s_val = e.s_validacion_y_guardado.median()
        s = s_img * n_total + s_val
        t.append({"modelo": modelo, "medido_en": Path(corrida).name, "ms_por_imagen": 1000 * s_img,
                  "s_validacion": s_val, "imagenes": n_total, "s_por_epoca": s,
                  f"h_{c['tiempo']['epocas']}_epocas": s * c["tiempo"]["epocas"] / 3600})
    t = pd.DataFrame(t)
    por_carpeta.to_csv(destino / "por_carpeta.csv", index=False)
    por_sitio.to_csv(destino / "por_sitio.csv", index=False)
    tot.to_csv(destino / "total.csv", index=False)
    t.to_csv(destino / "tiempo.csv", index=False)
    texto = (f"Tope de vacías nuevas: {e_max} (base {len(base_df)}, nuevas con persona {P}, "
             f"vacías disponibles {len(vac)}; fracción {fv})\n\n" + md(tot) + "\n\n" + md(por_sitio) + "\n\n"
             + md(por_carpeta) + "\n\n" + md(t, 2) + "\n")
    (destino / "tablas.md").write_text(texto, encoding="utf-8")
    print(texto)


def sin_repetidas(ruta_txt):
    """Líneas de un .txt YOLO sin las repetidas (se queda la primera), como `sin_repetidas` de la fase 3a."""
    vistas, lineas = set(), []
    for linea in Path(ruta_txt).read_text().splitlines():
        partes = linea.split()
        if not partes:
            continue
        if len(partes) != 5 or partes[0] != "0":
            raise RuntimeError(f"{ruta_txt}: línea inesperada {linea!r}")
        clave = tuple(map(float, partes[1:]))
        if clave not in vistas:
            vistas.add(clave)
            lineas.append(" ".join(partes))
    return lineas


def procesar(t):
    """Una imagen nueva: lee la térmica (y la RGB si hay pareja real) del dataset original, solo lectura, y escribe la
    térmica en gris, el TIFF B, G, R, T y la etiqueta sin repetidas. Si ya están las tres salidas, no hace nada."""
    salidas = [t["salida_termica"], t["salida_fusion"], t["salida_etiqueta"]] + ([t["salida_rgb"]] if t["rgb"] else [])
    if all(Path(s).exists() for s in salidas):
        return t["stem"], False
    ter = cv2.imread(t["termica"], cv2.IMREAD_COLOR)
    if ter is None:
        raise RuntimeError(f"no se pudo leer {t['termica']}")
    gris = cv2.cvtColor(ter, cv2.COLOR_BGR2GRAY)
    if gris.shape[::-1] != tuple(t["tam_ter"]):
        raise RuntimeError(f"{t['termica']}: tamaño {gris.shape[::-1]}, se esperaba {tuple(t['tam_ter'])}")
    png = [cv2.IMWRITE_PNG_COMPRESSION, t["nivel_png"]]
    if t["rgb"]:
        from src.alineacion.alinear import alinear_rgb

        rgb = cv2.imread(t["rgb"], cv2.IMREAD_COLOR)
        if rgb is None:
            raise RuntimeError(f"no se pudo leer {t['rgb']}")
        al = alinear_rgb(rgb, np.array(t["H"], np.float64), t["tam_ter"], t["prerreducir"], t["interpolacion"])
        if not cv2.imwrite(t["salida_rgb"], al, png):
            raise RuntimeError(f"no se pudo escribir {t['salida_rgb']}")
    else:
        al = np.zeros((*gris.shape, 3), np.uint8)  # sin pareja: B, G, R en 0
    if not cv2.imwrite(t["salida_termica"], gris, png):
        raise RuntimeError(f"no se pudo escribir {t['salida_termica']}")
    tifffile.imwrite(t["salida_fusion"], np.dstack([al, gris]), photometric="rgb", extrasamples=["unspecified"],
                     compression=t["tiff_compresion"], compressionargs={"level": t["tiff_nivel"]},
                     predictor=t["tiff_predictor"])  # muestras: B, G, R, térmica
    Path(t["salida_etiqueta"]).write_text("".join(f"{x}\n" for x in sin_repetidas(t["etiqueta"])))
    return t["stem"], True


def vaciar(carpeta, data):
    """Borra una carpeta generada por este script, solo si está dentro de data/."""
    carpeta = Path(carpeta).resolve()
    if data.resolve() not in carpeta.parents:
        raise SystemExit(f"No se borra {carpeta}: no está dentro de {data}")
    if carpeta.exists():
        shutil.rmtree(carpeta)


def construir(cfg, rutas, out):
    """Escribe las imágenes nuevas y sus etiquetas, arma los datasets termico_ampliado y fusion_ampliado con enlaces
    duros y los verifica."""
    import yaml

    from src.comun import agregar_a_bitacora, leer_yaml, ruta_para_yaml

    c = cfg["c1"]
    k = c["construir"]
    D = rutas["dataset"]
    data = rutas["data"]
    tw, th = cfg["tam_termica"]
    al = leer_yaml(ruta(k["alinear"]))["alinear"]
    comp = pd.read_csv(out / "c1" / "composicion.csv", keep_default_na=False)
    comp["rgb_real"] = comp.rgb_real.astype(str) == "True"
    comp["elegida"] = comp.elegida.astype(str) == "True"
    el = comp[comp.elegida].reset_index(drop=True)
    pr = c["pares_reales"]
    aprob = {pr["candidatos"][v] for v in pr["aprobados"]}
    if set(el.carpeta[el.rgb_real]) != (aprob & set(el.carpeta)):
        raise SystemExit("composicion.csv no coincide con pares_reales.aprobados: vuelve a correr --parte componer")
    H = None
    if aprob:
        T = yaml.safe_load(ruta(cfg["c0"]["alineacion"]["transformaciones"]).read_text(encoding="utf-8"))
        H = T[pr["semejanza"]]["H_rgb_a_termica"]
    raiz = data / c["salida"]
    tareas = []
    for r in el.itertuples():
        d = {x: raiz / x / r.carpeta for x in ("termica", "fusion", "rgb", "etiquetas")}
        for x in d.values():
            x.mkdir(parents=True, exist_ok=True)
        tareas.append({"stem": r.stem, "termica": str(D / r.ruta_termica), "rgb": str(D / r.ruta_rgb) if r.rgb_real else "",
                       "etiqueta": str((D / r.ruta_termica).with_suffix(".txt")), "H": H, "tam_ter": [tw, th],
                       "salida_termica": str(d["termica"] / f"{r.stem}.png"),
                       "salida_fusion": str(d["fusion"] / f"{r.stem}.tiff"),
                       "salida_rgb": str(d["rgb"] / f"{r.stem}.png"),
                       "salida_etiqueta": str(d["etiquetas"] / f"{r.stem}.txt"),
                       "nivel_png": al["nivel_png"], "tiff_compresion": al["tiff_compresion"],
                       "tiff_nivel": al["tiff_nivel"], "tiff_predictor": al["tiff_predictor"],
                       "prerreducir": al["prerreducir_area"], "interpolacion": al["interpolacion"]})
    t0 = time.time()
    escritas = 0
    with ProcessPoolExecutor(k["procesos"]) as ex:
        for i, (_, nueva) in enumerate(ex.map(procesar, tareas, chunksize=16), 1):
            escritas += nueva
            if i % 1000 == 0:
                print(f"{i}/{len(tareas)} imágenes ({time.time() - t0:.0f} s)", flush=True)
    print(f"{len(tareas)} imágenes nuevas, {escritas} escritas ahora, en {time.time() - t0:.0f} s", flush=True)

    # datasets de Ultralytics: base y validación enlazan a los datasets actuales; las nuevas, a data/<salida>/
    filas_real, resumen = [], []
    for modelo, nombre in k["nombres"].items():
        b = leer_yaml(ruta(c["base"][modelo]))
        bp = ruta(b["path"])
        ds = raiz / "datasets" / nombre
        vaciar(ds, data)
        for split in ("train", "val"):
            (ds / "images" / split).mkdir(parents=True)
            (ds / "labels" / split).mkdir(parents=True)
            for f in sorted((bp / b[split]).iterdir()):
                os.link(f, ds / "images" / split / f.name)
                lab = bp / "labels" / split / f"{f.stem}.txt"
                if lab.exists():
                    os.link(lab, ds / "labels" / split / lab.name)
                if modelo == "fusion":
                    filas_real.append({"stem": f.stem, "split": split, "origen": "base", "fuente": "pares actuales",
                                       "rgb_real": True})
        ext, sub = (".tiff", "fusion") if modelo == "fusion" else (".png", "termica")
        for r in el.itertuples():
            os.link(raiz / sub / r.carpeta / f"{r.stem}{ext}", ds / "images" / "train" / f"{r.stem}{ext}")
            os.link(raiz / "etiquetas" / r.carpeta / f"{r.stem}.txt", ds / "labels" / "train" / f"{r.stem}.txt")
            if modelo == "fusion":
                filas_real.append({"stem": r.stem, "split": "train", "origen": "nueva", "fuente": r.fuente,
                                   "rgb_real": bool(r.rgb_real)})
        archivo = ds / f"{nombre}.yaml"
        archivo.write_text(
            f"# Dataset de Ultralytics '{nombre}' (fase 7, C1). Generado por "
            f"src/ampliacion/c1_datasets_ampliados.py con "
            f"configs/fase7.yaml: no editar a mano.\n"
            f"# Entrenamiento: el de {c['base'][modelo]} más las imágenes nuevas de runs/{cfg['carpeta']}/c1/composicion.csv. "
            f"Validación: la de siempre.\n"
            + yaml.safe_dump({"path": ruta_para_yaml(ds), "train": "images/train", "val": "images/val",
                              "channels": b["channels"], "names": b["names"]}, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        n = {s: len(list((ds / "images" / s).iterdir())) for s in ("train", "val")}
        esperado = {"train": len(list((bp / b["train"]).iterdir())) + len(el), "val": len(list((bp / b["val"]).iterdir()))}
        if n != esperado:
            raise SystemExit(f"{nombre}: imágenes {n}, se esperaban {esperado}")
        resumen.append({"dataset": nombre, "yaml": archivo, **{f"imagenes_{s}": v for s, v in n.items()}})
    real = pd.DataFrame(filas_real)
    real.to_csv(raiz / "datasets" / k["nombres"]["fusion"] / "rgb_real.csv", index=False)
    real.to_csv(out / "c1" / "rgb_real.csv", index=False)

    # verificación con Ultralytics: todas las etiquetas (escribe labels/*.cache en los datasets nuevos) y una muestra
    # de imágenes nuevas leídas como las recibe el modelo
    from ultralytics.data.dataset import YOLODataset

    rng = np.random.default_rng(k["seed"])
    muestra = set(el.stem.iloc[sorted(rng.choice(len(el), k["verificacion"], replace=False))])
    filas_v = []
    for fila in resumen:
        y = leer_yaml(fila["yaml"])
        for split in ("train", "val"):
            ds = YOLODataset(img_path=str(ruta(y["path"]) / y[split]), imgsz=max(tw, th), augment=False,
                             data={"names": y["names"], "nc": len(y["names"]), "channels": y["channels"]},
                             task="detect")
            fila[f"cajas_{split}"] = int(sum(len(l["cls"]) for l in ds.labels))
            fila[f"leidas_{split}"] = len(ds)
            if split != "train":
                continue
            idx = {Path(f).stem: i for i, f in enumerate(ds.im_files)}
            for stem in sorted(muestra):
                r = el[el.stem == stem].iloc[0]
                img = ds[idx[stem]]["img"].numpy()  # C, H, W tras LetterBox, como entra al modelo
                y0, x0 = (img.shape[1] - th) // 2, (img.shape[2] - tw) // 2
                img = img[:, y0:y0 + th, x0:x0 + tw]
                gris = cv2.imread(str(raiz / "termica" / r.carpeta / f"{stem}.png"), cv2.IMREAD_UNCHANGED).astype(int)
                v = {"dataset": fila["dataset"], "stem": stem, "forma": tuple(img.shape)}
                if y["channels"] == 4:
                    v["max_rgb"] = int(img[:3].max()) if not r.rgb_real else None
                    v["dif_max_termica"] = int(np.abs(img[3].astype(int) - gris).max())
                else:
                    v["dif_max_termica"] = int(max(np.abs(img[j].astype(int) - gris).max() for j in range(3)))
                filas_v.append(v)
    ver = pd.DataFrame(filas_v)
    ver.to_csv(out / "c1" / "verificacion.csv", index=False)
    res = pd.DataFrame(resumen)
    res["yaml"] = res.yaml.map(ruta_para_yaml)
    res.to_csv(out / "c1" / "datasets.csv", index=False)
    print(md(res, 0))
    print(md(ver, 0))
    cajas_esperadas = int(el.cajas.sum())
    print(f"cajas nuevas en composicion.csv: {cajas_esperadas}")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "datasets termico_ampliado y fusion_ampliado",
                       f"C1 construir: {len(el)} imágenes nuevas ({int(el.rgb_real.sum())} con RGB real) en "
                       f"data/{c['salida']}/; datasets en data/{c['salida']}/datasets/ con enlaces duros",
                       "; ".join(f"{r.dataset}: train {r.imagenes_train} imágenes y {r.cajas_train} cajas, val "
                                 f"{r.imagenes_val} y {r.cajas_val}" for r in res.itertuples()))


def main():
    """Corre la parte pedida de C1: componer o construir."""
    from src.comun import leer_rutas, leer_yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["componer", "construir"])
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    globals()[args.parte](cfg, rutas, rutas["runs"] / cfg["carpeta"])


if __name__ == "__main__":
    main()
