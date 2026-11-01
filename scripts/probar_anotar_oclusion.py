r"""Prueba de scripts/anotar_oclusion.py con 3 personas simuladas, sin abrir ventanas.

Usa la lista real de personas (data/oclusion_personas.csv) y las imágenes alineadas, pero escribe las anotaciones en
una carpeta temporal: no toca data/oclusion.csv ni data/oclusion_segundo.csv. Simula el ratón y el teclado llamando a
los mismos métodos que usa la ventana (raton y tecla) y comprueba:
1. que la ventana entra en el área de trabajo de la pantalla;
2. persona A (con visible RGB precargada): precarga, caja completa dibujada en la térmica, visible RGB redibujada con
   el botón derecho, visible térmica redibujada y deshecha, zoom con la rueda (el punto bajo el cursor no se mueve) y λ;
3. persona B (sin caja RGB cerca): la visible RGB empieza pendiente, completa dibujada en la RGB, "no visible" en la RGB
   (λ = 1) puesto, quitado y vuelto a poner;
4. persona C: "no es persona" y "fuera de cuadro" (deshecho); volver a B con "anterior";
5. el CSV después de cada persona y al salir, y que al abrir de nuevo se retoma con lo guardado en la primera persona
   sin terminar;
6. modo del segundo anotador: solo la muestra, nada precargado ni dibujado (aunque el archivo del primero exista), y
   guarda en su propio archivo sin tocar el del primero.
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

from anotar_oclusion import COMPLETA, VISIBLE, crear_anotador, terminada
from comun import leer_rutas, leer_yaml
from marcar_puntos import preparar_pantalla


def comprobar(cond, texto):
    if not cond:
        raise AssertionError(texto)
    print(f"  ok: {texto}")


def arrastrar(a, lado, caja, boton="izq"):
    """Arrastra con el ratón en el panel `lado` de una esquina a la opuesta de `caja` (px de la térmica)."""
    xp = a.x_panel[lado]
    (u0, v0), (u1, v1) = a.a_panel(caja[0], caja[1]), a.a_panel(caja[2], caja[3])
    p0 = (int(round(xp + u0)), int(round(v0)))
    p1 = (int(round(xp + u1)), int(round(v1)))
    abajo, arriba = ((cv2.EVENT_LBUTTONDOWN, cv2.EVENT_LBUTTONUP) if boton == "izq"
                     else (cv2.EVENT_RBUTTONDOWN, cv2.EVENT_RBUTTONUP))
    a.raton(abajo, *p0, 0)
    a.raton(cv2.EVENT_MOUSEMOVE, (p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2, 0)
    a.raton(cv2.EVENT_MOUSEMOVE, *p1, 0)
    a.raton(arriba, *p1, 0)


def cerca(caja, esperada, a):
    """La caja dibujada coincide con la pedida salvo el redondeo a píxeles de pantalla (1 / zoom)."""
    return caja is not None and np.abs(np.array(caja) - np.array(esperada)).max() <= 1.0 / a.vista[2] + 0.01


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
            comprobar(a.ancho + 2 * o["margen_pantalla_px"] <= area[2]
                      and a.alto + o["reserva_titulo_px"] + o["margen_pantalla_px"] <= area[3],
                      "la ventana entra en el área de trabajo (con la barra de título)")
        comprobar(a.i == 0 and not salida1.exists(), "sin archivo previo, empieza en la primera persona")
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
        arrastrar(a, "ter", completa)
        comprobar(cerca(a.r["completa"], completa, a) and a.herramienta == "visible",
                  "A: completa dibujada en la térmica; la herramienta pasa a visible")
        vis_rgb = [precarga[0], precarga[1], precarga[2], (precarga[1] + precarga[3]) / 2]
        arrastrar(a, "rgb", vis_rgb, boton="der")
        comprobar(cerca(a.r["rgb"]["caja"], vis_rgb, a) and cerca(a.r["completa"], completa, a),
                  "A: visible RGB redibujada con el botón derecho (la completa no cambia)")
        vis_ter = [wisard[0] + 3, wisard[1] + 3, wisard[2] - 3, wisard[3] - 3]
        arrastrar(a, "ter", vis_ter)
        comprobar(cerca(a.r["ter"]["caja"], vis_ter, a), "A: visible térmica redibujada con la herramienta visible")
        tecla(a, "u")
        comprobar(a.r["ter"]["caja"] == wisard, "A: deshacer devuelve la visible térmica de WiSARD")
        comprobar(pd.read_csv(salida1).shape[0] == 1, "A: el CSV se guarda después de cada cambio")
        # zoom con la rueda: el punto bajo el cursor no se mueve
        pos = (a.x_panel["ter"] + a.pw // 3, a.ph // 3)
        a.raton(cv2.EVENT_MOUSEMOVE, *pos, 0)
        antes_zoom = a.desde_panel(pos[0] - a.x_panel["ter"], pos[1])
        z0 = a.vista[2]
        a.raton(cv2.EVENT_MOUSEWHEEL, 0, 0, 120 << 16)  # rueda hacia adelante (u, v de pantalla: se ignoran)
        despues = a.desde_panel(pos[0] - a.x_panel["ter"], pos[1])
        comprobar(a.vista[2] > z0 and np.allclose(antes_zoom, despues), "A: zoom con la rueda en torno al cursor")
        cv2.imwrite(str(capturas / "herramienta_primero.jpg"), a.dibujar(), [cv2.IMWRITE_JPEG_QUALITY, 90])
        tecla(a, "0")
        rA = a.r
        lam_rgb, lam_ter = lam(rA["rgb"]["caja"], rA["completa"]), lam(rA["ter"]["caja"], rA["completa"])
        comprobar(terminada(rA), f"A: terminada (lambda RGB {lam_rgb:.3f}, lambda térmica {lam_ter:.3f})")
        tecla(a, "n")

        # ---- persona B
        a.ir_a(iB)
        comprobar(a.r["rgb"]["estado"] == "pendiente" and a.r["ter"]["estado"] == "caja",
                  "B: sin caja RGB cerca, la visible RGB empieza pendiente")
        p = a.p
        completaB = [p.ter_x0 - 1, p.ter_y0 - 4, p.ter_x1 + 1, p.ter_y1 + 1]
        arrastrar(a, "rgb", completaB)
        comprobar(cerca(a.r["completa"], completaB, a) and not terminada(a.r),
                  "B: completa dibujada en la RGB; sin terminar porque falta la visible RGB")
        tecla(a, "r")
        comprobar(a.r["rgb"]["estado"] == "no_visible" and terminada(a.r), "B: 'no visible' en la RGB, terminada")
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
        comprobar(abs(fA.lambda_rgb - lam_rgb) < 1e-3 and abs(fA.lambda_termica - lam_ter) < 1e-3,
                  f"CSV: lambda de A igual al calculado aparte ({fA.lambda_rgb}, {fA.lambda_termica})")
        comprobar(df.loc[B].rgb_estado == "no_visible" and df.loc[B].lambda_rgb == 1.0 and pd.isna(df.loc[B].rgb_x0),
                  "CSV: B con la RGB no visible y lambda RGB = 1")
        comprobar(bool(df.loc[C].no_es_persona) and not bool(df.loc[C].fuera_de_cuadro), "CSV: C 'no es persona'")

        # ---- retomar
        a2 = crear_anotador(cfg, rutas, segundo=False, salida=salida1, area=area)
        hechas = {A, B, C}
        primera = next(k for k, i in enumerate(a2.ids) if i not in hechas)
        comprobar(a2.i == primera, f"al retomar empieza en la primera persona sin terminar ({a2.ids[primera]})")
        def igual(x, y):  # el CSV guarda 2 decimales
            return np.abs(np.array(x) - np.array(y)).max() <= 0.006
        comprobar(igual(a2.anot[A]["completa"], rA["completa"]) and igual(a2.anot[A]["rgb"]["caja"], rA["rgb"]["caja"])
                  and igual(a2.anot[A]["ter"]["caja"], wisard)
                  and a2.anot[B]["rgb"]["estado"] == "no_visible" and a2.anot[C]["no_es_persona"],
                  "al retomar se recuperan las cajas y las marcas guardadas")

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
        arrastrar(s, "ter", [p.ter_x0 - 1, p.ter_y0 - 3, p.ter_x1 + 1, p.ter_y1 + 1])
        arrastrar(s, "ter", [p.ter_x0, p.ter_y0, p.ter_x1, p.ter_y1])
        tecla(s, "r")
        s.raton(cv2.EVENT_MOUSEMOVE, s.x_panel["rgb"] + s.pw // 2 + 40, s.ph // 2 - 30, 0)
        cv2.imwrite(str(capturas / "herramienta_segundo.jpg"), s.dibujar(), [cv2.IMWRITE_JPEG_QUALITY, 90])
        tecla(s, "n")
        d2 = pd.read_csv(salida2, dtype={"id": str})
        comprobar(len(d2) == 1 and d2.anotador.iloc[0] == "segundo" and bool(d2.terminada.iloc[0]),
                  "segundo: guarda en su propio archivo, anotador 'segundo'")
        comprobar(hashlib.md5(salida1.read_bytes()).hexdigest() == huella, "segundo: el archivo del primero no cambia")

    despues_reales = {r: r.read_bytes() if r.exists() else None for r in reales}
    comprobar(despues_reales == antes, "data/oclusion.csv y data/oclusion_segundo.csv no se tocaron")
    print(f"Capturas en {capturas}")
    print("PRUEBA CORRECTA")


if __name__ == "__main__":
    main()
