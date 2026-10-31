"""Fase 2: imágenes de los bordes de cada tramo excluido por despegue, aterrizaje o cambio de zoom.

Los tramos vienen de `bordes_tramos.tramos` en configs/fase2.yaml (salen del barrido visual, fase2_barrido.py, y
ya están excluidos en configs/fase1.yaml).
Por cada borde, una imagen con tres filas: fotograma justo antes, el del borde y justo después. Cada fila tiene la
RGB completa con la franja que ve la térmica en amarillo, esa franja recortada y llevada al tamaño de la térmica, y la
térmica, todas con sus cajas. Un tramo que empieza en el primer fotograma del vuelo solo tiene borde final, y uno que
termina en el último solo tiene borde inicial.

Uso: python scripts/fase2_bordes_tramos.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse

from PIL import Image, ImageFont

from comun import lado_a_lado, leer_rutas, leer_yaml, panel, panel_franja, pares_anotados

TODA = {"x": [0, 1], "y": [0, 1]}  # la térmica entera


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    bt = cfg["bordes_tramos"]
    rutas = leer_rutas(args.rutas)
    pares = pares_anotados(rutas["data"] / cfg["pares"])
    salida = rutas["reports"] / bt["salida"]
    salida.mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(cfg["fuente"], 16)
    alto = bt["alto_panel"]
    tam = (round(alto * cfg["tam_termica"][0] / cfg["tam_termica"][1]), alto)
    franja = cfg["franja_inicial"]

    for t in bt["tramos"]:
        g = pares[pares.vuelo == t["vuelo"]].set_index("posicion").sort_index()
        bordes = []
        if t["desde"] > g.index.min():
            bordes.append(("inicio", [t["desde"] - 1, t["desde"], t["desde"] + 1]))
        if t["hasta"] < g.index.max():
            bordes.append(("fin", [t["hasta"] - 1, t["hasta"], t["hasta"] + 1]))
        for nombre, ks in bordes:
            filas = []
            for k in ks:
                p = g.loc[k]
                estado = "excluido" if t["desde"] <= k <= t["hasta"] else "se conserva"
                rgb, n_rgb = panel(rutas["dataset"] / p.ruta_rgb, alto, franja)
                recorte, _ = panel_franja(rutas["dataset"] / p.ruta_rgb, franja, tam)
                ter, n_ter = panel_franja(rutas["dataset"] / p.ruta_termica, TODA, tam)
                filas.append(lado_a_lado([rgb, recorte, ter],
                                         [f"pos {k} | {estado} | RGB completa, {n_rgb} cajas",
                                          "RGB recortada a la franja amarilla", f"térmica, {n_ter} cajas"], fuente))
            sep = 8
            lienzo = Image.new("RGB", (max(f.width for f in filas), sum(f.height for f in filas) + sep * (len(filas) - 1)),
                               (255, 255, 255))
            y = 0
            for f in filas:
                lienzo.paste(f, (0, y))
                y += f.height + sep
            destino = salida / f"{t['vuelo']}_{t['tipo'].replace(' ', '_')}_{t['desde']:04d}-{t['hasta']:04d}_borde_{nombre}.jpg"
            lienzo.save(destino, quality=bt["calidad_jpg"])
            print(f"{destino.name}  (filas {ks})")


if __name__ == "__main__":
    main()
