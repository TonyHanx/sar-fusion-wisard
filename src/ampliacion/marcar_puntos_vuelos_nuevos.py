"""Fase 7, C0: puntos de control RGB-térmica en FHL 0403, 0564 y 0566, cuya RGB no tiene etiquetas.

Usa la herramienta de la fase 2 (scripts/marcar_puntos.py) sin cambiarla, con tres diferencias:
  - lee todos los pares del vuelo en data/pares.csv (la RGB de estos vuelos no está anotada, así que no son "pares
    utilizables"), dentro del rango de `c0.alineacion.vuelos`;
  - marca 2 fotogramas por vuelo (`c0.marcado.nombres`), no 3;
  - en los vuelos de `c0.marcado.realce_rgb` (0566 es de noche) la RGB se aclara solo en pantalla.
La sugerencia (celeste) es la de la fase 2: la franja nominal hasta tener 4 puntos y luego la de los propios puntos.
No usa ninguna de las semejanzas que se están midiendo.

Uso:
  .venv\\Scripts\\python.exe scripts\\fase7_marcar_puntos.py --config configs\\fase7.yaml --rutas configs\\rutas.yaml --vuelo 210924_FHL_Enterprise_0403
  .venv\\Scripts\\python.exe scripts\\fase7_marcar_puntos.py --config configs\\fase7.yaml --rutas configs\\rutas.yaml --listar

Teclas: las de la fase 2 (u deshacer, s guardar, n/b fotograma, j/l mover el fotograma, h cajas, q salir).
Los puntos se guardan en `c0.marcado.carpeta_puntos`/<vuelo>.yaml; luego se miden con
  scripts\\fase7_c0_auditoria.py ... --parte puntos
"""
import argparse
from pathlib import Path

import cv2
import pandas as pd
import yaml

import src.alineacion.marcar_puntos as mp
from src.comun import RAIZ, leer_rutas, leer_yaml


def configurar(cfg):
    """Configuración con la forma que espera marcar_puntos.Marcador."""
    c0 = cfg["c0"]
    mk = c0["marcado"]
    mp.NOMBRES = list(mk["nombres"])
    vuelos = c0["alineacion"]["vuelos"]

    def pares_del_rango(ruta_pares):
        p = pd.read_csv(ruta_pares)
        partes = []
        for v, r in vuelos.items():
            g = p[p.vuelo == v]
            partes.append(g[g.posicion.between(*r)] if r else g)
        return pd.concat(partes)

    mp.pares_utilizables = pares_del_rango
    leer = mp.leer_cajas_yolo
    mp.leer_cajas_yolo = lambda r: leer(r) if Path(r).exists() else []   # la RGB de estos vuelos no tiene .txt
    return {"marcado": mk, "franja_inicial": mk["franja_inicial"], "tam_termica": cfg["tam_termica"],
            "pares": cfg["pares"]}, vuelos


class MarcadorFase7(mp.Marcador):
    def abrir_fotograma(self):
        super().abrir_fotograma()
        k = self.m.get("realce_rgb", {}).get(self.vuelo)
        if k:
            self.rgb = cv2.convertScaleAbs(self.rgb, alpha=k)
            self.disp["rgb"] = cv2.resize(self.rgb, None, fx=self.esc["rgb"], fy=self.esc["rgb"],
                                          interpolation=cv2.INTER_AREA)

    def tecla(self, k):
        if k in (ord("n"), ord("b")):
            self.i = (self.i + (1 if k == ord("n") else -1)) % len(mp.NOMBRES)
            self.hover, self.mensaje = None, ""
            self.abrir_fotograma()
            return True
        return super().tecla(k)

    def dibujar(self):
        # la barra de estado de la fase 2 dice "/3": se reescribe la primera línea con el número de fotogramas real
        lienzo = super().dibujar()
        f = self.actual
        pend = f["pendiente"]
        err = self.errores()
        n, minimo = len(f["puntos"]), self.m["puntos_minimos"]
        linea1 = (f"{self.vuelo} | {mp.NOMBRES[self.i]} ({self.i + 1}/{len(mp.NOMBRES)}), pos {f['posicion']} | "
                  f"puntos {n}/{minimo}"
                  + (" | falta el clic en la " + ("termica" if pend[0] == "rgb" else "RGB") if pend else "")
                  + ("" if err is None else f" | error medio {err.mean():.1f} px, max {err.max():.1f} px (termicos)")
                  + (" | SIN GUARDAR" if self.cambios else "")
                  + (" | RGB aclarada en pantalla" if self.m.get("realce_rgb", {}).get(self.vuelo) else ""))
        cv2.rectangle(lienzo, (0, self.alto), (lienzo.shape[1], self.alto + 30), (0, 0, 0), -1)
        cv2.putText(lienzo, linea1, (8, self.alto + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    mp.VERDE if n >= minimo else (255, 255, 255), 1, cv2.LINE_AA)
        return lienzo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--vuelo")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    cfg_m, vuelos = configurar(cfg)
    prohibidas = set(cfg["prohibidas"])
    if args.listar or not args.vuelo:
        for v in vuelos:
            archivo = RAIZ / cfg_m["marcado"]["carpeta_puntos"] / f"{v}.yaml"
            estado = "sin puntos"
            if archivo.exists():
                fot = yaml.safe_load(archivo.read_text(encoding="utf-8"))["fotogramas"]
                estado = ", ".join(f"{n} {len(fot[n]['puntos'])}" for n in mp.NOMBRES if n in fot)
            print(f"{v:34s} {estado}")
        return
    if args.vuelo not in vuelos:
        raise SystemExit(f"{args.vuelo} no está en c0.alineacion.vuelos: {list(vuelos)}")
    if {f"{args.vuelo[:-5]}{x}_{args.vuelo[-4:]}" for x in ("IR", "VIS")} & prohibidas:
        raise SystemExit("FHL 0405 no se usa")
    area = mp.preparar_pantalla()
    MarcadorFase7(cfg_m, rutas, args.vuelo, area).ejecutar()


if __name__ == "__main__":
    main()
