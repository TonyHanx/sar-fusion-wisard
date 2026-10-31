"""Fase 2: pares RGB y térmica lado a lado, con sus cajas, en los fotogramas de inicio, mitad y final de un vuelo.

Uso: python scripts/fase2_lado_a_lado.py --config configs/fase2.yaml --rutas configs/rutas.yaml
"""
import argparse

from PIL import ImageFont

from comun import fotogramas_clave, lado_a_lado, leer_rutas, leer_yaml, panel, pares_anotados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rev = cfg["lado_a_lado"]
    rutas = leer_rutas(args.rutas)

    pares = pares_anotados(rutas["data"] / cfg["pares"])  # incluye los excluidos (Carnation se revisó así)
    salida = rutas["reports"] / rev["salida"]
    salida.mkdir(parents=True, exist_ok=True)
    fuente = ImageFont.truetype(cfg["fuente"], 18)

    for vuelo, fotogramas in rev["fotogramas"].items():
        g = pares[pares.vuelo == vuelo].set_index("posicion")
        clave = fotogramas_clave(g.index)
        for nombre in fotogramas:  # inicio, mitad, final o una posición
            k = clave[nombre] if isinstance(nombre, str) else nombre
            nombre = nombre if isinstance(nombre, str) else "pos"
            p = g.loc[k]
            rgb, n_rgb = panel(rutas["dataset"] / p.ruta_rgb, rev["alto_panel"])
            ter, n_ter = panel(rutas["dataset"] / p.ruta_termica, rev["alto_panel"])
            lienzo = lado_a_lado([rgb, ter], [f"{vuelo} | {nombre}, pos {k} | RGB {n_rgb} cajas",
                                              f"térmica {n_ter} cajas"], fuente)
            destino = salida / f"{vuelo}_{nombre}_{k:05d}.jpg"
            lienzo.save(destino, quality=90)
            print(destino)


if __name__ == "__main__":
    main()
