# Fase 5a: prueba corta de entrenamiento

Fecha: 1 de noviembre de 2026.

**Estado: detenida antes de la comparación del cuarto canal.** Bajo la carga real del entrenamiento, el límite de
potencia aplicado a la GPU baja a unos 70 W, menos que los 90 W que pide CLAUDE.md, aunque la comprobación previa
con solo la GPU cargada da de 95 a 99 W (ver "Potencia y RAM durante el entrenamiento"). Hecho hasta aquí:
- `scripts/entrenar.py` y `configs/fase5.yaml`;
- la prueba del lote 16 con la fusión, que entra;
- el optimizador que elige Ultralytics;
- la regla del cuarto canal, anotada en CLAUDE.md antes de entrenar.

Todo se corrió en la laptop enchufada, con el plan Performance de Windows y Armoury Crate en Rendimiento (declarado:
no se puede leer desde Python). No se tocó el dataset original ni `data/`, salvo la caché de etiquetas que
Ultralytics escribe en `data/datasets/fusion/labels/`. Cada corrida agregó una fila a la bitácora.

## Comprobación de potencia antes de entrenar

`scripts/entrenar.py` la hace antes de cada corrida:
- la laptop tiene que estar enchufada y con el plan de `potencia.plan`;
- se cargan 30 s solo la GPU, con multiplicaciones de matrices;
- la mediana del límite aplicado (`enforced.power.limit`, de la segunda mitad de las lecturas) tiene que ser de al
  menos 90 W.

Si algo falla, el script se detiene sin entrenar.

| Momento | Límite aplicado, mediana | Rango | Consumo, mediana |
|---|---:|---:|---:|
| Antes de escribir el script (a mano) | 95.8 W | 93.0 a 97.4 W | 93.0 W |
| Antes de `fusion_lote16_2ep` | 95.5 W | 90.9 a 96.4 W | 92.8 W |
| Antes de `fusion_lote16_2ep_w4` | 98.6 W | 89.2 a 99.5 W | 95.7 W |

## Script y configuración

```
.venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_lote16_2ep
```

- **Entrenamiento:**
  - YOLO26s desde `yolo26s.pt`, con `seed=0`, `deterministic=True`, imagen de 640, `hsv_h=hsv_s=hsv_v=0` y
    `cache=False` (las imágenes se leen del disco por lotes).
  - El resto, con los valores por omisión de Ultralytics 8.4.194.
- **Configuración:** cada corrida de `configs/fase5.yaml` toma `base` y cambia solo lo suyo. Lo de `ultralytics` va
  tal cual a `model.train()`.
- **Cuarto canal:**
  - `inicio_cuarto_canal: azar` deja la primera capa como la deja Ultralytics: los 3 canales de color con los pesos
    preentrenados y el cuarto al azar (`DetectionModel.load`).
  - `promedio` pone en el cuarto canal el promedio de los 3 de color, antes de crear la EMA y el optimizador.
  - El script lo comprueba al empezar.
- **Salidas en `runs/fase5/<corrida>/`, además de lo de Ultralytics:**
  - `monitor.csv`: nvidia-smi y la RAM, cada segundo;
  - `epocas.csv`: tiempo de entrenamiento y de validación, y memoria máxima de PyTorch, por época;
  - `resumen.json`: potencia, optimizador, primera capa, memoria, tiempos y métricas de validación.
- **Bitácora:** una fila por corrida, también si falla.

Comprobación de la primera capa con `azar`:
- forma 32 × 4 × 3 × 3;
- los 3 canales de color, iguales a los de `yolo26s.pt`;
- la EMA, igual al modelo;
- desviación típica de los pesos de color 0.333, y del cuarto canal 0.098.

## Lote: el 16 entra

**"Entra"** quiere decir dos cosas:
- Ultralytics no bajó el lote. Esta versión lo baja sola si se queda sin memoria en la primera época, así que el script
  lo comprueba.
- El pico de memoria dedicada de la GPU (nvidia-smi) no pasó del 95 % de 8 188 MiB. Así se descarta que Windows usara
  memoria compartida del sistema.

Las dos corridas son de 2 épocas, con mosaico (`close_mosaic=0`, ver la nota de abajo).

