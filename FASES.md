# Fases del trabajo

Cada fase tiene un mensaje para pegar en Claude Code y una lista de lo que tú revisas antes de pasar a la siguiente.
Las fases siguen el flujo de trabajo de la Figura 1 (pasos 1 a 7).

---

## Fase 0. Preparar el entorno

**Antes (tú):** actualiza el controlador NVIDIA desde la aplicación NVIDIA o nvidia.com y reinicia la laptop.

**Mensaje:**

> Fase 0. Lee CLAUDE.md.
>
> 1. Crea la estructura de carpetas del repositorio que describe CLAUDE.md.
> 2. Crea un entorno virtual `.venv` con Python 3.11 o 3.12.
> 3. Instala PyTorch con soporte para GPU NVIDIA (usa el comando oficial de pytorch.org para Windows y CUDA) y luego
>    `ultralytics`, `opencv-python`, `pycocotools`, `statsmodels`, `scipy`, `pandas`, `tifffile` y `matplotlib`.
> 4. Verifica que `torch.cuda.is_available()` sea `True` y que se vea la RTX 4070. Si da `False`, detente y dime por qué.
> 5. Carga `yolo26s.pt` y haz una predicción de prueba con una imagen térmica cualquiera de WiSARD.
> 6. Guarda en `requirements.txt` las versiones exactas y en `reports/entorno.md` el sistema operativo y las
>    versiones de Python, PyTorch, CUDA y Ultralytics.

**Revisa:**
- `torch.cuda.is_available()` dio `True`.
- `reports/entorno.md` existe. Esos datos van a la Tabla 7 del reporte.

---

## Fase 1. Pares RGB-térmicos (paso 1 del flujo)

**Mensaje:**

> Fase 1. Reconstruye los pares RGB-térmicos de WiSARD con las reglas de CLAUDE.md. Puedes reutilizar
> `emparejamiento.py` y `analisis_pares.py` del proyecto anterior.
>
> 1. Genera `data/pares.csv` con una fila por par: vuelo, sitio, posición, ruta RGB, ruta térmica, cajas RGB,
>    cajas térmicas, si ambas imágenes están anotadas y si el par está excluido (tramo de Baker).
> 2. Comprueba que salgan 14 839 pares, 5 739 con ambas imágenes anotadas y 5 610 tras la exclusión.
>    Si no coinciden, detente y muéstrame la diferencia.
> 3. Genera `reports/tabla_pares_por_vuelo.csv` con, por vuelo: pares anotados y pares con persona solo en la térmica.
> 4. Escribe `reports/fase1.md` con el resumen.

**Revisa:**
- Los totales coinciden (5 610 pares). La tabla por vuelo es la Tabla 9 del reporte.

---

## Fase 2. Alineación (paso 2 del flujo)

**Mensaje:**

> Fase 2. Alinea la imagen RGB con la térmica en cada vuelo.
>
> 1. Haz una herramienta con OpenCV, `scripts/marcar_puntos.py`, que me muestre lado a lado una RGB y su térmica de un
>    vuelo, y me deje marcar al menos 6 puntos correspondientes (una roca, un tronco, una esquina) con clics.
>    Que pueda deshacer el último punto y guardar.
> 2. Con esos puntos, calcula una homografía por vuelo (`cv2.findHomography` con RANSAC) y guárdala en `configs/`.
>    Usa como punto de partida la franja de CLAUDE.md (x de 0.18 a 0.84, y de 0.06 a 0.98). Carnation 0023/0024 es
>    al revés: avísame qué ves ahí.
> 3. Escribe `scripts/alinear.py`, que lleve cada RGB a 640 × 512 en la geometría de la térmica y guarde, por cada par:
>    la RGB alineada (PNG), la térmica (PNG) y la imagen de 4 canales (TIFF, uint8). Procesa por partes.
> 4. Para verificar, guarda en `reports/alineacion/` 10 superposiciones por vuelo y calcula la distancia promedio en
>    píxeles entre los centros de las cajas RGB transformadas y las térmicas.

**Revisa:**
- En las superposiciones, las personas y los bordes coinciden.
- La distancia promedio es de pocos píxeles. Anota el valor: va al reporte.

---

## Fase 3. Partición y anotación de oclusión (paso 3 del flujo)

**Antes (tú):** decide con tu asesora qué vuelos van a cada partición. Propuesta: entrenamiento Baker 1, Carnation 0023,
MtErie 0003, FHL 0134 y FHL 0401; validación MtErie 0005 y 0007; prueba FHL 0405.

**Mensaje 3a:**

