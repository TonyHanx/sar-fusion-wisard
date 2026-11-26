# Entorno de ejecución: estación del laboratorio

Generado el 2026-11-26 con `scripts/fase0_entorno.py` (rama `main`, commit `4c70453`; en `limpieza-estructura` es
`src/entorno/entorno.py`) y corregido a mano el mismo día (ver "Correcciones a mano"). Desde el 26 de noviembre de 2026,
los entrenamientos que se reportan (segunda versión) corren en este equipo. Las corridas de la primera versión (fases
5 a 8) corrieron en la laptop: su entorno está en `reports/entorno.md`.

| Elemento | Valor |
|---|---|
| Sistema operativo | Windows 11 Enterprise 25H2 (build 26200.9974) |
| CPU | Intel(R) Xeon(R) w7-2495X (24 núcleos, 48 hilos) |
| RAM | 255.5 GiB |
| GPU | NVIDIA RTX 6000 Ada Generation, 49140 MiB, capacidad de cómputo 8.9 |
| Límite de potencia de la GPU | aplicado bajo carga: mediana 300 W (rango 300 a 300 W; consumo 280 W) en 30 s de carga; por defecto 300.00 W, máximo 300.00 W (mínimo configurable 100.00 W); límite fijo, sin Dynamic Boost |
| Límite de potencia durante el entrenamiento | pendiente: se mide en la primera corrida (`gpu_limite_aplicado_mediana_w` de `resumen.json`) |
| Modo de energía | sin batería (estación de escritorio: `psutil.sensors_battery()` da `None`); Armoury Crate: no aplica (no está instalado); plan de Windows: High performance |
| Controlador NVIDIA | 596.51 (admite CUDA hasta 13.2) |
| Python | 3.12.16 (instalado con `uv python install 3.12`) |
| PyTorch | 2.15.0+cu132 |
| CUDA (con la que se compiló PyTorch) | 13.2 |
| cuDNN | 9.26.0 |
| Ultralytics | 8.4.194 |
| `torch.cuda.is_available()` | True |

## Versiones de los paquetes principales

| Paquete | Versión |
|---|---|
| torch | 2.15.0+cu132 |
| torchvision | 0.29.2+cu132 |
| ultralytics | 8.4.194 |
| opencv-python | 5.0.0.93 |
| pycocotools | 2.0.11 |
| statsmodels | 0.15.0 |
| scipy | 1.18.1 |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| tifffile | 2026.10.15 |
| matplotlib | 3.11.2 |

## Instalación

El controlador 596.51 admite CUDA hasta 13.2, así que PyTorch no se instaló con el índice cu134 de
`requirements.txt` (el de la laptop), sino con el cu132. Se usó uv (0.13.10, instalado en el usuario) porque
`winget install Python.Python.3.12` falló con acceso denegado (0x80070005):

```
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe torch==2.15.0 torchvision --index-url https://download.pytorch.org/whl/cu132
uv pip install --python .venv\Scripts\python.exe -r <copia de requirements.txt sin torch, torchvision ni el índice cu134>
```

`requirements.txt` fija `torch==2.15.0+cu134`, `torchvision==0.29.2+cu134` y el índice cu134. Los demás paquetes
se instalaron con las versiones exactas de `requirements.txt`, desde una copia sin esas tres líneas. El archivo no
se modificó.

Intérprete: `C:\Users\I21326\tesis\sar-fusion-wisard\.venv\Scripts\python.exe`

## Correcciones a mano

El script tiene textos escritos para la laptop (RTX 4070 Laptop GPU). Se corrigieron con lo medido en esta estación:

| Texto del script | Corrección |
|---|---|
| "Todos los entrenamientos que se reporten corren en este equipo." | Se dice qué corridas van en cada equipo (CLAUDE.md, 26 de noviembre de 2026). |
| "techo de 100 W con Dynamic Boost" | Límite fijo de 300 W, sin Dynamic Boost (`nvidia-smi`: 300 W por defecto y como máximo). |
| "Armoury Crate: Rendimiento" (de `modo_armoury_crate` en `configs/fase0.yaml`) | No aplica: no hay procesos, servicios ni paquetes de Armoury Crate. |
| "enchufada: sí" | El script lo da porque no encuentra batería. Ahora dice "sin batería". |
| "plan de Windows: High performance" | Es el medido y se deja. En la laptop el plan se llama "Performance"; las comprobaciones usan el de cada perfil (`potencia.maquinas` de `configs/fase5.yaml`). |
| "PyTorch se instaló con el comando oficial de pytorch.org para Windows y CUDA 13.4" y `pip3 install ... /whl/cu134` | Los comandos de uv con el índice cu132 (ver "Instalación"). |
| "La lista completa con versiones exactas está en `requirements.txt`." | Lo mismo, salvo torch y torchvision, que aquí son `+cu132` (ver "Instalación"). |

El reporte se generó con una copia temporal de `configs/fase0.yaml` en la que solo cambia
`entorno: entorno_laboratorio.md`, para no sobrescribir `reports/entorno.md`.

**Pendiente de medir** (no se ha entrenado en esta estación):
- el límite de potencia aplicado y el consumo durante el entrenamiento (en la laptop bajaban con la CPU ocupada en leer
  imágenes);
- la temperatura máxima de la GPU, el pico de memoria de la GPU y el pico de RAM al entrenar;
- el tiempo por época.
