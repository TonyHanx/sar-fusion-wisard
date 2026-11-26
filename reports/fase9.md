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

## R3: entrada de 960 px con `scale: 0.3` (aprobada el 26 de noviembre de 2026)

**Qué cambia respecto al control:** solo `imgsz` (de 640 a 960) y `scale` (de 0.5, el valor por omisión, a 0.3). Se comprobó por código que no cambia nada más. Se corre con las semillas 0, 1 y 2.

- **No hay más detalle real.** Las imágenes miden 640 × 512. A 960 px se agrandan ×1.5 por interpolación, y la validación también se agranda. Una persona de 11 px pasa a ~16 px, pero los ~16 px salen de interpolar los mismos 11 px de la imagen original.
- **De dónde viene el beneficio esperado.** La red ve a la persona agrandada, así que en las capas de detección ocupa más celdas. En P3 (paso de 8 px), una persona de 11 px pasa de ~1.4 a ~2 celdas. Con más celdas, la red tiene más posiciones desde donde detectarla y más contexto en el campo receptivo.
- **Por qué `scale: 0.3`.** Con 0.5, el aumento de escala achica a las personas hasta la mitad: justo las pequeñas, que son las que fallan. Con 0.3 se achican hasta el 70 %.
- **Costo:** unas 2.25 veces más píxeles por imagen, tanto en el entrenamiento como en la inferencia. El tiempo por imagen en inferencia a 640 y a 960 px se mide en la sección siguiente, para la viabilidad en Jetson.

Estimado: 45 a 55 s por época, unos 40 a 48 min por semilla y unos 15 a 18 GB de GPU. Los valores reales se agregan cuando terminen las corridas.

## Control y R2 con 3 semillas: R1 por receta y por vuelo

Fuente: `src/evaluacion/fase9_validacion.py`; tablas en `reports/fase9/r1_corridas.csv`, `r1_recetas.csv` y `r1_comparaciones.csv`.

Qué mide cada columna:

- **R1:** la media móvil de 5 épocas del mAP@0.5 de validación (Ultralytics) en la época que elige R1.
- **Los mAP@0.5 por vuelo:** salen de las predicciones de `elegida.pt`, con el evaluador propio del diagnóstico. En total, ese evaluador difiere del de Ultralytics en 0.002 a 0.005.

Las semillas 1 y 2 del control y todas las de R2 corrieron con `workers: 12`. La semilla 0 del control corrió con 4.

| Receta | Semilla | Época R1 | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---|---:|---:|---:|---:|---:|---:|
| Control | 0 | 27 | 0.370 | 0.449 | 0.646 | 0.183 |
| Control | 1 | 39 | 0.303 | 0.285 | 0.467 | 0.064 |
| Control | 2 | 36 | 0.369 | 0.338 | 0.467 | 0.163 |
| R2 | 0 | 16 | 0.341 | 0.318 | 0.455 | 0.124 |
| R2 | 1 | 15 | 0.292 | 0.274 | 0.456 | 0.042 |
| R2 | 2 | 26 | 0.349 | 0.358 | 0.537 | 0.105 |

Promedio ± desviación estándar entre las 3 semillas:

| Receta | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---|---:|---:|---:|---:|
| Control | 0.347 ± 0.039 | 0.357 ± 0.084 | 0.527 ± 0.104 | 0.137 ± 0.064 |
| R2 | 0.327 ± 0.031 | 0.317 ± 0.042 | 0.483 ± 0.047 | 0.090 ± 0.043 |
| R2 − control | −0.020 (EE 0.029, p de Welch 0.52) | −0.041 (EE 0.054) | −0.044 (EE 0.066) | −0.047 (EE 0.045) |

**R2 no supera al control.** Las diferencias son negativas en todas las métricas y en los dos vuelos. Ninguna supera dos errores típicos entre semillas ni el mínimo relevante de 0.08.

- La dispersión entre semillas del mismo control es de 0.039 en R1, y entre sus semillas R1 va de 0.303 a 0.370. Es casi el doble de la diferencia entre recetas.
- R2 tarda unos 14 min por semilla y el control unos 25. Con el mosaico hasta el final la caída del tramo final desaparece, pero el nivel que alcanza R2 no es mayor.

## Tiempo por imagen en inferencia (lote 1, RTX 6000 Ada): no sirve para la Jetson

Fuente: `src/evaluacion/fase9_tiempo_inferencia.py` y `reports/fase9/tiempo_inferencia.csv`. Se midió con la GPU libre, antes de R3, sobre las 442 imágenes de validación.

| Tamaño | Precisión | Preproceso | Inferencia | Posproceso | Total (ms/imagen) |
|---:|---|---:|---:|---:|---:|
| 640 | fp32 | 1.76 | 11.66 | 1.19 | 14.6 |
| 640 | fp16 | 1.91 | 12.23 | 1.09 | 15.2 |
| 960 | fp32 | 3.05 | 9.55 | 0.96 | 13.6 |
| 960 | fp16 | 3.47 | 10.58 | 1.06 | 15.1 |

**Estas cifras no miden el cómputo.** Con lote 1, esta GPU pasa casi todo el tiempo lanzando operaciones desde Python, no calculando. Por eso salen dos resultados que no tienen sentido físico: 960 px "más rápido" que 640, y fp16 más lento que fp32.

- Sirve como dato el costo teórico de la red: 20.8 GFLOPs a 640 px, que escala con los píxeles a unos 47 GFLOPs a 960 px (×2.25).
- En una Jetson, donde el límite sí es el cómputo, cabe esperar que el tiempo crezca cerca de ×2.25.
- El tiempo real tiene que medirse en la Jetson.

## R3 con 3 semillas: resultado

**Recursos reales.** Unos 33 a 36 s por época y de 31 a 33 min por semilla, con `workers: 12`. Se había estimado de 45 a 55 s por época. El pico de memoria GPU fue de 15.3 GB de 48 GB.

**R1 por semilla**

| Semilla | Época R1 | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---:|---:|---:|---:|---:|---:|
| 0 | 31 | 0.309 | 0.316 | 0.554 | 0.037 |
| 1 | 29 | 0.316 | 0.304 | 0.428 | 0.146 |
| 2 | 28 | 0.333 | 0.258 | 0.302 | 0.192 |

**Promedio ± desviación estándar entre las 3 semillas, y diferencia con el control**

| Receta | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---|---:|---:|---:|---:|
| Control | 0.347 ± 0.039 | 0.358 ± 0.084 | 0.527 ± 0.104 | 0.137 ± 0.064 |
| R2 | 0.327 ± 0.031 | 0.317 ± 0.042 | 0.483 ± 0.047 | 0.090 ± 0.043 |
| R3 | 0.319 ± 0.012 | 0.293 ± 0.031 | 0.428 ± 0.126 | 0.125 ± 0.080 |
| R3 − control | −0.028 (EE 0.023, p 0.34) | −0.065 (EE 0.052) | −0.099 (EE 0.094) | −0.012 (EE 0.059) |

**R3 no supera al control.** Ninguna diferencia supera dos errores típicos ni el mínimo relevante de 0.08.

- Ni siquiera mejora en FHL 0134, el vuelo de personas pequeñas al que apuntaba: −0.012.
- En MtErie 0007 baja 0.099, aunque con mucha dispersión entre semillas.

Agrandar la imagen por interpolación no compensó la falta de detalle real. Con las semillas que hay, ninguna de las dos recetas corrige el problema mejor que la receta original.

Nota: al reevaluar con R3, `fase9_validacion.py` volvió a escribir en la bitácora la fila de R2 contra el control, con las mismas cifras.
