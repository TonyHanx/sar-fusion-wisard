# Estructura del repositorio

Guía para leer y volver a correr el código de la tesis. Dice qué hay en cada carpeta, en qué orden se corren los
scripts, de dónde salen los datos y adónde van los resultados. Las decisiones y las cifras están en `CLAUDE.md`,
`FASES.md` y los reportes de `reports/`. Este archivo solo explica cómo está organizado el código.

```
sar-fusion-wisard/
├── README.md            presentación corta del proyecto
├── ESTRUCTURA.md        este archivo
├── CLAUDE.md            contexto, datos verificados y decisiones fijas
├── FASES.md             qué se pidió en cada fase y qué se revisó
├── requirements.txt     versiones exactas de las librerías
├── configs/             configuración de cada fase, rutas y yaml de los datasets
│   ├── rutas.yaml       dónde están el dataset, data/, reports/, runs/ y la bitácora
│   ├── fase0.yaml ... fase8.yaml, diagnostico.yaml, conteo_particion.yaml, noche.yaml
│   ├── fusion.yaml, rgb.yaml, termico.yaml        datasets de Ultralytics (los genera la fase 3a)
│   ├── particion.yaml   qué vuelo va a entrenamiento, validación y prueba
│   ├── puntos_control/, fase7_puntos_control/      puntos marcados a mano para validar la alineación
│   └── homografias_cajas.yaml, exclusiones_desfase.yaml, cajas_dudosas.yaml, ...   generados por scripts
├── src/                 código del flujo, una carpeta por etapa
│   ├── comun.py         lectura de configuración, semilla, bitácora y utilidades de imagen
│   ├── cajas.py         cajas de personas: leerlas, llevarlas de la RGB a la térmica, centros
│   ├── entorno/         fase 0: versiones y prueba de predicción
│   ├── pares/           fase 1: pares RGB y térmica
│   ├── alineacion/      fase 2: transformación RGB a térmica, desfases e imágenes alineadas
│   ├── particion/       fase 3a: partición por vuelo y datasets de Ultralytics
│   ├── oclusion/        fases 3b y 4 (y C4): anotación, concordancia y nivel de oclusión
│   ├── entrenamiento/   fases 5 y 7: entrenamiento y dropout de modalidad
│   ├── ampliacion/      fase 7 (C0 y C1): datasets ampliados con más térmicas
│   ├── evaluacion/      fases 6, 7 (C4) y 8: métricas, intervalos y McNemar
│   └── utilidades/      copia de salidas livianas de runs/ a reports/
├── experimentos/        scripts exploratorios y de diagnóstico (no producen entradas del flujo)
├── pruebas/             prueba automática de la herramienta de anotación
├── scripts/noche.ps1    corridas de la noche del 3 al 4 de noviembre de 2026
├── docs/                reglas de anotación de oclusión
├── reports/             tablas, figuras, resúmenes de cada fase y bitácora (van a git)
├── data/                datos procesados (fuera de git)
├── runs/                salidas de entrenamiento y predicciones (fuera de git)
└── weights/             pesos preentrenados yolo26s.pt (fuera de git)
```

## Qué es cada cosa

El proyecto busca personas tapadas por vegetación en imágenes de dron. Compara tres detectores iguales que solo
cambian en lo que reciben:

- **fusión temprana**: la imagen RGB (la foto de color normal, con sus canales rojo, verde y azul) y la térmica juntas,
  como una sola imagen de 4 canales;
- **solo RGB**;
- **solo térmica**.

El detector es **YOLO26s** de Ultralytics. YOLO (You Only Look Once) es una familia de detectores de objetos que
encuentran y encuadran objetos en una sola pasada; la "s" es la versión pequeña. Los datos son de **WiSARD**
(Broyles et al., 2022), un conjunto de imágenes visibles y térmicas tomadas desde dron para búsqueda y rescate en zonas
naturales. Los nombres FHL, MtErie, Baker y Carnation son los sitios de vuelo de WiSARD, y el número que sigue (por
ejemplo FHL 0405) identifica el vuelo.

## Carpetas, en el orden del flujo

1. **`configs/`**: todo lo que cambia el resultado (rutas, hiperparámetros, umbrales, listas de exclusiones) está aquí,
   en archivos YAML (un formato de texto para configuración). Ningún script tiene rutas ni hiperparámetros escritos en
   el código: cada uno recibe `--config` con el yaml de su fase y `--rutas configs\rutas.yaml`. Algunos yaml los
   escriben los scripts (lo dice su primera línea) y no se editan a mano.
2. **`src/`**: el flujo, en este orden: `entorno`, `pares`, `alineacion`, `particion`, `oclusion`, `entrenamiento`,
   `ampliacion` y `evaluacion`. `comun.py` y `cajas.py` son funciones que usan varias etapas.
