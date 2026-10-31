"""Fase 2: marca puntos de control RGB-térmica en los fotogramas de inicio, mitad y final de un vuelo.

Uso:
  python scripts/marcar_puntos.py --config configs/fase2.yaml --rutas configs/rutas.yaml --vuelo 210924_FHL_Enterprise_0401
  python scripts/marcar_puntos.py --config configs/fase2.yaml --rutas configs/rutas.yaml --listar

Ventana principal: RGB a la izquierda y térmica a la derecha. Un punto de control es un clic en la RGB y otro en la
térmica sobre el mismo objeto (una roca, un tronco, una esquina), en cualquier orden. La ventana "lupa" amplía la zona
bajo el cursor; se puede hacer clic en ella para colocar el punto con más precisión. Con 4 puntos o más se muestra,
en celeste, dónde debería caer el punto que falta, y el error de cada punto.

Teclas:
  u    deshacer el último clic              s    guardar
  n/b  fotograma siguiente / anterior       j/l  mover el fotograma 5 posiciones (solo si no tiene puntos)
  h    mostrar u ocultar las cajas          q    salir (dos veces si hay cambios sin guardar)

Los puntos se guardan en configs/puntos_control/<vuelo>.yaml, en píxeles de las imágenes originales. Si el archivo
ya existe, se retoma.
"""
import argparse
from datetime import datetime

import cv2
import numpy as np
import yaml

from comun import RAIZ, fotogramas_clave, homografia_franja, leer_cajas_yolo, leer_rutas, leer_yaml, pares_utilizables

VENTANA, LUPA = "marcar puntos", "lupa"
NOMBRES = ["inicio", "mitad", "final"]
VERDE, AMARILLO, CELESTE, ROJO = (0, 255, 0), (0, 220, 255), (255, 255, 0), (0, 0, 255)
SEPARACION, BARRA = 10, 56


def aplicar(H, x, y):
    p = H @ np.array([x, y, 1.0])
    return p[0] / p[2], p[1] / p[2]


