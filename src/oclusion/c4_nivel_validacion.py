r"""Fase 7, C4: nivel de oclusión de la validación (FHL 0134 y MtErie 0007), a mano y en modo simple.

Decidido por el usuario el 21 de noviembre de 2026 (configs/fase7.yaml, `c4.oclusion`): las 500 personas de los 442
fotogramas de validación se anotan con la misma pantalla, las mismas teclas y la regla de la ronda 2 que el nivel a mano
de la prueba (src/oclusion/anotar_oclusion.py, modo simple del primer anotador). Esa herramienta no se cambia: aquí se
usa su
AnotadorSimple, con dos ajustes porque la validación tiene dos vuelos y la herramienta suponía uno solo:
- la imagen cargada se reconoce por vuelo y fotograma, no solo por fotograma;
- las otras cajas de WiSARD (gris) son las del mismo vuelo y fotograma.
En pantalla se ve además el vuelo de la persona.

Partes:
  --parte preparar  lista fija de personas (data/<c4.oclusion.personas>): las cajas térmicas de las etiquetas de
                    validación del dataset de la primera corrida de c4 (las que lee el evaluador), en orden de vuelo y
                    fotograma. No sobrescribe una lista distinta.
  --parte anotar    la herramienta (retoma si se cierra). Guarda en data/<c4.oclusion.respuestas>.
                    1 se ve en la RGB, 2 no se ve en la RGB, 3 no es persona. --persona N abre en la persona N.
  --parte nivel     con las 500 respondidas, escribe data/<c4.oclusion.nivel> para el evaluador: baja (se ve), severa
                    (no se ve) o vacío (no es persona: caja dudosa, sin nivel). Agrega, solo como referencia, la regla
                    automática (sin caja RGB de WiSARD a 3 alturas o menos) y su kappa contra el nivel a mano.
  --parte consistencia  sin reanotar: la misma persona en los fotogramas p y p+1 del mismo vuelo, emparejada por
                    la IoU de la caja térmica (asignación húngara; umbral en c4.oclusion.consistencia), y cuántas
                    veces cambia su respuesta. Tablas y figuras de los cambios en <c4.salidas>/<carpeta>.

Uso:
  .venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte preparar
  .venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte anotar
  .venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte nivel
  .venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte consistencia
"""
import argparse
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.oclusion.anotar_oclusion import CAJA_WISARD, GRIS, OTRAS, AnotadorSimple
from src.comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml, ruta_del_dataset
from src.cajas import cajas_llevadas, centros
from src.oclusion.oclusion_auto import cajas_px_en_orden

CAJA = ["x0", "y0", "x1", "y1"]
NIVEL = {"se_ve_rgb": "baja", "no_se_ve_rgb": "severa", "no_es_persona": None}


def ruta(p):
    """Ruta absoluta: si es relativa, desde la raíz del repositorio."""
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def corto(vuelo):
    """Nombre corto de un vuelo (sitio y número), para la pantalla."""
    partes = vuelo.split("_")
    return f"{partes[1]} {partes[-1]}"


def contexto(cfg):
    """Lee la configuración común de las partes: la sección c4, la configuración de la fase 6, la partición de
    validación y la de la herramienta. Comprueba que no se lea ningún vuelo de la prueba."""
    c4 = cfg["c4"]
    base = leer_yaml(ruta(c4["base"]))
    part = base["particiones"]["validacion"]
    herr = leer_yaml(ruta(c4["oclusion"]["herramienta"]))
    # como src/entrenamiento/entrenar_fase7.py: los vuelos de la prueba no se leen
    prohibidos = set(cfg["prohibidas"]) | set(leer_yaml(ruta(cfg["c1"]["particion"]))["prueba"])
    if any(x in v for v in part["vuelos"] for x in prohibidos):
        raise SystemExit(f"La validación incluye un vuelo de la prueba: {part['vuelos']}")
    return c4, base, part, herr