3. **`experimentos/`**: scripts que sirvieron para mirar los datos y tomar decisiones (dónde cortar un vuelo, por qué
   falla la validación). Sus conclusiones quedaron escritas en `configs/` y en los reportes; el flujo no los necesita
   para correr.
4. **`pruebas/`**: `probar_anotar_oclusion.py` simula el ratón y el teclado de la herramienta de anotación y comprueba
   102 casos sin abrir ventanas.
5. **`scripts/noche.ps1`**: un script de PowerShell que encadenó entrenamientos y predicciones una noche, con
   comprobaciones de potencia y de las aplicaciones abiertas. Solo funciona en Windows.
6. **`reports/`**: lo que va a la tesis. Hay un `.md` por fase (`fase1.md` a `fase8.md`, `diagnostico.md`), las tablas
   en CSV (tablas de texto con valores separados por comas), las figuras y `bitacora.csv`, con una fila por cada
   entrenamiento o evaluación.
7. **`data/`, `runs/` y `weights/`**: datos procesados, salidas de entrenamiento y pesos. Son archivos pesados
   (unos 10 GB en `data/` y 1.5 GB en `runs/`) y no van a git (ver "De dónde salen los datos").
8. **`docs/reglas_anotacion.md`**: las reglas que siguieron los anotadores de oclusión.

## Cómo correr el código

Todo se corre **desde la raíz del repositorio, como módulo** (`-m src.etapa.script`), en PowerShell de Windows:

```
.venv\Scripts\python.exe -m src.pares.emparejar --config configs\fase1.yaml --rutas configs\rutas.yaml
```

Correrlo como archivo (`python src\pares\emparejar.py`) falla, porque los scripts importan `src.comun` y Python solo
encuentra `src` si arranca desde la raíz. Cada script tiene al inicio una explicación de qué hace y su línea "Uso:", y
cada función una línea que dice qué hace y qué papel tiene en el flujo.

