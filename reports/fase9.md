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

## Pendiente al cierre del 26 de noviembre de 2026

Por decisión del usuario, no se lanzó nada más después de R3. Quedan pendientes, en este orden:

1. **R4: rebalanceo de vuelos.** Tomar 1 de cada 2 fotogramas de Baker y duplicar FHL 0401, como dataset nuevo en `configs/`; el WiSARD original no se toca.
   - Es la única receta del diagnóstico que queda por probar, y ataca otra causa: el desbalance de vuelos.
   - Se corre sobre el control, con las semillas 0, 1 y 2, y se compara con la misma regla que R2 y R3.
   - Costo estimado: unos 75 min para las 3 semillas.
2. **Datos base o ampliados.** Con la receta elegida: el control, salvo que R4 lo supere. Se decide una sola vez, igual para los tres modelos.
   - Con los datos ampliados, cada época cuesta unas 4 veces más: entre 1.5 y 2 h por semilla.
3. **Pasar la receta a los modelos de solo térmica y solo RGB.** Misma receta y mismos datos, con R1 y las 3 semillas, sin ajustar nada por modelo.
   - Antes de pasar al paso 4 se comprueba en validación que ninguno colapse; la señal sería la solo RGB con su mejor época en la 1.
   - Son 6 corridas: entre 2.5 y 5 h con datos base, más con los ampliados.
4. **La evaluación única de los tres modelos en la prueba.** Sería el segundo uso de la prueba, y el informe tiene que declararlo.
5. **El tiempo de inferencia real en la Jetson**, a 640 px. Lo medido en la RTX 6000 con lote 1 no sirve para eso.

Trabajo futuro, fuera de este curso: R5, el aumento fotométrico por modalidad.

## Reglas fijadas el 27 de noviembre de 2026, antes de ver R4

Las fijó el usuario antes de lanzar R4. Están en `decision_r4` de `configs/fase9.yaml`, y las aplica
`src/evaluacion/fase9_decidir.py`, desde `results.csv` y sin predecir nada.

1. **Receta final.** R4 gana solo si su R1 promedio entre las 3 semillas supera al del control **por 0.08 o más y por
   más de dos errores típicos entre semillas**. El error típico es el de Welch, el mismo de R2 y R3. Si no gana, la
   receta final es la del control.
   - **Por qué.** Es la misma vara que se usó con R2 y R3. El 0.08 es el mínimo relevante del diagnóstico, por el ruido
     de la validación por bloques. Los dos errores típicos cubren la dispersión entre semillas, que en el control ya es
     de 0.039 en R1. Con 3 semillas, una sola condición no basta.
2. **Datos base para los tres modelos, no los ampliados.**
   - **Por qué.** En la fase 7 los ampliados mejoraron la fusión apenas 0.02, dentro del ruido, y cada época cuesta
     unas 4 veces más.
   - Así queda cerrado el punto 2 del pendiente, sin otra corrida.

Con la receta ganadora y los datos base se entrenan **solo térmica y solo RGB** con las semillas 0, 1 y 2, sin ajustar
nada por modelo. Son 6 corridas: `control_termico_base` y `control_rgb_base`, o `r4_termico_base` y `r4_rgb_base` si
gana R4. La fusión con esa receta ya existe y no se repite. Si en alguna corrida la época que elige R1 cae entre las 5
primeras, se marca como posible colapso, pero la cola no se detiene.

## R4: rebalanceo de vuelos (27 de noviembre de 2026)

**Qué cambia respecto al control:** solo los datos de entrenamiento.

- De Baker quedan las posiciones pares, sin azar.
- FHL 0401 va dos veces.
- El resto de la receta es la del control: 50 épocas, `close_mosaic` 10, lote 16, AdamW con lr0 0.002, HSV en 0,
  `workers` 12 y R1, con las semillas 0, 1 y 2.

`src/particion/rebalanceo_r4.py` (sección `r4` de `configs/fase9.yaml`) arma `data/datasets/r4_{fusion,rgb,termico}/` y
`configs/r4_{fusion,rgb,termico}.yaml`, todo con enlaces duros a los datasets base. No se tocan ni los datasets base ni el
WiSARD original.

- Las copias de FHL 0401 llevan otro nombre (`<nombre>_copia2`). En una misma carpeta no puede haber dos archivos con el
  mismo nombre. Una lista `.txt` con rutas repetidas tampoco servía: Ultralytics habría reescrito la caché de etiquetas
  del dataset base, porque la guarda junto a las etiquetas.
- La validación es la misma carpeta de la base (`val: ../fusion/images/val`), así que también usa las mismas etiquetas.
- No hay partición de prueba.

