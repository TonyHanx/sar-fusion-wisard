# Fase 3: partición y anotación de oclusión

Fecha: 2026-11-01. No se entrenó nada.

Para regenerar:

```
.venv\Scripts\python.exe scripts\fase3_particion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --preparar
.venv\Scripts\python.exe scripts\probar_anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

## 3a. Partición y datasets

### Partición por vuelo

Está en `configs/particion.yaml`. La tabla completa está en `reports/fase3_particion.csv`.

| Partición | Vuelo | Pares | Con persona | Sin persona (fondo) | Personas | Pares "solo térmica" | Episodios (si los excluidos no cortan) |
|---|---|---:|---:|---:|---:|---:|---:|
| Entrenamiento | MtErie 0003 | 236 | 233 | 3 | 905 | 0 | 9 (2) |
| | MtErie 0005 | 257 | 257 | 0 | 494 | 8 | 6 (1) |
| | FHL 0401 | 783 | 683 | 100 | 2 755 | 0 | 20 (5) |
| | Baker | 1 971 | 1 888 | 83 | 5 186 | 1 | 9 (3) |
| | **Total** | **3 247** | **3 061** | **186** | **9 340** | **9** | **44 (11)** |
| Validación | MtErie 0007 | 169 | 169 | 0 | 289 | 7 | 2 (1) |
| | FHL 0134 | 273 | 136 | 137 | 211 | 61 | 9 (9) |
| | **Total** | **442** | **305** | **137** | **500** | **68** | **11 (10)** |
| Prueba | FHL 0405 | **928** | 779 | 149 | **1 501** | 394 | 18 (13) |

- **Personas:** cajas térmicas, contadas por fotograma.
- **Pares sin persona:** entran como fondo, es decir, imágenes sin cajas.
- **"Solo térmica":** casi todos los pares "solo térmica" están en la prueba (394 de 471).
- **Lo que no tiene el entrenamiento:** casi no tiene personas que falten en la RGB (9 pares "solo térmica").

### Cajas repetidas (46)

Son líneas idénticas dentro de un mismo `.txt` de WiSARD.

- Las etiquetas de los pares finales se escriben sin ellas en `data/etiquetas/{rgb,termica}/`; el dataset original no
  se toca. Se queda la primera línea de cada grupo repetido.
- Los pares excluidos no entran en ningún dataset.
- Detalle en `reports/fase3_cajas_repetidas.csv`.

| Vuelo | Modalidad | Pares | Cajas repetidas | Pares con repetidas |
|---|---|---|---:|---:|
| Baker | RGB | finales | 27 | 26 |
| FHL 0401 | RGB | finales | 4 | 4 |
| FHL 0401 | RGB | excluidos | 1 | 1 |
| FHL 0401 | térmica | excluidos | 14 | 5 |
| **Total** | | | **46** | |

- **Etiquetas de los modelos:** no hay ninguna térmica repetida en pares finales, así que las etiquetas que reciben
  los modelos son las mismas de WiSARD.
- **Etiquetas RGB:** las 31 repetidas en pares finales solo afectaban a las etiquetas RGB. Hoy esas etiquetas solo se
  usan para precargar la visible RGB.

### Datasets de Ultralytics

- `data/datasets/{fusion,rgb,termico}/images/{train,val,test}/` tiene enlaces duros a `data/alineados/` (no ocupan más
  disco). `labels/` tiene las etiquetas térmicas sin repetidas, las mismas para los tres.
- Yaml generados (con `path` absoluto):
  - `configs/fusion.yaml`: `channels: 4`, TIFF.
  - `configs/rgb.yaml`: `channels: 3`, PNG.
  - `configs/termico.yaml`: `channels: 3`, el PNG gris de 1 canal. Ultralytics lo lee con `IMREAD_COLOR` y repite el
    gris en los 3 canales.

**Verificación con Ultralytics** (`check_det_dataset` y `YOLODataset`, como en el entrenamiento; detalle en
`reports/fase3_verificacion_datasets.csv`):

- En los tres modelos y las tres particiones se leen todas las imágenes, sin etiquetas corruptas ni avisos.
  - Instancias: 9 340, 500 y 1 501.
  - Imágenes de fondo: 186, 137 y 149.
- Tensores de 3 imágenes al azar de la prueba (seed=0), comparados con los PNG: diferencia 0 en los tres modelos.
  - **fusion:** forma (4, 640, 640), en orden R, G, B, T.
  - **rgb:** forma (3, 640, 640), en orden R, G, B.
  - **termico:** forma (3, 640, 640), con los 3 canales iguales al gris.

**Para la Fase 5 (aumento de color):** Ultralytics solo aplica el aumento HSV (`hsv_h`, `hsv_s`, `hsv_v`) a imágenes
de 3 canales (`RandomHSV`: `if img.shape[-1] != 3: return`).

- **rgb:** recibe el aumento completo.
- **termico:** solo le cambia el brillo, porque con los 3 canales iguales la saturación es 0.
- **fusion:** no recibe ninguno.

Así, el modelo de fusión entrena con menos aumento que los otros dos. Hay que decidirlo antes de entrenar:
desactivarlo en los tres (`hsv_h=hsv_s=hsv_v=0`) o dejarlo y anotarlo como limitación.

## 3b. Anotación de oclusión

### Personas a anotar

FHL 0405, fotogramas con posición múltiplo de 3: 310 fotogramas y **498 personas**. La lista fija está en
`data/oclusion_personas.csv`.

| | Personas |
|---|---:|
| Con visible RGB precargada (caja RGB a 3 alturas o menos) | 175 |
| Sin caja RGB cerca (la visible RGB empieza pendiente) | 323 |
| En pares "solo térmica" | 278 |
| **Muestra del segundo anotador** (15 %, seed=0) | **75** |
| De la muestra: en pares "solo térmica" | 42 |
| De la muestra: con precarga RGB | 29 |

- La muestra cae en 66 fotogramas y está en `data/oclusion_muestra_segundo.csv`.
- Las personas son pequeñas: el alto de la caja térmica tiene mediana 14 px (p10 10 px, p90 22 px).

### Herramienta

- **Archivos:** `scripts/anotar_oclusion.py`; las reglas y las teclas están en `docs/reglas_anotacion.md`.
- **Ventana:** se ajusta al área de trabajo, consciente del DPI. En esta pantalla (1920 × 1140 sin la barra de
  tareas, escala 125 %) mide 1 800 × 1 085, con dos paneles de 895 × 821.
- **Capturas:** `reports/oclusion/herramienta_primero.jpg` y `herramienta_segundo.jpg`.

**Prueba con 3 personas simuladas** (`scripts/probar_anotar_oclusion.py`). Las anotaciones van a una carpeta temporal,
así que no se toca `data/oclusion.csv`. Las 32 comprobaciones pasaron:

- **Persona A (con precarga RGB):**
  - La precarga es correcta.
  - La completa se dibujó en la térmica y la herramienta pasó sola a visible.
  - La visible RGB se redibujó con el botón derecho.
  - La visible térmica se redibujó y se deshizo.
  - El zoom con la rueda mantiene el punto bajo el cursor.
  - λ coincide con un cálculo aparte (0.787 y 0.313).
- **Persona B (sin caja RGB cerca):**
  - La visible RGB empieza pendiente.
  - Con la completa sola no queda terminada.
  - "No visible" en la RGB da λ = 1, y se puede quitar y volver a poner.
- **Persona C:** "no es persona"; "fuera de cuadro" puesto y deshecho; "anterior" vuelve a B con lo anotado.
- **CSV:** se guarda después de cada cambio. Al reabrir se recupera todo y se sigue en la primera persona sin terminar.
- **Modo del segundo anotador:**
  - Trabaja solo con las 75 de la muestra.
  - No hay nada precargado ni dibujado, aunque exista el archivo del primero.
  - Guarda en su propio archivo y no cambia el del primero.

### Riesgo: desplazamiento entre la RGB y la térmica con una sola caja completa

En FHL 0405, la caja RGB precargada y la caja térmica de la misma persona no están centradas en el mismo punto. El
centro se corre:

- una mediana de **4.4 px** (0.27 alturas de la caja);
- en el p90, **10.6 px** (0.65 alturas).

Es el error de alineación de este vuelo (el más alto en la validación manual: 13.2 px), sumado a cómo se dibujaron las
cajas. Para personas de 14 px de alto, el corrimiento es grande.

Con una sola completa para las dos imágenes, la parte de la persona RGB que cae fuera de la completa cuenta como tapada.

**Cuánto sube λ RGB** (estimación aproximada con las cajas de WiSARD de las 175 personas con precarga):

- Para la estimación, la completa es la caja térmica y la visible RGB es la caja RGB.
- En el 83 % de ellas, más del 10 % de la caja RGB queda fuera de la térmica.
- λ RGB tiene mediana 0.44. Si se centra la caja RGB sobre la térmica, la mediana baja a 0.24.
- El desplazamiento suma una mediana de **+0.17 a λ RGB** (p90 +0.50).
- **78 de las 175 personas (45 %) subirían de nivel.**

| Nivel con la caja RGB centrada | Mismo nivel | Sube a moderada | Sube a severa |
|---|---:|---:|---:|
| Baja (124) | 61 | 51 | 12 |
| Moderada (50) | 35 | | 15 |
| Severa (1) | 1 | | |

Es una estimación aproximada: con las cajas reales, el anotador puede compensar en parte al dibujar la completa. La
herramienta avisa cuando una visible se sale de la completa más de un 10 %, y con la precarga ese aviso aparecerá en la
mayoría de las personas con caja RGB.

**Opciones, para decidir antes de anotar en serio:**

- **(a) Recomendada.** Una completa compartida en tamaño, pero que se pueda mover en cada imagen. Es una sola estimación
  del cuerpo, y λ de cada imagen no mezcla el error de alineación con la oclusión.
- **(b)** Dos completas, una por imagen (la regla anterior de CLAUDE.md).
- **(c)** Dejarla como está y reportar el sesgo como limitación.

### Pendiente para la Fase 6

Los niveles de oclusión solo existirán para las personas de los 310 fotogramas anotados. Hay que decidir si:

- las métricas globales usan los 928 fotogramas de la prueba;
- y las métricas por nivel usan solo los 310 anotados.