> Fase 3a. La partición es: [pega aquí la partición acordada].
>
> 1. Guarda la partición en `configs/particion.yaml` y genera las listas de entrenamiento, validación y prueba.
> 2. Crea los yaml de Ultralytics para los tres modelos (`fusion.yaml` con `channels: 4`, `rgb.yaml`, `termico.yaml`),
>    todos con las etiquetas térmicas.
> 3. Cuenta cuántas personas hay en la partición de prueba: eso es lo que voy a anotar.

**Mensaje 3b:**

> Fase 3b. Prepara la anotación de oclusión de la partición de prueba.
>
> 1. Escribe `docs/reglas_anotacion.md` con estas reglas:
>    - Caja visible: el rectángulo más ajustado a la parte del cuerpo que se ve.
>    - Caja completa: el cuerpo entero estimado según la postura (de pie, sentado o acostado), incluida la parte tapada.
>    - Si la persona no se ve en esa imagen, no hay caja visible y λ = 1.
>    - Si la persona está cortada por el borde de la imagen, se marca "fuera de cuadro" y no cuenta como oclusión.
>    - Las sombras no son parte de la persona.
> 2. Haz una herramienta, `scripts/anotar_oclusion.py`, que me muestre cada persona de la prueba con su RGB alineada y su
>    térmica lado a lado, ampliadas alrededor de la caja térmica, y me deje dibujar la caja completa y la visible en cada
>    imagen, marcar "fuera de cuadro" y avanzar. Que guarde el avance en `data/oclusion.csv` y permita retomar.
> 3. Prepara además una muestra al azar del 15 % de esas personas para un segundo anotador, en un archivo aparte.

**Revisa:**
- Anota tú todas las personas de la prueba. Luego otra persona anota la muestra sin ver tus cajas.

---

## Fase 4. Niveles de oclusión (paso 4 del flujo)

**Mensaje:**

> Fase 4.
>
> 1. Calcula λ en RGB y en térmica para cada persona anotada y asigna el nivel con λ RGB (baja, moderada o severa).
>    Marca también oclusión blanda (visible en al menos una imagen) o dura (tapada en ambas).
> 2. Calcula el kappa de Cohen entre los dos anotadores sobre el nivel asignado.
> 3. Genera `reports/tabla_niveles.csv` con personas por nivel y `reports/fase4.md` con el resumen y el kappa.

**Revisa:**
- Cuántas personas quedaron en el nivel severo. Si son muy pocas, avísame antes de entrenar.

---

## Fase 5. Entrenamiento (pasos 5 y 6 del flujo)

**Mensaje 5a (prueba corta):**

> Fase 5a.
>
> 1. Escribe `scripts/entrenar.py`, que lea un yaml de `configs/`, entrene YOLO26s desde `yolo26s.pt` y registre la
>    corrida en la bitácora.
> 2. Con el modelo de fusión, entrena 2 épocas con lote 16 y mide la memoria de la GPU y el tiempo por época.
>    Si no entra, prueba lote 8.
> 3. Compara dos formas de iniciar el cuarto canal: al azar (lo que hace Ultralytics) y con el promedio de los pesos
>    de color. Explícame la diferencia.
> 4. Dime qué optimizador y tasa de aprendizaje eligió Ultralytics (están en `args.yaml`) y cuánto tardaría un
>    entrenamiento de 100 épocas.

**Mensaje 5b (entrenamientos completos):**

> Fase 5b. Con el lote y la inicialización acordados, dame los comandos para entrenar, uno tras otro, los tres modelos:
> fusión temprana, solo RGB y solo térmica, 100 épocas, `seed=0`, misma configuración.

**Revisa:**
- Las curvas de entrenamiento de los tres modelos bajan y se estabilizan.
- La bitácora tiene las tres corridas.

---

## Fase 6. Evaluación por nivel (paso 7 del flujo)

**Mensaje:**

> Fase 6.
>
> 1. Escribe `scripts/evaluar.py`: para cada modelo, predice sobre la partición de prueba y calcula recall, precisión
>    (umbral de confianza 0.5), F2 y mAP@0.5 con pycocotools, global y por nivel de oclusión. Al evaluar un nivel, las
>    personas de los otros niveles van como `iscrowd=1`.
> 2. Para cada nivel, aplica McNemar entre los modelos sobre si cada persona fue detectada, con corrección de Bonferroni.
> 3. Genera `reports/resultados.csv`, `reports/mcnemar.csv` y un gráfico de recall por nivel con una línea por modelo.

**Revisa:**
- El recall baja al subir la oclusión (es lo esperado).
- Tráeme `resultados.csv`, `mcnemar.csv` y el gráfico para redactar Resultados.
