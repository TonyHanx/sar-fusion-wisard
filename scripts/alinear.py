r"""Fase 2, último paso: imágenes alineadas de los pares anotados y no excluidos.

Por cada par:
- la RGB llevada a la geometría de la térmica (640 × 512) con la semejanza congelada del vuelo
  (`homografias_cajas.salida`), en PNG de 3 canales. Se reduce primero con INTER_AREA a la escala de la semejanza y
  después se deforma con interpolación bicúbica (`interpolacion`);
- la térmica en gris, en PNG de 1 canal. Las térmicas de FHL y Baker traen un tinte constante entre canales (R y B
  de 2 a 5 niveles por debajo de G); el gris no pierde información;
- un TIFF de 4 canales uint8 con deflate y predictor horizontal, con las muestras en el orden B, G, R, térmica
  (fotométrica RGB + 1 muestra extra). OpenCV, con el que lee Ultralytics, lo devuelve como R, G, B, térmica, y con
  4 canales Ultralytics no invierte el orden: el modelo recibe R, G, B, térmica.

Los pares se procesan de uno en uno, repartidos en varios procesos: cada proceso tiene un solo par en memoria.
Después:
- escribe data/<carpeta>/indice.csv;
- arma `superposiciones_por_vuelo` superposiciones por vuelo con los TIFF ya generados, leídos con el lector de
  Ultralytics, en reports/<carpeta_superposiciones>/;
- lee `tiff_verificacion` TIFF al azar (seed) con el dataset de Ultralytics (channels: 4) y con su cargador de
  predicción, y comprueba que el modelo recibe R, G, B, térmica, comparando con los PNG;
- agrega una fila a la bitácora con el espacio en disco y el tiempo.

Uso:
    .venv\Scripts\python.exe scripts\alinear.py --config configs\fase2.yaml --rutas configs\rutas.yaml
"""
# Solo importaciones livianas arriba: en Windows cada proceso hijo vuelve a importar este módulo (comun importa torch).
import argparse
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import tifffile

MODALIDADES = {"rgb": "png", "termica": "png", "fusion": "tif"}
INTERPOLACIONES = {"lineal": cv2.INTER_LINEAR, "cubica": cv2.INTER_CUBIC, "lanczos": cv2.INTER_LANCZOS4}


def alinear_rgb(rgb, H, tam_ter, prerreducir, interpolacion):
    """Lleva la RGB (BGR de OpenCV) a la geometría de la térmica con la transformación H (RGB original -> térmica)."""
    if prerreducir:
        s = float(np.sqrt(abs(np.linalg.det(H[:2, :2]))))
        if s < 1:
            h, w = rgb.shape[:2]
            nw, nh = round(w * s), round(h * s)
            rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
            fx, fy = nw / w, nh / h
            # coordenadas de la imagen reducida en función de las originales (centros de píxel de OpenCV)
            S = np.array([[fx, 0, 0.5 * fx - 0.5], [0, fy, 0.5 * fy - 0.5], [0, 0, 1]])
            H = H @ np.linalg.inv(S)
    return cv2.warpPerspective(rgb, H, tuple(tam_ter), flags=INTERPOLACIONES[interpolacion],
                               borderMode=cv2.BORDER_CONSTANT)


def procesar(t):
    """Un par: lee las dos imágenes originales (solo lectura) y escribe la RGB alineada, la térmica gris y el TIFF."""
    rgb = cv2.imread(t["rgb"], cv2.IMREAD_COLOR)
    ter = cv2.imread(t["termica"], cv2.IMREAD_COLOR)
    if rgb is None or ter is None:
        raise RuntimeError(f"no se pudo leer {t['rgb']} o {t['termica']}")
    gris = cv2.cvtColor(ter, cv2.COLOR_BGR2GRAY)
    if gris.shape[::-1] != tuple(t["tam_ter"]):
        raise RuntimeError(f"{t['termica']}: tamaño {gris.shape[::-1]}, se esperaba {tuple(t['tam_ter'])}")
    al = alinear_rgb(rgb, np.array(t["H"], np.float64), t["tam_ter"], t["prerreducir"], t["interpolacion"])
    png = [cv2.IMWRITE_PNG_COMPRESSION, t["nivel_png"]]
    if not (cv2.imwrite(t["salida_rgb"], al, png) and cv2.imwrite(t["salida_termica"], gris, png)):
        raise RuntimeError(f"no se pudo escribir {t['salida_rgb']} o {t['salida_termica']}")
    tifffile.imwrite(t["salida_fusion"], np.dstack([al, gris]), photometric="rgb", extrasamples=["unspecified"],
                     compression=t["tiff_compresion"], compressionargs={"level": t["tiff_nivel"]},
                     predictor=t["tiff_predictor"])  # muestras: B, G, R, térmica
    return t["indice"]


