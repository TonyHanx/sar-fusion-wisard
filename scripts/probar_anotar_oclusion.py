r"""Prueba de scripts/anotar_oclusion.py con 3 personas simuladas, sin abrir ventanas.

Usa la lista real de personas (data/oclusion_personas.csv) y las imágenes alineadas, pero escribe las anotaciones en
una carpeta temporal: no toca data/oclusion.csv ni data/oclusion_segundo.csv. Simula el ratón y el teclado llamando a
los mismos métodos que usa la ventana (raton y tecla) y comprueba:
1. que el lienzo cabe en el área de trabajo y que la vista inicial de las 498 personas no sale de la imagen (sin
   gris) y contiene la caja térmica entera; que --persona abre en la persona pedida;
2. persona A (con visible RGB precargada): precarga; completa dibujada en la térmica (queda igual en las dos); completa
   RGB movida con Mayús + arrastrar (la térmica no cambia, el tamaño tampoco); completa térmica centrada con un clic de
   la herramienta m y deshecha; completa redibujada en la RGB (nuevo tamaño en las dos, la térmica conserva el
   centro); g (RGB a la semejanza) y deshacer; visibles redibujadas; zoom con la rueda; λ de cada imagen con su
   propia completa;
3. persona B (sin caja RGB cerca): visible RGB pendiente; con "no visible" en la RGB la completa RGB vuelve a donde la
   pone la semejanza, no se puede mover y sigue a la térmica; λ RGB = 1;
4. persona C: "no es persona" y "fuera de cuadro" (deshecho); volver a B con "anterior";
5. el CSV (completas de las dos imágenes, corrimiento, λ) y que al abrir de nuevo se retoma en la primera persona sin
   terminar;
6. modo del segundo anotador: solo la muestra, nada precargado ni dibujado, guarda en su propio archivo;
7. --muestra (primer anotador, solo la muestra, con precarga): las personas ya anotadas fuera de la muestra (la persona
   1 del archivo real) se conservan idénticas al guardar, y el modo completo sigue leyendo el archivo.
Guarda capturas del lienzo de los dos modos en reports/oclusion/.

Uso:
    .venv\Scripts\python.exe scripts\probar_anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
"""
import argparse
import hashlib
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from anotar_oclusion import COMPLETA, COMPLETA_OTRA, VISIBLE, centro, crear_anotador, terminada
from comun import leer_rutas, leer_yaml
from marcar_puntos import preparar_pantalla

MAYUS = cv2.EVENT_FLAG_SHIFTKEY


def comprobar(cond, texto):
    if not cond:
        raise AssertionError(texto)
    print(f"  ok: {texto}")


def a_pantalla(a, lado, x, y):
    u, v = a.a_panel(x, y)
    return int(round(a.x_panel[lado] + u)), int(round(v))


