r"""Fase 7, C4: nivel de oclusión de la validación (FHL 0134 y MtErie 0007), a mano y en modo simple.

Decidido por el usuario el 21 de noviembre de 2026 (configs/fase7.yaml, `c4.oclusion`): las 500 personas de los 442
fotogramas de validación se anotan con la misma pantalla, las mismas teclas y la regla de la ronda 2 que el nivel a mano
de la prueba (scripts/anotar_oclusion.py, modo simple del primer anotador). Esa herramienta no se cambia: aquí se usa su
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

Uso:
  .venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte preparar
  .venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte anotar
  .venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte nivel
"""
import argparse
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from anotar_oclusion import CAJA_WISARD, GRIS, OTRAS, AnotadorSimple
from comun import RAIZ, agregar_a_bitacora, leer_rutas, leer_yaml
from fase2_homografias_cajas import cajas_llevadas, centros
from oclusion_auto import cajas_px

CAJA = ["x0", "y0", "x1", "y1"]
NIVEL = {"se_ve_rgb": "baja", "no_se_ve_rgb": "severa", "no_es_persona": None}


def ruta(p):
    p = Path(p)
    return p if p.is_absolute() else RAIZ / p


def corto(vuelo):
    partes = vuelo.split("_")
    return f"{partes[1]} {partes[-1]}"


def contexto(cfg):
    c4 = cfg["c4"]
    base = leer_yaml(ruta(c4["base"]))
    part = base["particiones"]["validacion"]
    herr = leer_yaml(ruta(c4["oclusion"]["herramienta"]))
    # como scripts/fase7_entrenar.py: los vuelos de la prueba no se leen
    prohibidos = set(cfg["prohibidas"]) | set(leer_yaml(ruta(cfg["c1"]["particion"]))["prueba"])
    if any(x in v for v in part["vuelos"] for x in prohibidos):
        raise SystemExit(f"La validación incluye un vuelo de la prueba: {part['vuelos']}")
    return c4, base, part, herr


def preparar(cfg, rutas):
    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    W, H = base["evaluacion"]["tam_imagen"]
    primera = c4["corridas"][0]
    datos = leer_yaml(ruta(cfg["c3"]["corridas"][primera]["datos"]))
    d_lab = Path(datos["path"]) / "labels" / part["split"]
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
        if getattr(self, "_vuelo_cargado", None) != self.p.vuelo:  # la herramienta reconoce la imagen solo por
            self._pos_cargada = None                               # fotograma
            self._vuelo_cargado = self.p.vuelo
        super().cargar_imagenes()

    def panel(self, lado):  # como AnotadorSimple.panel, con las otras cajas del mismo vuelo
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
    c4, base, part, herr = contexto(cfg)
    oc = c4["oclusion"]
    ruta_personas = rutas["data"] / oc["personas"]
    if not ruta_personas.exists():
        raise SystemExit(f"No existe {ruta_personas}: corre antes --parte preparar")
    personas = pd.read_csv(ruta_personas, dtype={"id": str}).sort_values("orden")
    from marcar_puntos import preparar_pantalla
    area = preparar_pantalla()  # antes de crear cualquier ventana
    AnotadorValidacion(herr["oclusion"], personas, personas.id, rutas["data"] / herr["datasets"]["alineados"],
                       rutas["data"] / oc["respuestas"], tuple(herr["tam_termica"]), area, inicio, oc["ronda"],
                       "primero", "validacion").ejecutar()


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def nivel(cfg, rutas):
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
        cr = cajas_px(etq / "rgb" / f.vuelo / nombre, tuple(Hs[f.vuelo]["tam_rgb"]))
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

    tabla = df.assign(nivel=df.nivel.fillna("sin nivel (no es persona)")).pivot_table(
        index="vuelo", columns="nivel", values="id", aggfunc="size", fill_value=0, margins=True, margins_name="total")
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
    return Path(p).relative_to(RAIZ).as_posix()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    ap.add_argument("--parte", required=True, choices=["preparar", "anotar", "nivel"])
    ap.add_argument("--persona", type=int, help="con --parte anotar, abre en la persona N (desde 1)")
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    if args.parte == "preparar":
        preparar(cfg, rutas)
    elif args.parte == "anotar":
        anotar(cfg, rutas, args.persona)
    else:
        nivel(cfg, rutas)


if __name__ == "__main__":
    main()