| Corrida | Procesos de lectura | Lote final | Pico GPU (nvidia-smi) | Máx. reservada por PyTorch | Época 1 | Época 2 | mAP@0.5 val. (época 2) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fusion_lote16_2ep` | 8 (+16 en validación) | 16 | 5 331 MiB (65 %) | 5 164 MiB | 113.0 s | 45.9 s | 0.307 |
| `fusion_lote16_2ep_w4` | 4 (+8 en validación) | 16 | 5 331 MiB (65 %) | 5 164 MiB | 76.3 s | 44.1 s | 0.293 |

- **El lote 16 entra con margen**, unos 2.8 GB libres, así que es el de los tres modelos. El lote 8 no se corrió.
- **La época 2 es la representativa:** 40 a 41 s de entrenamiento (203 lotes) y 4 s de validación (442 imágenes).
  - La época 1 tarda más porque arrancan los procesos de lectura: con 8 procesos, solo la primera validación tardó 46 s.
- **Nota sobre el mosaico:**
  - Con `close_mosaic=10` por omisión, Ultralytics quita el mosaico en las 10 últimas épocas. En una corrida de 10
    épocas o menos, lo quita desde la primera.
  - Por eso la prueba del lote se hizo con mosaico (`close_mosaic=0`), como las 90 primeras épocas de un entrenamiento
    de 100. Con mosaico hay más personas por imagen, así que la memoria que mide es la del caso más exigente.

## Optimizador y tasa de aprendizaje

**`args.yaml` no guarda la elección.** Guarda lo pedido: `optimizer: auto`, `lr0: 0.01` y `momentum: 0.937`, porque se
escribe al crear el entrenador, antes de elegir el optimizador. La elección aparece en el registro de Ultralytics, en
`train_args` de `weights/last.pt` y en el optimizador mismo:

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

## Tiempo por época (provisional)

**Fusión, con mosaico:** unos 45 s por época (44 a 46 s), con el límite de unos 70 W que hubo al entrenar.

**Estimación aproximada para 100 épocas de la fusión:** 100 × 45 s ≈ 75 min. Hay que sumar:
- el arranque (la primera época tarda de 30 a 70 s más);
- unos 7 s de validación final.

Falta medir dos cosas, pendientes de la decisión de abajo:
- las épocas sin mosaico, de la corrida de 10 épocas;
- los modelos RGB y térmico (`rgb_tiempo_3ep` y `termico_tiempo_3ep`).

## Potencia y RAM durante el entrenamiento

**Potencia.** Durante el entrenamiento, el límite aplicado de la GPU quedó en unos 70 W:

| Corrida | Límite aplicado (mediana, con la GPU al 50 % o más) | Percentiles 10 a 90 | Consumo (mediana) | Uso de la GPU (mediana) |
|---|---:|---:|---:|---:|
| `fusion_lote16_2ep` (8 procesos) | 70.0 W | 70.0 a 70.1 W | 68.5 W | 95.5 % |
| `fusion_lote16_2ep_w4` (4 procesos) | 71.6 W | 70.0 a 74.9 W | 70.0 W | 93.0 % |

- **El límite baja en los primeros segundos de la corrida,** mientras arrancan los procesos de lectura y antes de que la
  GPU se cargue:
  - con 8 procesos: 96, 90, 77, 70 y 70 W en las primeras 5 lecturas;
  - con 4: 89, 88, 84, 75 y 71 W.
- **Con 4 procesos de lectura en vez de 8 no mejora.**
- **Prueba sin entrenar** (40 s de multiplicaciones en la GPU, y entre los 15 y los 35 s, 12 procesos que ocupan la
  CPU): el límite fue de 98 W con la GPU sola y de 89 W con la CPU también ocupada.
  - La carga de la CPU baja el límite, pero esos procesos no llegan a 70 W.
  - Los procesos de lectura de Ultralytics, que decodifican TIFF y transforman las imágenes, cargan la CPU bastante más.
- **En resumen:** la regla de CLAUDE.md (90 W o más bajo carga) se cumple con la GPU sola, pero no con la carga real
  del entrenamiento. El consumo va pegado al límite, así que la GPU entrena limitada por potencia.
  - Esto cambia la velocidad, no lo que aprende el modelo.

**RAM.**
- **Con 8 procesos de lectura** la RAM llegó al 99.9 % (15 978 MiB) y se mantuvo cerca del 98 % casi toda la corrida.
- **Con 4 llegó al 99.3 %** (mediana 14.9 GB).
- **Por qué se llena:**
  - Ultralytics abre el doble de procesos para la validación: 8 + 16 o 4 + 8, de unos 700 MB cada uno en Windows.
  - En reposo ya había 6.2 GB ocupados por otras aplicaciones: Chrome, VS Code, ChatGPT, Roblox y otras.
- **Velocidad:** pasar de 8 a 4 procesos no cambió la época 2 (46 → 44 s) y acortó la primera (113 → 76 s). El uso de
  la GPU siguió por encima del 90 %.

**Variación entre corridas.** Cambiar el número de procesos cambia el reparto de las semillas del aumento de datos. Con
todo lo demás igual, el mAP@0.5 de validación de la época 2 pasó de 0.307 a 0.293. Da una idea de la variación entre
corridas a 2 épocas. En la comparación del cuarto canal, (a) y (b) usan los mismos procesos de lectura.

## Pendiente

1. **Potencia:** decidir si se sigue con unos 70 W bajo la carga real del entrenamiento.
2. **Procesos de lectura y RAM:** cuántos se usan en todas las corridas (8 por omisión, o 4), y si se cierran otras
   aplicaciones al entrenar.
3. **Después:**
   - la comparación del cuarto canal (`fusion_azar_10ep` y `fusion_promedio_10ep`), con la regla de CLAUDE.md;
   - el tiempo de los modelos RGB y térmico;
   - la estimación de los tres entrenamientos de 100 épocas.

## Cambios en el código

- `scripts/entrenar.py` (nuevo):
  - comprueba la potencia;
  - entrena con el `DetectionTrainer` de Ultralytics, con el inicio del cuarto canal como opción;
  - registra la memoria, el tiempo, el optimizador y la primera capa;
  - agrega la fila a la bitácora.
- `configs/fase5.yaml` (nuevo): base y corridas de la fase 5a.
- `CLAUDE.md`: la regla del inicio del cuarto canal, anotada antes de entrenar; el optimizador elegido; el lote 16; el
  límite de potencia bajo la carga real.
- `FASES.md`: el mensaje 5a usado.
