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

**Mensaje 3c (usado, 1 de noviembre de 2026):**

> Calcula un λ RGB automático para las 1 501 personas de FHL 0405: λ = 1 − área(caja RGB más cercana a 3 alturas o
> menos) / área(caja térmica), recortado entre 0 y 1; si no hay caja RGB cerca, λ = 1. Asigna el nivel (baja,
> moderada, severa) y guarda todo en data/oclusion_auto.csv.
> Yo anoto a mano solo las 75 personas de la muestra con la herramienta, en modo primer anotador y solo esas 75.
> Conserva la persona 1 que ya anoté. Ábreme la herramienta así.
> Cuando termine, compara el automático contra el manual en esas 75: kappa de Cohen sobre el nivel, matriz de confusión
> y diferencia media de λ. Si el kappa es de 0.61 o más, usamos el automático; si no, volvemos a la anotación manual.
> Actualiza CLAUDE.md con este plan y haz commit y push.

```
.venv\Scripts\python.exe scripts\oclusion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --muestra
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
```

**Revisa:**
- Anota las 75 personas de la muestra con `--muestra`: avanzas con espacio y la herramienta guarda sola.
- La comparación (antes `--comparar`) ahora es de dos niveles, "se ve o no en la RGB", con
  `scripts/fase4_validacion_auto.py` (decidido el 1 de noviembre de 2026). Con tu anotación con cajas dio 0.940.
  Desde el 1 de noviembre de 2026 decide el kappa del automático contra tu modo simple de la ronda 2 (regla aclarada):
  con 0.61 o más se usa el automático; si no, el nivel binario de las 498 se anota a mano en modo simple. El 0.940
  queda como resultado de la primera anotación (`reports/fase4_validacion_auto.md`).
- Segundo anotador: modo simple (`--segundo-simple`), una tecla por persona.
  - Ronda 1 (regla ambigua): kappa 0.507 entre anotadores, no se acepta tal cual.
  - Ronda 2 (regla aclarada: "se ve" con el brillo normal, sin realce; si dudas, "no se ve"): los dos anotadores
    responden las 75 completas en modo simple (`--primero-simple` y `--segundo-simple`), en
    `data/oclusion_primero_simple_ronda2.csv` y `data/oclusion_segundo_simple_ronda2.csv`. Cuando estén las dos,
    `fase4_validacion_auto.py --partes entre_anotadores --ronda 2`: el primero contra el segundo (decide), el
    automático contra el primero en modo simple y los cambios del primero respecto de sus cajas.
  - Resultado de la ronda 2: concordancia 0.623 (se acepta; el IC va como limitación) y automático contra el primero
    0.427, así que no se usa el automático.
- Nivel a mano de las 498: tus 75 de la ronda 2 más las 423 que faltan, con `--primero-simple-resto` (guarda en
  `data/oclusion_primero_simple_resto.csv` y retoma si cierras). Las 10 "no es persona" de los dos están en
  `configs/cajas_dudosas.yaml`: no se tocan las etiquetas y quedan sin nivel.
- Después del cierre (1 de noviembre de 2026):
  - las 66 "no es persona" van todas a `configs/cajas_dudosas.yaml`, que genera `scripts/fase4_cajas_dudosas.py`
    siguiendo cada caja por los fotogramas no anotados;
  - la escena en sombra (468 a 588) se reanota entera con `--primero-simple-reanotar escena_sombra`.

---

## Fase 4. Niveles de oclusión (paso 4 del flujo)

**Lo que se hizo (cerrada el 1 de noviembre de 2026).** El nivel es de **dos clases**, sin λ:
- **Severa:** la persona no se ve en la RGB.
- **Baja:** se ve en la RGB.
- Se dejó de usar λ y los tres niveles porque en la muestra no hubo ninguna moderada (0 de 68).

Cómo se obtuvo:
- **A mano:** el primer anotador lo anota en modo simple, con la regla aclarada, para las 498 personas de los 310
  fotogramas anotados.
