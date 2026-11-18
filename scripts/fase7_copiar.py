"""Fase 7: copia las salidas livianas de runs/<carpeta>/ a reports/<destino>/ para subirlas a git (runs/ no va a git).

Copia los globs de `copiar.desde_runs` (configs/fase7.yaml) con la misma estructura, sin los de `copiar.excluir`. Los PNG
se guardan como JPEG con la calidad de `copiar.jpeg_calidad`.

Uso:
  .venv\\Scripts\\python.exe scripts\\fase7_copiar.py --config configs\\fase7.yaml --rutas configs\\rutas.yaml
"""
import argparse
import fnmatch
import shutil

from PIL import Image

from comun import leer_rutas, leer_yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    c = cfg["copiar"]
    origen = rutas["runs"] / cfg["carpeta"]
    destino = rutas["reports"] / c["destino"]
    n, total = 0, 0
    for patron in c["desde_runs"]:
        for f in sorted(origen.glob(patron)):
            if not f.is_file() or any(fnmatch.fnmatch(f.name, e) for e in c["excluir"]):
                continue
            d = destino / f.relative_to(origen)
            d.parent.mkdir(parents=True, exist_ok=True)
            if f.suffix.lower() == ".png":
                d = d.with_suffix(".jpg")
                Image.open(f).convert("RGB").save(d, quality=c["jpeg_calidad"])
            else:
                shutil.copy2(f, d)
            n += 1
            total += d.stat().st_size
    print(f"{n} archivos, {total / 2**20:.1f} MiB en {destino}")


if __name__ == "__main__":
    main()
