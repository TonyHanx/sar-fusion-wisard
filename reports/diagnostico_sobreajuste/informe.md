# Diagnóstico del sobreajuste de la primera versión

26 de noviembre de 2026. No se entrenó ni se predijo nada. La partición de prueba (FHL 0405) no se usó: ni sus predicciones ni sus etiquetas. Las fuentes son:

- los `results.csv` y los `best.pt` de `runs/`;
- las predicciones de **validación** de los `last.pt`, que ya existían en `runs/fase7/c4/validacion/` y `runs/fase8/validacion/`;
- las etiquetas de entrenamiento y validación.

Todo lo reproduce:

```
.venv\Scripts\python.exe -m experimentos.diagnostico_sobreajuste --config configs\diagnostico_sobreajuste.yaml --rutas configs\rutas.yaml
```

Este informe no repite lo que ya está en `reports/diagnostico.md` (B1/B2, A3, A4), `fase5a.md`, `fase5b.md`, `fase7.md` y `fase8.md`. Cuando lo usa, lo cita.

**Sobre la pérdida dfl.** YOLO26 no tiene pérdida dfl. Sus tres pérdidas son `box`, `cls` y `l1`, y `results.csv` no trae ninguna columna dfl. Las figuras muestran `l1` en su lugar.

## Archivos

| Archivo | Qué es |
|---|---|
| `curvas_<corrida>.png` (8) | Pérdidas box, cls y l1 de entrenamiento y de validación, y mAP@0.5, recall y precisión de validación por época. La línea punteada marca el best.pt y la zona gris las épocas sin mosaico. |
| `map50_corridas.png` | El mAP@0.5 de validación de las 8 corridas por época, con su media móvil de 5 épocas. |
| `corridas.csv` | Por corrida: el máximo y su época, la meseta, la caída, las brechas, la época del best.pt y los saltos entre épocas. |
| `ruido.csv`, `ruido_pares.csv`, `ruido_por_vuelo.csv` | El error típico del mAP@0.5 de validación, el de una diferencia entre dos modelos y el mAP@0.5 por vuelo. |
| `tamanos.csv`, `vuelos.csv` | El tamaño de las personas y el balance entre vuelos, en entrenamiento y validación. |

## 1. Curvas por modelo

Las corridas son las de la fase 5 y la fase 7. La fase 5 no tiene una corrida de solo térmica (`termico_100ep` nunca se entrenó). En su lugar va B2 (`runs/diagnostico/b2_termico_vuelo_30ep`): la receta de la fase 5, 30 épocas, la misma partición por vuelo.

En la tabla:

- "Deja de mejorar" es la primera época en que la media móvil de 5 épocas del mAP@0.5 llega al 90 % de su máximo.
- "Máx. suave" es el máximo de esa media móvil, y su época.
- La brecha box se toma en la última época: validación − entrenamiento, y entre paréntesis la razón entre ambas.
- "Mín. val box" es la época en que la pérdida box de validación toca su mínimo.

| Corrida | Deja de mejorar | Máx. suave (época) | Últimas 5 | Brecha box última | Mín. val box (época) | best.pt (criterio) | ¿best.pt = mejor época? |
|---|---:|---:|---:|---:|---:|---:|---|
| Fusión, fase 5, 100 ép. | 8 | 0.327 (37) | 0.247 | 1.94 (×3.6) | 1 | ép. 8 (mAP50-95) | Sí por su criterio. **No por mAP@0.5**: el máximo es 0.395 en la ép. 27, y el best.pt da 0.374. |
| Solo RGB, fase 5, cortada en la 67 | 1 | 0.148 (1) | 0.018 | 3.05 (×3.3) | 1 | ép. 2 (mAP50-95) | Sí, en los dos criterios. |
| Solo térmica, receta fase 5 (B2, 30 ép.) | 1 | 0.266 (16) | 0.197 | 1.28 (×2.5) | 18 | ép. 3 (mAP50-95) | Sí, en los dos criterios. |
| Fusión, fase 7 base | 22 | 0.363 (33) | 0.317 | 2.25 (×3.7) | 1 | ép. 23 (mAP50) | Sí. |
| Solo RGB, fase 7 base | 1 | 0.149 (1) | 0.030 | 2.94 (×3.3) | 1 | ép. 1 (mAP50) | Sí. |
| Solo térmica, fase 7 base | 10 | 0.303 (10) | 0.222 | 1.53 (×3.0) | 21 | ép. 12 (mAP50) | Sí. |
| Fusión, fase 7 ampliado | 1 | 0.380 (1) | 0.343 | 1.26 (×2.1) | 3 | ép. 3 (mAP50) | Sí. |
| Solo térmica, fase 7 ampliado | 7 | 0.417 (10) | 0.361 | 1.05 (×1.9) | 6 | ép. 9 (mAP50) | Sí. |