- **El automático no se usa:** su kappa contra el primero en la ronda 2 fue 0.427, menor que 0.61.
- **Concordancia entre anotadores** (ronda 2, 75 personas): kappa 0.623 (IC 95 % 0.400 a 0.846). Se acepta, y el IC va
  como limitación.
- **Escena en sombra:** los fotogramas 468 a 588 se reanotaron enteros.

Resultados:
- **Nivel final** (`data/oclusion_nivel.csv`): baja 184, severa 267 y 47 sin nivel ("no es persona", cajas dudosas).
- **Cajas dudosas** para la fase 6 (`configs/cajas_dudosas.yaml`): 47 anotadas + 84 seguidas por los fotogramas no
  anotados = 131 de 1 501.
- Detalle en `reports/fase4_validacion_auto.md`.

```
.venv\Scripts\python.exe scripts\fase4_nivel.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\fase4_cajas_dudosas.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

**Revisa:**
- Cuántas personas quedaron en el nivel severo: 267 de las 451 con nivel.

---

## Fase 5. Entrenamiento (pasos 5 y 6 del flujo)

**Mensaje 5a (usado, 1 de noviembre de 2026):**

> Fase 5a. Antes de entrenar, verifica con nvidia-smi que el límite bajo carga sea de al menos 90 W.
>
> 1. Escribe `scripts/entrenar.py`: lee un yaml de `configs/`, entrena YOLO26s desde `yolo26s.pt` con seed=0, imagen
>    de 640, `hsv_h=hsv_s=hsv_v=0`, y registra cada corrida en la bitácora.
> 2. Con el modelo de fusión, entrena 2 épocas con lote 16 y mide la memoria máxima de la GPU y el tiempo por época.
>    Si no entra, prueba lote 8. El lote que entre se usa para los tres modelos.
> 3. Dime qué optimizador y tasa de aprendizaje eligió Ultralytics (están en `args.yaml`) y cuánto tardaría cada
>    entrenamiento de 100 épocas.
> 4. Inicio del cuarto canal. Entrena la fusión 10 épocas de dos formas, con todo lo demás igual: (a) cuarto canal al
>    azar, como hace Ultralytics; (b) cuarto canal con el promedio de los pesos de color de la primera capa. Regla,
>    fijada antes de ver el resultado: se elige la que tenga mayor mAP@0.5 en validación; si la diferencia es menor que
>    0.01, se elige (b), porque así la térmica también arranca con pesos preentrenados. Anota la regla en CLAUDE.md
>    antes de entrenar.
> 5. Escribe `reports/fase5a.md` con todo, haz commit y push, y detente. No entrenes las 100 épocas todavía.

```
.venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_lote16_2ep
```

Las corridas están en `configs/fase5.yaml` (`corridas`), y el resultado en `reports/fase5a.md`.

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
>    (umbral de confianza 0.5), F2 y mAP@0.5 con pycocotools.
>    - Métricas globales sobre los 928 fotogramas de prueba y también sobre los 310 anotados.
>    - Métricas por nivel de oclusión sobre los 310 anotados. Al evaluar un nivel, las personas de los otros niveles van
>      como `iscrowd=1`.
>    - Todas, con y sin las cajas dudosas de `configs/cajas_dudosas.yaml` (las anotadas y las seguidas por los
>      fotogramas no anotados). "Sin ellas" = esas cajas van como `iscrowd=1`. Las etiquetas no se tocan.
> 2. Para cada nivel, aplica McNemar entre los modelos sobre si cada persona fue detectada, con corrección de Bonferroni.
> 3. Calcula intervalos de confianza con bootstrap por episodio. Se remuestrean episodios completos (tramos seguidos
>    con persona), no fotogramas, con seed=0. Hazlo para las métricas de cada modelo y para las diferencias entre
>    modelos, por nivel.
> 4. Genera `reports/resultados.csv`, `reports/mcnemar.csv` y un gráfico de recall por nivel con una línea por modelo.

**Revisa:**
- El recall baja al subir la oclusión (es lo esperado).
- Tráeme `resultados.csv`, `mcnemar.csv` y el gráfico para redactar Resultados.
