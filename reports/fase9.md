# Fase 9: segunda versión, corrección del sobreajuste

Estación del laboratorio (RTX 6000 Ada, 48 GB). Configuración: `configs/fase9.yaml`. Entrenamiento: `src/entrenamiento/entrenar_fase9.py`. Punto de partida: `reports/diagnostico_sobreajuste/informe.md`. La partición de prueba (FHL 0405) no se usa.

## Reglas de la fase (decisiones del usuario, 26 de noviembre de 2026)

- **Datos.** Las recetas se prueban con los datos base. La elección entre base y ampliados se hace al final, igual para los tres modelos.
- **R1.** Se guardan los pesos de cada época. La época elegida es la de mayor media móvil centrada de 5 épocas del mAP@0.5 de validación, solo entre épocas con la ventana completa. Sus pesos se copian a `weights/elegida.pt`.
- **Recetas.**
  - Primero el control: la receta de la laptop.
  - Después R2 y luego R3, cada una cambiando una sola cosa respecto al control.
  - R4 queda para después. R5 no se hace (trabajo futuro).
- **Semillas.** Cada receta se corre con las semillas 0, 1 y 2. Se comparan los promedios de R1 y su dispersión. La semilla 0 del control es la corrida `control_fusion_base`.
- **Carga de datos.**
  - Desde las repeticiones, `workers: 12` en lugar de 4. El lote queda igual.
  - Cambiar `workers` solo cambia qué proceso hace cada aumento al azar. El orden de las imágenes lo fija el generador del proceso principal, que no depende de `workers`.
  - `cache: ram` no se usa: en Ultralytics 8.4.194 cambia la regla con que el mosaico elige sus otras 3 imágenes. Con caché las toma de todo el dataset; sin caché, del búfer de las últimas imágenes leídas (`augment.py`, `buffer_enabled`). Además, Ultralytics avisa que con caché el entrenamiento no es determinista.
- **Velocidad de carga medida.** Solo la carga, 120 lotes de entrenamiento de la fusión:

| `workers` | Lotes por segundo | Carga de una época | Arranque de los procesos |
|---:|---:|---:|---:|
| 4 | 14.6 | ~14 s | 13 s |
| 12 | 40.8 | ~5 s | 37 s |
| 16 | 32.7 | ~6 s | 49 s |

## Control: `control_fusion_base` (semilla 0, `workers: 4`)

La receta es la de `fusion_base` de la fase 7 (laptop), más `save_period: 1`. Se comprobó por código que no cambia nada más.

**Recursos**

- 50 épocas en 22.7 min.
- Tiempo por época (mediana): 27 s con mosaico y 22 s sin mosaico. La primera época tardó 73 s.
- Uso de la GPU: 48 % (mediana). La carga de datos limitaba, no la GPU.
- Pico de memoria GPU: 7 608 MiB de 49 140 (nvidia-smi). PyTorch reservó como máximo 5 546 MiB.
- Consumo: 233 W (mediana), con límite aplicado de 300 W. Temperatura máxima: 83 °C.
- Pico de RAM: 14.6 %.
- Los pesos de las 50 épocas ocupan 4.8 GB.

**Validación (mAP@0.5) comparada con la laptop**

| | Laptop (`runs/fase7/fusion_base`) | Estación (`runs/fase9/control_fusion_base`) |
|---|---:|---:|
| R1: media móvil de 5 (época) | 0.363 (33) | **0.370 (27)** |
| Media de las épocas 46–50 | 0.317 | 0.268 |
| Última época | 0.307 | 0.258 |
| best.pt: máximo por época (época) | 0.425 (23) | 0.450 (27) |

- **Con la misma semilla, la corrida no se repite en otra máquina.**
  - La pérdida de entrenamiento casi coincide: la pérdida box difiere 0.005 en promedio.
  - El mAP@0.5 de validación ya difiere en la época 1: 0.296 en la laptop, 0.133 en la estación.
  - Época a época, las dos curvas de mAP@0.5 difieren 0.055 en promedio y su correlación es 0.33.
  - Esto coincide con el ruido medido en el diagnóstico.
- **R1 casi coincide entre máquinas** (0.363 y 0.370). Las cifras del final y del máximo cambian unas 0.05.
- **En la estación la caída final es mayor.** Del máximo de la media móvil a las últimas 5 épocas baja 0.10; en la laptop bajó 0.046.
- **Las recetas se comparan contra este control, no contra la laptop.**