def preparar(cfg, rutas):
    """Arma la lista fija de personas de la validación con las cajas térmicas de sus etiquetas, en orden de vuelo y
    fotograma."""
    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    W, H = base["evaluacion"]["tam_imagen"]
    primera = c4["corridas"][0]
    datos = leer_yaml(ruta(cfg["c3"]["corridas"][primera]["datos"]))
    d_lab = ruta_del_dataset(datos) / "labels" / part["split"]
    stems = sorted(p.stem for p in d_lab.glob("*.txt"))
    indice = pd.read_csv(rutas["data"] / herr["datasets"]["alineados"] / "indice.csv").set_index(["vuelo", "posicion"])
    etq = rutas["data"] / herr["datasets"]["etiquetas"] / "termica"
    filas, fot = [], []
    for v in part["vuelos"]:
        for st in sorted((s for s in stems if s.rsplit("_", 1)[0] == v), key=lambda s: int(s.rsplit("_", 1)[1])):
            pos = int(st.rsplit("_", 1)[1])
            lineas = [x.strip() for x in (d_lab / f"{st}.txt").read_text().splitlines() if x.strip()]
            original = etq / v / f"{st}.txt"
            if [x.strip() for x in original.read_text().splitlines() if x.strip()] != lineas:
                raise SystemExit(f"{d_lab / st}.txt no es igual a {original}")
            fot.append(st)
            im = indice.loc[(v, pos)]
            for k, linea in enumerate(lineas):
                _, cx, cy, w, h = (float(x) for x in linea.split())
                cx, cy, w, h = cx * W, cy * H, w * W, h * H
                filas.append({"id": f"{st}_{k}", "vuelo": v, "posicion": pos, "indice_caja": k,
                              "cajas_en_fotograma": len(lineas), "imagen_rgb": im.rgb, "imagen_termica": im.termica,
                              "ter_x0": cx - w / 2, "ter_y0": cy - h / 2, "ter_x1": cx + w / 2, "ter_y1": cy + h / 2})
    if set(s.rsplit("_", 1)[0] for s in stems) != set(part["vuelos"]):
        raise SystemExit(f"Vuelos en {d_lab}: {sorted(set(s.rsplit('_', 1)[0] for s in stems))}")
    personas = pd.DataFrame(filas)
    personas.insert(0, "orden", range(len(personas)))
    hay = {"fotogramas": len(fot), "personas": len(personas)}
    if hay != oc["comprobar"]:
        raise SystemExit(f"Se esperaba {oc['comprobar']} y hay {hay}")
    destino = rutas["data"] / oc["personas"]
    if destino.exists():
        viejo = pd.read_csv(destino, dtype={"id": str})
        if list(viejo.id) != list(personas.id):
            raise SystemExit(f"{destino} ya existe con otra lista: no se sobrescribe")
    destino.parent.mkdir(parents=True, exist_ok=True)
    personas.to_csv(destino, index=False, encoding="utf-8")
    alto = personas.ter_y1 - personas.ter_y0
    print(f"{len(personas)} personas en {len(fot)} fotogramas -> {destino}")
    print(personas.groupby("vuelo").agg(personas=("id", "size"), fotogramas=("posicion", "nunique")).to_string())
    print(f"Alto de la caja térmica (px): mediana {alto.median():.1f}, p10 {alto.quantile(0.1):.1f}, "
          f"p90 {alto.quantile(0.9):.1f}")
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "nivel de oclusión de la validación (C4)",
                       f"lista de personas: etiquetas térmicas de validación ({d_lab.relative_to(RAIZ)}), "
                       f"{', '.join(part['vuelos'])}; en orden de vuelo y fotograma",
                       f"{len(personas)} personas en {len(fot)} fotogramas -> {destino.relative_to(RAIZ)}")


class AnotadorValidacion(AnotadorSimple):
    """El modo simple del primer anotador, para una lista con más de un vuelo."""

    @property
    def nombre_lista(self):
        return f"{self._lista}, {corto(self.p.vuelo)}" if hasattr(self, "i") else self._lista

    @nombre_lista.setter
    def nombre_lista(self, valor):
        self._lista = valor

    def cargar_imagenes(self):
        """Carga las imágenes reconociendo el fotograma por vuelo y posición, porque la validación tiene dos vuelos."""
        if getattr(self, "_vuelo_cargado", None) != self.p.vuelo:  # la herramienta reconoce la imagen solo por
            self._pos_cargada = None                               # fotograma
            self._vuelo_cargado = self.p.vuelo
        super().cargar_imagenes()

    def panel(self, lado):  # como AnotadorSimple.panel, con las otras cajas del mismo vuelo
        """Como AnotadorSimple.panel, pero con las otras cajas del mismo vuelo y fotograma."""
        img = self.fondo_panel(lado)
        p = self.p
        if self.ver_cajas:
            mismo = self.todas[(self.todas.vuelo == p.vuelo) & (self.todas.posicion == p.posicion)]
            for q in mismo.itertuples():
                if q.id != p.id:
                    self.rect(img, [q.ter_x0, q.ter_y0, q.ter_x1, q.ter_y1], OTRAS, 1)
            self.rect(img, [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1], CAJA_WISARD, 1)
        self.senalar(img)
        self.dibujar_cursor(img, GRIS)
        self.rotular(img, "RGB alineada" if lado == "rgb" else "termica")
        return img


