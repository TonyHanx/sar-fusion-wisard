"""Fase 9: cola de los pasos 1 y 3 (sección `cola` de configs/fase9.yaml), pensada para correr sola, sin la sesión.

1. R4 (`cola.r4`) con las semillas de c3.semillas (entrenar_fase9 --corrida ... --semilla N).
2. La regla `decision_r4` (src/evaluacion/fase9_decidir.py), que deja la receta final y las corridas del paso 3.
3. Las corridas del paso 3 (solo térmica y solo RGB con la receta final), con las mismas semillas.

Cada paso corre como un proceso aparte. Su salida completa queda en runs/<cola.salidas>/<paso>.txt, y en `cola.log` queda
una línea por paso, con la hora. Si un paso falla (código distinto de 0), la cola se detiene y lo escribe en el log. Una
corrida con la época de R1 en las primeras `decision_r4.colapso_hasta_epoca` se marca como posible colapso, pero la cola
sigue. Si se vuelve a lanzar, salta las corridas que ya tienen R1 en resumen.json. No usa la prueba.

Uso: .venv\\Scripts\\python.exe -m src.entrenamiento.cola_fase9 --config configs\\fase9.yaml --rutas configs\\rutas.yaml
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

from src.comun import RAIZ, leer_rutas, leer_yaml


class Cola:
    """Corre los pasos en orden y los anota en el log."""

    def __init__(self, cfg, rutas, args):
        self.cfg, self.rutas = cfg, rutas
        self.base_args = ["--config", args.config, "--rutas", args.rutas]
        self.log = RAIZ / cfg["cola"]["log"]
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.salidas = rutas["runs"] / cfg["cola"]["salidas"]
        self.salidas.mkdir(parents=True, exist_ok=True)

    def anotar(self, texto):
        """Una línea en el log, con la hora."""
        linea = f"{datetime.now().isoformat(timespec='seconds')} {texto}"
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
        print(linea, flush=True)

    def correr(self, nombre, modulo, extra):
        """Corre `python -m modulo` con los argumentos; si falla, anota y detiene la cola."""
        salida = self.salidas / f"{nombre}.txt"
        self.anotar(f"inicio {nombre} (salida en {salida.relative_to(RAIZ).as_posix()})")
        entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        with open(salida, "a", encoding="utf-8") as f:
            codigo = subprocess.run([sys.executable, "-m", modulo, *self.base_args, *extra], cwd=RAIZ, stdout=f,
                                    stderr=subprocess.STDOUT, env=entorno).returncode
        if codigo != 0:
            self.anotar(f"COLA DETENIDA: {nombre} terminó con código {codigo}. Detalle al final de {salida.name}.")
            sys.exit(codigo)
        self.anotar(f"fin {nombre}")

    def entrenar(self, corrida, semilla):
        """Entrena una corrida con una semilla (si no está hecha) y revisa la época de R1."""
        nombre = f"{corrida}_s{semilla}"
        resumen = self.rutas["runs"] / self.cfg["c3"]["carpeta"] / nombre / "resumen.json"
        if resumen.exists() and "r1" in json.loads(resumen.read_text(encoding="utf-8")):
            self.anotar(f"salto {nombre}: ya tiene R1")
        else:
            self.correr(nombre, "src.entrenamiento.entrenar_fase9", ["--corrida", corrida, "--semilla", str(semilla)])
        datos = json.loads(resumen.read_text(encoding="utf-8"))
        r1 = datos["r1"]
        limite = self.cfg["decision_r4"]["colapso_hasta_epoca"]
        aviso = f"; POSIBLE COLAPSO: época R1 en las primeras {limite}" if r1["epoca"] <= limite else ""
        self.anotar(f"{nombre}: época R1 {r1['epoca']}, media móvil {r1['media_movil']:.4f}, "
                    f"{datos.get('epocas_corridas')} épocas{aviso}")


def main():
    """Corre la cola completa."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)
    cola = Cola(cfg, rutas, args)
    semillas = cfg["c3"]["semillas"]
    cola.anotar(f"COLA INICIADA (pid {os.getpid()}): {cfg['cola']['r4']} con las semillas {semillas}, decisión y paso 3")
    for s in semillas:
        cola.entrenar(cfg["cola"]["r4"], s)
    cola.correr("decision_r4", "src.evaluacion.fase9_decidir", [])
    decision = json.loads((RAIZ / cfg["decision_r4"]["salida"]).read_text(encoding="utf-8"))
    cola.anotar(f"receta final: {decision['receta_final']} (diferencia {decision['diferencia']:+.4f}, error típico "
                f"{decision['error_tipico']:.4f}); paso 3: {', '.join(decision['corridas_paso3'])}")
    for corrida in decision["corridas_paso3"]:
        for s in semillas:
            cola.entrenar(corrida, s)
    cola.anotar("COLA TERMINADA")


if __name__ == "__main__":
    main()