def superposiciones(indice, salida, dataset, Hs, cfg, c, carpeta):
    """Por vuelo, una hoja con `superposiciones_por_vuelo` pares (con alguna caja térmica) repartidos a lo largo del
    vuelo, hechos con los TIFF generados: RGB alineada | térmica | mezcla, con las cajas térmicas en rojo y las cajas
    RGB llevadas en verde."""
    from PIL import Image, ImageDraw, ImageFont
    from ultralytics.utils.patches import imread as imread_ultralytics

    from comun import ROJO, lado_a_lado
    from fase2_homografias_cajas import VERDE, apilar, cajas_llevadas, cajas_px

    tam_ter = tuple(cfg["tam_termica"])
    fuente = ImageFont.truetype(cfg["fuente"], 14)
    alto = c["alto_panel"]
    ancho = round(alto * tam_ter[0] / tam_ter[1])
    carpeta.mkdir(parents=True, exist_ok=True)
    elegidos_por_vuelo = {}
    for vuelo, g in indice.groupby("vuelo"):
        cand = g[g.cajas_termica > 0].reset_index(drop=True)
        k = sorted(set(np.linspace(0, len(cand) - 1, c["superposiciones_por_vuelo"]).round().astype(int)))
        H = np.array(Hs[vuelo]["H_rgb_a_termica"], np.float64)
        tam_rgb = tuple(Hs[vuelo]["tam_rgb"])
        filas = []
        for e in cand.iloc[k].itertuples():
            im = imread_ultralytics(str(salida / e.fusion), cv2.IMREAD_UNCHANGED)  # R, G, B, térmica
            rgb = Image.fromarray(np.ascontiguousarray(im[..., :3]))
            ter = Image.fromarray(np.ascontiguousarray(im[..., 3])).convert("RGB")
            mezcla = Image.blend(rgb, ter, 0.5)
            ct = cajas_px(dataset / Path(e.ruta_termica).with_suffix(".txt"), tam_ter)
            cr = cajas_px(dataset / Path(e.ruta_rgb).with_suffix(".txt"), tam_rgb)
            crl = cajas_llevadas(H, cr) if len(cr) else cr
            paneles = []
            for img in (rgb, ter, mezcla):
                d = ImageDraw.Draw(img)
                for b in ct:
                    d.rectangle(list(b), outline=ROJO, width=2)
                for b in crl:
                    d.rectangle(list(b), outline=VERDE, width=2)
                paneles.append(img.resize((ancho, alto)))
            filas.append(lado_a_lado(paneles, [f"pos {e.posicion}: RGB alineada", "térmica",
                                               "mezcla 50 % (rojo: cajas térmicas; verde: RGB)"], fuente))
        cab = Image.new("RGB", (filas[0].width, 30), (255, 255, 255))
        ImageDraw.Draw(cab).text((6, 6), f"{vuelo}: {len(filas)} pares de las imágenes finales (TIFF leído con el "
                                         f"lector de Ultralytics)", fill=(0, 0, 0), font=fuente)
        apilar([cab, *filas]).save(carpeta / f"superposiciones_{vuelo}.jpg", quality=c["calidad_jpg"])
        elegidos_por_vuelo[vuelo] = cand.posicion.iloc[k].tolist()
    return elegidos_por_vuelo