def anotar(cfg, rutas, inicio=None):
    """Abre la herramienta de modo simple sobre la lista de la validación; retoma si se cierra."""
    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    ruta_personas = rutas["data"] / oc["personas"]
    if not ruta_personas.exists():
        raise SystemExit(f"No existe {ruta_personas}: corre antes --parte preparar")
    personas = pd.read_csv(ruta_personas, dtype={"id": str}).sort_values("orden")
    from src.alineacion.marcar_puntos import preparar_pantalla
    area = preparar_pantalla()  # antes de crear cualquier ventana
    AnotadorValidacion(herr["oclusion"], personas, personas.id, rutas["data"] / herr["datasets"]["alineados"],
                       rutas["data"] / oc["respuestas"], tuple(herr["tam_termica"]), area, inicio, oc["ronda"],
                       "primero", "validacion").ejecutar()


def kappa(a, b):
    """Kappa de Cohen sin pesos entre dos listas de respuestas."""
    a, b = np.asarray(a), np.asarray(b)
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def nivel(cfg, rutas):
    """Con las 500 respondidas, escribe el nivel de la validación (baja, severa o vacío si no es persona) y, como
    referencia, el kappa contra la regla automática."""
    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    personas = pd.read_csv(rutas["data"] / oc["personas"], dtype={"id": str}).sort_values("orden")
    ruta_resp = rutas["data"] / oc["respuestas"]
    if not ruta_resp.exists():
        raise SystemExit(f"No existe {ruta_resp}: corre antes --parte anotar")
    resp = pd.read_csv(ruta_resp, dtype={"id": str})
    if set(resp.anotador) != {"primero_simple"}:
        raise SystemExit(f"{ruta_resp}: anotadores {sorted(set(resp.anotador))}")
    faltan = sorted(set(personas.id) - set(resp.id))
    if faltan or len(resp) != len(personas) or set(resp.id) - set(personas.id):
        raise SystemExit(f"Faltan {len(faltan)} de {len(personas)} personas por responder (por ejemplo {faltan[:3]})")
    df = personas.merge(resp[["id", "respuesta", "tiempo_s", "guardado"]], on="id", validate="1:1")
    df["nivel"] = df.respuesta.map(NIVEL)

    # referencia: la regla automática (fase 3b), con la semejanza congelada de cada vuelo
    Hs = yaml.safe_load((RAIZ / herr["transformaciones"]).read_text(encoding="utf-8"))
    etq = rutas["data"] / herr["datasets"]["etiquetas"]
    radio = herr["oclusion_auto"]["radio_alturas"]
    auto = []
    for f in df.itertuples():
        nombre = f"{f.vuelo}_{f.posicion:04d}.txt"
        cr = cajas_px_en_orden(etq / "rgb" / f.vuelo / nombre, tuple(Hs[f.vuelo]["tam_rgb"]))
        b = np.array([[f.ter_x0, f.ter_y0, f.ter_x1, f.ter_y1]])
        if not len(cr):
            auto.append(True)
            continue
        crl = cajas_llevadas(np.array(Hs[f.vuelo]["H_rgb_a_termica"], np.float64), cr)
        dist = np.linalg.norm(centros(crl) - centros(b)[0], axis=1) / (f.ter_y1 - f.ter_y0)
        auto.append(bool(dist.min() > radio))
    df["sin_caja_rgb_cerca"] = auto
    df["nivel_auto"] = np.where(df.sin_caja_rgb_cerca, "severa", "baja")

    destino = rutas["data"] / oc["nivel"]
    if destino.exists():
        viejo = pd.read_csv(destino, dtype={"id": str})
        if not viejo[["id", "nivel"]].fillna("").equals(df[["id", "nivel"]].fillna("")):
            respaldo = rutas["data"] / "respaldos" / f"{destino.stem}_{datetime.now():%Y%m%d-%H%M%S}.csv"
            respaldo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destino, respaldo)
            print(f"El nivel cambia: el anterior queda en {respaldo}")
    cols = ["orden", "id", "vuelo", "posicion", "indice_caja", *[f"ter_{c}" for c in CAJA], "respuesta", "nivel",
            "sin_caja_rgb_cerca", "nivel_auto", "tiempo_s", "guardado"]
    df[cols].to_csv(destino, index=False, encoding="utf-8")

    tabla = pd.crosstab(df.vuelo, df.nivel.fillna("sin nivel (no es persona)"), margins=True, margins_name="total")
    comp = df[df.nivel.notna()]
    k = kappa(comp.nivel, comp.nivel_auto)
    cruce = pd.crosstab(comp.nivel, comp.nivel_auto, rownames=["a mano"], colnames=["automático"])
    salidas = ruta(c4["salidas"])
    salidas.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salidas / "oclusion_validacion_niveles.csv", encoding="utf-8")
    cruce.to_csv(salidas / "oclusion_validacion_contra_automatico.csv", encoding="utf-8")
    t = df.tiempo_s
    print(tabla.to_string())
    print(f"\nContra la regla automática (solo referencia), {len(comp)} personas con nivel: kappa {k:.3f}\n"
          f"{cruce.to_string()}")
    print(f"Tiempo por persona: mediana {t.median():.2f} s, total {t.sum() / 60:.1f} min -> {destino}")
    n = df.nivel.value_counts()
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "nivel de oclusión de la validación (C4)",
                       f"a mano, modo simple del primer anotador con la regla de la ronda {oc['ronda']}; "
                       f"{rel(ruta_resp)} -> {rel(destino)}",
                       f"{len(df)} personas: baja {n.get('baja', 0)}, severa {n.get('severa', 0)}, sin nivel (no es "
                       f"persona) {int(df.nivel.isna().sum())}; mediana {t.median():.2f} s por persona; contra la regla "
                       f"automática (referencia) kappa {k:.3f} en {len(comp)}")


