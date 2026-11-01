# Contexto del proyecto (léelo siempre antes de trabajar)

Tesis de pregrado de Hans Quispe (Ingeniería de Sistemas, Universidad de Lima), curso Seminario de Investigación I.
Tema: detectar y localizar personas ocultas por vegetación en imágenes de dron, fusionando la imagen RGB y la térmica.

Pregunta central: ¿un detector que recibe RGB + térmica encuentra más personas que el mismo detector con una sola
cámara, cuando la vegetación tapa más del 70 % del cuerpo?

## Reglas de trabajo

- Trabaja **por fases**, según `FASES.md`. Al terminar una fase, detente, resume lo que hiciste y espera mi confirmación.
- **Nunca** modifiques, muevas ni borres nada dentro del dataset original.
- Nada de rutas ni hiperparámetros escritos a mano dentro del código: todo va en `configs/` y se pasa como argumento.
- Semilla fija `seed=0` en todo lo aleatorio.
- Cada entrenamiento o evaluación agrega una fila a `reports/bitacora.csv` (fecha, fase, modelo, configuración, resultado).
- Si algo no está claro o los datos no son como dice este archivo, **muéstrame ejemplos y pregúntame** antes de suponer.
- Ejecuta Python con el entorno virtual del proyecto (`.venv`).
- La memoria es limitada (16 GB de RAM y 8 GB en la GPU): procesa las imágenes por partes, nunca todas en memoria.
- Todos los entrenamientos se hacen con la laptop **enchufada**, en modo **Rendimiento** de Armoury Crate y con el
  plan de energía **Performance** de Windows. Antes de entrenar, verifica con `nvidia-smi` que el límite aplicado
  bajo carga (`enforced.power.limit`) sea de al menos 90 W; si no, detente y avísame.

## Equipo

- Laptop con Windows 11, Intel Core i7-13620H (10 núcleos, 16 hilos), 16 GB de RAM.
- GPU NVIDIA GeForce RTX 4070 Laptop GPU, 8 GB. Límite de potencia medido el 30 de octubre de 2026 con `nvidia-smi`
  (enchufada, modo Rendimiento): **hasta 100 W bajo carga** (80 W por defecto + hasta 20 W de Dynamic Boost; máximo
  configurable 120 W). El límite aplicado varía entre corridas (medianas de 92 a 100 W) según la temperatura y la
  carga de la CPU. Los 55 W anotados antes eran una lectura en modo de bajo consumo.
- Todos los entrenamientos que se reporten corren en esta misma laptop.
- Controlador NVIDIA 617.42 (CUDA 13.4), actualizado el 30 de octubre de 2026 (antes 555.97).

## Rutas

