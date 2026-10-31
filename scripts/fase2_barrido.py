"""Fase 2: barrido visual de cada vuelo para encontrar despegues, aterrizajes y cambios de zoom.

Hojas de contacto con un fotograma cada `paso` posiciones, de todos los pares anotados de los vuelos que tienen
pares utilizables; los excluidos llevan el rótulo en rojo. Cada celda tiene la RGB recortada
a la franja que ve la térmica (llevada al tamaño de la térmica) y la térmica, con sus cajas. Si el zoom de la RGB
cambia o el dron está en el suelo, las dos mitades dejan de coincidir a simple vista.

Uso: python scripts/fase2_barrido.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse

from PIL import Image, ImageDraw, ImageFont

from comun import ROJO, leer_rutas, leer_yaml, panel_franja, pares_anotados


TODA = {"x": [0, 1], "y": [0, 1]}  # la térmica entera


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    b = cfg["barrido"]
    rutas = leer_rutas(args.rutas)
    pares = pares_anotados(rutas["data"] / cfg["pares"])
    pares = pares[pares.vuelo.isin(pares.loc[~pares.excluido, "vuelo"])]
    salida = rutas["reports"] / b["salida"]
    salida.mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(cfg["fuente"], 14)
    W = b["ancho_panel"]
    tam = (W, round(W * cfg["tam_termica"][1] / cfg["tam_termica"][0]))
    celda_w, celda_h, sep = 2 * W + 4, tam[1] + 20, 12
    n_hojas = 0

    for vuelo, g in pares.groupby("vuelo"):
        g = g.set_index("posicion").sort_index()
        posiciones = [p for p in range(g.index.min(), g.index.max() + 1, b["paso"]) if p in g.index]
        for h, i0 in enumerate(range(0, len(posiciones), b["por_hoja"])):
            lote = posiciones[i0:i0 + b["por_hoja"]]
            filas = -(-len(lote) // b["por_fila"])
            lienzo = Image.new("RGB", (b["por_fila"] * (celda_w + sep) - sep, filas * celda_h), (255, 255, 255))
            d = ImageDraw.Draw(lienzo)
            for i, p in enumerate(lote):
                r = g.loc[p]
                x, y = (i % b["por_fila"]) * (celda_w + sep), (i // b["por_fila"]) * celda_h
                lienzo.paste(panel_franja(rutas["dataset"] / r.ruta_rgb, cfg["franja_inicial"], tam)[0], (x, y + 18))
                lienzo.paste(panel_franja(rutas["dataset"] / r.ruta_termica, TODA, tam)[0], (x + W + 4, y + 18))
                d.text((x + 2, y + 1), f"pos {p}" + (" · excluido" if r.excluido else ""),
                       fill=ROJO if r.excluido else (0, 0, 0), font=fuente)
            destino = salida / f"{vuelo}_{h:02d}_pos{lote[0]:04d}-{lote[-1]:04d}.jpg"
            lienzo.save(destino, quality=b["calidad_jpg"])
            n_hojas += 1
        print(f"{vuelo}: {len(posiciones)} fotogramas")
    print(f"{n_hojas} hojas en {salida}")


if __name__ == "__main__":
    main()