def rel(p):
    """Ruta relativa a la raíz del repositorio para mostrarla, o la ruta entera si está fuera."""
    p = Path(p)
    return p.relative_to(RAIZ).as_posix() if p.is_relative_to(RAIZ) else str(p)


def iou_matriz(a, b):
    """IoU entre las cajas (x0, y0, x1, y1) de a (filas) y de b (columnas)."""
    x0, y0 = np.maximum(a[:, None, 0], b[None, :, 0]), np.maximum(a[:, None, 1], b[None, :, 1])
    x1, y1 = np.minimum(a[:, None, 2], b[None, :, 2]), np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (area_a[:, None] + area_b[None, :] - inter)


RESPUESTA = {"se_ve_rgb": "se ve en la RGB", "no_se_ve_rgb": "no se ve en la RGB", "no_es_persona": "no es persona"}


def figuras_casos(casos, df, dir_alineados, cons, destino):
    """Cada caso en una fila: RGB alineada y térmica de los dos fotogramas, recortadas alrededor de la caja."""
    import cv2
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    por_id = df.set_index("id")
    archivos = []
    n = cons["casos_por_figura"]
    for k in range(0, len(casos), n):
        parte = casos.iloc[k:k + n]
        fig, ejes = plt.subplots(len(parte), 4, figsize=(10, 2.75 * len(parte)), squeeze=False)
        for fila, c in zip(ejes, parte.itertuples()):
            a, b = por_id.loc[c.id_a], por_id.loc[c.id_b]
            alto = max(a.ter_y1 - a.ter_y0, b.ter_y1 - b.ter_y0)
            lado = max(cons["ventana_min"], int(np.ceil(cons["ventana_alturas"] * alto)))
            paneles = [(a, "imagen_rgb", "RGB"), (b, "imagen_rgb", "RGB"), (a, "imagen_termica", "térmica"),
                       (b, "imagen_termica", "térmica")]
            for eje, (p, col, nombre) in zip(fila, paneles):
                img = cv2.imread(str(dir_alineados / getattr(p, col)), cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                cx, cy = (p.ter_x0 + p.ter_x1) / 2, (p.ter_y0 + p.ter_y1) / 2
                x0 = int(np.clip(round(cx - lado / 2), 0, img.shape[1] - lado))
                y0 = int(np.clip(round(cy - lado / 2), 0, img.shape[0] - lado))
                eje.imshow(img[y0:y0 + lado, x0:x0 + lado], interpolation="nearest",
                           extent=(x0, x0 + lado, y0 + lado, y0))
                eje.add_patch(Rectangle((p.ter_x0, p.ter_y0), p.ter_x1 - p.ter_x0, p.ter_y1 - p.ter_y0, fill=False,
                                        edgecolor="#ffd400", linewidth=1.2))
                eje.set_xticks([])
                eje.set_yticks([])
                eje.set_title(f"{nombre}, fotograma {p.posicion}\n{RESPUESTA[p.respuesta]}", fontsize=8.5)
            fila[0].set_ylabel(f"caso {c.caso}: {corto(c.vuelo)}\nIoU {c.iou:.2f}", fontsize=9)
        fig.tight_layout()
        archivo = destino / f"casos_{k // n + 1}.png"
        fig.savefig(archivo, dpi=110)
        plt.close(fig)
        archivos.append(archivo)
    return archivos


def consistencia(cfg, rutas):
    """Cambios de respuesta de la misma persona entre fotogramas seguidos (descriptivo, sin reanotar)."""
    from scipy.optimize import linear_sum_assignment

    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    cons = oc["consistencia"]
    ruta_nivel = rutas["data"] / oc["nivel"]
    if not ruta_nivel.exists():
        raise SystemExit(f"No existe {ruta_nivel}: corre antes --parte nivel")
    df = pd.read_csv(ruta_nivel, dtype={"id": str}).sort_values("orden")
    personas = pd.read_csv(rutas["data"] / oc["personas"], dtype={"id": str})
    df = df.merge(personas[["id", "imagen_rgb", "imagen_termica"]], on="id", validate="1:1")
    caja = [f"ter_{c}" for c in CAJA]
    umbrales = sorted(set(cons["sensibilidad"]) | {cons["iou_min"]})

    # emparejamiento de cada par de fotogramas seguidos (p, p+1), con todas sus cajas
    filas = []
    for v, g in df.groupby("vuelo", sort=False):
        fot = {p: x for p, x in g.groupby("posicion")}
        for p in sorted(fot):
            if p + 1 not in fot:
                continue
            A, B = fot[p], fot[p + 1]
            M = iou_matriz(A[caja].to_numpy(float), B[caja].to_numpy(float))
            for i, j in zip(*linear_sum_assignment(-M)):
                if M[i, j] > 0:
                    a, b = A.iloc[i], B.iloc[j]
                    filas.append({"vuelo": v, "posicion_a": p, "id_a": a.id, "id_b": b.id, "iou": M[i, j],
                                  "respuesta_a": a.respuesta, "respuesta_b": b.respuesta,
                                  "nivel_a": a.nivel, "nivel_b": b.nivel})
    pares = pd.DataFrame(filas)
    pares["cambia"] = pares.respuesta_a != pares.respuesta_b
    pares["baja_severa"] = pares.cambia & pares.nivel_a.notna() & pares.nivel_b.notna()

    # resumen por umbral; tramos (cadenas de la misma persona) con cada umbral
    resumen, tramo_de = [], {}
    for t in umbrales:
        pt = pares[pares.iou >= t]
        tramo = {}
        for r in pt.sort_values(["vuelo", "posicion_a"]).itertuples():
            tramo[r.id_b] = tramo.get(r.id_a, r.id_a)
        tr = df.id.map(lambda i: tramo.get(i, i))
        if t == cons["iou_min"]:
            tramo_de = tr
        for v in [*df.vuelo.unique(), None]:
            sel = pt if v is None else pt[pt.vuelo == v]
            dv = df if v is None else df[df.vuelo == v]
            largo = tr[dv.index].value_counts()
            resumen.append({"iou_min": t, "vuelo": "total" if v is None else corto(v), "personas": len(dv),
                            "pares_emparejados": len(sel), "cambios": int(sel.cambia.sum()),
                            "cambios_baja_severa": int(sel.baja_severa.sum()),
                            "cambios_con_no_es_persona": int((sel.cambia & ~sel.baja_severa).sum()),
                            "tramos": len(largo), "tramos_de_1": int((largo == 1).sum()),
                            "largo_mediano": float(largo.median()), "largo_maximo": int(largo.max()),
                            "severas": int((dv.nivel == "severa").sum()),
                            "tramos_con_severa": int(tr[dv.index][dv.nivel == "severa"].nunique()),
                            "bajas": int((dv.nivel == "baja").sum()),
                            "tramos_con_baja": int(tr[dv.index][dv.nivel == "baja"].nunique()),
                            "tramos_con_cambio": int(sel[sel.cambia].id_a.map(lambda i: tramo.get(i, i)).nunique())})
    resumen = pd.DataFrame(resumen)

    # tiempo: la primera persona de su tramo contra la que sigue a la del fotograma anterior (umbral principal)
    sigue = df.id.isin(pares[pares.iou >= cons["iou_min"]].id_b)
    tiempo = pd.DataFrame({"tipo": np.where(sigue, "sigue a la del fotograma anterior", "primera de su tramo"),
                           "vuelo": df.vuelo.map(corto), "tiempo_s": df.tiempo_s})
    t_res = tiempo.groupby(["vuelo", "tipo"]).tiempo_s.describe(percentiles=[.25, .5, .75])
    t_res = pd.concat([t_res, tiempo.groupby("tipo").tiempo_s.describe(percentiles=[.25, .5, .75])
                       .assign(vuelo="total").set_index("vuelo", append=True).swaplevel()])

    casos = pares[pares.cambia & (pares.iou >= min(umbrales))].sort_values(["vuelo", "posicion_a"]).reset_index(drop=True)
    casos.insert(0, "caso", range(1, len(casos) + 1))
    for t in umbrales:
        casos[f"cuenta_con_iou_{t}"] = casos.iou >= t

    destino = ruta(c4["salidas"]) / cons["carpeta"]
    destino.mkdir(parents=True, exist_ok=True)
    pares.to_csv(destino / "pares.csv", index=False, encoding="utf-8")
    resumen.to_csv(destino / "resumen.csv", index=False, encoding="utf-8")
    casos.to_csv(destino / "cambios.csv", index=False, encoding="utf-8")
    df.assign(tramo=tramo_de)[["id", "vuelo", "posicion", "indice_caja", "respuesta", "tramo"]].to_csv(
        destino / "tramos.csv", index=False, encoding="utf-8")
    t_res.round(2).to_csv(destino / "tiempo.csv", encoding="utf-8")
    for f in destino.glob("casos_*.png"):
        f.unlink()
    figs = figuras_casos(casos, df, rutas["data"] / herr["datasets"]["alineados"], cons, destino)

    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(resumen.to_string(index=False))
        print(t_res.round(2).to_string())
        print(casos[["caso", "vuelo", "posicion_a", "id_a", "id_b", "iou", "respuesta_a", "respuesta_b"]]
              .round(3).to_string(index=False))
    print(f"Salidas en {rel(destino)} ({len(figs)} figuras)")
    tot = resumen[(resumen.vuelo == "total") & (resumen.iou_min == cons["iou_min"])].iloc[0]
    otros = "; ".join(f"IoU >= {r.iou_min}: {r.cambios} de {r.pares_emparejados}"
                      for r in resumen[(resumen.vuelo == "total") & (resumen.iou_min != cons["iou_min"])].itertuples())
    agregar_a_bitacora(rutas["bitacora"], cfg["fase_bitacora"], "nivel de oclusión de la validación (C4)",
                       f"consistencia entre fotogramas seguidos, sin reanotar: misma persona en p y p+1 por IoU de la "
                       f"caja térmica (asignación húngara), IoU >= {cons['iou_min']} (sensibilidad {cons['sensibilidad']}); "
                       f"{rel(ruta_nivel)} -> {rel(destino)}",
                       f"IoU >= {cons['iou_min']}: {tot.cambios} cambios de respuesta en {tot.pares_emparejados} pares "
                       f"({tot.cambios_baja_severa} entre baja y severa, {tot.cambios_con_no_es_persona} con 'no es "
                       f"persona'); {tot.tramos} tramos para {tot.personas} personas ({tot.tramos_de_1} de un solo "
                       f"fotograma, largo máximo {tot.largo_maximo}); {otros}")


def main():
    """Corre la parte pedida: preparar, anotar, nivel o consistencia."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["preparar", "anotar", "nivel", "consistencia"])
    ap.add_argument("--persona", type=int, help="con --parte anotar, abre en la persona N (desde 1)")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.parte == "preparar":
        preparar(cfg, rutas)
    elif args.parte == "anotar":
        anotar(cfg, rutas, args.persona)
    elif args.parte == "nivel":
        nivel(cfg, rutas)
    else:
        consistencia(cfg, rutas)


if __name__ == "__main__":
    main()
