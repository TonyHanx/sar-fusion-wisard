# Fase 5a: prueba corta de entrenamiento

Fecha: 1 de noviembre de 2026.

**Resumen:**
- **Lote 16:** entra con la fusión (pico de 5 331 de 8 188 MiB), así que es el de los tres modelos.
- **Optimizador que elige Ultralytics:** AdamW con lr0 = 0.002. `args.yaml` guarda lo pedido: `auto` y 0.01.
- **Inicio del cuarto canal: se elige (b), el promedio de los pesos de color.** En la época 10, el mAP@0.5 de
  validación es 0.306 con (b) y 0.260 con (a). (a) no supera a (b) por 0.02 o más.
- **Cada entrenamiento de 100 épocas tardaría unos 70 a 74 min,** y los tres seguidos, unas 3.6 h.

**Condiciones:**
- Todo se corrió en la laptop enchufada, con el plan Performance de Windows y Armoury Crate en Rendimiento. El modo de
  Armoury Crate se declara, porque no se puede leer desde Python.
- No se tocó el dataset original ni `data/`, salvo la caché de etiquetas que Ultralytics escribe en
  `data/datasets/*/labels/`.
- Cada corrida agregó una fila a la bitácora. Son 6, todas de la fase 5a.

## Corridas

| Corrida | Modelo | Épocas | Procesos de lectura | Para qué |
|---|---|---:|---:|---|
| `fusion_lote16_2ep` | fusión | 2 | 8 | ¿entra el lote 16? |
| `fusion_lote16_2ep_w4` | fusión | 2 | 4 | diagnóstico de RAM y potencia |
| `fusion_azar_10ep` | fusión, cuarto canal (a) al azar | 10 | 4 | inicio del cuarto canal |
| `fusion_promedio_10ep` | fusión, cuarto canal (b) promedio | 10 | 4 | inicio del cuarto canal |
| `rgb_tiempo_3ep` | solo RGB | 3 | 4 | tiempo por época |
| `termico_tiempo_3ep` | solo térmica | 3 | 4 | tiempo por época |

Configuración común:
- YOLO26s desde `yolo26s.pt`, con `seed=0`, `deterministic=True`, imagen de 640, lote 16 y `hsv_h=hsv_s=hsv_v=0`.
- `cache=False`: las imágenes se leen del disco por lotes.
- El resto, con los valores por omisión de Ultralytics 8.4.194.
- Salidas en `runs/fase5/<corrida>/`.

Las dos primeras corridas se hicieron con Roblox, ChatGPT y Chrome abiertos. Las cuatro últimas, con los tres cerrados
y 4 procesos de lectura, que son las condiciones fijadas para todas las corridas.

```
.venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_promedio_10ep
```

## Script y configuración

- **`scripts/entrenar.py`, antes de entrenar:**
  - comprueba que Roblox, ChatGPT y Chrome estén cerrados (`cerrar_antes`);
  - comprueba que la laptop esté enchufada y con el plan Performance;
  - hace la **comprobación previa de potencia**: 30 s con solo la GPU cargada, y la mediana del límite aplicado
    (`enforced.power.limit`) tiene que ser de al menos 90 W.
  - Si algo falla, se detiene sin entrenar.
- **Configuración** (`configs/fase5.yaml`): cada corrida toma `base` y cambia solo lo suyo. Lo de `ultralytics` va tal
  cual a `model.train()`.
- **Cuarto canal:**
  - `inicio_cuarto_canal: azar` deja la primera capa como la deja Ultralytics (`DetectionModel.load`): los 3 canales
    de color con los pesos preentrenados y el cuarto al azar.
  - `promedio` pone en el cuarto canal el promedio de los 3 de color, antes de crear la EMA y el optimizador.
- **Salidas, además de lo de Ultralytics:**
  - `monitor.csv`: nvidia-smi y la RAM, cada segundo;
  - `epocas.csv`: tiempo de entrenamiento y de validación, y memoria máxima de PyTorch, por época;
  - `resumen.json`: potencia previa y durante el entrenamiento, optimizador, primera capa, memoria, tiempos y métricas.
- **Bitácora:** una fila por corrida, también si falla, con el límite de potencia real y el pico de RAM.