### Preparar el entorno

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` trae PyTorch para CUDA 13.4 (CUDA es la plataforma de NVIDIA para calcular en la tarjeta gráfica, la
GPU). Todo se corrió en una laptop con Windows 11, una GPU NVIDIA RTX 4070 de 8 GB y 16 GB de RAM (la memoria de
trabajo); el detalle está en `reports/entorno.md`.

### De dónde salen los datos

| Qué | De dónde sale | Dónde va |
|---|---|---|
| Dataset WiSARDv1 | Se descarga de https://sites.google.com/uw.edu/wisard/ | Fuera del repositorio. Su carpeta se pone en `dataset:` de `configs/rutas.yaml`. Los scripts solo lo leen. |
| Pesos preentrenados `yolo26s.pt` | Los publica Ultralytics; `YOLO("yolo26s.pt")` los descarga si no están | `weights/yolo26s.pt` |
| `data/` | Lo regeneran las fases 1 a 4 y la 7 (ver la tabla de pasos) | `data/` (fuera de git) |
| Respuestas de los anotadores de oclusión (`data/oclusion*.csv`, `data/fase7/oclusion_validacion_simple.csv`) | Las escribió la herramienta de anotación mientras dos personas respondían a mano. **No se pueden regenerar.** | Fuera de git por ahora (el repositorio es público); hay una copia fuera del repositorio. Sin ellas, las fases 4, 6, 7 (C4) y 8 no se pueden recalcular. |
| `runs/` | Entrenamientos y predicciones (fases 5 a 8 y diagnóstico) | `runs/` (fuera de git). Las salidas livianas se copian a `reports/`. |

El `path:` de los yaml de datasets es relativo a la raíz del repositorio (por ejemplo `data/datasets/fusion`), así que
no depende de la laptop. Si `data:` de `configs/rutas.yaml` apunta fuera del repositorio, los scripts escriben la ruta
absoluta. Ultralytics resolvería un `path` relativo contra la carpeta desde donde se lanza el comando, así que los
scripts no le pasan el yaml de git: le pasan una copia con la ruta absoluta de la máquina en `runs/_datos/`
(`yaml_para_ultralytics` de `src/comun.py`), que se reescribe en cada corrida y no va a git.

### Pasos del experimento, en orden

Cada paso usa la configuración de su fase. Todos los comandos llevan `--rutas configs\rutas.yaml`, y todos los que
entrenan o evalúan agregan una fila a `reports/bitacora.csv`. Lo aleatorio usa siempre `seed=0`. Los pasos marcados
"a mano" abren una ventana de OpenCV y los hace una persona.

#### Fase 0. Entorno

```
.venv\Scripts\python.exe -m src.entorno.entorno --config configs\fase0.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.entorno.prueba_prediccion --config configs\fase0.yaml --rutas configs\rutas.yaml
```

Escribe `reports/entorno.md` (sistema, GPU y versiones) y una predicción de prueba en `runs/fase0_prueba/`.

#### Fase 1. Pares RGB y térmica

Reconstruye qué imagen RGB va con qué térmica. WiSARD no trae esa lista: se arma por número de carpeta y por posición
del fotograma (las reglas están en `CLAUDE.md`). También marca qué pares se excluyen y por qué (`configs/fase1.yaml`).

```
.venv\Scripts\python.exe -m src.pares.emparejar --config configs\fase1.yaml --rutas configs\rutas.yaml
```

Escribe `data/pares.csv` (un par por fila) y `reports/tabla_pares_por_vuelo.csv`, y comprueba los totales esperados
(4 617 pares finales).

#### Fase 2. Alineación

La cámara RGB y la térmica no ven exactamente lo mismo, así que se lleva la RGB a la geometría de la térmica. Para eso
se usa una **semejanza por vuelo** (escala, giro y traslación) estimada con los centros de las cajas de personas,
con RANSAC (un método que descarta los puntos que no encajan). Está congelada desde el 31 de octubre de 2026: el
script la vuelve a medir pero no la reestima.

```
.venv\Scripts\python.exe -m src.alineacion.marcar_puntos --config configs\fase2.yaml --rutas configs\rutas.yaml --vuelo 210924_FHL_Enterprise_0405
.venv\Scripts\python.exe -m src.alineacion.semejanza_por_vuelo --config configs\fase2.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.alineacion.revision_desfases --config configs\fase2.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.alineacion.alinear --config configs\fase2.yaml --rutas configs\rutas.yaml
```

- `marcar_puntos` (a mano): puntos de control en tres fotogramas por vuelo, para medir el error de la alineación.
  Escribe `configs/puntos_control/<vuelo>.yaml`.
- `semejanza_por_vuelo`: la transformación de cada vuelo (`configs/homografias_cajas.yaml`) y su error en
  `reports/alineacion/homografias_cajas/`.
- `revision_desfases`: pares en que la térmica muestra otro instante que la RGB. Con `--aplicar`, escribe
  `configs/exclusiones_desfase.yaml` desde las decisiones de `configs/revision_desfases.yaml`; la fase 1 lee ese
  archivo, así que después hay que volver a correr la fase 1.
- `alinear`: las imágenes alineadas de 640 x 512 en `data/alineados/`: la RGB y la térmica en PNG (formato de imagen
  sin pérdida) y la fusión en TIFF de 4 canales (un formato de imagen que admite más de 3 canales). Deja
  superposiciones para revisar en `reports/alineacion/final/`.

Para volver a sacar los mismos datos basta con fase 1, `semejanza_por_vuelo` y `alinear`: las decisiones ya están en
`configs/`.

#### Fase 3a. Partición por vuelo y datasets

Cada vuelo va entero a una sola partición (`configs/particion.yaml`), para que el modelo no se evalúe con fotogramas
casi iguales a los que vio al entrenar.

```
.venv\Scripts\python.exe -m src.particion.particion --config configs\fase3.yaml --rutas configs\rutas.yaml
```

Escribe las etiquetas sin cajas repetidas (`data/etiquetas/`), los tres datasets de Ultralytics con enlaces duros a
`data/alineados/` (`data/datasets/{fusion,rgb,termico}/`), sus yaml (`configs/fusion.yaml`, `rgb.yaml`, `termico.yaml`)
y las tablas `reports/fase3_*.csv`.

#### Fase 3b. Anotación de oclusión (a mano)

Para medir el recall por nivel de oclusión hace falta saber cuánto se ve cada persona en la RGB. Se anotan las personas
de la prueba (FHL 0405) en 1 de cada 3 fotogramas: 310 fotogramas y 498 personas.

```
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --preparar
.venv\Scripts\python.exe -m pruebas.probar_anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.oclusion.oclusion_auto --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --muestra
.venv\Scripts\python.exe -m src.oclusion.corregir_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --ajuste
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-resto
.venv\Scripts\python.exe -m src.oclusion.anotar_oclusion --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-reanotar escena_sombra
```

- `--preparar`: la lista fija de personas (`data/oclusion_personas.csv`) y la muestra al azar del segundo anotador
  (`data/oclusion_muestra_segundo.csv`).
- `oclusion_auto`: la oclusión estimada sin anotar, con las cajas RGB de WiSARD (`data/oclusion_auto.csv`). No pasó la
  validación y no se usa como nivel; queda como referencia.
- Los modos de la herramienta: `--muestra` y `--ajuste` son la primera anotación, con cajas; `--segundo-simple` y
  `--primero-simple` son las dos rondas con una tecla por persona ("se ve", "no se ve", "no es persona");
  `--primero-simple-resto` completa las 498 y `--primero-simple-reanotar` repite la escena en sombra. Cada modo
  escribe su propio `data/oclusion_*.csv` (ver `CLAUDE.md`, "Rutas").
- La ronda que anota `--segundo-simple` sale de `oclusion.modo_simple.ronda_actual` en `configs/fase3.yaml`.

#### Fase 4. Concordancia y nivel final de oclusión

Comprueba si dos personas anotan lo mismo y fija el nivel de cada persona. La concordancia se mide con el kappa de
Cohen, que compara el acuerdo con el que se esperaría por azar.

```
.venv\Scripts\python.exe -m src.oclusion.concordancia --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 1
.venv\Scripts\python.exe -m src.oclusion.concordancia --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 2
.venv\Scripts\python.exe -m src.oclusion.concordancia --config configs\fase3.yaml --rutas configs\rutas.yaml --partes comparar no_es_persona fondo
.venv\Scripts\python.exe -m src.oclusion.nivel_final --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.oclusion.cajas_dudosas --config configs\fase3.yaml --rutas configs\rutas.yaml
```

- `concordancia`: tablas e imágenes de los desacuerdos en `reports/fase4_validacion_auto/`.
- `nivel_final`: `data/oclusion_nivel.csv`, el nivel que usan las fases 6 y 8. Si cambia, guarda antes una copia en
  `data/respaldos/`.
- `cajas_dudosas`: `configs/cajas_dudosas.yaml`, las cajas de WiSARD que los anotadores marcaron como "no es persona",
  seguidas por los fotogramas no anotados. Las métricas se calculan con y sin ellas; las etiquetas no se tocan.

**Niveles de oclusión.** Son dos desde el 1 de noviembre de 2026:

- **baja**: la persona se ve en la RGB;
- **severa**: no se ve en la RGB.

Al principio eran tres, según la fracción del cuerpo tapada en la RGB (λ): baja de 0 a 35 %, moderada de 35 a 70 % y
severa más de 70 %. El nivel moderado se descartó porque en la muestra anotada con cajas no hubo ninguna persona
moderada (0 de 68): o se veía casi entera, o no se veía. Un nivel sin personas no se puede evaluar. Los tres niveles
solo se usan al reportar esa comparación.

#### Fase 5. Entrenamiento

```
.venv\Scripts\python.exe -m src.entrenamiento.entrenar --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_100ep
.venv\Scripts\python.exe -m src.utilidades.copiar_fase5b --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_100ep
.venv\Scripts\python.exe -m src.entrenamiento.resumen_fase5b --config configs\fase5.yaml --rutas configs\rutas.yaml
```

- `entrenar`: antes de entrenar comprueba la potencia de la GPU, el plan de energía y que estén cerradas las
  aplicaciones de `cerrar_antes`; si algo falla, no entrena. Las corridas están en `corridas` de `configs/fase5.yaml`:
  las pruebas cortas (`fusion_lote16_2ep`, `fusion_azar_10ep`, `fusion_promedio_10ep`, ...) y las de 100 épocas
  (`fusion_100ep`, `rgb_100ep`, `termico_100ep`). Escribe en `runs/fase5/<corrida>/`, con `resumen.json`,
  `epocas.csv` y `monitor.csv`.
- `copiar_fase5b` y `resumen_fase5b`: copian los archivos livianos a `reports/fase5b/` y arman las curvas y la tabla.
- `scripts/noche.ps1` encadenó `rgb_100ep`, `termico_100ep` y las predicciones de la fase 6. De las de 100 épocas solo
  terminó `fusion_100ep`: `rgb_100ep` se cortó dos veces y `termico_100ep` no llegó a correr.

#### Fase 6. Evaluación por nivel (solo validación)

Mide qué tan bien detecta cada modelo, con un script propio sobre pycocotools (la herramienta de evaluación del
conjunto de imágenes COCO):

- **recall**: qué fracción de las personas encuentra;
- **precisión**: qué fracción de sus detecciones son personas;
- **F2**: una media de las dos que pesa más el recall, porque en rescate importa más no perder a nadie;
- **mAP@0.5** (mean average precision): resume la precisión en todos los umbrales de confianza. Una detección cuenta
  como acierto si su IoU con la caja real es de 0.5 o más; el IoU (intersection over union) es el área común de las
  dos cajas dividida por el área que cubren entre las dos.

Recall, precisión y F2 usan el umbral de confianza de cada modelo; el mAP@0.5 no usa umbral.

Los intervalos de confianza (IC) se calculan con bootstrap por episodios: se remuestrean tramos enteros del vídeo, no
fotogramas sueltos, porque los fotogramas seguidos no son independientes. Los modelos se comparan con la prueba de
McNemar, que mira las personas que detecta uno y no el otro, con la corrección de Bonferroni por hacer varias
comparaciones.

```
.venv\Scripts\python.exe -m src.evaluacion.evaluar --config configs\fase6.yaml --rutas configs\rutas.yaml --particion validacion --modelos fusion fusion_last
```

Escribe las predicciones en `runs/fase6/validacion/<modelo>/` y las tablas en `runs/fase6/validacion/`. La prueba
**no** se evalúa con este script: esa parte quedó bloqueada y marcada como obsoleta, porque la reemplaza
`src/evaluacion/evaluar_prueba.py` (fase 8). Con `--solo-predecir` solo guarda predicciones, sin métricas.

#### Diagnóstico (A1 a A6 y B1 a B3)

Se hizo porque el mAP@0.5 de validación de la fase 5 salió muy bajo. Lee las corridas y los datos sin cambiarlos y no
evalúa la prueba.

```
.venv\Scripts\python.exe -m experimentos.diagnostico --config configs\diagnostico.yaml --rutas configs\rutas.yaml --parte inventario
.venv\Scripts\python.exe -m experimentos.diagnostico --config configs\diagnostico.yaml --rutas configs\rutas.yaml --parte b1_datos
.venv\Scripts\python.exe -m src.entrenamiento.entrenar --config configs\diagnostico.yaml --rutas configs\rutas.yaml --corrida b1_termico_aleatoria_30ep
.venv\Scripts\python.exe -m experimentos.diagnostico --config configs\diagnostico.yaml --rutas configs\rutas.yaml --parte b_evaluar --corrida b1_termico_aleatoria_30ep
```

Las partes son `inventario`, `estado`, `tamanos`, `integridad`, `validar`, `hoja`, `b1_datos`, `b_evaluar`,
`b_por_vuelo` y `copiar` (qué es cada una, en la tabla de etiquetas). Escribe en `runs/diagnostico/` y la parte
`copiar` lleva lo liviano a `reports/diagnostico/`. El resumen está en `reports/diagnostico.md`.

#### Fase 7. Más térmicas y nueva receta (C0 a C4)

La lista completa de comandos, en el orden en que se corrieron, está al final de `reports/fase7.md`. En resumen:

```
.venv\Scripts\python.exe -m src.ampliacion.c0_auditoria_termicas --config configs\fase7.yaml --rutas configs\rutas.yaml --parte auditar
.venv\Scripts\python.exe -m src.ampliacion.c0_auditoria_termicas --config configs\fase7.yaml --rutas configs\rutas.yaml --parte ampliar
.venv\Scripts\python.exe -m src.ampliacion.c0_auditoria_termicas --config configs\fase7.yaml --rutas configs\rutas.yaml --parte alineacion
.venv\Scripts\python.exe -m src.ampliacion.c0_auditoria_termicas --config configs\fase7.yaml --rutas configs\rutas.yaml --parte clasificar
.venv\Scripts\python.exe -m src.ampliacion.marcar_puntos_vuelos_nuevos --config configs\fase7.yaml --rutas configs\rutas.yaml --vuelo 210924_FHL_Enterprise_0403
.venv\Scripts\python.exe -m src.ampliacion.c0_auditoria_termicas --config configs\fase7.yaml --rutas configs\rutas.yaml --parte puntos
.venv\Scripts\python.exe -m src.ampliacion.c1_datasets_ampliados --config configs\fase7.yaml --rutas configs\rutas.yaml --parte componer
.venv\Scripts\python.exe -m src.ampliacion.c1_datasets_ampliados --config configs\fase7.yaml --rutas configs\rutas.yaml --parte construir
.venv\Scripts\python.exe -m src.ampliacion.origen_imagenes --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.entrenamiento.entrenar_fase7 --config configs\fase7.yaml --rutas configs\rutas.yaml --verificar
.venv\Scripts\python.exe -m src.entrenamiento.entrenar_fase7 --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida termico_base
.venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte preparar
.venv\Scripts\python.exe -m src.evaluacion.c4_evaluar_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --solo-predecir
.venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte anotar
.venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte nivel
.venv\Scripts\python.exe -m src.oclusion.c4_nivel_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml --parte consistencia
.venv\Scripts\python.exe -m src.evaluacion.c4_evaluar_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.evaluacion.c4_desglose_validacion --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe -m src.utilidades.copiar_fase7 --config configs\fase7.yaml --rutas configs\rutas.yaml
```

- Las corridas de C3 se entrenan en este orden: `termico_base`, `termico_ampliado`, `fusion_base`, `fusion_ampliado` y
  `rgb_base` (la misma línea de `termico_base`, cambiando `--corrida`).
- `c4_nivel_validacion --parte anotar` es a mano.
- Los datasets ampliados van en `data/fase7/`; las corridas y predicciones, en `runs/fase7/`; lo liviano se copia a
  `reports/fase7/`.

#### Fase 8. Evaluación en la prueba (una sola vez)

```
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte umbrales
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte verificar
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte prueba
```

1. `umbrales`: fija el umbral de confianza de cada modelo en validación (el que da el mayor F2) y lo escribe en
   `reports/fase8/umbrales.csv`, que se sube a GitHub antes de seguir.
2. `verificar`: comprueba todo lo que se puede sin predecir (umbrales en GitHub, pesos, canales, etiquetas, niveles).
3. `prueba`: predice la prueba con todos los modelos y la mide. Escribe `reports/fase8/` (`resultados.csv`,
   `mcnemar.csv`, `sensibilidad.csv`, `prediccion.csv` y `recall_por_nivel.png`) y las predicciones en
   `runs/fase8/prueba/`.

Si ya existe alguna salida en `reports/fase8/`, `verificar` y `prueba` se niegan a correr (`una_sola_vez: true`): la
prueba se evalúa una sola vez.

#### Experimentos de las fases 1 y 2

Sirvieron para decidir las exclusiones de `configs/fase1.yaml` y la transformación de la fase 2. Escriben en
`reports/baker_corte/` y `reports/alineacion/`. Ninguna salida del flujo depende de ellos.

| Script | Para qué |
|---|---|
| `experimentos/fase1_baker_corte.py` | Ver dónde empiezan las personas sin caja en Baker, para fijar el corte. |
| `experimentos/fase2_lado_a_lado.py` | Pares RGB y térmica lado a lado al inicio, la mitad y el final de cada vuelo. |
| `experimentos/fase2_escala_por_fotograma.py` | Escala y posición de la RGB en cada par, para encontrar despegues, aterrizajes y cambios de zoom. |
| `experimentos/fase2_zoom_temporal.py` | Zoom de la RGB respecto de la térmica a lo largo de cada vuelo. |
| `experimentos/fase2_barrido.py` | Barrido visual de cada vuelo, para encontrar a ojo despegues, aterrizajes y cambios de zoom. |
| `experimentos/fase2_bordes_tramos.py` | Los bordes de cada tramo excluido, para revisarlos. |
| `experimentos/fase2_homografias.py` | La homografía completa desde puntos marcados a mano; se descartó (se deforma donde las personas ocupan poca parte de la imagen). |
| `experimentos/conteo_particion.py` | Conteos por vuelo para elegir la partición y cuántos fotogramas anotar (`reports/conteo_particion*`). |

Todos se corren igual: `.venv\Scripts\python.exe -m experimentos.<script> --config configs\<su yaml> --rutas
configs\rutas.yaml` (el yaml de cada uno está en su línea "Uso:").

## Etiquetas A1 a A6, B1 a B3 y C0 a C4

Aparecen en `reports/`, en los nombres de las carpetas de `runs/` y en los documentos de la tesis, así que se dejaron
como están.

| Etiqueta | Qué es | Dónde está el código | Resultados |
|---|---|---|---|
| A1 | Inventario de WiSARDv1: carpetas, resoluciones, etiquetas y térmicas anotadas que quedan fuera de los pares | `experimentos/diagnostico.py --parte inventario` | `reports/diagnostico.md`, `reports/diagnostico/a1/` |
| A2 | Estado de las corridas de 100 épocas de la fase 5b (la noche del 3 al 4 de noviembre): época del mejor modelo y sus métricas | `--parte estado` | `reports/diagnostico/a2/` |
| A3 | Tamaño de las personas en píxeles, por partición y vuelo | `--parte tamanos` | `reports/diagnostico/a3/` |
| A4 | Validación de la fusión desglosada por vuelo, por pares "solo térmica" y por tamaño | `--parte validar` | `reports/diagnostico/a4/` |
| A5 | Revisión visual: 16 imágenes de validación con las cajas reales y las predicciones | `--parte hoja` | `reports/diagnostico/a5/` |
| A6 | Integridad de los datasets: etiquetas legibles, conteos y que entrenamiento, validación y prueba no compartan imágenes | `--parte integridad` | `reports/diagnostico/a6/` |
| B1 | Solo térmica con partición al azar por fotograma (60/20/20), 6 vuelos, 30 épocas: muestra cuánto sube la cifra si se mezclan fotogramas de un mismo vuelo | `--parte b1_datos`, `src.entrenamiento.entrenar --config configs\diagnostico.yaml`, `--parte b_evaluar` y `b_por_vuelo` | `reports/diagnostico.md` |
| B2 | Solo térmica con la partición por vuelo de la tesis, 30 épocas | igual que B1 | `reports/diagnostico.md` |
| B3 | Solo térmica a 1280 píxeles; planeado, no se corrió | `configs/diagnostico.yaml` | no hay |
| C0 | Auditoría de las térmicas anotadas que quedan fuera de los 4 617 pares (sin entrenar) | `src/ampliacion/c0_auditoria_termicas.py`, `marcar_puntos_vuelos_nuevos.py` | `reports/fase7/c0/` |
| C1 | Datasets nuevos `termico_ampliado` y `fusion_ampliado`, con esas térmicas | `src/ampliacion/c1_datasets_ampliados.py`, `origen_imagenes.py` | `reports/fase7/c1/` |
| C2 | Receta para objetos pequeños: mejor época elegida por mAP@0.5 y dropout de modalidad (a veces se apaga la RGB al entrenar) | `src/entrenamiento/entrenar_fase7.py --verificar`, `dropout_modalidad.py` | `reports/fase7/c2/` |
| C3 | Corridas `termico_base`, `termico_ampliado`, `fusion_base`, `fusion_ampliado` y después `rgb_base` | `src/entrenamiento/entrenar_fase7.py --corrida` | `reports/fase7/<corrida>/` |
| C4 | Evaluación en validación, con nivel de oclusión anotado a mano en la validación | `src/oclusion/c4_nivel_validacion.py`, `src/evaluacion/c4_evaluar_validacion.py`, `c4_desglose_validacion.py` | `reports/fase7/c4/` |

## Rutas viejas y nuevas

Hasta el 25 de noviembre de 2026 todo el código estaba en `scripts/`. Los reportes, `CLAUDE.md`, `FASES.md` y los
comentarios de `configs/` ya citan las rutas nuevas (se cambiaron solo las rutas y los comandos, sin tocar ninguna cifra
ni conclusión), pero la bitácora, los `.log` y los encabezados de algunos yaml generados (`configs/cajas_dudosas.yaml`,
`configs/exclusiones_desfase.yaml`, `configs/homografias_cajas.yaml`) conservan el nombre viejo, porque registran lo que
se corrió entonces.

| Antes | Ahora |
|---|---|
| `scripts/comun.py` | `src/comun.py` |
| `scripts/fase0_entorno.py` | `src/entorno/entorno.py` |
| `scripts/fase0_prueba_prediccion.py` | `src/entorno/prueba_prediccion.py` |
| `scripts/fase1_pares.py` | `src/pares/emparejar.py` |
| `scripts/marcar_puntos.py` | `src/alineacion/marcar_puntos.py` |
| `scripts/fase2_homografias_cajas.py` | `src/alineacion/semejanza_por_vuelo.py` (las funciones de cajas, en `src/cajas.py`) |
| `scripts/fase2_revision_desfases.py` | `src/alineacion/revision_desfases.py` |
| `scripts/alinear.py` | `src/alineacion/alinear.py` |
| `scripts/fase3_particion.py` | `src/particion/particion.py` |
| `scripts/anotar_oclusion.py` | `src/oclusion/anotar_oclusion.py` |
| `scripts/corregir_oclusion.py` | `src/oclusion/corregir_oclusion.py` |
| `scripts/oclusion_auto.py` | `src/oclusion/oclusion_auto.py` |
| `scripts/fase4_validacion_auto.py` | `src/oclusion/concordancia.py` |
| `scripts/fase4_nivel.py` | `src/oclusion/nivel_final.py` |
| `scripts/fase4_cajas_dudosas.py` | `src/oclusion/cajas_dudosas.py` |
| `scripts/fase7_c4_oclusion.py` | `src/oclusion/c4_nivel_validacion.py` |
| `scripts/fase7_c0_auditoria.py` | `src/ampliacion/c0_auditoria_termicas.py` |
| `scripts/fase7_marcar_puntos.py` | `src/ampliacion/marcar_puntos_vuelos_nuevos.py` |
| `scripts/fase7_c1_datasets.py` | `src/ampliacion/c1_datasets_ampliados.py` |
| `scripts/fase7_origen.py` | `src/ampliacion/origen_imagenes.py` |
| `scripts/entrenar.py` | `src/entrenamiento/entrenar.py` |
| `scripts/fase7_entrenar.py` | `src/entrenamiento/entrenar_fase7.py` |
| `scripts/modalidad.py` | `src/entrenamiento/dropout_modalidad.py` |
| `scripts/fase5b_resumen.py` | `src/entrenamiento/resumen_fase5b.py` |
| `scripts/evaluar.py` | `src/evaluacion/evaluar.py` |
| `scripts/fase7_c4_evaluar.py` | `src/evaluacion/c4_evaluar_validacion.py` |
| `scripts/fase7_c4_desglose.py` | `src/evaluacion/c4_desglose_validacion.py` |
| `scripts/fase8_evaluar.py` | `src/evaluacion/evaluar_prueba.py` |
| `scripts/fase5b_copiar.py` | `src/utilidades/copiar_fase5b.py` |
| `scripts/fase7_copiar.py` | `src/utilidades/copiar_fase7.py` |
| `scripts/conteo_particion.py` | `experimentos/conteo_particion.py` (la función `episodios`, en `src/particion/particion.py`) |
| `scripts/diagnostico.py` | `experimentos/diagnostico.py` |
| `scripts/fase1_baker_corte.py`, `scripts/fase2_*.py` (los 6 exploratorios) | `experimentos/` con el mismo nombre |
| `scripts/probar_anotar_oclusion.py` | `pruebas/probar_anotar_oclusion.py` |

## Qué se comprobó después de reorganizar

La reorganización no cambia ninguna cifra. Se comprobó así, el 25 de noviembre de 2026:

- **El código hace lo mismo.** Se comparó el árbol de sintaxis de cada archivo con el de antes, quitando los
  comentarios y las explicaciones y aplicando los cambios de nombre. Solo cambian, a propósito, las líneas que arman
  rutas (relativas a la raíz en vez de absolutas). Las funciones que cambiaron de archivo (`src/cajas.py`, `episodios`)
  se compararon con su original.
- **Los scripts dan los mismos archivos.** Se corrieron el código viejo y el nuevo con la misma configuración, con las
  salidas en una carpeta temporal, y se compararon byte a byte entre sí y con lo que está en el repositorio:
  - fase 1: `data/pares.csv` y `reports/tabla_pares_por_vuelo.csv`, iguales;
  - fase 2 (`semejanza_por_vuelo`): los 26 archivos de su reporte, iguales, y `configs/homografias_cajas.yaml` sin
    cambios;
  - fase 3a (`particion`, en una copia del repositorio para no tocar `data/`): las 9 234 etiquetas sin repetidas, las
    etiquetas y las listas de imágenes de los tres datasets, sus yaml (salvo `path`, que ahora es relativo) y las tres
    tablas `reports/fase3_*.csv`, iguales. `experimentos/conteo_particion.py` da sus dos tablas iguales;
  - fases 3b y 4: la prueba de la herramienta de anotación (102 casos), `concordancia` (las dos rondas y el resto),
    `nivel_final` (`data/oclusion_nivel.csv`) y `cajas_dudosas` (`configs/cajas_dudosas.yaml` salvo los comentarios),
    iguales;
  - fase 6: `resultados.csv` y `mcnemar.csv` de la validación, iguales;
  - fase 7: las tablas de `entrenar_fase7 --verificar` y la carga de imágenes con el dropout de modalidad en 2
    procesos, iguales;
  - fase 8: `umbrales.csv` (salvo la hora en que se fijó) y `umbrales_rejilla.csv`, iguales. Las cinco salidas de la
    prueba se recalcularon desde las predicciones ya guardadas, sin volver a predecir y en una carpeta temporal, y son
    iguales byte a byte a las de `reports/fase8/`;
  - `verificar` de la fase 8 se sigue negando a correr porque la prueba ya se evaluó.
- **No se volvió a correr:** los entrenamientos, `alinear` (escribe los 4 617 pares), C0 y C1 completos, el
  diagnóstico, `marcar_puntos` y los modos de anotación a mano (sí la prueba automática), ni `scripts/noche.ps1`
  (se comprobó que PowerShell lo lee sin errores). Todos importan bien y responden a `--help`.

## Pendientes

- **`configs/fase6.yaml` cita corridas que no existen.** En `modelos` (líneas 13 a 15) aparecen `rgb_100ep` y
  `termico_100ep`, pero `rgb_100ep` se cortó dos veces (épocas 7 y 67; están en `runs/fase5/rgb_100ep_cortada` y
  `rgb_100ep_cortada2`) y `termico_100ep` no se entrenó. Por eso la fase 6 solo corre con `fusion` y `fusion_last`. No
  se corrigió: queda para decidir.
- **Funciones largas sin partir.** Cinco pasan de 150 líneas: `main` de `src/alineacion/semejanza_por_vuelo.py` (310),
  de `src/oclusion/nivel_final.py` (187), de `src/evaluacion/evaluar.py` (171) y de `src/oclusion/cajas_dudosas.py`
  (162), y `aplicar` de `src/alineacion/revision_desfases.py` (156). Se dejaron enteras para no arriesgar la lógica.
- **Respuestas de los anotadores fuera de git.** `data/oclusion*.csv` y `data/fase7/oclusion_validacion_*.csv` no están
  en el repositorio público. Falta decidir si se suben, según los términos de uso de WiSARD: en los archivos descargados
  no hay licencia ni términos, y el artículo solo enlaza al sitio.
- **Solo en Windows.** `src/entorno/entorno.py` lee el plan de energía de Windows (`powercfg`, `winreg`), y
  `src/entrenamiento/entrenar.py` lo comprueba con esas mismas funciones; los dos entrenamientos leen la GPU con
  `nvidia-smi`; `scripts/noche.ps1` es PowerShell; la herramienta de anotación y
  `marcar_puntos` abren ventanas de OpenCV; algunas figuras usan la fuente `arial.ttf` de Windows (si no está, PIL usa
  la suya).
- **`configs/noche.yaml`** guarda en `git.coautor` una línea `Co-Authored-By` que `noche.ps1` agregó a sus commits. Se
  dejó como está porque registra lo que pasó esa noche.
- **Imports sin usar** que ya estaban antes: `DatasetSinRGB` en `src/entrenamiento/entrenar_fase7.py`, `RAIZ` en
  `src/evaluacion/c4_evaluar_validacion.py` y `np` en `src/oclusion/corregir_oclusion.py`.
- **Encabezados de yaml generados** con el nombre viejo del script (ver "Rutas viejas y nuevas"). Cambian solos la
  próxima vez que se generen.
- **Recorrido completo sin probar.** Nadie ha corrido el flujo entero desde cero en otra computadora; lo comprobado es
  lo de la sección anterior.
