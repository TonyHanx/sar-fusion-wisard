# Entorno de ejecución

Generado el 2026-10-30 con `scripts/fase0_entorno.py`. Todos los entrenamientos que se reporten corren en este equipo.

| Elemento | Valor |
|---|---|
| Sistema operativo | Windows 11 Home 25H2 (build 26200.9711) |
| CPU | 13th Gen Intel(R) Core(TM) i7-13620H (10 núcleos, 16 hilos) |
| RAM | 15.6 GiB |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU, 8188 MiB, capacidad de cómputo 8.9 |
| Límite de potencia de la GPU | aplicado bajo carga: mediana 98 W (rango 97 a 99 W; consumo 98 W) en 30 s de carga; por defecto 80.00 W, máximo 120.00 W; techo de 100 W con Dynamic Boost |
| Modo de energía | enchufada: sí; Armoury Crate: Rendimiento; plan de Windows: Performance |
| Controlador NVIDIA | 617.42 |
| Python | 3.12.10 |
| PyTorch | 2.15.0+cu134 |
| CUDA (con la que se compiló PyTorch) | 13.4 |
| cuDNN | 9.26.0 |
| Ultralytics | 8.4.194 |
| `torch.cuda.is_available()` | True |

## Versiones de los paquetes principales

| Paquete | Versión |
|---|---|
| torch | 2.15.0+cu134 |
| torchvision | 0.29.2+cu134 |
| ultralytics | 8.4.194 |
| opencv-python | 5.0.0.93 |
| pycocotools | 2.0.11 |
| statsmodels | 0.15.0 |
| scipy | 1.18.1 |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| tifffile | 2026.10.15 |
| matplotlib | 3.11.2 |

La lista completa con versiones exactas está en `requirements.txt`. PyTorch se instaló con el comando oficial de pytorch.org para Windows y CUDA 13.4:

```
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu134
```

Intérprete: `C:\Users\User\Desktop\sar-fusion-wisard\sar-fusion-wisard\.venv\Scripts\python.exe`