**Pares y personas de entrenamiento por vuelo** (`reports/fase9/r4_vuelos.csv`; es la misma tabla para los tres modelos):

| Vuelo | Pares antes | Pares después | Personas antes | Personas después | Queda |
|---|---:|---:|---:|---:|---:|
| MtErie 0003 | 236 | 236 | 905 | 905 | 100 % |
| MtErie 0005 | 257 | 257 | 494 | 494 | 100 % |
| FHL 0401 | 783 | 1 566 | 2 755 | 5 510 | 200 % |
| Baker | 1 971 | 987 | 5 186 | 2 593 | **50.1 % de los pares, 50.0 % de las personas** |
| Total | 3 247 | 3 046 | 9 340 | 9 502 | 93.8 % y 101.7 % |

En el total, Baker pasa del 60.7 % de los pares al 32.4 %, y FHL 0401 del 24.1 % al 51.4 %.

**Comprobaciones antes de lanzar:**

- **Ultralytics cuenta las copias dos veces.** El lector de Ultralytics (`YOLODataset`) da, en cada modelo, 3 046 imágenes
  de entrenamiento, 783 de ellas copias, y 9 502 cajas. La validación da 442 imágenes y 500 cajas, como siempre.
- **Solo cambian los datos de entrenamiento** (`entrenar_fase9 --comparar r4_fusion_base control_fusion_base`, y lo
  mismo con térmica y RGB).
  - La receta mezclada solo difiere en `datos`.
  - En el yaml del dataset solo cambian `path`, `train`, cómo se escribe `val` y la falta de `test`.
  - La validación es la misma carpeta, con los mismos 442 archivos.
- **Comprobaciones previas** (`entrenar_fase9 --solo-comprobar`, nuevo): datos sin la prueba, carpeta nueva, Roblox y
  ChatGPT cerrados, y potencia. Dieron bien.
- **Caché de validación.** Al leer la validación de solo RGB y solo térmica, Ultralytics rehízo su `val.cache`. La
  anterior era de la laptop, del 1 de noviembre, y su firma incluye las rutas de los archivos. Lo mismo le pasó ayer
  a la de la fusión con el primer control en la estación. Solo es el índice de etiquetas que Ultralytics regenera; las
  imágenes y las etiquetas no cambian.

## R4 con 3 semillas: resultado

Fuente: `src/evaluacion/fase9_validacion.py`. Las tablas están en `reports/fase9/r1_corridas.csv`, `r1_recetas.csv` y
`r1_comparaciones.csv`, y la decisión en `reports/fase9/decision_r4.json`.

**Recursos:** de 24.1 a 24.8 min por semilla, con una mediana de 26 a 27 s por época. El pico de memoria de la GPU fue de
7.3 a 8.1 GB, el consumo de unos 216 W, con un límite aplicado de 300 W, y la temperatura máxima de 85 °C. La RAM llegó
al 19.4 %.

**R1 por semilla**

| Semilla | Época R1 | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---:|---:|---:|---:|---:|---:|
| 0 | 23 | 0.339 | 0.407 | 0.631 | 0.090 |
| 1 | 41 | 0.408 | 0.442 | 0.618 | 0.221 |
| 2 | 30 | 0.391 | 0.393 | 0.542 | 0.189 |

**Promedio ± desviación estándar entre las 3 semillas, y diferencia con el control**

| Receta | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---|---:|---:|---:|---:|
| Control | 0.347 ± 0.039 | 0.358 ± 0.084 | 0.527 ± 0.104 | 0.137 ± 0.064 |
| R2 | 0.327 ± 0.031 | 0.317 ± 0.042 | 0.483 ± 0.047 | 0.090 ± 0.043 |
| R3 | 0.319 ± 0.012 | 0.293 ± 0.031 | 0.428 ± 0.126 | 0.125 ± 0.080 |
| R4 | 0.379 ± 0.036 | 0.414 ± 0.025 | 0.597 ± 0.048 | 0.167 ± 0.068 |
| R4 − control | +0.032 (EE 0.030, p 0.35) | +0.057 (EE 0.050) | +0.070 (EE 0.066) | +0.030 (EE 0.054) |

**R4 no supera al control según la regla fijada antes.** En R1, la diferencia es de +0.032. Para ganar necesitaba 0.08 o
más y, además, más de dos errores típicos (2 × 0.030 = 0.061). No cumple ninguna de las dos. **La receta final es la del
control, con los datos base.**

- Es la primera receta con diferencias positivas en las cuatro métricas y en los dos vuelos. Ninguna llega a dos errores
  típicos ni al mínimo de 0.08.
