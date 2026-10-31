"""Fase 0: escribe reports/entorno.md con el sistema operativo, el hardware y las versiones del software.

Uso: python scripts/fase0_entorno.py --config configs/fase0.yaml --rutas configs/rutas.yaml
"""
import argparse
import platform
import re
import statistics
import subprocess
import sys
import time
import winreg
from datetime import date
from importlib.metadata import version

import psutil
import torch

from comun import leer_rutas, leer_yaml

PAQUETES = ["torch", "torchvision", "ultralytics", "opencv-python", "pycocotools", "statsmodels", "scipy",
            "pandas", "numpy", "tifffile", "matplotlib"]


def registro(ruta, nombre):
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta) as k:
        return winreg.QueryValueEx(k, nombre)[0]


def nvidia_smi(campos):
    salida = subprocess.run(["nvidia-smi", f"--query-gpu={campos}", "--format=csv,noheader"],
                            capture_output=True, text=True, check=True).stdout
    return [c.strip() for c in salida.strip().split(",")]


def potencia_bajo_carga(segundos):
    """Carga la GPU con multiplicaciones de matrices y devuelve las lecturas estables de límite aplicado y consumo (W).

    Se descarta la primera mitad de las lecturas, mientras Dynamic Boost sube el límite.
    """
    x = torch.randn(8192, 8192, device="cuda", dtype=torch.float16)
    lecturas = []
    fin = time.time() + segundos
    while time.time() < fin:
        for _ in range(50):
            x @ x
        torch.cuda.synchronize()
        lecturas.append([float(v.split()[0]) for v in nvidia_smi("enforced.power.limit,power.draw")])
    estables = lecturas[len(lecturas) // 2:]
    return [l for l, _ in estables], [c for _, c in estables]


def plan_de_energia():
    salida = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, check=True).stdout
    return re.search(r"\(([^)]*)\)\s*$", salida.strip()).group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--rutas", required=True)
    args = ap.parse_args()
    cfg = leer_yaml(args.config)
    rutas = leer_rutas(args.rutas)

    nt = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    producto = registro(nt, "ProductName")
    build = int(registro(nt, "CurrentBuildNumber"))
    if build >= 22000:  # el registro sigue diciendo "Windows 10" en Windows 11
        producto = producto.replace("Windows 10", "Windows 11")
    so = f"{producto} {registro(nt, 'DisplayVersion')} (build {build}.{registro(nt, 'UBR')})"
    cpu = registro(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString").strip()
    gpu, controlador, vram, pot_defecto, pot_max = nvidia_smi(
        "name,driver_version,memory.total,power.default_limit,power.max_limit")
    limite_carga, consumo_carga = potencia_bajo_carga(cfg["segundos_carga"])
    bateria = psutil.sensors_battery()
    enchufada = "sí" if bateria is None or bateria.power_plugged else "no"
    cudnn = torch.backends.cudnn.version()
    props = torch.cuda.get_device_properties(0)

    filas = [
        ("Sistema operativo", so),
        ("CPU", f"{cpu} ({psutil.cpu_count(logical=False)} núcleos, {psutil.cpu_count()} hilos)"),
        ("RAM", f"{psutil.virtual_memory().total / 2**30:.1f} GiB"),
        ("GPU", f"{gpu}, {vram}, capacidad de cómputo {props.major}.{props.minor}"),
        ("Límite de potencia de la GPU", f"aplicado bajo carga: mediana {statistics.median(limite_carga):.0f} W "
                                         f"(rango {min(limite_carga):.0f} a {max(limite_carga):.0f} W; consumo "
                                         f"{statistics.median(consumo_carga):.0f} W) en {cfg['segundos_carga']} s de "
                                         f"carga; por defecto {pot_defecto}, máximo {pot_max}; "
                                         "techo de 100 W con Dynamic Boost"),
        ("Modo de energía", f"enchufada: {enchufada}; Armoury Crate: {cfg['modo_armoury_crate']}; "
                            f"plan de Windows: {plan_de_energia()}"),
        ("Controlador NVIDIA", controlador),
        ("Python", platform.python_version()),
        ("PyTorch", torch.__version__),
        ("CUDA (con la que se compiló PyTorch)", torch.version.cuda),
        ("cuDNN", f"{cudnn // 10000}.{cudnn // 100 % 100}.{cudnn % 100}"),
        ("Ultralytics", version("ultralytics")),
        ("`torch.cuda.is_available()`", str(torch.cuda.is_available())),
    ]
    lineas = [
        "# Entorno de ejecución",
        "",
        f"Generado el {date.today().isoformat()} con `scripts/fase0_entorno.py`. "
        "Todos los entrenamientos que se reporten corren en este equipo.",
        "",
        "| Elemento | Valor |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in filas],
        "",
        "## Versiones de los paquetes principales",
        "",
        "| Paquete | Versión |",
        "|---|---|",
        *[f"| {p} | {version(p)} |" for p in PAQUETES],
        "",
        "La lista completa con versiones exactas está en `requirements.txt`. PyTorch se instaló con el comando "
        "oficial de pytorch.org para Windows y CUDA 13.4:",
        "",
        "```",
        "pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu134",
        "```",
        "",
        f"Intérprete: `{sys.executable}`",
        "",
    ]
    destino = rutas["reports"] / cfg["entorno"]
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print(destino.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