Cómo se sacó la época del best.pt: el best.pt final de Ultralytics guarda `epoch = -1`, pero conserva sus métricas de validación (`train_metrics`). La época es la única fila de `results.csv` con el mismo mAP@0.5 y el mismo mAP@0.5:0.95. En las 8 corridas, el best.pt coincide con la época máxima de su criterio de selección. **Ningún best.pt quedó mal guardado.** La única discrepancia es de criterio: `fusion_100ep` eligió por mAP@0.5:0.95 (eso ya está en `fase5b.md`).

### Lo que muestran las curvas

**La brecha existe desde la época 1.** La pérdida box de validación de la primera época (2.0 a 2.2) ya es mayor que la de entrenamiento al final de cualquier corrida (0.76 a 1.35). Una brecha que está ahí antes de memorizar nada no es sobreajuste: es una diferencia entre los datos de entrenamiento y los de validación (sección 3).

**Encima de esa brecha hay sobreajuste de verdad, pero moderado.** Cuatro señales:

- La pérdida de entrenamiento baja sin pausa en las 8 corridas (Spearman con la época entre −0.93 y −1.00).
- La pérdida box de validación sube después de su mínimo en 7 de las 8 corridas (Spearman +0.12 a +0.63; la excepción es fusion_ampliado, −0.28). La de cls se estanca en 2.2–6.7, entre 7 y 18 veces la de entrenamiento.
- **Medida con la media móvil**, la caída del mAP@0.5 desde el máximo hasta las últimas 5 épocas es:
  - fusión: 0.046 (base), 0.038 (ampliado) y 0.080 (fase 5);
  - solo térmica: 0.081 (base) y 0.056 (ampliado).
- Al apagar el mosaico (últimas 10 épocas), el mAP@0.5 baja en las 7 corridas que llegan a esa fase: de −0.006 (RGB) a −0.050 (térmica base). En esas mismas épocas la pérdida de entrenamiento baja otro 12 % y la de validación sube. Sin mosaico, el modelo ve las imágenes de entrenamiento tal cual y se ajusta a ellas.

**La caída de 0.11 a 0.17 que muestran `fase7.md` y `fase8.md` exagera el sobreajuste.** Esa cifra compara el best.pt con las últimas épocas. Pero el best.pt es el máximo de una serie con mucho ruido (sección 3.4), y ese máximo sale alto por azar. Dos ejemplos:

- El best.pt de `fusion_ampliado` (0.475, época 3) está 0.095 por encima de la media móvil en esa época.
- El de `termico_ampliado` (0.507, época 9) está 0.09 por encima.

Restando ese sesgo, la caída real es de 0.04 a 0.08.

**Solo RGB es la excepción, y ahí sí hay divergencia clara:**

- su mejor época es la 1 o la 2;
- el mAP@0.5 se hunde de 0.15 a 0.02–0.03;
- la pérdida box de validación pasa de 2.0 a 4.2–4.4.

En FHL 0134 su mAP@0.5 es 0.000.

## 2. Causas que no son sobreajuste: evidencia

### 2.1 Tamaño de las personas a 640 px

Las imágenes miden 640 × 512 y entran a imgsz 640 sin reescalar: el tamaño de las etiquetas es el que ve la red. El lado mayor de cada persona (`tamanos.csv`, `vuelos.csv`):

