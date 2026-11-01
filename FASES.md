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
> 2. Comprueba que salgan 14 839 pares, 5 739 con ambas imágenes anotadas y 5 590 tras la exclusión.
>    Si no coinciden, detente y muéstrame la diferencia.
> 3. Genera `reports/tabla_pares_por_vuelo.csv` con, por vuelo: pares anotados y pares con persona solo en la térmica.
> 4. Escribe `reports/fase1.md` con el resumen.

**Revisa:**
- Los totales coinciden (5 590 pares). La tabla por vuelo es la Tabla 9 del reporte.

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

**Decidido con la asesora (1 de noviembre de 2026):**

| Partición | Vuelos | Pares | Personas |
|---|---|---:|---:|
| Entrenamiento | Baker, MtErie 0003, MtErie 0005 y FHL 0401 | 3 247 | 9 340 |
| Validación | FHL 0134 y MtErie 0007 | 442 | 500 |
| Prueba | FHL 0405 | 928 | 1 501 |

Carnation 0023/0024 salió entero en la fase 2. La oclusión se anota en 1 de cada 3 fotogramas de la prueba: 310
fotogramas y 498 personas, que cubren los 18 episodios. Los conteos están en `reports/conteo_particion.md`.

**Mensaje 3a (usado):**

> 3a. Partición: entrenamiento Baker, MtErie 0003, MtErie 0005 y FHL 0401; validación FHL 0134 y MtErie 0007; prueba
> FHL 0405. Guárdala en configs/particion.yaml. Elimina las 46 cajas duplicadas y anota cuántas eran por vuelo. Crea
> fusion.yaml (4 canales), rgb.yaml y termico.yaml (gris repetido en 3 canales), todos con las etiquetas térmicas. No
> entrenes nada.

**Mensaje 3b (usado):**

> 3b. Anotación de oclusión en FHL 0405, fotogramas con posición múltiplo de 3 (498 personas):
>
> 1. Escribe `docs/reglas_anotacion.md`:
>    - Caja completa (una por persona, la misma para las dos imágenes): el cuerpo entero estimado según la postura (de
>      pie, sentado o acostado), incluida la parte tapada.
>    - Caja visible RGB y caja visible térmica: el rectángulo más ajustado a lo que se ve del cuerpo en cada imagen. Si
>      no se ve nada, no hay caja y λ = 1.
>    - λ = 1 − área (visible ∩ completa) / área completa, en cada imagen.
>    - "Fuera de cuadro" si el cuerpo está cortado por el borde; no cuenta como oclusión.
>    - "No es persona" si la caja térmica de WiSARD está mal; se reporta aparte.
>    - Las sombras no son parte de la persona.
> 2. Haz `scripts/anotar_oclusion.py`:
>    - Muestra cada persona con la RGB alineada y la térmica lado a lado, ampliadas alrededor de la caja térmica.
>    - Precarga la caja visible térmica con la etiqueta de WiSARD, y la visible RGB con la caja RGB más cercana a 3
>      alturas o menos, si hay.
>    - Yo dibujo la caja completa y corrijo las visibles.
>    - Teclas para deshacer, "no visible", "fuera de cuadro", "no es persona", avanzar y retroceder.
>    - Guarda en `data/oclusion.csv` después de cada persona y permite retomar.
>    - La ventana tiene que entrar en mi pantalla (escala de Windows al 125 %).
> 3. Prepara una muestra al azar del 15 % de esas personas (seed=0) para un segundo anotador, en un archivo aparte, con
>    la herramienta en modo "sin precargar ni mostrar mis cajas".
> 4. Actualiza CLAUDE.md y FASES.md con estas decisiones.
> 5. Prueba la herramienta con 3 personas simuladas, haz commit y push, y ábreme la herramienta.

**Cómo se usa:**

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo
```

El primer comando es para ti; el segundo, para el segundo anotador.

**Revisa:**
- Anota tú las 498 personas: avanzas con espacio y la herramienta guarda sola.
- Luego otra persona anota las 75 de la muestra con `--segundo`, sin ver tus cajas.

---

## Fase 4. Niveles de oclusión (paso 4 del flujo)

**Mensaje:**

> Fase 4.
>
> 1. Calcula λ en RGB y en térmica para cada persona anotada (`data/oclusion.csv`; una caja completa compartida y una
>    visible por imagen) y asigna el nivel con λ RGB (baja, moderada o severa). Marca también oclusión blanda (visible
>    en al menos una imagen) o dura (tapada en ambas). Cuenta aparte las "fuera de cuadro" y las "no es persona".
> 2. Calcula el kappa de Cohen entre los dos anotadores sobre el nivel asignado, con las 75 personas de la muestra
>    (`data/oclusion_segundo.csv`).
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
> 3. Calcula intervalos de confianza con bootstrap por episodio. Se remuestrean episodios completos (tramos seguidos
>    con persona), no fotogramas, con seed=0. Hazlo para las métricas de cada modelo y para las diferencias entre
>    modelos, por nivel.
> 4. Genera `reports/resultados.csv`, `reports/mcnemar.csv` y un gráfico de recall por nivel con una línea por modelo.

**Revisa:**
- El recall baja al subir la oclusión (es lo esperado).
- Tráeme `resultados.csv`, `mcnemar.csv` y el gráfico para redactar Resultados.