- Con 3 semillas por receta, la comparación tiene poca potencia. Que R4 no gane no demuestra que sea igual al control:
  el resultado es que no se pudo distinguir del ruido. Va como limitación.
- **Posible limitación del rebalanceo.** Con R4, FHL 0401 pasa al 51 % de los pares de entrenamiento, y la mitad de
  ellos son copias exactas. No hay fotogramas nuevos de ese vuelo: el modelo ve dos veces las mismas imágenes, aunque
  con aumentos al azar distintos en cada lectura. Esto puede llevar a memorizar ese vuelo en vez de aprender más del
  tipo de escena.

## Paso 3: solo térmica y solo RGB con la receta del control

Son la misma receta y los mismos datos base que el control de la fusión, con R1 y las semillas 0, 1 y 2, sin ajustar
nada por modelo. Las corridas son `control_termico_base_s{0,1,2}` y `control_rgb_base_s{0,1,2}`; a diferencia de la
fusión, la semilla 0 lleva sufijo. **La fusión con esta receta es la del control y no se repitió.**

**Recursos:**

- solo térmica: de 21.0 a 24.1 min por semilla, con una mediana de 22 a 26 s por época;
- solo RGB: de 21.0 a 21.3 min, con 23 s por época;
- en las dos, un pico de memoria de la GPU de 7.9 a 8.5 GB, un consumo de unos 233 W y una temperatura máxima de 85 °C.

**R1 por corrida.** Hay posible colapso cuando la época R1 cae entre las 5 primeras.

| Modelo | Semilla | Época R1 | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 | Posible colapso |
|---|---:|---:|---:|---:|---:|---:|---|
| Fusión (control) | 0 | 27 | 0.370 | 0.449 | 0.646 | 0.183 | no |
| Fusión (control) | 1 | 39 | 0.303 | 0.285 | 0.467 | 0.064 | no |
| Fusión (control) | 2 | 36 | 0.369 | 0.338 | 0.467 | 0.163 | no |
| Solo térmica | 0 | 27 | 0.287 | 0.371 | 0.409 | 0.352 | no |
| Solo térmica | 1 | 35 | 0.299 | 0.304 | 0.256 | 0.357 | no |
| Solo térmica | 2 | 10 | 0.321 | 0.213 | 0.280 | 0.165 | no |
| Solo RGB | 0 | 10 | 0.136 | 0.117 | 0.211 | 0.000 | no |
| Solo RGB | 1 | 3 | 0.112 | 0.165 | 0.284 | 0.000 | **sí** |
| Solo RGB | 2 | 3 | 0.067 | 0.045 | 0.073 | 0.000 | **sí** |

**R1 por modelo: promedio ± desviación estándar entre las 3 semillas**

| Modelo | R1 | mAP@0.5 `elegida.pt` | MtErie 0007 | FHL 0134 |
|---|---:|---:|---:|---:|
| Fusión | 0.347 ± 0.039 | 0.358 ± 0.084 | 0.527 ± 0.104 | 0.137 ± 0.064 |
| Solo térmica | 0.302 ± 0.018 | 0.296 ± 0.080 | 0.315 ± 0.082 | 0.291 ± 0.109 |
| Solo RGB | 0.105 ± 0.035 | 0.109 ± 0.060 | 0.190 ± 0.107 | 0.000 ± 0.000 |

Es solo la validación; la prueba no se usó. Lo que sigue es descripción, sin prueba estadística entre modelos.

- **Fusión contra solo térmica cambia según el vuelo.**
  - En MtErie 0007, la fusión queda por encima: 0.527 contra 0.315.
  - En FHL 0134, el vuelo de personas pequeñas, la térmica duplica a la fusión: 0.291 contra 0.137.
  - En el total, la fusión queda por encima en R1, 0.347 contra 0.302. R1 mezcla los dos vuelos, así que esconde la
    diferencia entre ellos.
- **Solo RGB colapsa en 2 de 3 semillas.**
  - En las semillas 1 y 2, R1 elige la época 3. El mAP@0.5 de validación es mejor en las primeras épocas y baja de forma
    sostenida: en la semilla 1, de 0.160 en la época 3 a 0.028 en la 50.
  - Es el mismo patrón que `rgb_base` en la primera versión, que bajó de 0.160 a 0.032.
  - En FHL 0134 da 0.000 en las tres semillas.
  - La cola no se detuvo, como se había pedido. Va como limitación del modelo de solo RGB: lo que aprende de los vuelos
    de entrenamiento no se transfiere a la validación.