| | Personas | p10 | Mediana | < 12 px | < 12 px con `scale: 0.5` |
|---|---:|---:|---:|---:|---:|
| Entrenamiento | 9 340 | 17 | 36 | 1.9 % | 5.6 % |
| Validación | 500 | 10 | 28.5 | **23 %** | 26.8 % |
| · MtErie 0007 | 289 | | 45 | 0 % | |
| · FHL 0134 | 211 | | **11** | **54.5 %** | |

- La cabeza más fina de YOLO26 (P3) tiene un paso de 8 px. Una persona de 11 px ocupa 1.4 celdas de P3.
- El aumento `scale: 0.5` también produce personas pequeñas, pero solo lleva a 5.6 % la fracción de personas < 12 px en entrenamiento. En validación es el 23 %.
- El mAP@0.5 por vuelo de los `last.pt` (`ruido_por_vuelo.csv`):

  | Modelo | MtErie 0007 | FHL 0134 |
  |---|---:|---:|
  | fusion_base | 0.52 | 0.06 |
  | fusion_ampliado | 0.49 | 0.18 |
  | termico_base | 0.23 | 0.21 |
  | termico_ampliado | 0.31 | 0.45 |
  | rgb_base | 0.08 | 0.00 |

  Coincide con A4 de `diagnostico.md`: el mAP sube con el tamaño, de 0.10 a 8–12 px hasta 0.62 a ≥ 32 px.

Dato nuevo: **la fusión rinde peor que la solo térmica en las personas pequeñas de FHL 0134, y mejor en MtErie 0007.** Con personas de 1 a 2 celdas, la parte RGB de la fusión empeora el resultado. Este diagnóstico no separa si es porque la RGB no ve a la persona o porque el registro RGB–térmico no alinea esas cajas tan chicas.

### 2.2 Inicio del cuarto canal (térmico)

- La fusión arranca su cuarto canal con el **promedio** de los 3 canales de color preentrenados (`inicio_cuarto_canal: promedio`, elegido en la fase 5a).
- La ventaja del promedio sobre el azar fue de 0.047 de mAP en la época 10 (`fase5a.md`). Eso es menos de un error típico de una diferencia emparejada en esta validación (0.04 a 0.07, sección 2.4). Es decir: el inicio no se distingue del ruido.
- Lo que la red hace con el canal térmico después del inicio sí depende del modelo. Según C4 de `fase7.md`, con la RGB en 0, `fusion_ampliado` conserva el 92 % de su recall y `fusion_base` solo el 22 %.

**Conclusión:** el inicio no explica la brecha.

### 2.3 Aumentos de Ultralytics 8.4.194 con 4 canales

Revisé el código de `ultralytics/data/augment.py` y `utils/patches.py` y los `args.yaml` de la fase 7:

| Aumento | Con 4 canales | ¿Daña el térmico? |
|---|---|---|
| Lectura TIFF (`imread`, `IMREAD_UNCHANGED`) | Conserva los 4 canales. | No. |
| Orden de canales (`Format`) | Invierte el orden solo si la imagen tiene 3 canales; `bgr: 0`. Comprobado con un fotograma de validación: el tensor de fusión es R, G, B, T, idéntico canal a canal al tensor RGB y al térmico. | No. |
| HSV (`RandomHSV`) | Se salta las imágenes que no tienen 3 canales. Además `hsv_h/s/v = 0` en todas las corridas. | No: no se aplica. |
| Albumentations (blur, CLAHE…) | No está instalado. Aunque lo estuviera, se salta las imágenes que no tienen 1 o 3 canales. | No: no se aplica. |
| Mosaico, `translate 0.1`, `scale 0.5` | Relleno 114 en los 4 canales (`borderValue` de 4 valores; el código comenta el error anterior que dejaba el 4.º en 0). | No: el térmico rellena con el mismo gris que la versión de solo térmica. |
| `LetterBox` | Relleno 114 en todos los canales (rama multiespectral). | No. |
| `fliplr 0.5` | Voltea los 4 canales juntos. | No. |
| `mixup`, `cutmix`, `copy_paste`, `degrees`, `shear`, `perspective` | Todos en 0. | No. |