## Lote: el 16 entra

**"Entra"** quiere decir dos cosas:
- Ultralytics no bajó el lote. Esta versión lo baja sola si se queda sin memoria en la primera época, así que el script
  lo comprueba.
- El pico de memoria dedicada de la GPU (nvidia-smi) no pasó del 95 % de 8 188 MiB. Así se descarta que Windows usara
  memoria compartida del sistema.

| Corrida | Lote final | Pico GPU (nvidia-smi) | Máx. reservada por PyTorch |
|---|---:|---:|---:|
| `fusion_lote16_2ep` (con mosaico) | 16 | 5 331 MiB (65 %) | 5 164 MiB |
| `fusion_lote16_2ep_w4` (con mosaico) | 16 | 5 331 MiB (65 %) | 5 164 MiB |
| `fusion_azar_10ep` y `fusion_promedio_10ep` | 16 | 5 289 MiB | 5 122 MiB |
| `rgb_tiempo_3ep` y `termico_tiempo_3ep` | 16 | 5 287 MiB | 5 120 MiB |

- **El lote 16 entra con unos 2.8 GB libres** en los tres modelos, así que es el de los tres. El lote 8 no se corrió.
- **La prueba del lote se hizo con mosaico** (`close_mosaic=0`). Con `close_mosaic=10`, Ultralytics quita el mosaico
  en las 10 últimas épocas, y en una corrida de 10 épocas o menos lo quita desde la primera. Con mosaico hay más
  personas por imagen, así que la memoria que se mide es la del caso más exigente.

## Optimizador y tasa de aprendizaje

**`args.yaml` no guarda la elección.** Guarda lo pedido (`optimizer: auto`, `lr0: 0.01`, `momentum: 0.937`), porque se
escribe al crear el entrenador, antes de elegir el optimizador. La elección aparece en el registro de Ultralytics, en
`train_args` de `weights/last.pt` y en el optimizador mismo. Fue la misma en las 6 corridas:

| | Valor |
|---|---|
| Optimizador | **AdamW** |
| Tasa de aprendizaje inicial (`lr0`) | **0.002** |
| Momentos (betas) | 0.9 y 0.999 |
| `weight_decay` | 0.0005 en los pesos (126 tensores); 0 en los de BatchNorm (114) y en los sesgos (126) |
| Acumulación | 4 lotes de 16 (lote nominal `nbs` = 64) |
| Calendario | lineal hasta `lr0 × lrf` = 0.00002 (`lrf=0.01`), con 3 épocas de calentamiento |
| Precisión | mixta (AMP) |

**Cómo elige Ultralytics** (`build_optimizer`, con `optimizer=auto`):
- Cuenta las iteraciones: ⌈imágenes de entrenamiento / máx(lote, 64)⌉ × épocas = ⌈3 247 / 64⌉ × épocas = 51 × épocas.
- **Con más de 10 000** usa MuSGD con 0.01.
- **Si no**, usa AdamW con 0.002 × 5 / (4 + clases) = 0.002 (una clase).

**Con 100 épocas** son 5 100 iteraciones, así que también AdamW con 0.002. Vale para los tres modelos, que tienen las
mismas 3 247 imágenes de entrenamiento.

## Inicio del cuarto canal

**Regla** (CLAUDE.md, cambiada el 1 de noviembre de 2026 antes de correr la comparación, commit `6b6eb3e`):
- Se elige (a) solo si su mAP@0.5 de validación en la época 10 supera al de (b) por 0.02 o más. Si no, se elige (b).
- La regla anterior pedía el mayor mAP@0.5 y elegía (b) si la diferencia era menor que 0.01. Se cambió porque, en las
  pruebas de 2 épocas, cambiar solo el número de procesos de lectura movió el mAP@0.5 de 0.307 a 0.293 (0.014).

Las dos corridas son iguales salvo el cuarto canal: misma semilla, mismos datos, 4 procesos de lectura y 10 épocas sin
mosaico.

Primera capa al empezar, comprobada por el script:

| | (a) azar | (b) promedio |
|---|---:|---:|
| Canales de color iguales a `yolo26s.pt` | sí | sí |
| Desviación típica, canales de color | 0.333 | 0.333 |
| Desviación típica, cuarto canal | 0.098 | 0.182 |
| Diferencia máxima entre el cuarto canal y el promedio de color | 0.688 | 0 |
| EMA igual al modelo | sí | sí |

**Resultado (validación: FHL 0134 y MtErie 0007, 442 imágenes):**

| | (a) azar | (b) promedio | (a) − (b) |
|---|---:|---:|---:|
| **mAP@0.5, época 10 (decide)** | **0.260** | **0.306** | **−0.047** |
| mAP@0.5:0.95, época 10 | 0.122 | 0.137 | −0.015 |
| Precisión, época 10 | 0.397 | 0.441 | |
| Recall, época 10 | 0.288 | 0.332 | |
| Mejor mAP@0.5 (época) | 0.297 (9) | 0.323 (9) | −0.027 |
| mAP@0.5 de `best.pt` (elegido por mAP@0.5:0.95) | 0.297 | 0.318 | −0.021 |

**Decisión: (b), el promedio de los pesos de color.** (a) no supera a (b) por 0.02 o más: queda 0.047 por debajo. Con
la regla anterior también salía (b).

mAP@0.5 de validación por época:

| Época | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| (a) azar | 0.127 | 0.104 | 0.132 | 0.122 | 0.230 | 0.291 | 0.219 | 0.229 | 0.297 | 0.260 |
| (b) promedio | 0.181 | 0.271 | 0.224 | 0.207 | 0.298 | 0.322 | 0.318 | 0.277 | 0.324 | 0.306 |

- **(b) queda por encima en las 10 épocas.**
- **Las curvas son ruidosas:** de una época a la siguiente, el mAP@0.5 sube o baja hasta 0.11 en (a) y 0.09 en (b).
  - Es una sola semilla y 10 épocas.
  - La diferencia mide el arranque, no el resultado tras 100 épocas.

## Tiempo por época y estimación de 100 épocas

| Corrida | Época 1 | Con mosaico | Sin mosaico | Validación por época |
|---|---:|---:|---:|---:|
| fusión (`fusion_lote16_2ep_w4` y las de 10 épocas) | 70.8 a 76.3 s | 44.1 s | 42.5 s (mediana de las épocas 2 a 10) | 3 a 4 s |
| solo RGB (`rgb_tiempo_3ep`) | 71.9 s | 42.2 s | 52.3 s (época 3) | 3.2 s |
| solo térmica (`termico_tiempo_3ep`) | 71.3 s | 41.8 s | 51.8 s (época 3) | 2.9 s |

- **La época 1 tarda más** porque arrancan los procesos de lectura. La primera validación sola tarda de 21 a 25 s.
- **La época 3 del RGB y del térmico** incluye el reinicio de los procesos de lectura al quitar el mosaico, unos 10 s.
  Es la misma transición que habrá en la época 91 de un entrenamiento de 100.

**Estimación de 100 épocas:**
- **Cálculo:** arranque + época 1 + 89 épocas con mosaico + 10 sin mosaico + validación final con `best.pt`.
- **Supuestos:**
  - Las 10 épocas sin mosaico tardan una como la época 3 medida (con el reinicio) y 9 como una con mosaico.
  - En la fusión, las 10 tardan como las de la corrida de 10 épocas, y el reinicio se suma aparte (unos 10 s).
- No incluye la comprobación previa (30 s) ni la carga del modelo.

| Modelo | Estimación |
|---|---:|
| Fusión temprana | **≈ 74 min** (4 445 s) |
| Solo RGB | **≈ 71 min** (4 274 s) |
| Solo térmica | **≈ 70 min** (4 231 s) |
| Los tres seguidos | **≈ 3.6 h** |

Con el límite de potencia que hubo en estas corridas, de 82 a 85 W (ver abajo). Si cambia, la estimación también.

## Potencia y RAM durante el entrenamiento

**Regla de potencia** (ajustada el 1 de noviembre de 2026, CLAUDE.md):
- La comprobación previa, con solo la GPU cargada, tiene que dar 90 W o más.
- El límite real durante el entrenamiento se registra en cada corrida, sin mínimo.
- Se sigue en modo Rendimiento, y los tres modelos entrenan en las mismas condiciones.