def verificar(indice, salida, dataset, n, seed, tam_ter):
    """Lee n TIFF al azar con el dataset de Ultralytics (channels: 4, el de entrenamiento y validación) y con su
    cargador de predicción, y compara lo que recibe el modelo con los PNG (R, G, B de la RGB alineada y la térmica)."""
    import shutil
    import tempfile

    from ultralytics.data.dataset import YOLODataset
    from ultralytics.data.loaders import LoadImagesAndVideos

    sel = indice.iloc[sorted(np.random.default_rng(seed).choice(len(indice), n, replace=False))]
    filas = []
    with tempfile.TemporaryDirectory() as tmp:
        imagenes, etiquetas = Path(tmp) / "images", Path(tmp) / "labels"
        imagenes.mkdir()
        etiquetas.mkdir()
        for e in sel.itertuples():
            shutil.copy(salida / e.fusion, imagenes / Path(e.fusion).name)
            shutil.copy(dataset / Path(e.ruta_termica).with_suffix(".txt"), etiquetas / f"{Path(e.fusion).stem}.txt")
        ds = YOLODataset(img_path=str(imagenes), imgsz=max(tam_ter), augment=False, data={"names": {0: "persona"},
                         "nc": 1, "channels": 4}, task="detect")
        if len(ds) != n:
            raise SystemExit(f"El dataset de Ultralytics leyó {len(ds)} de {n} TIFF")
        por_nombre = {Path(e.fusion).stem: e for e in sel.itertuples()}
        for i in range(len(ds)):
            item = ds[i]
            e = por_nombre[Path(item["im_file"]).stem]
            rgb = cv2.imread(str(salida / e.rgb), cv2.IMREAD_COLOR)[..., ::-1]  # PNG -> R, G, B
            ter = cv2.imread(str(salida / e.termica), cv2.IMREAD_UNCHANGED)
            esperado = {"R, G, B, T": np.dstack([rgb, ter]), "B, G, R, T": np.dstack([rgb[..., ::-1], ter])}
            t = item["img"].numpy()  # C, H, W tras LetterBox y Format, tal como entra al modelo
            y0, x0 = (t.shape[1] - tam_ter[1]) // 2, (t.shape[2] - tam_ter[0]) // 2
            t = t[:, y0:y0 + tam_ter[1], x0:x0 + tam_ter[0]].transpose(1, 2, 0)
            _, im0s, _ = next(iter(LoadImagesAndVideos(str(imagenes / Path(e.fusion).name), channels=4)))
            p = im0s[0]  # predicción: con 4 canales el predictor no invierte el orden
            filas.append({"vuelo": e.vuelo, "posicion": e.posicion, "forma_tensor": tuple(item["img"].shape),
                          **{f"dif_max_{k.replace(', ', '')}": int(np.abs(t.astype(int) - v).max())
                             for k, v in esperado.items()},
                          "dif_max_prediccion_RGBT": int(np.abs(p.astype(int) - esperado["R, G, B, T"]).max())})
    return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()

    import pandas as pd
    import yaml

    from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, pares_utilizables

    cfg = leer_yaml(args.config)
    c = cfg["alinear"]
    rutas = leer_rutas(args.rutas)
    D = rutas["dataset"]
    tam_ter = tuple(cfg["tam_termica"])
    Hs = yaml.safe_load((RAIZ / cfg["homografias_cajas"]["salida"]).read_text(encoding="utf-8"))
    pares = pares_utilizables(rutas["data"] / cfg["pares"]).sort_values(["vuelo", "posicion"]).reset_index(drop=True)
    salida = rutas["data"] / c["carpeta"]

    filas, tareas = [], []
    for k, p in enumerate(pares.itertuples()):
        if p.vuelo not in Hs:
            raise SystemExit(f"{p.vuelo}: no hay transformación en {cfg['homografias_cajas']['salida']}")
        rel = {m: Path(m) / p.vuelo / f"{p.vuelo}_{p.posicion:04d}.{ext}" for m, ext in MODALIDADES.items()}
        for r in rel.values():
            (salida / r).parent.mkdir(parents=True, exist_ok=True)
        filas.append({"vuelo": p.vuelo, "posicion": p.posicion, "ruta_rgb": p.ruta_rgb, "ruta_termica": p.ruta_termica,
                      **{m: r.as_posix() for m, r in rel.items()}, "cajas_rgb": p.cajas_rgb,
                      "cajas_termica": p.cajas_termica})
        tareas.append({"indice": k, "rgb": str(D / p.ruta_rgb), "termica": str(D / p.ruta_termica),
                       "H": Hs[p.vuelo]["H_rgb_a_termica"], "tam_ter": tam_ter, "prerreducir": c["prerreducir_area"],
                       "interpolacion": c["interpolacion"],
                       "nivel_png": c["nivel_png"], "tiff_compresion": c["tiff_compresion"],
                       "tiff_nivel": c["tiff_nivel"], "tiff_predictor": c["tiff_predictor"],
                       **{f"salida_{m}": str(salida / r) for m, r in rel.items()}})
    indice = pd.DataFrame(filas)

    print(f"{len(tareas)} pares en {indice.vuelo.nunique()} vuelos -> {salida} ({c['procesos']} procesos)")
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=c["procesos"]) as ex:
        for i, _ in enumerate(ex.map(procesar, tareas, chunksize=8), 1):
            if i % 500 == 0 or i == len(tareas):
                print(f"  {i} / {len(tareas)} ({time.perf_counter() - t0:.0f} s)", flush=True)
    t_gen = time.perf_counter() - t0
    indice.to_csv(salida / "indice.csv", index=False, encoding="utf-8")

    esperados = {(salida / indice[m].iloc[i]).resolve() for m in MODALIDADES for i in range(len(indice))}
    sobrantes = [f for m in MODALIDADES for f in (salida / m).rglob("*") if f.is_file() and f.resolve() not in esperados]
    if sobrantes:
        print(f"AVISO: {len(sobrantes)} archivos en {salida} que no son de esta corrida (p. ej. {sobrantes[0]})")

    bytes_m = {m: sum((salida / f).stat().st_size for f in indice[m]) for m in MODALIDADES}
    total = sum(bytes_m.values())
    tam = indice.assign(**{f"bytes_{m}": [(salida / f).stat().st_size for f in indice[m]] for m in MODALIDADES})
    por_vuelo = tam.groupby("vuelo").agg(pares=("posicion", "size"), **{f"MiB_{m}": (f"bytes_{m}", "sum")
                                                                          for m in MODALIDADES})
    for m in MODALIDADES:
        por_vuelo[f"MiB_{m}"] /= 2 ** 20
    pd.set_option("display.width", 200)
    print(f"\nGenerado en {t_gen / 60:.1f} min ({t_gen / len(indice) * 1000:.0f} ms por par con {c['procesos']} procesos)")
    print(por_vuelo.round(1).to_string())
    print("Por par (MB): " + ", ".join(f"{m} {bytes_m[m] / len(indice) / 1e6:.2f}" for m in MODALIDADES)
          + f"; total {total / 2 ** 30:.2f} GiB")

    t1 = time.perf_counter()
    elegidos = superposiciones(indice, salida, D, Hs, cfg, c, rutas["reports"] / c["carpeta_superposiciones"])
    t_sup = time.perf_counter() - t1
    print(f"\nSuperposiciones ({t_sup:.0f} s): " + "; ".join(f"{v}: {p}" for v, p in elegidos.items()))

    t2 = time.perf_counter()
    ver = pd.DataFrame(verificar(indice, salida, D, c["tiff_verificacion"], cfg["seed"], tam_ter))
    t_ver = time.perf_counter() - t2
    print(f"\nVerificación con Ultralytics ({t_ver:.0f} s): diferencia máxima con cada orden (0 = idéntico)")
    print(ver.to_string(index=False))
    ok = (ver.dif_max_RGBT == 0).all() and (ver.dif_max_BGRT > 0).all() and (ver.dif_max_prediccion_RGBT == 0).all()
    print("El modelo recibe R, G, B, térmica" if ok else "AVISO: el orden de los canales NO es R, G, B, térmica")
    ver.to_csv(rutas["reports"] / c["carpeta_superposiciones"] / "verificacion_tiff.csv", index=False,
               encoding="utf-8")
    por_vuelo.round(2).to_csv(rutas["reports"] / c["carpeta_superposiciones"] / "espacio_por_vuelo.csv",
                              encoding="utf-8")

    agregar_a_bitacora(
        rutas["bitacora"], 2, "imágenes alineadas (semejanza congelada): RGB PNG, térmica PNG gris, TIFF B,G,R,T",
        f"prerreducción INTER_AREA {c['prerreducir_area']} + {c['interpolacion']}; PNG nivel {c['nivel_png']}; TIFF "
        f"{c['tiff_compresion']} nivel {c['tiff_nivel']}, predictor {c['tiff_predictor']}; {c['procesos']} procesos; "
        f"seed={cfg['seed']}",
        f"{len(indice)} pares; {total / 2 ** 30:.2f} GiB ({', '.join(f'{m} {bytes_m[m] / 2 ** 30:.2f}' for m in MODALIDADES)}"
        f"); {t_gen / 60:.1f} min; verificación de {len(ver)} TIFF con Ultralytics: "
        f"{'el modelo recibe R, G, B, T' if ok else 'orden incorrecto'}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