- Dataset original: `C:\Users\User\Downloads\WiSARDv1` (solo lectura).
- Proyecto: esta carpeta. Datos procesados en `data\` (no van a GitHub).
- Imágenes alineadas de los 4 617 pares (fase 2, `scripts/alinear.py`): `data\alineados\` con `rgb\`, `termica\`
  (gris, 1 canal), `fusion\` (TIFF con muestras B, G, R, T, que Ultralytics entrega al modelo como R, G, B, T) e
  `indice.csv`.
- Fase 3a (`scripts/fase3_particion.py`):
  - Etiquetas de los pares finales sin cajas repetidas: `data\etiquetas\` (`rgb\` y `termica\`).
  - Datasets de Ultralytics: `data\datasets\{fusion,rgb,termico}\`, con enlaces duros a `data\alineados\` y las
    etiquetas térmicas.
  - Yaml de los datasets: `configs\fusion.yaml`, `configs\rgb.yaml` y `configs\termico.yaml`.
- Anotación de oclusión (fase 3b, `scripts/anotar_oclusion.py`):
  - `data\oclusion_personas.csv`: lista fija de 498 personas, con la precarga.
  - `data\oclusion.csv`: anotaciones del primer anotador. Por persona guarda las dos completas, el corrimiento de la RGB
    respecto de la térmica, las visibles, las marcas y λ.
  - `data\oclusion_muestra_segundo.csv`: las 75 personas de la muestra.
  - `data\oclusion_segundo.csv`: anotaciones del segundo anotador con cajas (modo `--segundo`, ya no se usa).
  - Respuestas en modo simple, una ronda por archivo y anotador (`oclusion.modo_simple` en `configs/fase3.yaml`; la
    herramienta escribe en el de `ronda_actual`):
    - ronda 1 (regla ambigua), solo el segundo: `data\oclusion_segundo_simple_ronda1.csv`;
    - ronda 2 (regla aclarada), los dos: `data\oclusion_primero_simple_ronda2.csv` (`--primero-simple`) y
      `data\oclusion_segundo_simple_ronda2.csv` (`--segundo-simple`).
- Correcciones de la muestra: `configs\correcciones_oclusion.yaml` (las aplica `scripts/corregir_oclusion.py`).
  - Respaldo de las anotaciones antes de cada corrección: `data\respaldos\`.
  - Lista para ajustar la visible RGB (herramienta `--ajuste`): `data\oclusion_ajuste_visibles.csv`.
- λ RGB automático (`scripts/oclusion_auto.py`): `data\oclusion_auto.csv`, con las 1 501 personas de FHL 0405.
- Validación del nivel automático (`scripts/fase4_validacion_auto.py`): `reports\fase4_validacion_auto.md`, con tablas
  e imágenes en `reports\fase4_validacion_auto\`.
- Proyecto anterior, solo como consulta: `C:\Users\User\sar-fusion\reports\` (scripts `emparejamiento.py` y
  `analisis_pares.py`, y `resumen_wisard.md`). Se puede reutilizar código de ahí, pero los resultados se regeneran aquí.

## Lo que ya sabemos de WiSARDv1 (análisis del 28 y 29 de octubre de 2026)

- 80 carpetas planas, una por vuelo y modalidad: `AAMMDD_Sitio_Dron_VIS[_ID]` (RGB) e `..._IR[_ID]` (térmica).
- Cada imagen tiene un `.txt` con el mismo nombre en formato YOLO (`clase cx cy w h`, normalizado). Solo clase 0 = persona.
- Un `.txt` vacío significa 0 cajas, no "descartar". Una carpeta sin ningún `.txt` está sin anotar.
- Térmicas: 640 × 512. RGB: 1920 × 1080, 2720 × 1530, 3840 × 2160 o 4096 × 2160.
- **No hay** archivos `.yaml` de metadatos ni lista de pares. Las imágenes no tienen EXIF.
- **Emparejamiento:** la carpeta VIS con número N va con la IR con número N+1 del mismo `fecha_sitio_dron`
  (en `220109_Baker` el número sale del nombre de archivo: DJI_0582 con DJI_0583). Dentro de cada pareja, los
  fotogramas se emparejan **por posición** en orden natural, hasta la longitud mínima.
- Resultado esperado: 14 839 pares en total; 5 739 con las dos imágenes anotadas.
- **Exclusión:** Baker VIS_1/IR_1, posiciones 2031 a 2179 (en la térmica hay personas sin caja desde la 2031;
  revisado a mano el 30 de octubre de 2026, ver `reports/baker_corte/`; antes el corte era 2051). Tras excluirlas
  quedan 5 590 pares anotados en 8 parejas de vuelos de 4 sitios (MtErie, Carnation, FHL, Baker).
- **Exclusiones de la fase 2 (31 de octubre de 2026):** Carnation 0023/0024 completo, de los tres modelos (zoom
  variable en la RGB, que cubre cerca del 11 % de la térmica; posible desfase en la posición 470); despegue de Baker
  (0 a 15); cambio de zoom de FHL 0401 (0 a 10) y aterrizaje de FHL 0401 (857 a 895); desfases entre cámaras
  (la térmica muestra otro instante) en MtErie 0005 (160 a 162) y Baker (620 a 626). El inicio de MtErie 0003 (0 a
  11) se excluyó y se devolvió: el desfase venía de la homografía y con la semejanza no hay. Con eso quedaban 4 775
  pares anotados. Todas estas exclusiones están en `configs/fase1.yaml`, con su motivo.
- **Desfases cerrados el 31 de octubre de 2026.** Regla de desfase (confirmada y aplicada con revisión a ojo): para
  cada persona térmica, la caja RGB alineada más cercana; distancia entre centros dividida por la altura de la caja
  térmica. Solo cuentan las personas con alguna caja RGB a 3 alturas o menos (las demás pueden estar tapadas). Un par
  está desfasado si la mediana de sus personas pasa de 1. Un tramo son 2 o más pares desfasados seguidos; con él salen
  los "solo térmica" a 2 posiciones o menos.
  - Se aplicó con la **opción 2 acotada**. Los tramos en que todas las personas (2 o más) pasan de 1 altura salen sin
    revisión. Los demás se revisaron a ojo, mirando también si el fondo se corre, y lo mismo todos los de FHL 0405,
    MtErie 0005 y MtErie 0007.
  - De 45 tramos salen 41 (133 pares + 2 "solo térmica" = 135). Se conservan 4, porque son oclusión o un cambio de la
    caja y no desfase: MtErie 0005 71–73 y 85–87, FHL 0134 268–272 y FHL 0401 656–657.
  - Además se excluye **FHL 0401 371–372** (2 pares), que apareció al reestimar la semejanza.
  - **Extensión por el fondo:** cada tramo de desfase excluido se extiende a los pares vecinos seguidos mientras el
    fondo esté corrido más de 20 px (correlación de fase, medida fiable). Solo vecinos de tramos ya detectados. Salen
    18 pares; las extensiones de FHL 0405 y MtErie 0005 se revisaron a ojo.
  - Decisiones en `configs/revision_desfases.yaml`; las exclusiones generadas, en `configs/exclusiones_desfase.yaml`
    (`exclusiones_adicionales` de `configs/fase1.yaml`).
  - **Al cerrar:** se excluye a mano **MtErie 0005 207** (fondo +99 px, en `exclusiones` de `configs/fase1.yaml`) y,
    tras revisarlo a ojo, **FHL 0405 160–161** (fondo corrido; en `tramos_adicionales`). El resto de "Lo que queda
    sin excluir" se queda.
  - En total salen 158 pares por desfase. **Quedan 4 617 pares anotados** en 7 parejas de vuelos de 3 sitios
    (MtErie, FHL, Baker); 471 de ellos con persona solo en la térmica. FHL 0405: 928 (salen 15), con sus 394 "solo
    térmica". Lo que queda sin excluir está en `reports/fase2.md`, "Lo que queda sin excluir".
- La térmica ve aproximadamente la franja central de la RGB (x de 0.18 a 0.84, y de 0.06 a 0.98; cerca del 60 % del
  área), salvo en **Carnation 0023/0024**, donde la RGB tiene zoom y la relación se invierte.
- 476 pares tienen persona en la térmica y ninguna en la RGB, casi todos de FHL (394 en FHL 0405/0406). Son los
  candidatos a oclusión severa.
- **Cajas repetidas:** son líneas idénticas dentro de un mismo `.txt`. Hay 46:
  - Baker: 27 RGB, en pares finales.
  - FHL 0401: 4 RGB en pares finales, y 1 RGB y 14 térmicas en pares excluidos.
  - Ninguna térmica en pares finales: las etiquetas de los modelos no cambian.
  - La fase 3a las quita al escribir `data\etiquetas\`. El dataset original no se toca. Detalle en
    `reports/fase3_cajas_repetidas.csv`.

## Decisiones fijas (no cambiar sin consultarme)

- **Detector:** YOLO26s de Ultralytics, con pesos preentrenados `yolo26s.pt`.
- **Tres modelos:** fusión temprana (4 canales: RGB alineada + térmica), solo RGB alineada y solo térmica.
- **Fusión temprana:** imagen TIFF de 4 canales, `channels: 4` en el yaml del dataset.
  Verificado: con 4 canales, la primera capa recibe los pesos preentrenados en los 3 canales de color y el cuarto
  queda al azar. Se probará también inicializar el cuarto canal con el promedio de los pesos de color.
- **Modelo solo térmica:** la térmica entra con **3 canales (el gris repetido)**, para aprovechar los pesos
  preentrenados de la primera capa. Decidido el 1 de noviembre de 2026.
- **Etiquetas de referencia:** las de la imagen térmica, sin cajas repetidas, para los tres modelos.
- **Alineación:** la RGB se recorta a la zona que ve la térmica y se lleva a 640 × 512. La transformación es una
  **semejanza por vuelo** (escala, giro y traslación; `cv2.estimateAffinePartial2D`) estimada con los centros de las
  cajas de personas de los pares con persona en las dos imágenes, con RANSAC y seed=0. Los pares se reparten en
  **bloques fijos de 20 posiciones alternados** (0–19 calibración, 20–39 evaluación, etc.): una mitad la estima y la
  otra mide la distancia entre centros. Se estimó una vez con 4 640 pares y está **congelada** (31 de octubre de
  2026): no se vuelve a estimar (`transformacion_congelada` en `configs/fase2.yaml`). Se valida con puntos de control marcados a mano y con
  superposiciones. La homografía completa se descartó porque se deforma donde las personas ocupan poco espacio
  (FHL 0134, MtErie 0007). Decidido el 31 de octubre de 2026.
- **Partición por vuelo:** cada vuelo va entero en una sola partición. Decidida el 1 de noviembre de 2026; está en
  `configs/particion.yaml`.

  | Partición | Vuelos | Pares | Personas |
  |---|---|---:|---:|
  | Entrenamiento | Baker, MtErie 0003, MtErie 0005 y FHL 0401 | 3 247 | 9 340 |
  | Validación | FHL 0134 y MtErie 0007 (bajo el dosel, con la cámara de frente) | 442 | 500 |
  | Prueba | FHL 0405 | 928 | 1 501 |

- **Oclusión:** decidido el 1 de noviembre de 2026. Las reglas están en `docs/reglas_anotacion.md`.
  - **Qué se anota:** la prueba (FHL 0405), solo los fotogramas con posición múltiplo de 3 (1 de cada 3). Son 310
    fotogramas y 498 personas, y cubren los 18 episodios.
  - **Cajas por persona:**
    - **Una sola caja completa** (cuerpo entero estimado), **del mismo tamaño en las dos imágenes**. Se puede **mover
      en cada imagen** para centrarla sobre la persona, porque el error de alineación en FHL 0405 es de unos 4 px en
      personas de 14 px.
    - Si la persona no se ve en la RGB, la completa RGB queda donde la pone la semejanza, en el lugar de la térmica.
    - Opción (a), decidida el 1 de noviembre de 2026.
    - Una caja visible en cada imagen, o "no visible" (λ = 1).
  - **λ = 1 − área (visible ∩ completa) / área completa**, en cada imagen y con la completa de esa imagen.
  - **"Fuera de cuadro"** no cuenta como oclusión. **"No es persona"** (caja térmica de WiSARD mal puesta) se reporta
    aparte.
  - **Precarga del primer anotador:** la visible térmica es la caja de WiSARD, y la visible RGB es la caja RGB más
    cercana a 3 alturas o menos.
  - **Segundo anotador:** responde sobre una muestra al azar del 15 % (75 personas, seed=0), sin precarga y sin ver
    las respuestas del primero. La concordancia se mide en la fase 4.
    - Modo simple, decidido el 1 de noviembre de 2026 (`anotar_oclusion.py --segundo-simple`).
    - Ve la RGB y la térmica con la caja térmica de WiSARD y responde con una tecla: `1` se ve en la RGB, `2` no se ve
      en la RGB, `3` no es persona. No dibuja cajas.
    - **Ronda 1, regla ambigua** (1 de noviembre de 2026, 63 comparables; las "no es persona" de cualquiera van
      aparte): kappa **0.507** (IC 95 % 0.312 a 0.701), acuerdo 74.6 %.
      - 14 de los 16 desacuerdos son personas que el segundo ve y el primero no. Casi todas están en sombra profunda.
      - **No se acepta tal cual.**
    - **Regla aclarada** (1 de noviembre de 2026, en `docs/reglas_anotacion.md`; la herramienta la muestra en
      pantalla):
      - "Se ve" = reconoces una parte del cuerpo (ropa, cabeza, brazos o piernas) en la RGB con el brillo normal, sin
        realce.
      - Una mancha oscura, una sombra o una rama no cuentan. Si dudas, "no se ve".
      - En el modo simple el realce (`e`) está desactivado.
    - **Ronda 2, regla aclarada:** decidido el 1 de noviembre de 2026.
      - **Los dos anotadores** responden las 75 completas, desde cero, en modo simple: la misma pantalla y la misma
        regla, sin precarga ni cajas RGB y sin ver ningún archivo de respuestas.
      - El primero usa `anotar_oclusion.py --primero-simple`. No revisa a mano solo la 72 y la 75.
      - Pendiente.
    - **Al terminar los dos** (`fase4_validacion_auto.py --partes entre_anotadores --ronda 2`):
      - kappa del primero contra el segundo, los dos en modo simple: **el que decide**;
      - kappa del automático contra el primero en modo simple;
      - cuántas respuestas del primero cambian entre su anotación con cajas y el modo simple.
    - El reporte deja las dos rondas y la anotación con cajas del primero, y explica qué cambió en la regla. Detalle en
      `reports/fase4_validacion_auto.md`.
- **λ RGB automático, validado con la muestra:** decidido el 1 de noviembre de 2026.
  - **Automático, para las 1 501 personas de FHL 0405** (`data/oclusion_auto.csv`):
    - λ = 1 − área(caja RGB más cercana a 3 alturas o menos) / área(caja térmica), recortado entre 0 y 1.
    - La caja RGB es la de WiSARD sin repetidas, llevada a la térmica con la semejanza congelada; es la misma regla
      que la precarga.
    - Sin caja RGB cerca, λ = 1. Nivel con los límites de siempre.
    - Resultado: baja 398, moderada 124 y severa 979. De ellas, 976 no tienen caja RGB cerca; 13 comparten la caja
      RGB con otra persona del mismo par.
  - **Manual, solo de las 75 de la muestra** (`data/oclusion_muestra_segundo.csv`):
    - Las anota el primer anotador con la herramienta en modo `--muestra` (con la precarga) y se guardan en
      `data/oclusion.csv`.
    - La persona 1 (`..._0405_0000_0`), anotada antes y fuera de la muestra, se conserva en ese archivo.
  - **Comparación** (`scripts/fase4_validacion_auto.py`): kappa de Cohen sobre el nivel de **dos clases**, matriz de
    confusión y desacuerdos con sus imágenes. Las personas "no es persona" o "fuera de cuadro" van aparte. El kappa de
    3 niveles (λ por áreas) y la diferencia de λ solo se reportan.
  - **Regla de decisión:**
    - Si el **kappa binario es de 0.61 o más**, se usa el nivel automático.
    - Si no, se vuelve a la anotación manual (las 498 personas de 1 de cada 3).
  - **Resultado** (1 de noviembre de 2026, 68 comparables):
    - Kappa binario **0.940** (IC 95 % 0.858 a 1), acuerdo 97.1 %, 2 desacuerdos (68 y 73). **Se usa el nivel
      automático.**
    - Kappa de 3 niveles 0.675, solo informativo.
    - Detalle en `reports/fase4_validacion_auto.md`.
  - **Revisión antes del kappa** (1 de noviembre de 2026):
    - Se revisaron a ojo las personas con la completa RGB corrida más de 12 px o con una visible RGB en un par
      "solo térmica" (`oclusion_auto.py --revisar`, imágenes en `reports/oclusion/revision_muestra/`).
    - Correcciones del primer anotador en `configs/correcciones_oclusion.yaml`, aplicadas con
      `scripts/corregir_oclusion.py`, que guarda un respaldo en `data\respaldos\`:
      - 8 RGB pasan a "no visible".
      - La 63 tenía cambiadas las teclas `t` y `r`.
      - La 46 y la 38 pasan a "no es persona".
    - Luego el primer anotador ajusta la visible RGB de las 29 con visible (herramienta `--ajuste`), porque las
      visibles se salían de la completa y daban λ = 0.
    - Hecho: ajustó 23 y dejó 6 como estaban. Las 29 se ven enteras (λ RGB de 0 a 0.047).
    - Estado de las 75: 7 "no es persona" y 68 comparables. Baja 29, moderada 0 y severa 39 (la RGB "no visible").
      Detalle en `reports/fase3.md`.
    - Decidido después:
      - 63 y 64 son dos personas; la completa de la 63 se centró en su propia caja.
      - 21, 22 y 58: la visible térmica es la caja de WiSARD, y siguen en severa.
      - Los niveles no cambian.
  - **Pendiente de decidir** (ver `reports/fase4_validacion_auto.md`):
    - si el fotograma 60 de FHL 0405 se excluye por desfase (y 71–72);
    - si se confirman las 7 "no es persona" y qué se hace con la caja de WiSARD de ese objeto (fotogramas 429 a 474)
      en las etiquetas de prueba;
    - si las métricas por nivel van sobre los 310 fotogramas anotados o sobre los 928.
- **Niveles: dos clases**, decidido el 1 de noviembre de 2026, porque en la muestra no hubo ninguna moderada (0 de 68).
  - **Severa:** la persona no se ve en la RGB.
    - Automático: no hay caja RGB de WiSARD a 3 alturas o menos (`sin_caja_rgb_cerca` en `data/oclusion_auto.csv`).
    - Manual: visible RGB "no visible".
  - **Baja:** se ve en la RGB.
  - En FHL 0405: severa 976 y baja 525 de 1 501. En los 310 anotados: severa 323 y baja 175 de 498.
  - Antes eran tres niveles según λ RGB: baja (0 a 35 %), moderada (35 a 70 %) y severa (más de 70 %). Solo se usan
    para reportar la comparación.
- **Configuración base:** 100 épocas, imagen de 640, lote 16 (bajar si no entra en 8 GB; el mismo para los tres),
  optimizador y tasa de aprendizaje por defecto de Ultralytics para YOLO26 (registrar cuáles fueron).
- **Aumento de color (fase 5):** **`hsv_h=0`, `hsv_s=0`, `hsv_v=0` en los tres modelos**, para que entrenen igual.
  - Ultralytics no aplica el aumento HSV a imágenes de 4 canales (`RandomHSV` sale si la imagen no tiene 3), así que
    la fusión no lo recibiría.
  - Al modelo solo térmica solo le cambiaría el brillo.
  - Decidido el 1 de noviembre de 2026.
- **Métricas:** recall, precisión (umbral de confianza 0.5), F2 y mAP@0.5, con script propio sobre pycocotools.
  Decidido el 1 de noviembre de 2026.
  - **Globales** sobre los **928 fotogramas** de prueba, y también sobre los **310 anotados**.
  - **Por nivel de oclusión** sobre los **310 anotados**, los únicos con nivel. Al evaluar un nivel, las personas de los
    otros niveles se marcan como ignoradas.
- **Prueba estadística:** McNemar (statsmodels) entre modelos dentro de cada nivel, corrección de Bonferroni, α = 0.05.
- **Bootstrap por episodio (fase 6):** los intervalos de confianza se calculan remuestreando episodios completos, no
  fotogramas, porque los fotogramas seguidos de un episodio no son independientes. Usa seed=0.
  - Los episodios son tramos seguidos con persona.
  - En la fase 6 se fijan el número de remuestreos y qué episodios se usan: los 18 de FHL 0405, o los 13 que quedan
    si los pares excluidos no cortan.

## Estructura del repositorio

```
configs/     yaml de datasets y de entrenamiento
scripts/     código de cada fase
data/        datos procesados (fuera de git)
reports/     tablas, figuras, resúmenes y bitácora
runs/        salidas de entrenamiento (fuera de git)
docs/        reglas de anotación y notas
```