**Ningún aumento daña el canal térmico.** La consecuencia que sí importa es otra: **ningún modelo tiene aumento fotométrico.** El HSV está en 0 en los tres modelos, para que los tres tengan la misma receta. Así, la solo RGB aprende el color y la iluminación de los vuelos de entrenamiento. La solo RGB es justo el modelo que diverge.

### 2.4 Tamaño de la validación (442 fotogramas, 500 personas)

`ruido.csv` remuestrea las predicciones de validación de cada `last.pt`, 2 000 veces:

| Modelo | mAP@0.5 | EE por imagen | EE por bloque de 20 fotogramas (23 bloques) | IC 95 % por bloque |
|---|---:|---:|---:|---:|
| fusion_base | 0.314 | 0.022 | **0.076** | 0.16–0.46 |
| termico_base | 0.227 | 0.021 | 0.060 | 0.12–0.35 |
| fusion_ampliado | 0.338 | 0.021 | 0.068 | 0.20–0.47 |
| termico_ampliado | 0.368 | 0.023 | 0.066 | 0.24–0.49 |
| rgb_base | 0.039 | 0.009 | 0.023 | 0.00–0.09 |

Cómo leer esta tabla:

- Mi cálculo da el mismo mAP@0.5 que Ultralytics, con una diferencia de 0.004 a 0.007.
- Los fotogramas vecinos son casi iguales, así que el error que cuenta es el **remuestreo por bloque**: 0.06 a 0.08.
- La diferencia entre dos modelos sobre los mismos bloques (`ruido_pares.csv`) tiene un error típico de **0.04 a 0.07**:

  | Diferencia | Valor | IC 95 % |
  |---|---:|---:|
  | fusion_ampliado − fusion_base | +0.024 | −0.05 a +0.11 |
  | termico_ampliado − termico_base | +0.141 | +0.06 a +0.23 |

Dentro de una sola corrida, el salto medio entre épocas consecutivas es de 0.033 a 0.054 en toda la corrida. Baja a 0.005–0.022 en las últimas 10, cuando la tasa de aprendizaje ya es baja y el mosaico está apagado.

**Consecuencias:**

- el máximo por época es en buena parte ruido;
- dos recetas que difieran en menos de unas 0.08 a 0.10 de mAP@0.5 no se distinguen con una sola corrida cada una.

### 2.5 Balance de vuelos

| Partición | Vuelo | Imágenes | Personas | Mediana del lado | < 12 px |
|---|---|---:|---:|---:|---:|
| Entrenamiento | Baker | 61 % | 56 % | 64 px | 0 % |
| | FHL 0401 | 24 % | 29 % | 21 px | 6.4 % |
| | MtErie 0003 | 7 % | 10 % | 23 px | 0.4 % |
| | MtErie 0005 | 8 % | 5 % | 72 px | 0 % |
| Validación | FHL 0134 | 62 % | 42 % | 11 px | 54.5 % |
| | MtErie 0007 | 38 % | 58 % | 45 px | 0 % |

Lo que muestra la tabla:

- Más de la mitad del entrenamiento es un solo vuelo (Baker) con personas grandes.
- Los fotogramas de Baker son secuencias casi repetidas: hay menos datos efectivos de lo que dice el número de imágenes.
- La validación son solo dos vuelos, de tipos opuestos. El mAP de validación depende sobre todo de cómo le vaya al modelo en FHL 0134.

## 3. Causas, de más a menos probable

1. **Distinta distribución entre los vuelos de entrenamiento y los de validación, sobre todo en el tamaño.**
   - La brecha está desde la época 1.
   - El 23 % de la validación mide < 12 px, contra el 1.9 % del entrenamiento.
   - Hay una diferencia de 0.3 a 0.5 de mAP entre los dos vuelos de validación.
   - Hay una diferencia de 0.66 entre la partición al azar y la partición por vuelo (B1/B2).

   Esto explica la mayor parte del bajo rendimiento, y no se corrige con regularización.
