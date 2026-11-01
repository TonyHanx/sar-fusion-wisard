r"""Conteos para planear la partición y la anotación de oclusión (antes de la Fase 3; no crea la partición).

Sobre los pares finales (anotados y no excluidos de data/pares.csv), por vuelo:
- pares, pares con persona en la térmica y pares "solo térmica" (alguna caja térmica y ninguna RGB);
- personas: cajas térmicas, sin las repetidas (las que la Fase 3a elimina); se cuentan por fotograma, no son
  personas distintas;
- personas "sin caja RGB": sin ninguna caja RGB llevada a la térmica a `radio_cerca_alturas` alturas o menos;
- episodios: tramos de posiciones seguidas con alguna persona en la térmica. Un par sin persona o excluido corta el
  episodio; también se da el número si los pares excluidos no cortan (la persona sigue ahí en el vídeo).

Para el vuelo de prueba: personas a anotar si se anota todo, 1 de cada 3 o 1 de cada 5 fotogramas (posición % k == 0;
también el mínimo y el máximo con los k desfases posibles), y cuántas son "solo térmica".

Uso:
    .venv\Scripts\python.exe scripts\conteo_particion.py --config configs\conteo_particion.yaml --rutas configs\rutas.yaml
"""
import argparse

import numpy as np
import pandas as pd
import yaml

from comun import RAIZ, leer_rutas, leer_yaml
from fase2_homografias_cajas import cajas_llevadas, cajas_px, centros


def personas_del_par(par, dataset, H, tam_rgb, tam_ter, radio):
    """Cajas térmicas sin repetidas del par y, para cada una, si tiene una caja RGB llevada cerca."""
    ct = cajas_px((dataset / par.ruta_termica).with_suffix(".txt"), tam_ter)
    cr = cajas_px((dataset / par.ruta_rgb).with_suffix(".txt"), tam_rgb)
    if not len(ct):
        return 0, 0
    if not len(cr):
        return len(ct), len(ct)
    rgb = centros(cajas_llevadas(H, cr))
    d = np.linalg.norm(centros(ct)[:, None, :] - rgb[None, :, :], axis=2).min(axis=1)
    alto = ct[:, 3] - ct[:, 1]
    return len(ct), int((d > radio * alto).sum())


def episodios(estado):
    """Tramos de posiciones seguidas con persona. `estado`: Serie indexada por posición (todas las posiciones del
    vuelo) con 'persona', 'sin persona' o 'excluido'. Devuelve las longitudes estrictas (cualquier otro estado corta)
    y las que se obtienen si 'excluido' no corta (los pares excluidos no se cuentan en la longitud)."""
    estrictos, unidos = [], []
    n = m = 0
    for e in estado.to_numpy():
        if e == "persona":
            n += 1
            m += 1
        else:
            if n:
                estrictos.append(n)
            n = 0
            if e != "excluido":
                if m:
                    unidos.append(m)
                m = 0
    if n:
        estrictos.append(n)
    if m:
        unidos.append(m)
    return estrictos, unidos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    D = rutas["dataset"]
    tam_ter = tuple(cfg["tam_termica"])
    Hs = yaml.safe_load((RAIZ / cfg["transformaciones"]).read_text(encoding="utf-8"))

    todos = pd.read_csv(rutas["data"] / cfg["pares"], dtype={"cajas_rgb": "Int64", "cajas_termica": "Int64"})
    anotados = todos[todos.anotado]
    filas, por_par = [], []
    for vuelo, g in anotados.groupby("vuelo"):
        fin = g[~g.excluido].sort_values("posicion")
        if not len(fin):
            continue
        H = np.array(Hs[vuelo]["H_rgb_a_termica"], np.float64)
        tam_rgb = tuple(Hs[vuelo]["tam_rgb"])
        cuenta = [personas_del_par(p, D, H, tam_rgb, tam_ter, cfg["radio_cerca_alturas"]) for p in fin.itertuples()]
        fin = fin.assign(personas=[a for a, _ in cuenta], sin_caja_rgb=[b for _, b in cuenta],
                         cajas_termicas_con_repetidas=fin.cajas_termica.astype(int))
        fin["solo_termica"] = (fin.personas > 0) & (fin.cajas_rgb == 0)
        por_par.append(fin)
        # estado de cada posición del vuelo (anotada): persona, sin persona o excluido
        estado = pd.Series("excluido", index=g.sort_values("posicion").posicion.to_numpy(), dtype=object)
        estado.loc[fin.posicion.to_numpy()] = np.where(fin.personas > 0, "persona", "sin persona")
        estrictos, unidos = episodios(estado)
        filas.append({
            "vuelo": vuelo, "pares": len(fin), "pares_con_persona": int((fin.personas > 0).sum()),
            "personas": int(fin.personas.sum()), "cajas_termicas_con_repetidas": int(fin.cajas_termicas_con_repetidas.sum()),
            "pares_solo_termica": int(fin.solo_termica.sum()),
            "personas_en_pares_solo_termica": int(fin.personas[fin.solo_termica].sum()),
            "personas_sin_caja_rgb": int(fin.sin_caja_rgb.sum()),
            "episodios": len(estrictos), "episodios_de_1_par": int(sum(e == 1 for e in estrictos)),
            "episodio_mediana_pares": float(np.median(estrictos)), "episodio_max_pares": int(max(estrictos)),
            "episodios_si_excluidos_no_cortan": len(unidos)})
    tabla = pd.DataFrame(filas)
    total = tabla.drop(columns="vuelo").sum(numeric_only=True)
    total[["episodio_mediana_pares", "episodio_max_pares"]] = np.nan
    tabla = pd.concat([tabla, pd.DataFrame([{"vuelo": "TOTAL", **total.to_dict()}])], ignore_index=True)
    pd.set_option("display.width", 250)
    print(tabla.to_string(index=False))
    tabla.to_csv(rutas["reports"] / cfg["salida_vuelos"], index=False, encoding="utf-8")

    # submuestreo de la anotación en el vuelo de prueba
    p = pd.concat(por_par)
    p = p[p.vuelo == cfg["vuelo_prueba"]]
    sub = []
    for k in cfg["pasos_anotacion"]:
        variantes = []
        for desfase in range(k):
            s = p[p.posicion % k == desfase]
            variantes.append({"fotogramas": len(s), "fotogramas_con_persona": int((s.personas > 0).sum()),
                              "personas": int(s.personas.sum()),
                              "personas_en_pares_solo_termica": int(s.personas[s.solo_termica].sum()),
                              "pares_solo_termica": int(s.solo_termica.sum()),
                              "personas_sin_caja_rgb": int(s.sin_caja_rgb.sum())})
        v = pd.DataFrame(variantes)
        fila = {"paso": k, **{c: int(v.loc[0, c]) for c in v.columns}}
        fila.update({f"{c}_min": int(v[c].min()) for c in v.columns})
        fila.update({f"{c}_max": int(v[c].max()) for c in v.columns})
        sub.append(fila)
    sub = pd.DataFrame(sub)
    print(f"\nVuelo de prueba {cfg['vuelo_prueba']} (desfase 0; _min y _max con los k desfases posibles):")
    print(sub.to_string(index=False))
    sub.to_csv(rutas["reports"] / cfg["salida_prueba"], index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