| Corrida | Previa | Límite al entrenar (mediana, con la GPU al 50 % o más) | Percentiles 10 a 90 | Consumo | Uso de la GPU | Temp. máx. |
|---|---:|---:|---:|---:|---:|---:|
| `fusion_lote16_2ep` (8 procesos, aplicaciones abiertas) | 95.5 W | 70.0 W | 70.0 a 70.1 W | 68.5 W | 96 % | 73 °C |
| `fusion_lote16_2ep_w4` (4, aplicaciones abiertas) | 98.6 W | 71.6 W | 70.0 a 74.9 W | 70.0 W | 93 % | 77 °C |
| `fusion_azar_10ep` | 99.2 W | 82.3 W | 76.4 a 85.3 W | 79.5 W | 88 % | 84 °C |
| `fusion_promedio_10ep` | 99.1 W | 85.2 W | 80.2 a 87.0 W | 81.8 W | 88 % | 87 °C |
| `rgb_tiempo_3ep` | 98.9 W | 82.2 W | 78.7 a 85.0 W | 79.4 W | 89 % | 84 °C |
| `termico_tiempo_3ep` | 97.7 W | 82.5 W | 79.1 a 85.3 W | 80.2 W | 88 % | 84 °C |

- **La comprobación previa pasó siempre:** de 95.5 a 99.2 W.
- **Al entrenar, el límite queda por debajo de los 90 W.**
  - Baja en los primeros segundos de la corrida, cuando arrancan los procesos de lectura y ocupan la CPU.
  - En la prueba sin entrenar, 12 procesos que ocupan la CPU lo bajaron de 98 a 89 W.
- **Con las condiciones fijadas** (4 procesos y las aplicaciones cerradas) quedó entre 82 y 85 W. En las dos primeras
  corridas, con las aplicaciones abiertas, quedó en 70 W. No se puede separar si la diferencia viene de cerrar las
  aplicaciones o de otra cosa, como la temperatura.
- **La GPU se calienta hasta 84 a 87 °C** en las corridas largas.

**RAM:**
- **Con las condiciones fijadas, el pico sigue entre el 98.7 y el 99.9 %**, con una mediana de 13 994 a 15 148 MiB.
- **Antes de entrenar** había de 6 390 a 7 109 MiB ocupados, incluido el proceso de entrenamiento con la GPU ya
  iniciada.
- **El resto son los procesos de lectura:** Ultralytics abre 4 para entrenar y 8 para validar, de unos 700 MB cada uno.
- No hubo errores. El uso de la GPU se mantuvo entre el 88 y el 96 %, y ninguna época se alargó: en las corridas de 10
  épocas, las épocas 2 a 10 tardaron de 41.9 a 43.4 s.

**Variación entre corridas:** en las pruebas de 2 épocas, cambiar solo el número de procesos de lectura (8 → 4) movió
el mAP@0.5 de la época 2 de 0.307 a 0.293. Por eso se cambió la regla del cuarto canal.

## Pendiente (fase 5b)

- Entrenar los tres modelos 100 épocas, con el lote 16, 4 procesos de lectura y la fusión con el cuarto canal en
  promedio. No se entrenó todavía.
- Las corridas de 100 épocas se agregan a `configs/fase5.yaml` en la fase 5b.

## Cambios en el código

- **`scripts/entrenar.py` (nuevo):**
  - antes de entrenar, comprueba las aplicaciones cerradas y la potencia;
  - entrena con el `DetectionTrainer` de Ultralytics, con el inicio del cuarto canal como opción;
  - registra la memoria, el tiempo, el optimizador, la primera capa y la potencia real;
  - agrega la fila a la bitácora.
- **`configs/fase5.yaml` (nuevo):** base, aplicaciones que se cierran y corridas de la fase 5a.
- **`CLAUDE.md`:**
  - la regla del cuarto canal: anotada antes de entrenar, cambiada a 0.02 antes de la comparación, y su resultado;
  - la regla de potencia ajustada;
  - 4 procesos de lectura y las aplicaciones que se cierran;
  - el optimizador elegido y el lote 16.
- **`FASES.md`:** el mensaje 5a usado.
