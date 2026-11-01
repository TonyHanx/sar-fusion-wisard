r"""Fase 3b: anotación de oclusión de la prueba (FHL 0405, fotogramas con posición múltiplo de 3).

Reglas en docs/reglas_anotacion.md. Por persona (cada caja térmica de WiSARD del fotograma):
- caja completa: una sola, la misma para las dos imágenes (están alineadas: comparten la geometría de la térmica);
- caja visible RGB y caja visible térmica, o "no visible" (λ = 1);
- marcas "fuera de cuadro" y "no es persona".
λ = 1 − área(visible ∩ completa) / área(completa), en cada imagen.

Tres usos:
  --preparar  arma la lista fija de personas (data/<personas>) con su precarga y la muestra al azar (seed) para el
              segundo anotador (data/<muestra_segundo>). Si la lista ya existe y cambiaría, se detiene.
  (nada)      primer anotador: la visible térmica viene con la caja de WiSARD y la visible RGB con la caja RGB más
              cercana (llevada a la térmica con la semejanza congelada) a `radio_precarga_alturas` alturas o menos, si
              hay. Guarda en data/<anotaciones>.
  --segundo   segundo anotador: solo las personas de la muestra, sin precarga, sin las cajas de WiSARD y sin las del
              primer anotador (no lee su archivo). La persona a anotar se señala con triángulos amarillos en los bordes
              de la vista. Guarda en data/<anotaciones_segundo>.

Uso:
    .venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --preparar
    .venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
    .venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo

Ventana: arriba, la RGB alineada y la térmica lado a lado, ampliadas alrededor de la persona y con la misma vista (el
cursor se repite en las dos); abajo, las imágenes completas con la zona ampliada en amarillo, la información de la
persona y la ayuda.

Ratón y teclas:
  arrastrar (botón izq.)  dibuja la caja de la herramienta: completa (c), en cualquiera de las dos imágenes, o
                          visible (v), la de la imagen donde se dibuja. Tras dibujar la completa pasa a visible.
  arrastrar (botón der.)  dibuja siempre la visible de esa imagen
  r / t   no visible en la RGB / en la térmica (otra vez: lo quita)
  f       fuera de cuadro          p   no es persona          u   deshacer
  n / b   persona siguiente / anterior          espacio   siguiente sin terminar
  rueda, + / -   zoom          flechas   mover la vista          0   vista inicial
  e   realce de contraste      i   píxeles sin suavizar           h   ocultar las cajas
  q   salir (también con la X). Esc cancela un arrastre.

Se guarda en el CSV después de cada cambio y al pasar de persona (escritura atómica), y al abrir se retoma en la
primera persona sin terminar. Una persona está terminada con la completa y las dos visibles resueltas (caja o no
visible), o si está marcada "fuera de cuadro" o "no es persona". Coordenadas: px de las imágenes alineadas (640 x 512,
la geometría de la térmica), continuas (el píxel i cubre [i, i + 1]), como las de YOLO por el tamaño.

Pantalla: en Windows el proceso se declara consciente del DPI y la ventana se ajusta al área de trabajo.
"""
import argparse
import copy
import os
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

from comun import RAIZ, agregar_a_bitacora, leer_cajas_yolo, leer_rutas, leer_yaml
from fase2_homografias_cajas import cajas_llevadas, centros

VENTANA = "anotar oclusion"
COMPLETA, VISIBLE, OTRAS, MARCA = (255, 200, 0), (0, 255, 0), (150, 150, 150), (0, 220, 255)
BLANCO, GRIS, AVISO, BIEN = (255, 255, 255), (185, 185, 185), (90, 90, 255), (120, 230, 120)
FONDO, BORDE_IMAGEN = (30, 30, 30), (70, 70, 70)
FUENTE = cv2.FONT_HERSHEY_SIMPLEX
LADOS = {"rgb": "rgb", "ter": "termica"}  # clave interna -> prefijo de columna
NOMBRE = {"rgb": "RGB", "ter": "termica"}
FLECHAS = {2424832: (-1, 0), 2490368: (0, -1), 2555904: (1, 0), 2621440: (0, 1)}  # cv2.waitKeyEx en Windows
CAJA = ["x0", "y0", "x1", "y1"]
COLUMNAS = (["id", "vuelo", "posicion", "indice_caja", "anotador"] + [f"completa_{c}" for c in CAJA]
            + [f"{p}_{c}" for p in ("rgb", "termica") for c in ["estado"] + CAJA]
            + ["fuera_de_cuadro", "no_es_persona", "lambda_rgb", "lambda_termica", "terminada", "tiempo_s", "guardado"])


# ---------------------------------------------------------------------------------------------------- cajas y λ
def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def interseccion(a, b):
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def lambda_oclusion(visible, completa):
    """λ = 1 − área(visible ∩ completa) / área(completa); 1 si no se ve; None si falta la completa o la visible."""
    if completa is None or visible["estado"] == "pendiente" or area(completa) <= 0:
        return None
    if visible["estado"] == "no_visible":
        return 1.0
    return 1.0 - interseccion(visible["caja"], completa) / area(completa)