def arrastrar(a, lado, p0, p1, boton="izq", flags=0):
    """Arrastra con el ratón en el panel `lado` del punto p0 al p1 (px de la térmica)."""
    q0, q1 = a_pantalla(a, lado, *p0), a_pantalla(a, lado, *p1)
    abajo, arriba = ((cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP) if boton == "izq"
                     else (cv2.EVENT_RBUTTONDOWN, cv2.EVENT_RBUTTONUP))
    a.raton(abajo, *q0, flags)
    a.raton(cv2.EVENT_MOUSEMOVE, (q0[0] + q1[0]) // 2, (q0[1] + q1[1]) // 2, flags)
    a.raton(cv2.EVENT_MOUSEMOVE, *q1, flags)
    a.raton(arriba, *q1, flags)


def dibujar_caja(a, lado, caja, boton="izq"):
    arrastrar(a, lado, caja[:2], caja[2:], boton)


def cerca(x, y, a, tol=None):
    """Iguales salvo el redondeo a píxeles de pantalla (1 / zoom)."""
    tol = 1.0 / a.vista[2] + 0.02 if tol is None else tol
    return x is not None and np.abs(np.array(x, float) - np.array(y, float)).max() <= tol


def tam(b):
    return round(b[2] - b[0], 2), round(b[3] - b[1], 2)


def lam(visible, completa):
    """λ calculado aparte, para comparar con el de la herramienta."""
    if visible is None:
        return 1.0
    ix = max(0.0, min(visible[2], completa[2]) - max(visible[0], completa[0]))
    iy = max(0.0, min(visible[3], completa[3]) - max(visible[1], completa[1]))
    return 1 - ix * iy / ((completa[2] - completa[0]) * (completa[3] - completa[1]))


def pixeles_de(a, color):
    lienzo = a.dibujar()[:a.ph]
    return int((lienzo == np.array(color, np.uint8)).all(axis=2).sum())


def tecla(a, c):
    return a.tecla(ord(c))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    o = cfg["oclusion"]
    capturas = rutas["reports"] / "oclusion"
    capturas.mkdir(parents=True, exist_ok=True)
    reales = [rutas["data"] / o["anotaciones"], rutas["data"] / o["anotaciones_segundo"]]
    antes = {r: r.read_bytes() if r.exists() else None for r in reales}
    area = preparar_pantalla()

    with tempfile.TemporaryDirectory() as tmp:
        salida1, salida2 = Path(tmp) / "oclusion.csv", Path(tmp) / "oclusion_segundo.csv"
        a = crear_anotador(cfg, rutas, segundo=False, salida=salida1, area=area)
        print(f"Primer anotador: {len(a.ids)} personas; lienzo {a.ancho} x {a.alto}, paneles {a.pw} x {a.ph}; "
              f"área de trabajo {area}")
        if area is not None:
            comprobar(a.ancho + o["ventana_x_px"] + o["margen_pantalla_px"] <= area[2]
                      and a.alto + o["reserva_titulo_px"] + o["margen_pantalla_px"] <= area[3],
                      "el lienzo cabe en el área de trabajo (con la barra de título)")
        comprobar(a.i == 0 and not salida1.exists(), "sin archivo previo, empieza en la primera persona")

        # ---- vista inicial de todas las personas
        malas_gris, malas_caja, en_borde = [], [], []
        for k in range(len(a.ids)):
            a.i = k
            a.vista = a.vista_inicial()
            x0, y0, z = a.origen()
            x1, y1 = x0 + a.pw / z, y0 + a.ph / z
            p = a.p
            if x0 < -1e-6 or y0 < -1e-6 or x1 > a.tw + 1e-6 or y1 > a.th + 1e-6:
                malas_gris.append(p.id)
            # caja recortada al fotograma (algunas cajas de WiSARD salen hasta 1 px del borde)
            b = [max(p.ter_x0, 0), max(p.ter_y0, 0), min(p.ter_x1, a.tw), min(p.ter_y1, a.th)]
            if b != [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1]:
                en_borde.append(p.id)
            if not (x0 <= b[0] and y0 <= b[1] and b[2] <= x1 and b[3] <= y1):
                malas_caja.append(p.id)
        comprobar(not malas_gris, f"vista inicial dentro de la imagen (sin gris) en las {len(a.ids)} personas")
        comprobar(not malas_caja, "la vista inicial contiene la caja térmica entera (dentro del fotograma) en todas; "
                                  f"{len(en_borde)} cajas de WiSARD salen del borde: {en_borde}")
        a.i = 0
        a.abrir()
        p = a.p
        x0, y0, z = a.origen()
        cx, cy = (p.ter_x0 + p.ter_x1) / 2, (p.ter_y0 + p.ter_y1) / 2
        print(f"  persona 1 ({p.id}): caja térmica x {p.ter_x0}-{p.ter_x1}, y {p.ter_y0}-{p.ter_y1}; vista x "
              f"{x0:.1f}-{x0 + a.pw / z:.1f}, y {y0:.1f}-{y0 + a.ph / z:.1f}; persona a "
              f"{(cx - x0) / (a.pw / z):.0%} del ancho y {(cy - y0) / (a.ph / z):.0%} del alto de la vista")
        cv2.imwrite(str(capturas / "herramienta_persona1.jpg"), a.dibujar(), [cv2.IMWRITE_JPEG_QUALITY, 90])

        per = a.todas.loc[a.ids]
        iA = 0
        iB = int(np.flatnonzero(per.rgb_x0.isna().to_numpy())[0])
        iC = iB + 1
        A, B, C = (a.ids[k] for k in (iA, iB, iC))
        print(f"Personas simuladas: A {A} (con precarga RGB), B {B} (sin caja RGB cerca), C {C}")

        # ---- persona A
        a.ir_a(iA)
        p = a.p
        wisard = [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1]
        precarga = [p.rgb_x0, p.rgb_y0, p.rgb_x1, p.rgb_y1]
        r = a.r
        comprobar(r["ter"]["caja"] == wisard and r["rgb"]["caja"] == precarga and r["completa"] is None,
                  "A: visible térmica = caja de WiSARD, visible RGB = caja RGB precargada, sin completa")
        comprobar(pixeles_de(a, VISIBLE) > 0, "A: las visibles precargadas se dibujan")
        completa = [wisard[0] - 2, wisard[1] - 6, wisard[2] + 2, wisard[3] + 3]
        dibujar_caja(a, "ter", completa)
        c = a.r["completa"]
        comprobar(cerca(c["ter"], completa, a) and c["rgb"] == c["ter"] and a.herramienta == "visible",
                  "A: completa dibujada en la térmica, en el mismo lugar en las dos imágenes; herramienta visible")
        tam0 = tam(c["ter"])
        ter_antes = list(c["ter"])
        cx, cy = centro(c["rgb"])
        arrastrar(a, "rgb", (cx, cy), (cx - 3, cy + 2), flags=MAYUS)
        c = a.r["completa"]
        comprobar(cerca(np.subtract(centro(c["rgb"]), centro(c["ter"])), (-3, 2), a) and c["ter"] == ter_antes
                  and tam(c["rgb"]) == tam0, "A: Mayús + arrastrar mueve solo la completa RGB, sin cambiar su tamaño")
        rgb_movida = list(c["rgb"])
        comprobar(pixeles_de(a, COMPLETA_OTRA) > 0, "A: cada panel muestra dónde está la completa de la otra imagen")
        tecla(a, "m")
        objetivo = (cx + 1.5, cy - 1)
        q = a_pantalla(a, "ter", *objetivo)
        a.raton(cv2.EVENT_LBUTTONDOWN, *q, 0)
        a.raton(cv2.EVENT_LBUTTONUP, *q, 0)
        comprobar(cerca(centro(a.r["completa"]["ter"]), objetivo, a) and a.r["completa"]["rgb"] == rgb_movida,
                  "A: con la herramienta m, un clic centra la completa térmica en ese punto (la RGB no cambia)")
        tecla(a, "u")
        comprobar(a.r["completa"]["ter"] == ter_antes, "A: deshacer devuelve la completa térmica")
        tecla(a, "c")
        nueva = [rgb_movida[0] - 1, rgb_movida[1] - 2, rgb_movida[2] + 3, rgb_movida[3] + 1]
        dibujar_caja(a, "rgb", nueva)
        c = a.r["completa"]
        comprobar(cerca(c["rgb"], nueva, a) and tam(c["ter"]) == tam(c["rgb"])
                  and cerca(centro(c["ter"]), centro(ter_antes), a, 0.011),
                  "A: redibujar la completa en la RGB cambia el tamaño en las dos; la térmica conserva su centro")
        tecla(a, "g")
        comprobar(a.r["completa"]["rgb"] == a.r["completa"]["ter"], "A: g pone la completa RGB donde la térmica")
        tecla(a, "u")
        comprobar(cerca(a.r["completa"]["rgb"], nueva, a), "A: deshacer devuelve la completa RGB movida")
        vis_rgb = [precarga[0], precarga[1], precarga[2], (precarga[1] + precarga[3]) / 2]
        dibujar_caja(a, "rgb", vis_rgb, boton="der")
        comprobar(cerca(a.r["rgb"]["caja"], vis_rgb, a) and cerca(a.r["completa"]["rgb"], nueva, a),
                  "A: visible RGB redibujada con el botón derecho (la completa no cambia)")
        vis_ter = [wisard[0] + 3, wisard[1] + 3, wisard[2] - 3, wisard[3] - 3]
        dibujar_caja(a, "ter", vis_ter)
        comprobar(cerca(a.r["ter"]["caja"], vis_ter, a), "A: visible térmica redibujada con la herramienta visible")
        tecla(a, "u")
        comprobar(a.r["ter"]["caja"] == wisard, "A: deshacer devuelve la visible térmica de WiSARD")
        comprobar(pd.read_csv(salida1).shape[0] == 1, "A: el CSV se guarda después de cada cambio")
        pos = (a.x_panel["ter"] + a.pw // 3, a.ph // 3)
        a.raton(cv2.EVENT_MOUSEMOVE, *pos, 0)
        antes_zoom = a.desde_panel(pos[0] - a.x_panel["ter"], pos[1])
        z0 = a.vista[2]
        a.raton(cv2.EVENT_MOUSEWHEEL, 0, 0, 120 << 16)  # rueda hacia adelante (u, v de pantalla: se ignoran)
        despues = a.desde_panel(pos[0] - a.x_panel["ter"], pos[1])
        comprobar(a.vista[2] > z0 and np.allclose(antes_zoom, despues), "A: zoom con la rueda en torno al cursor")
        for _ in range(30):
            a.raton(cv2.EVENT_MOUSEWHEEL, 0, 0, -(120 << 16))
        x0, y0, z = a.origen()
        x1, y1 = x0 + a.pw / z, y0 + a.ph / z
        comprobar(z == a.z_min and x0 <= 1e-6 and y0 <= 1e-6 and x1 >= a.tw - 1e-6 and y1 >= a.th - 1e-6
                  and abs((x0 + x1) / 2 - a.tw / 2) < 1e-6 and abs((y0 + y1) / 2 - a.th / 2) < 1e-6,
                  "A: alejando del todo, la imagen entera se ve centrada en el panel")
        tecla(a, "0")
        a.raton(cv2.EVENT_MOUSEMOVE, a.x_panel["rgb"] + a.pw // 2 + 60, a.ph // 2 + 40, 0)
        cv2.imwrite(str(capturas / "herramienta_primero.jpg"), a.dibujar(), [cv2.IMWRITE_JPEG_QUALITY, 90])
        rA = a.r
        lam_rgb = lam(rA["rgb"]["caja"], rA["completa"]["rgb"])
        lam_ter = lam(rA["ter"]["caja"], rA["completa"]["ter"])
        lam_rgb_sin_mover = lam(rA["rgb"]["caja"], rA["completa"]["ter"])
        comprobar(terminada(rA), f"A: terminada (lambda RGB {lam_rgb:.3f} con su completa; {lam_rgb_sin_mover:.3f} "
                                 f"con la de la térmica; lambda térmica {lam_ter:.3f})")
        tecla(a, "n")

        # ---- persona B
        a.ir_a(iB)
        comprobar(a.r["rgb"]["estado"] == "pendiente" and a.r["ter"]["estado"] == "caja",
                  "B: sin caja RGB cerca, la visible RGB empieza pendiente")
        p = a.p
        completaB = [p.ter_x0 - 1, p.ter_y0 - 4, p.ter_x1 + 1, p.ter_y1 + 1]
        dibujar_caja(a, "rgb", completaB)
        comprobar(cerca(a.r["completa"]["ter"], completaB, a) and not terminada(a.r),
                  "B: completa dibujada en la RGB (igual en las dos); sin terminar porque falta la visible RGB")
        cx, cy = centro(a.r["completa"]["rgb"])
        arrastrar(a, "rgb", (cx, cy), (cx + 4, cy), flags=MAYUS)
        comprobar(a.r["completa"]["rgb"] != a.r["completa"]["ter"], "B: completa RGB movida")
        tecla(a, "r")
        c = a.r["completa"]
        comprobar(a.r["rgb"]["estado"] == "no_visible" and c["rgb"] == c["ter"] and terminada(a.r),
                  "B: 'no visible' en la RGB: la completa RGB vuelve a donde la pone la semejanza; terminada")
        arrastrar(a, "rgb", (cx, cy), (cx + 5, cy + 5), flags=MAYUS)
        comprobar(a.r["completa"]["rgb"] == a.r["completa"]["ter"] and "no visible" in a.mensaje,
                  "B: con la RGB no visible, la completa RGB no se puede mover")
        arrastrar(a, "ter", (cx, cy), (cx - 2, cy + 1), flags=MAYUS)
        c = a.r["completa"]
        comprobar(cerca(centro(c["ter"]), (cx - 2, cy + 1), a) and c["rgb"] == c["ter"],
                  "B: al mover la completa térmica, la RGB (no visible) la sigue")
        tecla(a, "r")
        comprobar(a.r["rgb"]["estado"] == "pendiente", "B: otra vez r quita 'no visible'")
        tecla(a, "r")
        tecla(a, "n")

        # ---- persona C
        comprobar(a.i == iC, "C: 'n' pasa a la persona siguiente")
        tecla(a, "p")
        comprobar(a.r["no_es_persona"] and terminada(a.r), "C: 'no es persona', terminada sin cajas")
        tecla(a, "f")
        tecla(a, "u")
        comprobar(not a.r["fuera_de_cuadro"] and a.r["no_es_persona"], "C: 'fuera de cuadro' puesto y deshecho")
        tecla(a, "b")
        comprobar(a.id == B and a.r["rgb"]["estado"] == "no_visible", "'b' vuelve a B con lo anotado")
        tecla(a, "n")
        comprobar(tecla(a, "q") is False, "q sale")
        a.salir_de_persona()

        df = pd.read_csv(salida1, dtype={"id": str}).set_index("id")
        comprobar(list(df.index) == [A, B, C] and df.terminada.all() and (df.anotador == "primero").all(),
                  "CSV: 3 filas (A, B, C), terminadas, anotador 'primero'")
        fA = df.loc[A]
        crgb = [fA[f"completa_rgb_{k}"] for k in ("x0", "y0", "x1", "y1")]
        cter = [fA[f"completa_termica_{k}"] for k in ("x0", "y0", "x1", "y1")]
        comprobar(cerca(crgb, rA["completa"]["rgb"], a, 0.006) and cerca(cter, rA["completa"]["ter"], a, 0.006)
                  and cerca((fA.completa_rgb_dx, fA.completa_rgb_dy),
                            np.subtract(centro(rA["completa"]["rgb"]), centro(rA["completa"]["ter"])), a, 0.011),
                  f"CSV: completas de A en las dos imágenes y su corrimiento ({fA.completa_rgb_dx}, "
                  f"{fA.completa_rgb_dy}) px")
        comprobar(abs(fA.lambda_rgb - lam_rgb) < 1e-3 and abs(fA.lambda_termica - lam_ter) < 1e-3,
                  f"CSV: lambda de A con la completa de cada imagen ({fA.lambda_rgb}, {fA.lambda_termica})")
        fB = df.loc[B]
        comprobar(fB.rgb_estado == "no_visible" and fB.lambda_rgb == 1.0 and pd.isna(fB.rgb_x0)
                  and fB.completa_rgb_dx == 0 and fB.completa_rgb_dy == 0,
                  "CSV: B con la RGB no visible, lambda RGB = 1 y la completa RGB donde la pone la semejanza")
        comprobar(bool(df.loc[C].no_es_persona) and not bool(df.loc[C].fuera_de_cuadro), "CSV: C 'no es persona'")

        # ---- retomar y --persona
        a2 = crear_anotador(cfg, rutas, segundo=False, salida=salida1, area=area)
        hechas = {A, B, C}
        primera = next(k for k, i in enumerate(a2.ids) if i not in hechas)
        comprobar(a2.i == primera, f"al retomar empieza en la primera persona sin terminar ({a2.ids[primera]})")

        def igual(x, y):  # el CSV guarda 2 decimales
            return np.abs(np.array(x) - np.array(y)).max() <= 0.006
        comprobar(igual(a2.anot[A]["completa"]["rgb"], rA["completa"]["rgb"])
                  and igual(a2.anot[A]["completa"]["ter"], rA["completa"]["ter"])
                  and igual(a2.anot[A]["rgb"]["caja"], rA["rgb"]["caja"]) and igual(a2.anot[A]["ter"]["caja"], wisard)
                  and a2.anot[B]["rgb"]["estado"] == "no_visible" and a2.anot[C]["no_es_persona"],
                  "al retomar se recuperan las cajas y las marcas guardadas")
        a3 = crear_anotador(cfg, rutas, segundo=False, salida=salida1, area=area, inicio=1)
        comprobar(a3.i == 0 and a3.id == A, "--persona 1 abre en la persona 1 aunque haya avance guardado")

        # ---- segundo anotador
        huella = hashlib.md5(salida1.read_bytes()).hexdigest()
        s = crear_anotador(cfg, rutas, segundo=True, salida=salida2, area=area)
        muestra = pd.read_csv(rutas["data"] / o["muestra_segundo"], dtype={"id": str}).id
        comprobar(list(s.ids) == list(muestra) and len(s.ids) == round(o["fraccion_segundo"] * len(a.ids)),
                  f"segundo: solo las {len(s.ids)} personas de la muestra")
        comprobar(all(s.anot[i]["completa"] is None and s.anot[i]["rgb"]["estado"] == "pendiente"
                      and s.anot[i]["ter"]["estado"] == "pendiente" for i in s.ids),
                  "segundo: nada precargado (tampoco en las personas ya anotadas por el primero)")
        comprobar(pixeles_de(s, VISIBLE) == 0 and pixeles_de(s, COMPLETA) == 0,
                  "segundo: no se dibuja ninguna caja (ni de WiSARD ni del primer anotador)")
        p = s.p
        dibujar_caja(s, "ter", [p.ter_x0 - 1, p.ter_y0 - 3, p.ter_x1 + 1, p.ter_y1 + 1])
        cx, cy = centro(s.r["completa"]["rgb"])
        arrastrar(s, "rgb", (cx, cy), (cx - 3, cy), flags=MAYUS)
        dibujar_caja(s, "ter", [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1])
        dibujar_caja(s, "rgb", [p.ter_x0 - 4, p.ter_y0 + 2, p.ter_x1 - 6, p.ter_y1], boton="der")
        s.raton(cv2.EVENT_MOUSEMOVE, s.x_panel["rgb"] + s.pw // 2 + 40, s.ph // 2 - 30, 0)
        cv2.imwrite(str(capturas / "herramienta_segundo.jpg"), s.dibujar(), [cv2.IMWRITE_JPEG_QUALITY, 90])
        tecla(s, "n")
        d2 = pd.read_csv(salida2, dtype={"id": str})
        comprobar(len(d2) == 1 and d2.anotador.iloc[0] == "segundo" and bool(d2.terminada.iloc[0])
                  and abs(d2.completa_rgb_dx.iloc[0] + 3) <= 1 / s.vista[2] + 0.02,
                  "segundo: guarda en su propio archivo, anotador 'segundo', con su completa RGB movida")
        comprobar(hashlib.md5(salida1.read_bytes()).hexdigest() == huella, "segundo: el archivo del primero no cambia")

        # ---- primer anotador, solo la muestra (--muestra): conserva las personas ya anotadas fuera de la muestra
        salida3 = Path(tmp) / "oclusion_muestra.csv"
        base = reales[0] if reales[0].exists() else salida1  # el archivo real (con la persona 1 ya anotada)
        previas = pd.read_csv(base, dtype={"id": str})
        previas = previas[~previas.id.isin(set(muestra))]
        previas.to_csv(salida3, index=False, encoding="utf-8")
        texto_previas = salida3.read_text(encoding="utf-8").splitlines()[1:]
        m = crear_anotador(cfg, rutas, segundo=False, salida=salida3, area=area, muestra=True)
        comprobar(list(m.ids) == list(muestra) and m.primero and len(m.ajenas) == len(previas) > 0,
                  f"muestra: las {len(m.ids)} personas de la muestra en modo primer anotador; "
                  f"{len(previas)} anotadas fuera de la muestra apartadas ({', '.join(previas.id)})")
        comprobar(all(m.anot[i]["ter"]["estado"] == "caja" for i in m.ids)
                  and all((m.anot[i]["rgb"]["estado"] == "caja") == (not np.isnan(m.todas.loc[i].rgb_x0))
                          for i in m.ids), "muestra: con la precarga del primer anotador")
        comprobar(m.i == 0, "muestra: abre en la primera persona de la muestra")
        p = m.p
        dibujar_caja(m, "ter", [p.ter_x0 - 1, p.ter_y0 - 2, p.ter_x1 + 1, p.ter_y1 + 1])
        if m.r["rgb"]["estado"] == "pendiente":
            tecla(m, "r")  # sin precarga RGB: "no visible" en la RGB
        tecla(m, "n")
        d3 = pd.read_csv(salida3, dtype={"id": str})
        lineas = salida3.read_text(encoding="utf-8").splitlines()[1:]
        comprobar(len(d3) == len(previas) + 1 and set(d3.id) == set(previas.id) | {m.ids[0]}
                  and set(d3.anotador) == {"primero"},
                  "muestra: guarda la persona anotada junto con las de fuera de la muestra")
        comprobar(all(l in lineas for l in texto_previas),
                  "muestra: las filas de fuera de la muestra (la persona 1) quedan idénticas, texto por texto")
        orden = list(m.todas.index.get_indexer(d3.id))
        comprobar(orden == sorted(orden), "muestra: el archivo queda en el orden de la lista de personas")
        m2 = crear_anotador(cfg, rutas, segundo=False, salida=salida3, area=area, muestra=True)
        comprobar(m2.i == 1 and len(m2.ajenas) == len(previas), "muestra: al retomar sigue en la segunda de la muestra")
        completo = crear_anotador(cfg, rutas, segundo=False, salida=salida3, area=area)
        comprobar(len(completo.ajenas) == 0 and completo.tocadas == set(d3.id),
                  "muestra: el modo completo lee el mismo archivo con todas sus personas")

    despues_reales = {r: r.read_bytes() if r.exists() else None for r in reales}
    comprobar(despues_reales == antes, "data/oclusion.csv y data/oclusion_segundo.csv no se tocaron")
    print(f"Capturas en {capturas}")
    print("PRUEBA CORRECTA")


if __name__ == "__main__":
    main()
