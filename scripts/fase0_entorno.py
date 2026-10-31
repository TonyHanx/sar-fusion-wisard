"""Fase 0: escribe reports/entorno.md con el sistema operativo, el hardware y las versiones del software.

Uso: python scripts/fase0_entorno.py --config configs/fase0.yaml --rutas configs/rutas.yaml
"""
import argparse
import platform
import subprocess
import sys
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
    gpu, controlador, vram, pot_aplicada, pot_defecto, pot_max = nvidia_smi(
        "name,driver_version,memory.total,enforced.power.limit,power.default_limit,power.max_limit")
    cudnn = torch.backends.cudnn.version()
    props = torch.cuda.get_device_properties(0)

    filas = [
        ("Sistema operativo", so),
        ("CPU", f"{cpu} ({psutil.cpu_count(logical=False)} núcleos, {psutil.cpu_count()} hilos)"),
        ("RAM", f"{psutil.virtual_memory().total / 2**30:.1f} GiB"),
        ("GPU", f"{gpu}, {vram}, capacidad de cómputo {props.major}.{props.minor}"),
        ("Límite de potencia de la GPU", f"aplicado {pot_aplicada} al generar este archivo "
                                         f"(por defecto {pot_defecto}, máximo {pot_max}); "
                                         "varía con el modo de energía de la laptop"),
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