def vacia():
    return {"estado": "pendiente", "caja": None, "guardada": None}


def registro_inicial(p, precargar):
    r = {"completa": None, "rgb": vacia(), "ter": vacia(), "fuera_de_cuadro": False, "no_es_persona": False,
         "tiempo_s": 0.0, "guardado": ""}
    if precargar:
        r["ter"] = {"estado": "caja", "caja": [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1], "guardada": None}
        if not np.isnan(p.rgb_x0):
            r["rgb"] = {"estado": "caja", "caja": [p.rgb_x0, p.rgb_y0, p.rgb_x1, p.rgb_y1], "guardada": None}
    return r


def terminada(r):
    if r["no_es_persona"] or r["fuera_de_cuadro"]:
        return True
    return r["completa"] is not None and r["rgb"]["estado"] != "pendiente" and r["ter"]["estado"] != "pendiente"


def faltante(r):
    falta = [] if r["completa"] is not None else ["caja completa"]
    falta += [f"visible {NOMBRE[l]} (caja o no visible)" for l in LADOS if r[l]["estado"] == "pendiente"]
    return falta


def a_fila(p, r, anotador):
    fila = {"id": p.id, "vuelo": p.vuelo, "posicion": int(p.posicion), "indice_caja": int(p.indice_caja),
            "anotador": anotador}
    for c, v in zip(CAJA, r["completa"] or [None] * 4):
        fila[f"completa_{c}"] = None if v is None else round(float(v), 2)
    for l, pre in LADOS.items():
        fila[f"{pre}_estado"] = r[l]["estado"]
        caja = r[l]["caja"] if r[l]["estado"] == "caja" else [None] * 4
        for c, v in zip(CAJA, caja):
            fila[f"{pre}_{c}"] = None if v is None else round(float(v), 2)
    fila["fuera_de_cuadro"], fila["no_es_persona"] = r["fuera_de_cuadro"], r["no_es_persona"]
    for l, pre in LADOS.items():
        lam = lambda_oclusion(r[l], r["completa"])
        fila[f"lambda_{pre}"] = None if lam is None else round(lam, 4)
    fila["terminada"], fila["tiempo_s"], fila["guardado"] = terminada(r), round(r["tiempo_s"], 1), r["guardado"]
    return fila


def desde_fila(f):
    def caja(pre):
        v = [f[f"{pre}_{c}"] for c in CAJA]
        return None if any(pd.isna(x) for x in v) else [float(x) for x in v]
    r = {"completa": caja("completa"), "fuera_de_cuadro": bool(f["fuera_de_cuadro"]),
         "no_es_persona": bool(f["no_es_persona"]), "tiempo_s": float(f["tiempo_s"]),
         "guardado": "" if pd.isna(f["guardado"]) else str(f["guardado"])}
    for l, pre in LADOS.items():
        estado = f[f"{pre}_estado"]
        r[l] = {"estado": estado, "caja": caja(pre) if estado == "caja" else None, "guardada": None}
        if estado not in ("caja", "no_visible", "pendiente") or (estado == "caja" and r[l]["caja"] is None):
            raise SystemExit(f"{f['id']}: estado de la visible {NOMBRE[l]} inválido ({estado})")
    return r