- **Solo térmica, semilla 2.** R1 elige la época 10. No está entre las 5 primeras, así que no se marca como posible
  colapso. Pero su `elegida.pt` da el mAP@0.5 más bajo de las tres (0.213), y en FHL 0134 baja a 0.165.

## Estado al cierre del 27 de noviembre de 2026

- **Receta final de la segunda versión:** la del control (`fusion_base` de la laptop más R1), con los datos base, para los
  tres modelos y con las semillas 0, 1 y 2.
- **Pendiente:**
  - La evaluación única de los tres modelos en la prueba. Es el segundo uso de la prueba, una vez por versión, y el
    informe tiene que declararlo.
  - Qué pesos y qué semilla se llevan a la prueba no está decidido.
  - El tiempo de inferencia real en la Jetson.
- **Pesos de las 9 corridas de hoy:** `elegida.pt`, `best.pt` y `last.pt` están en un zip aparte, fuera del repositorio
  (`fase9_pesos_27nov.zip`, 27 archivos y 1.2 GB), con la misma estructura que el de ayer. No se guardaron los pesos de
  cada época.

## Corte de la cola del 27 de noviembre de 2026

- **Qué se cortó:** la cola se lanzó a las 13:10. A las 15:04:21 se cortaron la cola y la corrida en curso,
  `control_termico_base_s1`, en la época 27 de 50; `results.csv` tenía 26 épocas.
- **Causa:** la consola de la cola recibió un Ctrl+C. Se ve un `^C` al final de su salida
  (`runs/fase9/cola/cola_stdout_1.txt`), y terminaron todos sus procesos a la vez.
  - No hubo traceback ni evento en los registros de Windows, y la sesión siguió activa.
  - **El origen del Ctrl+C no se pudo confirmar.** Coincidió con una consulta de estado de Claude Code, que solo leía
    archivos.
  - La cola no lo anotó, porque solo registraba el fallo de un paso y no su propio cierre. Se anotó a mano en
    `reports/fase9/cola_log.txt`.
- **Lo que ya estaba hecho no se vio afectado:** R4 con las semillas 0, 1 y 2, la decisión y
  `control_termico_base_s0`.
- **Se repitió desde cero, no se retomó.**
  - La corrida cortada se movió a `runs/fase9/control_termico_base_s1_cortada/`, y su salida a
    `runs/fase9/cola/control_termico_base_s1_cortada.txt`. No se usa, como `rgb_100ep_cortada`, y no alcanzó a escribir
    una fila en la bitácora.
  - `control_termico_base_s1` se volvió a entrenar desde la época 1, con la semilla 1 y la misma receta. Así no depende
    de cómo Ultralytics reanuda el estado aleatorio.
- **Relanzamiento:** a las 15:20:40.
  - La cola saltó las corridas que ya tenían R1, y también la decisión, que ya estaba escrita. Así su fila no se repitió
    en la bitácora.
  - Esta vez se lanzó en un grupo de procesos propio (`CREATE_NEW_PROCESS_GROUP`), para que un Ctrl+C de otra consola
    no le llegue.
  - `control_termico_base_s1` terminó a las 15:42:58.

## Copia de las corridas

`runs/` no va a git. Por eso, las salidas livianas de las corridas están en `reports/fase9/<corrida>/`. Al 26 de noviembre
eran 9 corridas, con 135 archivos y 17.8 MiB. Al 27 de noviembre son 18, con 284 archivos y 89.7 MiB:

- se suman R4 y las de solo térmica y solo RGB;
- en `reports/fase9/cola/` está la salida completa de cada paso de la cola;
- lo más pesado son las predicciones de validación de solo RGB, de 11 a 19 MB cada una. Ese modelo deja muchas
  detecciones de baja confianza.

Cada corrida tiene:

- `results.csv`, `args.yaml`, `resumen.json`, `epocas.csv` y `monitor.csv`;
- las figuras de Ultralytics: curvas, matrices de confusión, etiquetas y `results`. Los PNG se guardaron como JPEG.

También quedaron en `reports/fase9/validacion/` las predicciones de validación de cada `elegida.pt`.

Los copió `src/utilidades/copiar_fase7.py` con la sección `copiar` de `configs/fase9.yaml`.

Los pesos no van a git. `elegida.pt`, `best.pt` y `last.pt` de cada corrida se guardaron en zips aparte, fuera del
repositorio, con la misma estructura de carpetas: `fase9_pesos.zip` tiene las 9 del 26 de noviembre y
`fase9_pesos_27nov.zip` las 9 del 27. No se guardaron los pesos de cada época.