2. **Ruido de la validación y elección del best.pt por el máximo.**
   - Error típico de 0.06 a 0.08 por bloque.
   - Saltos de hasta 0.16 entre épocas.
   - El best.pt queda 0.09 por encima de la tendencia.

   Infla el "mejor" resultado y exagera la caída: la parte que parece sobreajuste mide 0.11–0.17, y la real 0.04–0.08.
3. **Sobreajuste real después de unas 10 a 30 épocas**, más fuerte sin mosaico.
   - La pérdida de validación sube después de su mínimo mientras la de entrenamiento sigue bajando.
   - La pérdida cls de validación es de 7 a 18 veces la de entrenamiento.
   - Hay una caída de 0.01 a 0.05 al apagar el mosaico.
   - Datos efectivos pocos y repetidos (Baker).
4. **Resolución insuficiente para personas de 1 a 2 celdas de P3.**
   - Mediana de 11 px en FHL 0134.
   - `scale: 0.5` las achica todavía más en el entrenamiento.

   Es parte de la causa 1, pero es la parte que sí se puede atacar con la receta.
5. **Sin aumento fotométrico.** Afecta sobre todo a la solo RGB, que diverge desde la época 1 y tiene 0.000 en FHL 0134.
6. **Inicio del cuarto canal.** Poco probable: la ventaja medida está dentro del ruido.
7. **Un aumento que dañe el canal térmico.** Descartado por el código y por la comprobación de canales.

## 4. Recetas de corrección, en orden de prioridad

Cada receta cambia una sola cosa sobre el control. Los tiempos son **estimaciones**:

- En la laptop (medido): unos 42 s por época con los datos base y unos 175 s con los ampliados, a 640.
- En la estación no hay ninguna época medida (`entorno_laboratorio.md`, pendiente). Supongo de 20 a 30 s por época base, asumiendo que la lectura de datos limita antes que la GPU. **Esa cifra debe reemplazarse por la medida en la primera corrida.**

| # | Receta | Qué cambia | Por qué | Costo estimado en la estación (50 ép., datos base) |
|---|---|---|---|---|
| R1 | **Elección estable de la época** (no cambia el entrenamiento) | En vez del best.pt por el máximo: el `last.pt`, o la mejor época de la **media móvil de 5** del mAP@0.5 de validación. También reportar siempre el mAP por vuelo de validación y el error por bloque. | Causa 2. Quita el sesgo del máximo y hace comparables las recetas siguientes. | 0 (se calcula sobre lo que guarda cada corrida). |
| R2 | **Mosaico hasta el final y menos épocas** | `close_mosaic: 0`, `epochs: 30`, `cos_lr: true`. | Causa 3. El mosaico es lo único que frena el sobreajuste, y apagarlo bajó el mAP en todas las corridas. Además la meseta (90 % del máximo suave) llega antes de la época 30 en las 8 corridas. | De 10 a 15 min (30 ép.). |
| R3 | **Más resolución de entrada** | `imgsz: 960` (las imágenes se agrandan ×1.5) y `scale: 0.3`, para no achicar tanto a las personas. | Causas 1 y 4. Una persona de 11 px pasa a 16 px, unas 2 celdas de P3. | Unas 2.25 veces el píxel: de 45 a 70 min (50 ép.), o de 25 a 40 min con R2. Hay que vigilar la memoria con lote 16 (48 GB deberían bastar; se mide). |
| R4 | **Rebalanceo de vuelos** | Tomar 1 de cada 2 fotogramas de Baker (de 1 971 a unos 985) y duplicar FHL 0401, el único vuelo de entrenamiento con personas pequeñas. Se arma como un dataset nuevo en `configs/`; el WiSARD original no se toca. | Causas 1 y 3. Menos fotogramas casi repetidos y más peso al tipo de vuelo que falla. La decisión usa solo datos de entrenamiento. | Similar a la base: de 20 a 25 min. |
| R5 | **Aumento fotométrico por modalidad** | Brillo, contraste y gamma al azar, por separado para el bloque RGB y para el térmico. Necesita un transform propio, porque el HSV de Ultralytics se salta los 4 canales. En la solo RGB y la solo térmica se aplica la misma transformación a su bloque. | Causa 5. Es la que más ayudaría a la solo RGB, y mantiene la misma receta en los tres modelos. | Similar a la base, más el código y su prueba. |