# ---------------------------------------------------------------------------------------------------- preparar
def preparar(cfg, rutas, forzar=False):
    """Lista fija de personas a anotar con su precarga, y muestra al azar para el segundo anotador."""
    o, d = cfg["oclusion"], cfg["datasets"]
    data = rutas["data"]
    tam_ter = tuple(cfg["tam_termica"])
    Hs = yaml.safe_load((RAIZ / cfg["transformaciones"]).read_text(encoding="utf-8"))
    v = o["vuelo"]
    H = np.array(Hs[v]["H_rgb_a_termica"], np.float64)
    tam_rgb = tuple(Hs[v]["tam_rgb"])
    indice = pd.read_csv(data / d["alineados"] / "indice.csv")
    sel = indice[(indice.vuelo == v) & (indice.posicion % o["paso"] == 0)].sort_values("posicion")
    etq = data / d["etiquetas"]

    def px(ruta, tam):  # en el orden del archivo (el índice de la caja identifica a la persona)
        w, h = tam
        return np.array([[(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]
                         for _, cx, cy, bw, bh in leer_cajas_yolo(ruta)], np.float64).reshape(-1, 4)

    filas = []
    for f in sel.itertuples():
        nombre = f"{v}_{f.posicion:04d}.txt"
        ct = px(etq / "termica" / v / nombre, tam_ter)
        cr = px(etq / "rgb" / v / nombre, tam_rgb)
        crl = cajas_llevadas(H, cr) if len(cr) else cr
        for k, b in enumerate(ct):
            fila = {"id": f"{v}_{f.posicion:04d}_{k}", "vuelo": v, "posicion": f.posicion, "indice_caja": k,
                    "cajas_en_fotograma": len(ct), "imagen_rgb": f.rgb, "imagen_termica": f.termica,
                    **{f"ter_{c}": round(float(x), 3) for c, x in zip(CAJA, b)},
                    **{f"rgb_{c}": np.nan for c in CAJA}, "rgb_dist_alturas": np.nan,
                    "par_solo_termica": len(cr) == 0}
            if len(crl):
                dist = np.linalg.norm(centros(crl) - centros(b[None])[0], axis=1) / (b[3] - b[1])
                j = int(dist.argmin())
                fila["rgb_dist_alturas"] = round(float(dist[j]), 3)
                if dist[j] <= o["radio_precarga_alturas"]:
                    fila.update({f"rgb_{c}": round(float(x), 3) for c, x in zip(CAJA, crl[j])})
            filas.append(fila)
    personas = pd.DataFrame(filas)
    personas.insert(0, "orden", range(len(personas)))

    n2 = int(round(o["fraccion_segundo"] * len(personas)))
    elegidas = np.sort(np.random.default_rng(cfg["seed"]).choice(len(personas), n2, replace=False))
    muestra = personas.iloc[elegidas][["id", "vuelo", "posicion", "indice_caja"]].reset_index(drop=True)
    muestra.insert(0, "orden", range(len(muestra)))

    destino = {"personas": (data / o["personas"], personas), "muestra": (data / o["muestra_segundo"], muestra)}
    for clave, (ruta, df) in destino.items():
        if ruta.exists() and not forzar:
            viejo = pd.read_csv(ruta, dtype={"id": str})
            if list(viejo.id) != list(df.id):
                raise SystemExit(f"{ruta} ya existe y la nueva lista de {clave} sería otra: no se sobrescribe "
                                 f"(usa --forzar solo si no hay anotaciones hechas con la lista anterior)")
        df.to_csv(ruta, index=False, encoding="utf-8")

    con = personas[personas.rgb_x0.notna()]
    desplaz = np.linalg.norm(centros(con[[f"rgb_{c}" for c in CAJA]].to_numpy())
                             - centros(con[[f"ter_{c}" for c in CAJA]].to_numpy()), axis=1)
    alto = (personas.ter_y1 - personas.ter_y0).to_numpy()
    print(f"{v}: {sel.posicion.size} fotogramas (posición múltiplo de {o['paso']}), {len(personas)} personas")
    print(f"  con visible RGB precargada: {len(con)}; sin caja RGB a {o['radio_precarga_alturas']} alturas o menos: "
          f"{len(personas) - len(con)}; en pares 'solo térmica': {int(personas.par_solo_termica.sum())}")
    print(f"  alto de la caja térmica (px): mediana {np.median(alto):.1f}, p10 {np.percentile(alto, 10):.1f}, "
          f"p90 {np.percentile(alto, 90):.1f}")
    print(f"  distancia entre el centro térmico y el de la RGB precargada (px): mediana {np.median(desplaz):.1f}, "
          f"p90 {np.percentile(desplaz, 90):.1f}; en alturas de la caja térmica: mediana "
          f"{con.rgb_dist_alturas.median():.2f}, p90 {con.rgb_dist_alturas.quantile(0.9):.2f}")
    print(f"  muestra del segundo anotador: {len(muestra)} personas ({o['fraccion_segundo']:.0%}, seed={cfg['seed']}) "
          f"-> {destino['muestra'][0]}")
    agregar_a_bitacora(rutas["bitacora"], "3b", "preparación de la anotación de oclusión",
                       f"{v}, posición múltiplo de {o['paso']}; precarga RGB a {o['radio_precarga_alturas']} alturas; "
                       f"segundo anotador {o['fraccion_segundo']:.0%}, seed={cfg['seed']}",
                       f"{len(personas)} personas en {sel.posicion.size} fotogramas; {len(con)} con visible RGB "
                       f"precargada; muestra del segundo anotador: {len(muestra)} personas")
    return personas, muestra


# ---------------------------------------------------------------------------------------------------- herramienta
class Anotador:
    def __init__(self, o, personas, ids, alineados, salida, modo, tam_ter, area=None):
        self.o, self.modo, self.salida = o, modo, Path(salida)
        self.primero = modo == "primero"
        self.alineados = Path(alineados)
        self.tw, self.th = tam_ter
        self.todas = personas.set_index("id", drop=False)
        self.ids = list(ids)
        self.area = area
        self.disponer(area)
        self.anot = {i: registro_inicial(self.todas.loc[i], self.primero) for i in self.ids}
        self.tocadas, self.pilas = set(), {}
        self.cargar()
        self.mensaje, self.aviso_guardado = "", ""
        self.arrastre, self.raton_pos = None, None
        self.realce, self.pixeles, self.ver_cajas = False, False, True
        self._pos_cargada = None
        sin = self.siguiente_sin_terminar(desde=-1)
        self.i = 0 if sin is None else sin
        self.abrir()

    # ------------------------------------------------------------------ disposición
    def disponer(self, area):
        o = self.o
        ancho, alto = o["ancho_max"], o["alto_max"]
        if area is not None:
            ancho = min(ancho, area[2] - 2 * o["margen_pantalla_px"])
            alto = min(alto, area[3] - o["reserva_titulo_px"] - o["margen_pantalla_px"])
        sep = self.sep = o["separacion_px"]
        self.pw = (ancho - sep) // 2
        self.ancho, self.alto = 2 * self.pw + sep, alto
        self.gh = o["alto_vista_general_px"]
        self.gw = round(self.gh * self.tw / self.th)
        self.ph = alto - o["barra_px"] - self.gh - 2 * sep
        self.x_panel = {"rgb": 0, "ter": self.pw + sep}
        self.y_general = self.ph + sep
        self.y_barra = self.y_general + self.gh + sep
        self.z_min = 0.5 * min(self.pw / self.tw, self.ph / self.th)

    # ------------------------------------------------------------------ datos
    @property
    def id(self):
        return self.ids[self.i]

    @property
    def p(self):
        return self.todas.loc[self.id]

    @property
    def r(self):
        return self.anot[self.id]

    def cargar(self):
        if not self.salida.exists():
            return
        df = pd.read_csv(self.salida, dtype={"id": str})
        ajenos = sorted(set(df.id) - set(self.ids))
        if ajenos:
            raise SystemExit(f"{self.salida}: {len(ajenos)} personas que no están en la lista ({ajenos[:3]}...)")
        if len(df) and set(df.anotador) != {self.modo}:
            raise SystemExit(f"{self.salida}: anotaciones de {sorted(set(df.anotador))}, se esperaba {self.modo}")
        for f in df.to_dict("records"):
            self.anot[f["id"]] = desde_fila(f)
            self.tocadas.add(f["id"])
        print(f"Retomando {self.salida}: {len(df)} personas guardadas, "
              f"{sum(terminada(self.anot[i]) for i in self.tocadas)} terminadas")

    def guardar(self):
        ahora = time.monotonic()
        self.r["tiempo_s"] += ahora - self.t0
        self.t0 = ahora
        filas = [a_fila(self.todas.loc[i], self.anot[i], self.modo) for i in self.ids if i in self.tocadas]
        tmp = self.salida.with_name(self.salida.name + ".tmp")
        self.salida.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(filas, columns=COLUMNAS).to_csv(tmp, index=False, encoding="utf-8")
        try:
            os.replace(tmp, self.salida)
            self.aviso_guardado = ""
        except PermissionError:
            self.aviso_guardado = (f"NO SE PUDO GUARDAR {self.salida.name}: cierralo si esta abierto en otro programa "
                                   f"(se reintenta en el proximo cambio)")

    def cambiar(self, fn, mensaje=""):
        self.pilas.setdefault(self.id, []).append(copy.deepcopy(self.r))
        fn(self.r)
        self.r["guardado"] = datetime.now().isoformat(timespec="seconds")
        self.tocadas.add(self.id)
        self.mensaje = mensaje
        self.guardar()

    def deshacer(self):
        pila = self.pilas.get(self.id)
        if not pila:
            self.mensaje = "nada que deshacer en esta persona"
            return
        anterior = pila.pop()
        anterior["tiempo_s"] = self.r["tiempo_s"]
        self.anot[self.id] = anterior
        self.mensaje = "deshecho"
        self.guardar()

    def poner_caja(self, destino, caja):
        def fn(r):
            if destino == "completa":
                r["completa"] = caja
            else:
                r[destino] = {"estado": "caja", "caja": caja, "guardada": None}
        self.cambiar(fn)
        if destino == "completa" and self.herramienta == "completa":
            self.herramienta = "visible"
            self.mensaje = "caja completa dibujada; herramienta: caja visible (c para volver a la completa)"

    def alternar_no_visible(self, lado):
        def fn(r):
            v = r[lado]
            if v["estado"] == "no_visible":
                r[lado] = ({"estado": "caja", "caja": v["guardada"], "guardada": None} if v["guardada"] else vacia())
            else:
                r[lado] = {"estado": "no_visible", "caja": None, "guardada": v["caja"]}
        self.cambiar(fn)
        self.mensaje = f"visible {NOMBRE[lado]}: " + ("no visible" if self.r[lado]["estado"] == "no_visible"
                                                      else "se quito 'no visible'")

    def alternar(self, marca, texto):
        self.cambiar(lambda r: r.__setitem__(marca, not r[marca]))
        self.mensaje = f"{texto}: {'si' if self.r[marca] else 'no'}"

    # ------------------------------------------------------------------ navegación
    def siguiente_sin_terminar(self, desde=None):
        desde = self.i if desde is None else desde
        n = len(self.ids)
        for k in range(1, n + 1):
            j = (desde + k) % n
            if not terminada(self.anot[self.ids[j]]):
                return j
        return None

    def salir_de_persona(self):
        if self.id in self.tocadas:
            self.guardar()

    def ir_a(self, j):
        if not 0 <= j < len(self.ids):
            self.mensaje = ("es la primera persona" if j < 0 else
                            "es la ultima persona; espacio va a la siguiente sin terminar")
            return
        self.salir_de_persona()
        self.i = j
        self.mensaje = ""
        self.abrir()

    def abrir(self):
        p = self.p
        if self._pos_cargada != p.posicion:
            rgb = cv2.imread(str(self.alineados / p.imagen_rgb), cv2.IMREAD_COLOR)
            ter = cv2.imread(str(self.alineados / p.imagen_termica), cv2.IMREAD_GRAYSCALE)
            if rgb is None or ter is None:
                raise SystemExit(f"no se pudo leer {p.imagen_rgb} o {p.imagen_termica}")
            self.img = {"rgb": rgb, "ter": cv2.cvtColor(ter, cv2.COLOR_GRAY2BGR)}
            self._pos_cargada = p.posicion
            self.preparar_imagenes()
        self.vista = self.vista_inicial()
        self.herramienta = "completa" if self.r["completa"] is None else "visible"
        self.t0 = time.monotonic()

    def preparar_imagenes(self):
        if not self.realce:
            self.mostrar = self.img
            return
        c = self.o["clahe"]
        clahe = cv2.createCLAHE(clipLimit=c["limite"], tileGridSize=(c["rejilla"], c["rejilla"]))
        lab = cv2.cvtColor(self.img["rgb"], cv2.COLOR_BGR2LAB)
        lab[..., 0] = clahe.apply(lab[..., 0])
        gris = clahe.apply(self.img["ter"][..., 0])
        self.mostrar = {"rgb": cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), "ter": cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)}

    # ------------------------------------------------------------------ vista
    def vista_inicial(self):
        p, o = self.p, self.o
        x0, y0, x1, y1 = p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        asp = self.ph / self.pw
        f = o["recorte_factor_alto"]
        alto = max(o["recorte_alto_min_px"], f * (y1 - y0), f * (x1 - x0) * asp)
        if self.primero and not np.isnan(p.rgb_x0):
            ux0, uy0, ux1, uy1 = min(x0, p.rgb_x0), min(y0, p.rgb_y0), max(x1, p.rgb_x1), max(y1, p.rgb_y1)
            ext = max(2 * max(cy - uy0, uy1 - cy), 2 * max(cx - ux0, ux1 - cx) * asp)
            alto = max(alto, o["recorte_factor_union"] * ext)
        return [cx, cy, max(self.z_min, min(o["zoom_max"], self.ph / alto))]

    def origen(self):
        cx, cy, z = self.vista
        return cx - self.pw / (2 * z), cy - self.ph / (2 * z), z

    def a_panel(self, x, y):
        """Imagen (px de la térmica) -> px del panel."""
        x0, y0, z = self.origen()
        return z * (x - x0), z * (y - y0)

    def desde_panel(self, u, v):
        """Px del panel (índice) -> imagen (px de la térmica, continuas)."""
        x0, y0, z = self.origen()
        return x0 + (u + 0.5) / z, y0 + (v + 0.5) / z

    def panel_en(self, u, v):
        if not 0 <= v < self.ph:
            return None
        for lado, xp in self.x_panel.items():
            if xp <= u < xp + self.pw:
                return lado
        return None

    def zoom(self, factor, pos=None):
        cx, cy, z = self.vista
        nz = min(self.o["zoom_max"], max(self.z_min, z * factor))
        lado = self.panel_en(*pos) if pos is not None else None
        if lado is None:
            self.vista = [cx, cy, nz]
            return
        u, v = pos[0] - self.x_panel[lado], pos[1]
        x, y = self.desde_panel(u, v)
        x0n, y0n = x - (u + 0.5) / nz, y - (v + 0.5) / nz
        self.vista = [x0n + self.pw / (2 * nz), y0n + self.ph / (2 * nz), nz]

    def mover(self, dx, dy):
        cx, cy, z = self.vista
        self.vista = [cx + dx * self.pw / (8 * z), cy + dy * self.ph / (8 * z), z]

    # ------------------------------------------------------------------ dibujo
    def rect(self, img, caja, color, grosor):
        u0, v0 = self.a_panel(caja[0], caja[1])
        u1, v1 = self.a_panel(caja[2], caja[3])
        cv2.rectangle(img, (int(round(u0)), int(round(v0))), (int(round(u1)) - 1, int(round(v1)) - 1), color, grosor)

    def panel(self, lado):
        x0, y0, z = self.origen()
        M = np.float64([[z, 0, z * (0.5 - x0) - 0.5], [0, z, z * (0.5 - y0) - 0.5]])
        img = cv2.warpAffine(self.mostrar[lado], M, (self.pw, self.ph),
                             flags=cv2.INTER_NEAREST if self.pixeles else cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=BORDE_IMAGEN)
        r, p = self.r, self.p
        if self.ver_cajas:
            if self.primero:  # las otras personas del fotograma, de WiSARD
                for q in self.todas[self.todas.posicion == p.posicion].itertuples():
                    if q.id != p.id:
                        self.rect(img, [q.ter_x0, q.ter_y0, q.ter_x1, q.ter_y1], OTRAS, 1)
            if r[lado]["estado"] == "caja":
                self.rect(img, r[lado]["caja"], VISIBLE, 2)
            if r["completa"] is not None:
                self.rect(img, r["completa"], COMPLETA, 2)
        # triángulos en los bordes que señalan el centro de la persona a anotar
        uc, vc = self.a_panel((p.ter_x0 + p.ter_x1) / 2, (p.ter_y0 + p.ter_y1) / 2)
        t = 9
        if 0 <= uc < self.pw:
            for y, s in ((0, 1), (self.ph - 1, -1)):
                cv2.fillPoly(img, [np.int32([[uc - t, y], [uc + t, y], [uc, y + s * 1.6 * t]])], MARCA, cv2.LINE_AA)
        if 0 <= vc < self.ph:
            for x, s in ((0, 1), (self.pw - 1, -1)):
                cv2.fillPoly(img, [np.int32([[x, vc - t], [x, vc + t], [x + s * 1.6 * t, vc]])], MARCA, cv2.LINE_AA)
        # arrastre en curso
        a = self.arrastre
        if a is not None:
            caja = self.caja_de_arrastre(a)
            destino = self.destino_de_arrastre(a)
            if destino == "completa" or destino == lado:
                self.rect(img, caja, COMPLETA if destino == "completa" else VISIBLE, 1)
        # cursor repetido en los dos paneles
        if self.raton_pos is not None and self.panel_en(*self.raton_pos) is not None:
            lado_r = self.panel_en(*self.raton_pos)
            x, y = self.desde_panel(self.raton_pos[0] - self.x_panel[lado_r], self.raton_pos[1])
            u, v = (int(round(c - 0.5)) for c in self.a_panel(x, y))
            color = COMPLETA if self.herramienta == "completa" else VISIBLE
            cv2.line(img, (u, 0), (u, self.ph - 1), color, 1)
            cv2.line(img, (0, v), (self.pw - 1, v), color, 1)
        estado = {"caja": "caja", "no_visible": "NO VISIBLE", "pendiente": "visible pendiente"}[r[lado]["estado"]]
        rotulo = f"{'RGB alineada' if lado == 'rgb' else 'termica'} - {estado}"
        (w, h), _ = cv2.getTextSize(rotulo, FUENTE, 0.6, 1)
        cv2.rectangle(img, (0, 0), (w + 12, h + 12), (0, 0, 0), -1)
        cv2.putText(img, rotulo, (6, h + 5), FUENTE, 0.6, AVISO if r[lado]["estado"] == "no_visible" else BLANCO, 1,
                    cv2.LINE_AA)
        return img

    def vista_general(self, lado):
        img = cv2.resize(self.mostrar[lado], (self.gw, self.gh), interpolation=cv2.INTER_AREA)
        s = self.gw / self.tw
        x0, y0, z = self.origen()
        cv2.rectangle(img, (int(x0 * s), int(y0 * s)), (int((x0 + self.pw / z) * s), int((y0 + self.ph / z) * s)),
                      MARCA, 1)
        p = self.p
        cv2.circle(img, (int((p.ter_x0 + p.ter_x1) / 2 * s), int((p.ter_y0 + p.ter_y1) / 2 * s)), 3, MARCA, -1)
        return img

    def texto(self, img, linea, x, y, color=GRIS, escala=0.5):
        cv2.putText(img, linea, (x, y), FUENTE, escala, color, 1, cv2.LINE_AA)

    def dibujar(self):
        L = np.full((self.alto, self.ancho, 3), FONDO, np.uint8)
        for lado, xp in self.x_panel.items():
            L[:self.ph, xp:xp + self.pw] = self.panel(lado)
            k = 0 if lado == "rgb" else 1
            L[self.y_general:self.y_general + self.gh, k * (self.gw + self.sep):k * (self.gw + self.sep) + self.gw] = \
                self.vista_general(lado)
        p, r = self.p, self.r
        x = 2 * (self.gw + self.sep) + self.sep
        y = self.y_general + 16
        n_term = sum(terminada(self.anot[i]) for i in self.ids)
        modo = "PRIMER ANOTADOR" if self.primero else "SEGUNDO ANOTADOR (sin precarga)"
        self.texto(L, f"{modo} | persona {self.i + 1} de {len(self.ids)} | terminadas {n_term} de {len(self.ids)} | "
                      f"fotograma {p.posicion}, caja {p.indice_caja + 1} de {p.cajas_en_fotograma}", x, y, BLANCO, 0.55)
        if self.primero:
            pre = ("visible RGB precargada: caja RGB de WiSARD a {:.1f} alturas".format(p.rgb_dist_alturas)
                   if not np.isnan(p.rgb_x0) else "visible RGB sin precarga: ninguna caja RGB a "
                   f"{self.o['radio_precarga_alturas']} alturas o menos")
            linea2 = pre + (" | par 'solo termica' (sin cajas RGB)" if p.par_solo_termica else "")
        else:
            linea2 = "la persona a anotar es la que senalan los triangulos amarillos"
        self.texto(L, linea2, x, y + 22)
        est = {"caja": "caja", "no_visible": "no visible", "pendiente": "PENDIENTE"}
        self.texto(L, f"completa: {'caja' if r['completa'] is not None else 'PENDIENTE'} | visible RGB: "
                      f"{est[r['rgb']['estado']]} | visible termica: {est[r['ter']['estado']]}", x, y + 44)
        lam = {l: lambda_oclusion(r[l], r["completa"]) for l in LADOS}
        marcas = [m for m, b in (("FUERA DE CUADRO", r["fuera_de_cuadro"]), ("NO ES PERSONA", r["no_es_persona"])) if b]
        self.texto(L, " | ".join([f"lambda {NOMBRE[l]}: " + ("-" if lam[l] is None else f"{lam[l]:.2f}") for l in LADOS]
                                 + marcas), x, y + 66, BLANCO)
        if terminada(r):
            self.texto(L, "TERMINADA", x, y + 88, BIEN, 0.55)
        else:
            self.texto(L, "falta: " + ", ".join(faltante(r)), x, y + 88, MARCA, 0.55)
        avisos = []
        if r["completa"] is not None:
            for l in LADOS:
                if r[l]["estado"] == "caja" and area(r[l]["caja"]) > 0:
                    fuera = 1 - interseccion(r[l]["caja"], r["completa"]) / area(r[l]["caja"])
                    if fuera > self.o["aviso_visible_fuera"]:
                        avisos.append(f"la visible {NOMBRE[l]} se sale de la completa ({fuera:.0%} de su area)")
        if avisos:
            self.texto(L, " | ".join(avisos), x, y + 110, AVISO)
        if self.aviso_guardado or self.mensaje:
            self.texto(L, self.aviso_guardado or self.mensaje, x, y + 132, AVISO if self.aviso_guardado else MARCA)
        # ayuda
        herr = "CAJA COMPLETA" if self.herramienta == "completa" else "CAJA VISIBLE"
        yb = self.y_barra + 17
        self.texto(L, f"herramienta: {herr} (c completa, v visible) | arrastrar con el boton izquierdo: caja de la "
                      f"herramienta | con el derecho: caja visible de esa imagen", 8, yb,
                   COMPLETA if self.herramienta == "completa" else VISIBLE, 0.5)
        self.texto(L, "r / t: no visible en RGB / termica | f: fuera de cuadro | p: no es persona | u: deshacer | "
                      "n / b: siguiente / anterior | espacio: siguiente sin terminar", 8, yb + 23)
        self.texto(L, "rueda o + / -: zoom | flechas: mover | 0: vista inicial | e: contraste | i: pixeles | "
                      "h: ocultar cajas | q: salir (se guarda solo)", 8, yb + 46)
        return L

    # ------------------------------------------------------------------ eventos
    def destino_de_arrastre(self, a):
        return "completa" if (a["boton"] == "izq" and self.herramienta == "completa") else a["lado"]

    def caja_de_arrastre(self, a):
        xp = self.x_panel[a["lado"]]
        pts = []
        for u, v in ((a["u0"], a["v0"]), (a["u1"], a["v1"])):
            u = min(max(u - xp, 0), self.pw - 1)
            v = min(max(v, 0), self.ph - 1)
            pts.append(self.desde_panel(u, v))
        (xa, ya), (xb, yb) = pts
        return [round(min(max(c, 0.0), lim), 2) for c, lim in
                ((min(xa, xb), self.tw), (min(ya, yb), self.th), (max(xa, xb), self.tw), (max(ya, yb), self.th))]

    def raton(self, evento, u, v, flags, _=None):
        if evento == cv2.EVENT_MOUSEWHEEL:  # en Windows (u, v) llegan en coordenadas de pantalla: se usa el último
            if self.raton_pos is not None:  # el giro va en los 16 bits altos de flags, con signo: > 0 hacia adelante
                self.zoom(self.o["zoom_paso"] if flags > 0 else 1 / self.o["zoom_paso"], self.raton_pos)
            return
        self.raton_pos = (u, v)
        if evento in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN):
            lado = self.panel_en(u, v)
            if lado is not None:
                self.arrastre = {"lado": lado, "boton": "izq" if evento == cv2.EVENT_LBUTTONDOWN else "der",
                                 "u0": u, "v0": v, "u1": u, "v1": v}
        elif evento == cv2.EVENT_MOUSEMOVE and self.arrastre is not None:
            self.arrastre["u1"], self.arrastre["v1"] = u, v
        elif evento in (cv2.EVENT_LBUTTONUP, cv2.EVENT_RBUTTONUP) and self.arrastre is not None:
            a, self.arrastre = self.arrastre, None
            a["u1"], a["v1"] = u, v
            if min(abs(u - a["u0"]), abs(v - a["v0"])) < self.o["caja_min_px"]:
                return
            self.poner_caja(self.destino_de_arrastre(a), self.caja_de_arrastre(a))

    def tecla(self, k):
        """Devuelve False para salir."""
        if k in FLECHAS:
            self.mover(*FLECHAS[k])
            return True
        c = chr(k) if 0 <= k < 256 else ""
        if c == "c":
            self.herramienta = "completa"
        elif c == "v":
            self.herramienta = "visible"
        elif c == "r":
            self.alternar_no_visible("rgb")
        elif c == "t":
            self.alternar_no_visible("ter")
        elif c == "f":
            self.alternar("fuera_de_cuadro", "fuera de cuadro")
        elif c == "p":
            self.alternar("no_es_persona", "no es persona")
        elif c == "u":
            self.deshacer()
        elif c == "n":
            self.ir_a(self.i + 1)
        elif c == "b":
            self.ir_a(self.i - 1)
        elif c == " ":
            j = self.siguiente_sin_terminar()
            if j is None:
                self.mensaje = "todas las personas estan terminadas"
            else:
                self.ir_a(j)
        elif c in ("+", "="):
            self.zoom(self.o["zoom_paso"], self.raton_pos)
        elif c == "-":
            self.zoom(1 / self.o["zoom_paso"], self.raton_pos)
        elif c == "0":
            self.vista = self.vista_inicial()
        elif c == "e":
            self.realce = not self.realce
            self.preparar_imagenes()
        elif c == "i":
            self.pixeles = not self.pixeles
        elif c == "h":
            self.ver_cajas = not self.ver_cajas
        elif k == 27:
            self.arrastre = None
        elif c == "q":
            return False
        return True

    def ejecutar(self):
        cv2.namedWindow(VENTANA, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(VENTANA, self.raton)
        cv2.imshow(VENTANA, self.dibujar())
        if self.area is not None:
            cv2.moveWindow(VENTANA, self.area[0] + self.o["margen_pantalla_px"], self.area[1])
        while True:
            cv2.imshow(VENTANA, self.dibujar())
            k = cv2.waitKeyEx(30)
            if k != -1 and not self.tecla(k):
                break
            if cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:  # cerrada con la X
                break
        self.salir_de_persona()
        cv2.destroyAllWindows()
        n = sum(terminada(self.anot[i]) for i in self.ids)
        print(f"{n} de {len(self.ids)} personas terminadas; guardado en {self.salida}")


def crear_anotador(cfg, rutas, segundo, salida=None, area=None):
    """Anotador del primer o del segundo anotador. `salida` permite escribir en otro archivo (para pruebas)."""
    o, data = cfg["oclusion"], rutas["data"]
    ruta_personas = data / o["personas"]
    if not ruta_personas.exists():
        raise SystemExit(f"No existe {ruta_personas}: corre antes con --preparar")
    personas = pd.read_csv(ruta_personas, dtype={"id": str})
    if segundo:
        ids = pd.read_csv(data / o["muestra_segundo"], dtype={"id": str}).id
        salida = salida or data / o["anotaciones_segundo"]
    else:
        ids = personas.id
        salida = salida or data / o["anotaciones"]
    return Anotador(o, personas, ids, data / cfg["datasets"]["alineados"], salida,
                    "segundo" if segundo else "primero", tuple(cfg["tam_termica"]), area)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--preparar", action="store_true", help="arma la lista de personas y la muestra del segundo")
    ap.add_argument("--forzar", action="store_true", help="con --preparar, sobrescribe una lista distinta")
    ap.add_argument("--segundo", action="store_true", help="modo del segundo anotador")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.preparar:
        preparar(cfg, rutas, args.forzar)
        return
    from marcar_puntos import preparar_pantalla
    area = preparar_pantalla()  # antes de crear cualquier ventana
    crear_anotador(cfg, rutas, args.segundo, area=area).ejecutar()


if __name__ == "__main__":
    main()