class Marcador:
    def __init__(self, cfg, rutas, vuelo):
        self.cfg, self.m = cfg, cfg["marcado"]
        self.dataset = rutas["dataset"]
        self.vuelo = vuelo
        pares = pares_utilizables(rutas["data"] / cfg["pares"])
        self.pares = pares[pares.vuelo == vuelo].set_index("posicion").sort_index()
        if self.pares.empty:
            raise SystemExit(f"No hay pares utilizables del vuelo {vuelo}")
        self.archivo = RAIZ / self.m["carpeta_puntos"] / f"{vuelo}.yaml"
        self.tam_termica = tuple(cfg["tam_termica"])
        self.invertido = vuelo in cfg.get("vuelos_invertidos", [])
        self.fotogramas = self.cargar()
        self.i = 0
        self.cajas = True
        self.cambios = False
        self.aviso_salida = False
        self.mensaje = ""
        self.hover = None  # (lado, x, y) en píxeles originales
        self.lupa_centro = None
        self.abrir_fotograma()

    # ------------------------------------------------------------------ datos
    def cargar(self):
        # fotogramas preconfigurados en la parte estable del vuelo; si no hay, el primero, el del medio y el último
        clave = self.m.get("fotogramas", {}).get(self.vuelo) or fotogramas_clave(self.pares.index)
        fuera = {n: clave[n] for n in NOMBRES if clave[n] not in self.pares.index}
        if fuera:
            raise SystemExit(f"Fotogramas preconfigurados que no son pares utilizables de {self.vuelo}: {fuera}")
        fot = {n: {"posicion": int(clave[n]), "puntos": []} for n in NOMBRES}
        if self.archivo.exists():
            guardado = yaml.safe_load(self.archivo.read_text(encoding="utf-8"))
            for n in NOMBRES:
                if n in guardado.get("fotogramas", {}):
                    g = guardado["fotogramas"][n]
                    fot[n] = {"posicion": int(g["posicion"]), "puntos": [list(map(float, p)) for p in g["puntos"]]}
            print(f"Retomando {self.archivo}")
        for f in fot.values():
            f["pendiente"] = None
        return fot

    def guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        datos = {"vuelo": self.vuelo, "guardado": datetime.now().isoformat(timespec="seconds"),
                 "formato_punto": "[x_rgb, y_rgb, x_termica, y_termica] en píxeles de las imágenes originales",
                 "tam_rgb": list(self.tam_rgb), "tam_termica": list(self.tam_termica), "fotogramas": {}}
        for n in NOMBRES:
            f = self.fotogramas[n]
            p = self.pares.loc[f["posicion"]]
            datos["fotogramas"][n] = {"posicion": f["posicion"], "ruta_rgb": p.ruta_rgb, "ruta_termica": p.ruta_termica,
                                      "puntos": [[round(v, 2) for v in q] for q in f["puntos"]]}
        self.archivo.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.cambios = False
        self.mensaje = f"guardado en {self.archivo.name}"

    @property
    def actual(self):
        return self.fotogramas[NOMBRES[self.i]]

    def abrir_fotograma(self):
        p = self.pares.loc[self.actual["posicion"]]
        self.rgb = cv2.imread(str(self.dataset / p.ruta_rgb))
        self.ter = cv2.imread(str(self.dataset / p.ruta_termica))
        self.cajas_rgb = leer_cajas_yolo((self.dataset / p.ruta_rgb).with_suffix(".txt"))
        self.cajas_ter = leer_cajas_yolo((self.dataset / p.ruta_termica).with_suffix(".txt"))
        self.tam_rgb = (self.rgb.shape[1], self.rgb.shape[0])
        # escala común: las dos imágenes con el mismo alto en pantalla
        aspecto = self.tam_rgb[0] / self.tam_rgb[1] + self.tam_termica[0] / self.tam_termica[1]
        self.alto = int(min(self.m["alto_ventana"] - BARRA, (self.m["ancho_ventana"] - SEPARACION) / aspecto))
        self.esc = {"rgb": self.alto / self.tam_rgb[1], "ter": self.alto / self.tam_termica[1]}
        self.x_ter = round(self.tam_rgb[0] * self.esc["rgb"]) + SEPARACION
        self.disp = {"rgb": cv2.resize(self.rgb, None, fx=self.esc["rgb"], fy=self.esc["rgb"], interpolation=cv2.INTER_AREA),
                     "ter": cv2.resize(self.ter, None, fx=self.esc["ter"], fy=self.esc["ter"], interpolation=cv2.INTER_CUBIC)}

    # ------------------------------------------------------------------ geometría
    def homografia_actual(self):
        """Homografía para sugerir: la del fotograma actual con >= 4 puntos, si no la de todos los puntos del vuelo,
        y si no la de la franja inicial (salvo en vuelos invertidos)."""
        for puntos in (self.actual["puntos"], [q for f in self.fotogramas.values() for q in f["puntos"]]):
            if len(puntos) >= 4:
                a = np.array(puntos, dtype=np.float64)
                H, _ = cv2.findHomography(a[:, :2], a[:, 2:], 0)
                if H is not None:
                    return H
        return None if self.invertido else homografia_franja(self.cfg["franja_inicial"], self.tam_rgb, self.tam_termica)

    def errores(self):
        puntos = self.actual["puntos"]
        if len(puntos) < 5:  # con 4 puntos el ajuste es exacto y el error no informa
            return None
        a = np.array(puntos, dtype=np.float64)
        H, _ = cv2.findHomography(a[:, :2], a[:, 2:], 0)
        if H is None:
            return None
        proy = cv2.perspectiveTransform(a[:, None, :2], H)[:, 0]
        return np.linalg.norm(proy - a[:, 2:], axis=1)

    def a_pantalla(self, lado, x, y):
        return (int(round(x * self.esc[lado])) + (self.x_ter if lado == "ter" else 0), int(round(y * self.esc[lado])))

    def desde_pantalla(self, u, v):
        if v >= self.alto:
            return None
        if u < self.x_ter - SEPARACION:
            return "rgb", u / self.esc["rgb"], v / self.esc["rgb"]
        if u >= self.x_ter:
            return "ter", (u - self.x_ter) / self.esc["ter"], v / self.esc["ter"]
        return None

    # ------------------------------------------------------------------ edición
    def agregar(self, lado, x, y):
        f = self.actual
        pend = f["pendiente"]
        if pend is None or pend[0] == lado:
            f["pendiente"] = (lado, x, y)
        else:
            rgb, ter = ((x, y), pend[1:]) if lado == "rgb" else (pend[1:], (x, y))
            f["puntos"].append([*rgb, *ter])
            f["pendiente"] = None
        self.cambios, self.aviso_salida, self.mensaje = True, False, ""

    def deshacer(self):
        f = self.actual
        if f["pendiente"] is not None:
            f["pendiente"] = None
        elif f["puntos"]:
            f["puntos"].pop()
        self.cambios, self.aviso_salida, self.mensaje = True, False, ""

    def mover(self, delta):
        if self.actual["puntos"] or self.actual["pendiente"]:
            self.mensaje = "el fotograma ya tiene puntos: deshazlos antes de moverlo"
            return
        pos = list(self.pares.index)
        k = pos.index(self.actual["posicion"])
        self.actual["posicion"] = int(pos[min(max(k + delta, 0), len(pos) - 1)])
        self.cambios = True
        self.abrir_fotograma()

    # ------------------------------------------------------------------ dibujo
    def dibujar(self):
        lienzo = np.zeros((self.alto + BARRA, self.x_ter + self.disp["ter"].shape[1], 3), np.uint8)
        lienzo[:self.alto, :self.disp["rgb"].shape[1]] = self.disp["rgb"]
        lienzo[:self.alto, self.x_ter:] = self.disp["ter"]
        if self.cajas:
            for lado, cajas, (w, h) in (("rgb", self.cajas_rgb, self.tam_rgb), ("ter", self.cajas_ter, self.tam_termica)):
                for _, cx, cy, bw, bh in cajas:
                    p1 = self.a_pantalla(lado, (cx - bw / 2) * w, (cy - bh / 2) * h)
                    p2 = self.a_pantalla(lado, (cx + bw / 2) * w, (cy + bh / 2) * h)
                    cv2.rectangle(lienzo, p1, p2, ROJO, 1)
        err = self.errores()
        for k, (xr, yr, xt, yt) in enumerate(self.actual["puntos"]):
            for lado, x, y in (("rgb", xr, yr), ("ter", xt, yt)):
                u, v = self.a_pantalla(lado, x, y)
                cv2.drawMarker(lienzo, (u, v), VERDE, cv2.MARKER_CROSS, 14, 2)
                texto = str(k + 1) if err is None else f"{k + 1} ({err[k]:.1f})"
                cv2.putText(lienzo, texto, (u + 6, v - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, VERDE, 1, cv2.LINE_AA)
        pend = self.actual["pendiente"]
        if pend is not None:
            lado, x, y = pend
            cv2.drawMarker(lienzo, self.a_pantalla(lado, x, y), AMARILLO, cv2.MARKER_CROSS, 18, 2)
            H = self.homografia_actual()
            if H is not None:
                otro, (xo, yo) = ("ter", aplicar(H, x, y)) if lado == "rgb" else ("rgb", aplicar(np.linalg.inv(H), x, y))
                cv2.drawMarker(lienzo, self.a_pantalla(otro, xo, yo), CELESTE, cv2.MARKER_TILTED_CROSS, 22, 1)
        # barra de estado (cv2.putText no tiene tildes)
        f = self.actual
        n, minimo = len(f["puntos"]), self.m["puntos_minimos"]
        linea1 = (f"{self.vuelo} | {NOMBRES[self.i]} ({self.i + 1}/3), pos {f['posicion']} | puntos {n}/{minimo}"
                  + (" | falta el clic en la " + ("termica" if pend[0] == "rgb" else "RGB") if pend else "")
                  + ("" if err is None else f" | error medio {err.mean():.1f} px, max {err.max():.1f} px (termicos)")
                  + (" | SIN GUARDAR" if self.cambios else ""))
        linea2 = self.mensaje or "u deshacer | s guardar | n/b fotograma | j/l mover fotograma | h cajas | q salir"
        color = VERDE if n >= minimo else (255, 255, 255)
        cv2.putText(lienzo, linea1, (8, self.alto + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
        cv2.putText(lienzo, linea2, (8, self.alto + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        return lienzo

    def dibujar_lupa(self):
        lado_px = self.m["lado_lupa"]
        lupa = np.zeros((lado_px, lado_px, 3), np.uint8)
        if self.hover is None:
            return lupa
        lado, x, y = self.hover
        aum = self.esc[lado] * self.m["zoom_lupa"]
        img = self.rgb if lado == "rgb" else self.ter
        M = np.array([[aum, 0, lado_px / 2 - aum * x], [0, aum, lado_px / 2 - aum * y]])
        lupa = cv2.warpAffine(img, M, (lado_px, lado_px), flags=cv2.INTER_NEAREST if aum > 2 else cv2.INTER_AREA)
        def en_lupa(px, py):
            return int(round(lado_px / 2 + aum * (px - x))), int(round(lado_px / 2 + aum * (py - y)))
        for k, q in enumerate(self.actual["puntos"]):
            px, py = q[:2] if lado == "rgb" else q[2:]
            cv2.drawMarker(lupa, en_lupa(px, py), VERDE, cv2.MARKER_CROSS, 20, 2)
            cv2.putText(lupa, str(k + 1), np.add(en_lupa(px, py), (8, -8)).tolist(), cv2.FONT_HERSHEY_SIMPLEX, 0.6, VERDE, 2)
        pend = self.actual["pendiente"]
        if pend is not None and pend[0] == lado:
            cv2.drawMarker(lupa, en_lupa(*pend[1:]), AMARILLO, cv2.MARKER_CROSS, 24, 2)
        c = lado_px // 2
        cv2.line(lupa, (c - 12, c), (c - 4, c), (255, 255, 255), 1)
        cv2.line(lupa, (c + 4, c), (c + 12, c), (255, 255, 255), 1)
        cv2.line(lupa, (c, c - 12), (c, c - 4), (255, 255, 255), 1)
        cv2.line(lupa, (c, c + 4), (c, c + 12), (255, 255, 255), 1)
        cv2.putText(lupa, "RGB" if lado == "rgb" else "termica", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, AMARILLO, 2)
        self.lupa_centro = (lado, x, y, aum)
        return lupa

    # ------------------------------------------------------------------ eventos
    def raton(self, evento, u, v, flags, _):
        p = self.desde_pantalla(u, v)
        if evento == cv2.EVENT_MOUSEMOVE and p is not None:
            self.hover = p
        elif evento == cv2.EVENT_LBUTTONDOWN and p is not None:
            self.agregar(*p)

    def raton_lupa(self, evento, u, v, flags, _):
        if evento == cv2.EVENT_LBUTTONDOWN and self.lupa_centro is not None:
            lado, x, y, aum = self.lupa_centro
            c = self.m["lado_lupa"] / 2
            self.agregar(lado, x + (u - c) / aum, y + (v - c) / aum)

    def tecla(self, k):
        """Devuelve False para salir."""
        if k == ord("u"):
            self.deshacer()
        elif k == ord("s"):
            self.guardar()
        elif k in (ord("n"), ord("b")):
            self.i = (self.i + (1 if k == ord("n") else -1)) % 3
            self.hover, self.mensaje = None, ""
            self.abrir_fotograma()
        elif k in (ord("j"), ord("l")):
            self.mover(self.m["paso_mover"] * (1 if k == ord("l") else -1))
        elif k == ord("h"):
            self.cajas = not self.cajas
        elif k == ord("q"):
            if self.cambios and not self.aviso_salida:
                self.aviso_salida = True
                self.mensaje = "hay cambios sin guardar: s para guardar, q otra vez para salir sin guardar"
            else:
                return False
        return True

    def ejecutar(self):
        cv2.namedWindow(VENTANA, cv2.WINDOW_AUTOSIZE)
        cv2.namedWindow(LUPA, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(VENTANA, self.raton)
        cv2.setMouseCallback(LUPA, self.raton_lupa)
        while True:
            cv2.imshow(VENTANA, self.dibujar())
            cv2.imshow(LUPA, self.dibujar_lupa())
            k = cv2.waitKey(30) & 0xFF
            if k != 255 and not self.tecla(k):
                break
            if cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:  # cerrada con la X
                if self.cambios:
                    self.guardar()
                    print("La ventana se cerró con cambios: se guardaron.")
                break
        cv2.destroyAllWindows()
        for n in NOMBRES:
            f = self.fotogramas[n]
            print(f"{n}: pos {f['posicion']}, {len(f['puntos'])} puntos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--vuelo")
    ap.add_argument("--listar", action="store_true", help="lista los vuelos y cuántos puntos tiene cada uno")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.listar or not args.vuelo:
        pares = pares_utilizables(rutas["data"] / cfg["pares"])
        for vuelo in pares.vuelo.unique():
            archivo = RAIZ / cfg["marcado"]["carpeta_puntos"] / f"{vuelo}.yaml"
            estado = "sin puntos"
            if archivo.exists():
                fot = yaml.safe_load(archivo.read_text(encoding="utf-8"))["fotogramas"]
                estado = ", ".join(f"{n} {len(fot[n]['puntos'])}" for n in NOMBRES)
            print(f"{vuelo:34s} {estado}")
        return
    Marcador(cfg, rutas, args.vuelo).ejecutar()


if __name__ == "__main__":
    main()