R1 va siempre. Las otras cuatro se prueban en orden.

**Los datos ampliados de la fase 7 no son una receta nueva**, pero son la decisión más cara: cuestan 4 veces más por época. En la solo térmica ganaron +0.14 (IC de +0.06 a +0.23). En la fusión ganaron +0.02, sin diferencia clara. Conviene decidir si el control lleva datos base o ampliados **antes** de probar R2 a R5, y repetir esa misma elección en los tres modelos.

## 5. Cómo probarlas solo con validación

**El control.** Hay que repetir `fusion_base` en la estación con la receta de la fase 7 y la semilla 0. Tres razones:

- es la base contra la que se miden las recetas;
- da el tiempo real por época;
- muestra cuánto cambia el resultado al cambiar de máquina, con la misma semilla.

**Fusión primero, una receta a la vez.**

- En orden R2, R3, R4 y R5, cada corrida cambia una sola cosa sobre la mejor receta acumulada.
- Se compara siempre con R1: el `last.pt` o la mejor época de la media móvil, nunca el máximo por época.

**La regla para quedarse con un cambio:**

1. Predecir la validación con el modelo elegido de cada corrida y calcular la diferencia emparejada por bloques contra la receta anterior, con este mismo script (`ruido_pares`).
2. Adoptar el cambio solo si cumple las tres condiciones:
   - el IC 95 % de la diferencia queda por encima de 0;
   - no empeora ninguno de los dos vuelos de validación en más de un error típico;
   - el sobreajuste baja: menos caída entre el máximo suave y las últimas 5 épocas, o menos brecha de pérdida box.
3. Con una sola semilla, una diferencia menor que unas 0.08 se reporta como "sin diferencia clara" y no se adopta, salvo que la receta sea más barata.

**El registro.** Cada cambio queda escrito con su motivo y su resultado de validación, como pide CLAUDE.md. El informe final declara que la validación sirvió tanto para elegir la receta como para elegir la época.

**Pasar la receta a los tres modelos.**

1. La receta ganadora, completa y sin tocarla, se corre una vez en la solo térmica y una vez en la solo RGB, con el mismo control de energía y la misma semilla.
2. En esas dos corridas no se ajusta nada por modelo. Solo se comprueba en validación que ninguno colapse; la señal sería la RGB con su mejor época en la 1.
3. Si alguno colapsa, el problema se reporta. No se cambia la receta de un solo modelo.
4. Después, una única evaluación de los tres modelos en la prueba. Sería el segundo uso de la prueba, declarado en el informe.

**Presupuesto estimado** (por confirmar con el control):

| Paso | Estimación |
|---|---|
| Control | De 20 a 25 min |
| R2 a R5 en la fusión | De 1.5 a 3 h, según cuántas recetas se adopten y si entra R3 |
| Transferir a la térmica y la RGB | De 0.5 a 2 h |

Con los datos ampliados, todo esto se multiplica por unas 4 veces.

## 6. Decisiones (26 de noviembre de 2026) y trabajo futuro

Decisiones del usuario después de este diagnóstico:

- Las recetas se prueban con los **datos base**. La elección entre datos base y ampliados queda para el final y será la misma para los tres modelos.
- **R1 se adopta en todas las corridas nuevas.** Se guardan los pesos de cada época y la época elegida es la de mayor media móvil centrada de 5 épocas del mAP@0.5 de validación (`configs/fase9.yaml`, `src/entrenamiento/entrenar_fase9.py`).
- Primero el control (`fusion_base` con la receta de la laptop, en la estación). Después R2 y luego R3, cada una cambiando una sola cosa respecto al control y con aprobación previa de su configuración. R4 queda para después de R2 y R3.
- **R5 (aumento fotométrico por modalidad) no se hace en este curso.** Queda como trabajo futuro: es la causa 5, la que más afectaría a la solo RGB, y necesita un transform propio para 4 canales, porque el HSV de Ultralytics se salta esas imágenes.
