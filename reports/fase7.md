# Fase 7: mejorar el resultado sin romper el protocolo

Empezada el 18 de noviembre de 2026, después del diagnóstico (`reports/diagnostico.md`). Según el diagnóstico, la
distancia con WiSARD viene de tres cosas:

- la partición por fotograma (B1 0.985 contra B2 0.328);
- que los vuelos de entrenamiento no se parecen a los de validación;
- las personas diminutas de FHL 0134.

Reglas de esta fase:

- **FHL 0405/0406 (la prueba) no se usa en nada.** Los scripts salen si aparece en la configuración.
- La validación es la de siempre: FHL 0134 y MtErie 0007.
- No se tocan `runs/` ni los datasets existentes. Todo lo nuevo va en `configs/fase7.yaml`, en scripts nuevos, en
  `runs/fase7/` y en este reporte.
- Cada parte deja su fila en la bitácora.

Partes: C0 auditoría, C1 datasets, C2 receta, C3 corridas y C4 evaluación en validación.

## C0. Auditoría de las térmicas anotadas fuera de los 4 617 pares

Scripts:

- `scripts/fase7_c0_auditoria.py`, con las partes `auditar`, `ampliar`, `alineacion`, `clasificar` y `puntos`;
- `scripts/fase7_marcar_puntos.py`, para los puntos a mano;
- `scripts/fase7_copiar.py`, que copia las salidas a `reports/fase7/`.

La configuración está en la sección `c0` de `configs/fase7.yaml`. Las salidas completas quedan en `runs/fase7/c0/` y
una copia liviana en `reports/fase7/c0/` (los PNG como JPEG).

### Qué se hizo

- **26 carpetas IR con etiquetas** que no están en nuestros pares:
  - Airfield FLIR 1–8;
  - Karen FLIR 1–6;
  - Carnation FLIR 1–7;
  - Baker FLIR 1–2 (2020);
  - FHL 0404, 0565 y 0567 (las térmicas de FHL 0403, 0564 y 0566, cuya RGB no tiene etiquetas).
  - Baker IR_2 de 2022 (todos los `.txt` vacíos) queda fuera, como se pidió.
- **Por carpeta** (`auditoria/por_carpeta.csv`): fotogramas, `.txt`, cajas, repetidas, cajas raras, tramos seguidos
  con caja, tamaño de las personas (lado mayor en px de 640 × 512) y tramos de tamaño.
  - Cajas repetidas: 1 en Karen 3, 3 en Karen 4 y 1 en Carnation 1. Se quitan, como en la fase 3a.
  - No hay cajas raras (otra clase o fuera de la imagen).
- **Muestra al azar** (seed 0, un generador por carpeta) de 10 fotogramas con cajas y 10 sin cajas.
  - Va en un mosaico por carpeta (`auditoria/mosaicos/`), con:
    - las cajas en verde y las predicciones en rojo;
    - recortes ampliados de las cajas sin predicción, de las predicciones sin caja y de dónde estaban las cajas del
      fotograma anotado más cercano;
    - un gráfico de todo el vuelo, con las cajas por fotograma y las predicciones ≥ 0.5 sin caja.
  - Además, fotogramas completos que respaldan cada decisión (`revision/`, sección `c0.ampliaciones`).
- **Detector de apoyo:** el `best.pt` de B1 del diagnóstico. Solo sirvió para señalar dónde mirar.
  - B1 se entrenó con el reparto al azar de los 6 vuelos, que incluye los de validación. Por eso **no filtra nada
    automáticamente**: todas las decisiones son a ojo, y sus predicciones no entran en ningún dataset.
  - No vio FHL 0405.
- **Marca de agua "FLIR":** está en la esquina inferior izquierda de las térmicas de 2020 (Baker, Karen y Carnation
  FLIR), y el detector la toma por persona (confianza de 0.55 a 0.73).
  - Se detecta por carpeta (`c0.logo`) y sus predicciones se ignoran.
  - **Para C1:** sigue en las imágenes. Si una persona cae sobre ella, la caja la cubre; si no, es un fondo fijo sin
    caja, que el modelo aprende como "no persona".
- **Bitácora:** la auditoría se corrió 3 veces y dejó 3 filas.
  - La primera no quitaba la marca de agua: 12 403 predicciones ≥ 0.5 sin caja.
  - La segunda y la tercera dan lo mismo: 2 366. Vale la última.

### Personas sin caja y cajas mal puestas

- **Personas sin caja** en fotogramas con `.txt`:
  - **Airfield 3, 985–1061:** una segunda figura humana sin caja junto a la persona anotada, en todo el tramo
    (`revision/210327_Airfield_FLIR_IR_3`).
  - **Airfield 4, 0–58:** la misma escena, con la misma segunda persona sin caja.
  - **Airfield 5, posición 95:** una figura alargada sin caja. Solo hay 2 fotogramas con caja en todo el vuelo.
  - **Airfield 1, 584–666:** una mancha caliente en el matorral, quizá una persona vista desde arriba (el detector le da
    de 0.73 a 0.87). Es dudosa. La de la posición 78 es un árbol.
  - **Karen 1, desde 316:** cajas intermitentes, y una persona sin caja en 451.
  - **Karen 2:** personas sin caja en dos huecos cortos (posiciones 100 y 337), con la caja en los fotogramas vecinos.
  - **FHL 0404, desde 216:** el `.txt` está vacío, pero el grupo de 4 a 7 personas sigue a la vista (el detector da
    hasta 0.86). La anotación se cortó en el fotograma 215.
- **Personas cortadas por el borde:** no tienen caja (Carnation, y Airfield 4 en la 1030). Es la misma convención en
  todas las carpetas, así que se acepta.
- **Cajas mal puestas:** no vi ninguna clara en las muestras.
  - Las "cajas sin predicción" (5 819) son personas que el detector no ve en escenas nuevas: la sombra del dosel en
    Karen 6, Baker FLIR 1 y las copas de FHL 0565.
  - Solo hay una caja dudosa, en el borde superior de FHL 0404 (posición 16), sobre una rama o una persona cortada.
- **Objetos fijos que no son personas:**
  - un disco caliente en los claros de Airfield 4 (484–606), 7 y 8, sin caja en las tres carpetas;
  - arbustos en FHL 0567 (597–885).
  - El detector se equivoca con ellos; las etiquetas están bien.
- **Otros:**
  - Airfield 7 tiene cuadros celestes superpuestos en unos 15 fotogramas;
  - Carnation 7 tiene la cola borrosa (≈ 196–380);
  - Baker FLIR 2 termina con unos 15 fotogramas en blanco.
  - Se dejan: son pocos, y en las dos últimas no hay personas sin caja.

### Clasificación (pendiente de tu confirmación)

Está en `c0.clasificacion` de `configs/fase7.yaml`.

- **Usable:** en la muestra, las cajas caen sobre personas y no hay personas sin caja, salvo las cortadas por el borde.
- **Con tramos:** el problema está en tramos que se quitan.
- **No usable:** faltan personas en los fotogramas anotados, o casi nada está anotado.
- **Regla de los huecos cortos, en todas las carpetas:** se quitan los `.txt` vacíos de 10 fotogramas o menos que tienen
  cajas a los dos lados. En Karen 2 ahí había personas sin caja. Cuesta 140 fotogramas en total.

Columnas de la tabla:

- **Con caja**: fotogramas con alguna caja, antes de quitar nada.
- **Usados**: fotogramas que quedan, con persona o sin ella.
- **Personas** y **lado mediano**: de los fotogramas usados.

| Carpeta | Escena | Fotogramas | Con caja | Usados | Personas | Lado mediano (px) | Clase | Qué se quita |
|---|---|---:|---:|---:|---:|---:|---|---|
| Airfield 1 | bosque con claros y matorral, cenital | 983 | 22 | 882 | 22 | 21 | con tramos | 575–675 (mancha dudosa) |
| Airfield 2 | bosque con claros, cenital | 922 | 413 | 873 | 499 | 19 | usable | 49 en huecos cortos |
| Airfield 3 | campo abierto y bosque, cenital | 1 062 | 295 | 985 | 367 | 49 | con tramos | 985–1061 (segunda persona sin caja) |
| Airfield 4 | campo abierto y dosel, cenital | 1 061 | 83 | 1 002 | 24 | 19 | con tramos | 0–58 (segunda persona sin caja) |
| Airfield 5 | bosque, cenital; muchos fotogramas borrosos | 313 | 2 | 0 | 0 | — | no usable | todo |
| Airfield 6 | huecos del dosel, cenital | 1 059 | 195 | 1 059 | 195 | 17 | usable | — |
| Airfield 7 | huecos del dosel y claros, cenital | 1 059 | 280 | 1 057 | 280 | 17 | usable | 2 en huecos cortos |
| Airfield 8 | superficie oscura y huecos del dosel, cenital | 415 | 97 | 413 | 97 | 22.8 | usable | 2 en huecos cortos |
| Karen 1 | matorral y prado con árboles, oblicua | 452 | 341 | 316 | 316 | 63 | con tramos | 316–451 |
| Karen 2 | matorral, prado y una cabaña, oblicua | 452 | 399 | 440 | 400 | 31 | con tramos | 12 en huecos cortos |
| Karen 3 | matorral y prado, oblicua | 452 | 432 | 444 | 432 | 51 | usable | 8 en huecos cortos |
| Karen 4 | matorral y prado, oblicua | 452 | 452 | 452 | 461 | 46 | usable | — |
| Karen 5 | matorral y prado, oblicua | 452 | 452 | 452 | 919 | 42 | usable | — |
| Karen 6 | prado con la sombra del dosel, oblicua | 451 | 451 | 451 | 1 291 | 25 | usable | — |
| Carnation FLIR 1 | campo abierto, cenital | 183 | 86 | 183 | 236 | 44 | usable | — |
| Carnation FLIR 2 | campo abierto, cenital | 450 | 423 | 450 | 1 230 | 42 | usable | — |
| Carnation FLIR 3 | campo abierto, cenital | 452 | 101 | 452 | 101 | 24 | usable | — |
| Carnation FLIR 4 | campo abierto, cenital | 452 | 61 | 452 | 61 | 33 | usable | — |
| Carnation FLIR 5 | campo abierto, cenital | 452 | 221 | 452 | 221 | 38 | usable | — |
| Carnation FLIR 6 | campo abierto, cenital | 452 | 204 | 452 | 208 | 31 | usable | — |
| Carnation FLIR 7 | campo abierto, cenital | 408 | 118 | 408 | 118 | 66.5 | usable | — |
| Baker FLIR 1 | río con dosel y un puente de troncos, cenital | 912 | 873 | 912 | 994 | 19 | usable | — |
| Baker FLIR 2 | río con dosel y un puente de troncos, cenital | 1 081 | 1 060 | 1 081 | 2 026 | 24 | usable | — |
| FHL 0404 | costa rocosa con troncos y bosque, oblicua | 1 417 | 216 | 216 | 951 | 34 | con tramos | 216–1416 (sin anotar) |
| FHL 0565 | dosel de coníferas, cenital | 982 | 712 | 925 | 1 166 | 20 | usable | 57 en huecos cortos |
| FHL 0567 | costa con acantilado, sendero y casas, oblicua, de noche | 909 | 690 | 899 | 1 095 | 41 | usable | 10 en huecos cortos |
| Carnation Enterprise 0024 (añadida) | campo y borde del bosque, oblicua; después franja de pasto, cenital | 740 | 736 | 736 | 1 714 | 11.3 | usable | 4 en huecos cortos |

**Carnation Enterprise 0024** se auditó después, igual que las demás, cuando decidiste usar su térmica.

- Las cajas están bien.
- En 144 y en 535–537 hay personas sin caja, en huecos cortos que la regla ya quita.
- Las detecciones en las copas de los árboles, arriba del todo, son errores del detector.
- Tiene las personas más chicas de todo el material: mediana de 11 px, 294 de menos de 8 px y 710 de 8 a 12 px.

**FHL 0565 se parece a FHL 0134**, uno de los vuelos de validación: dosel de coníferas visto desde arriba, el mismo
sitio y el mismo día (24 de septiembre de 2021), con el mismo dron.

- Pero es **otro vuelo**, otra grabación (DJI 0564/0565 frente a 0134/0135), así que **no rompe la partición por
  vuelo**: ningún fotograma de validación ni sus vecinos entran en entrenamiento.
- Lo mismo vale para FHL 0404 y 0567, y para los pares excluidos de FHL 0401, que ya era de entrenamiento.
- Lo que sí cambia es que el entrenamiento se parece más a la validación. Era justamente uno de los problemas del
  diagnóstico, y hay que tenerlo en cuenta al leer la mejora.
- La prueba (FHL 0405) también es de ese sitio y día, pero no se usa en esta fase.

**Lo que quedaba sin tope de vacías** con las 26 carpetas, antes de añadir Carnation 0024 (`clasificacion/por_sitio.csv`),
comparado con el entrenamiento actual (diagnóstico, A3). La composición final, con el tope, está en C1:

| Sitio | Fotogramas usados | Con persona | Personas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Airfield | 6 271 | 1 249 | 1 484 | 31 | 65 | 547 | 432 | 409 |
| Baker FLIR | 1 993 | 1 933 | 3 020 | 0 | 8 | 774 | 1 929 | 309 |
| Carnation FLIR | 2 849 | 1 214 | 2 175 | 0 | 0 | 8 | 304 | 1 863 |
| FHL (0404, 0565, 0567) | 2 040 | 1 618 | 3 212 | 2 | 86 | 548 | 1 158 | 1 418 |
| Karen | 2 555 | 2 502 | 3 819 | 0 | 3 | 384 | 859 | 2 573 |
| **Nuevo, total** | **15 708** | **8 516** | **13 710** | **33** | **162** | **2 261** | **4 682** | **6 572** |
| Entrenamiento actual | 3 247 | — | 9 340 | 22 | 159 | 1 459 | 2 411 | 5 289 |

- 7 192 de esos fotogramas (46 %) no tienen personas. 5 022 son de Airfield. Por eso se puso el tope de vacías de C1.

### Alineación de FHL 0403, 0564 y 0566 (RGB sin etiquetas)

Son vuelos del mismo dron y del mismo día que FHL 0134, 0401 y 0405. Se probó si la semejanza congelada de alguno
alinea su RGB con la térmica.

- **Qué hay en la RGB** (`c0.alineacion.vuelos`):
  - **0403:** de día, costa con troncos.
    - Se usarían solo las posiciones 0–215, porque su térmica (0404) solo está anotada ahí.
  - **0564:** de día, dosel de coníferas.
  - **0566:** **de noche**.
    - Brillo medio de 7 a 17 sobre 255 y marca de hora 19:4x. Solo se ven las luces de un muelle y una baranda.
- **Medida automática** (`--parte alineacion`): la RGB se lleva a la térmica con cada semejanza candidata. Luego se mide
  el corrimiento del fondo con la correlación de fase de los gradientes, la misma de la fase 2.
  - Se miden 40 pares repartidos por vuelo.
  - Solo cuentan los pares con respuesta ≥ 0.10.
  - Referencias: FHL 0134 y 0401, cada una con su propia semejanza.
- **Criterio, fijado antes de medir** (`c0.alineacion.criterio`). Una semejanza alcanza si cumple las dos condiciones:
  - el corrimiento mediano del fondo es ≤ 1.5 veces la mayor mediana de las referencias;
  - y el error medio con los puntos a mano es ≤ 13.2 px, el de la fase 2 en FHL.

| Vuelo | Semejanza | Pares fiables | Corrimiento mediano (px) | p90 (px) |
|---|---|---:|---:|---:|
| FHL 0134 (referencia) | la suya | 32 de 40 | 6.02 | 11.34 |
| FHL 0401 (referencia) | la suya | 36 de 40 | 2.29 | 20.14 |
| FHL 0403 | 0134 | 38 de 40 | 4.00 | 5.53 |
| FHL 0403 | **0401** | 40 de 40 | **1.44** | 3.73 |
| FHL 0403 | 0405 | 30 de 40 | 4.05 | 5.64 |
| FHL 0564 | 0134 | 21 de 40 | 5.33 | 22.69 |
| FHL 0564 | **0401** | 31 de 40 | **3.36** | 19.25 |
| FHL 0564 | 0405 | 18 de 40 | 5.55 | 17.86 |
| FHL 0566 | 0134 | 12 de 40 | 3.45 | 4.92 |
| FHL 0566 | 0401 | 12 de 40 | 1.47 | 1.74 |
| FHL 0566 | 0405 | 12 de 40 | 3.42 | 5.87 |

- El límite del fondo es 1.5 × 6.02 = **9.02 px**. Todas las semejanzas lo pasan.
- **La de 0401 es la mejor en los tres vuelos.** Además es de un vuelo de entrenamiento.
  - La de 0405 se midió porque se pidió, pero no se adopta: se estimó con las cajas de la prueba.
- **0564:** el p90 de 19 px indica pares con el fondo corrido, como los desfases de la fase 2, o con la RGB movida (la
  posición 245 está borrosa).
  - Si se usa, propongo quitar en C1 los pares con el fondo corrido más de 20 px. Es el umbral de la extensión por el
    fondo de la fase 2, porque aquí no hay cajas RGB para aplicar la regla de desfase.
- **0566:** solo 12 de 40 pares tienen una medida fiable (respuesta mediana 0.02), así que la medida automática no
  vale.
- **Superposiciones** (`alineacion/superposicion_*`, los bordes de la RGB llevada sobre la térmica): los bordes de la
  vegetación lo llenan todo y no permiten juzgar a ojo. Quedan como referencia, pero no deciden.
- **Puntos a mano.** Los marcó el usuario el 18 de noviembre de 2026, 2 fotogramas por vuelo y 6 puntos o más por
  fotograma (`configs/fase7_puntos_control/`).
  - Usó la herramienta de la fase 2, sin cambiarla, con `scripts/fase7_marcar_puntos.py`.
  - Fotogramas: los más nítidos cerca de 1/3 y 2/3 del rango (`c0.marcado.fotogramas`).
    - 0403: 63 y 156 (7 y 6 puntos).
    - 0564: 345 y 663 (6 y 6 puntos).
    - 0566 no se marcó: el usuario decidió usarlo sin pareja.
  - La sugerencia celeste es la de la fase 2: la franja nominal y luego la de los propios puntos. No usa ninguna de las
    semejanzas que se miden, así que no ancla a ellas.
  - `--parte puntos` mide el error de las 3 semejanzas (`alineacion/puntos.csv` y `puntos_resumen.csv`).

**Resultado de los puntos:**

| Vuelo | Semejanza | Puntos | Error medio (px) | Mediano (px) | Máximo (px) | ¿Pasa (≤ 13.2)? |
|---|---|---:|---:|---:|---:|---|
| FHL 0403 | 0134 | 13 | 15.9 | 14.6 | 33.1 | no |
| FHL 0403 | 0401 | 13 | 18.0 | 17.0 | 39.2 | no |
| FHL 0403 | 0405 | 13 | 15.2 | 13.7 | 32.8 | no |
| FHL 0564 | 0134 | 12 | 24.4 | 17.1 | 84.7 | no |
| FHL 0564 | 0401 | 12 | 28.3 | 21.3 | 89.8 | no |
| FHL 0564 | 0405 | 12 | 23.2 | 14.7 | 81.5 | no |

- **Ninguna semejanza pasa en ninguno de los dos vuelos.** Por la regla que fijó el usuario antes de medir, **FHL 0403 y
  0564 entran solo como térmica sin pareja** (`c1.pares_reales.aprobados: []`).
- **Limitación: los puntos no encajan entre sí.**
  - Su propia semejanza, ajustada con todos los puntos del fotograma, les deja un error medio de 11.4 y 17.9 px en
    0403, y de 24.1 y 17.9 px en 0564.
  - Si se quita un punto y se ajusta la semejanza con los demás, el punto quitado cae a 20 px (mediana) en 0403 y a
    28 px en 0564. En la fase 2 esa coherencia era de unos 10 px.
  - En 0564 hay dos puntos de 49 y 85 px con las tres semejanzas: probablemente no son el mismo objeto en las dos
    imágenes. En las copas y las orillas es difícil marcar.
  - Así, esta medida está dominada por el error de marcado más que por la alineación. La del fondo (1.4 y 3.4 px con
    0401) apuntaba a una buena alineación.
  - Se aplica la regla tal como quedó fijada. El efecto es pequeño: 970 de las 14 110 imágenes de entrenamiento quedan
    con la RGB en 0 en vez de real.
- El cálculo de la coherencia se cambió antes de este resultado.
  - Antes usaba `cv2.estimateAffinePartial2D` (LMEDS), que fallaba con este tipo de tabla.
  - Ahora es una semejanza por mínimos cuadrados (Umeyama), comprobada con datos sintéticos.
  - El error de las semejanzas candidatas no cambia.

### Decisiones del usuario al cerrar C0 (18 de noviembre de 2026)

Están en los comentarios de la sección `c1` de `configs/fase7.yaml`.

1. **Se confirman** la clasificación de las 26 carpetas y la regla de los huecos cortos.
   - Además, las imágenes nuevas sin persona serán como máximo el 10 % del total de entrenamiento, al azar (seed 0) y
     repartidas por carpeta.
2. **FHL 0566:** solo como térmica sin pareja (RGB en 0). No se marcan sus puntos.
3. **Carnation 0023/0024:** su térmica entra en `termico_ampliado` y, como térmica sin pareja, en `fusion_ampliado`.
   Se auditó como una carpeta más (arriba).
4. **Pares anotados y excluidos de los vuelos de entrenamiento:** entran, menos el tramo de Baker 2031–2179. En
   `fusion_ampliado` van como térmica sin pareja.
5. **FHL 0403 y 0564:** el usuario marca sus puntos.
   - Si un vuelo no pasa el criterio de 13.2 px, entra solo como térmica sin pareja.
   - Si pasa, entra como pares reales con la semejanza de 0401.
   - **Resultado: no pasa ninguno** (arriba), así que los dos entran como térmica sin pareja.

## C1. Datasets nuevos

`scripts/fase7_c1_datasets.py`, sección `c1` de `configs/fase7.yaml`. Salidas en `runs/fase7/c1/`.

### Composición (`--parte componer`)

- **`termico_ampliado` y `fusion_ampliado` tienen las mismas imágenes.** Solo cambia si los canales RGB son reales
  o van en 0. Así, la diferencia entre los dos modelos es solo la modalidad.
- **Base:** el entrenamiento actual (3 247 imágenes de los 4 vuelos), sin cambios.
- **Nuevas:**
  - los fotogramas de C0 que quedan tras la clasificación y los huecos cortos;
  - los 216 pares anotados y excluidos de los vuelos de entrenamiento: 28 de MtErie 0003, 15 de MtErie 0005, 113 de
    FHL 0401 y 60 de Baker, sin el tramo 2031–2179. A estos no se les aplica la regla de los huecos cortos, porque
    sus etiquetas ya se revisaron en las fases 1 y 2.
- **Tope de vacías nuevas:**
  - E ≤ 0.10 × (base + nuevas con persona + E), es decir, E ≤ (3 247 + 9 452) / 9 = **1 411**, de 7 208 disponibles.
  - El cupo se reparte por carpeta en proporción a sus vacías, con restos mayores, y se elige al azar dentro de cada
    una (seed 0).
- **Controles:** el script sale si alguna carpeta nueva es de validación o de prueba, o si una imagen nueva ya está en la
  base o tiene el nombre repetido.
- **Validación:** la de siempre, 442 imágenes.

| Parte | Imágenes | Con persona | Vacías | Personas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Base (entrenamiento actual) | 3 247 | 3 061 | 186 | 9 340 | 22 | 159 | 1 459 | 2 411 | 5 289 |
| Nuevas | 10 863 | 9 452 | 1 411 | 15 965 | 327 | 891 | 3 086 | 4 917 | 6 744 |
| **Total de entrenamiento** | **14 110** | **12 513** | **1 597** | **25 305** | **349** | **1 050** | **4 545** | **7 328** | **12 033** |

Las nuevas, por sitio:

| Sitio | Imágenes | Con persona | Vacías | Personas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Airfield | 2 231 | 1 249 | 982 | 1 484 | 31 | 65 | 547 | 432 | 409 |
| Baker (FLIR 2020 y excluidos) | 1 992 | 1 977 | 15 | 3 075 | 0 | 8 | 774 | 1 930 | 363 |
| Carnation (FLIR 2020 y Enterprise 0024) | 2 271 | 1 950 | 321 | 3 889 | 294 | 710 | 652 | 362 | 1 871 |
| FHL (0404, 0565, 0567 y excluidos de 0401) | 1 814 | 1 731 | 83 | 3 565 | 2 | 105 | 696 | 1 242 | 1 520 |
| Karen | 2 512 | 2 502 | 10 | 3 819 | 0 | 3 | 384 | 859 | 2 573 |
| MtErie (excluidos) | 43 | 43 | 0 | 133 | 0 | 0 | 33 | 92 | 8 |

- Las personas de menos de 12 px pasan de 181 a 1 399. 1 004 de ellas son de Carnation 0024. En validación, 115 de las
  500 personas miden menos de 12 px.
- El detalle por carpeta, con las vacías disponibles y las elegidas, está en `c1/por_carpeta.csv`. La lista de
  imágenes, con su fuente y si su RGB es real, está en `c1/composicion.csv`.
- Las 982 vacías de Airfield son el 70 % del cupo, porque Airfield tiene la mayoría de las vacías disponibles (5 022 de
  7 208).
- **RGB real:** FHL 0403 y 0564 no pasaron los puntos. Así que en `fusion_ampliado` solo tienen RGB real las 3 247
  imágenes de la base y las 442 de validación. Las 10 863 nuevas van con la RGB en 0, y la lista está en
  `c1/rgb_real.csv`.

### Tiempo estimado por época

El tiempo por imagen de entrenamiento se midió con `epocas.csv` (mediana, sin la época 1). Es de 12.0 ms en la térmica
(B2) y 12.3 ms en la fusión (`fusion_100ep`), más unos 3 s de validación.

| Modelo | Imágenes de entrenamiento | s por época | 100 épocas |
|---|---:|---:|---:|
| `termico_ampliado` | 14 110 | ≈ 173 | ≈ 4.8 h |
| `fusion_ampliado` | 14 110 | ≈ 176 | ≈ 4.9 h |
| Base actual (como referencia) | 3 247 | ≈ 42 | ≈ 1.2 h |

Con `patience=20` pueden parar antes. Es una estimación lineal: la primera época de cada corrida la confirma.

### Construcción (`--parte construir`)

**Imágenes nuevas.** Se escribieron las 10 863 elegidas en `data/fase7/`, que no va a git. Tardó 123 s con 6 procesos.

- **Térmica:** en gris (PNG de 1 canal), como en la fase 2, en `termica/<carpeta>/`. Ocupa 1.7 GB.
- **TIFF de 4 canales:** en `fusion/<carpeta>/`, con las muestras B, G, R y térmica, comprimido como en la fase 2
  (deflate y predictor horizontal). Ocupa 2.5 GB.
  - Como ninguna nueva tiene pareja real, B, G y R van en 0.
- **Etiquetas:** las térmicas sin repetidas, con la misma regla que la fase 3a, en `etiquetas/<carpeta>/`.

**Datasets.** Están en `data/fase7/datasets/{termico_ampliado,fusion_ampliado}/`, cada uno con su yaml, y se armaron
con enlaces duros.

- El entrenamiento base y la validación enlazan a los archivos de `data/datasets/termico` y `data/datasets/fusion`,
  sin modificarlos ni escribir en ellos.
- Las imágenes nuevas enlazan a `data/fase7/`.
- `rgb_real.csv` marca qué imágenes de `fusion_ampliado` tienen RGB real: las 3 247 de la base y las 442 de
  validación.

**Verificación**, con el dataset de Ultralytics (`c1/datasets.csv` y `c1/verificacion.csv`):

| Dataset | Entrenamiento: imágenes leídas | Cajas | Validación: imágenes | Cajas |
|---|---:|---:|---:|---:|
| `termico_ampliado` | 14 110 de 14 110 | 25 305 | 442 | 500 |
| `fusion_ampliado` | 14 110 de 14 110 | 25 305 | 442 | 500 |

- Las cajas de entrenamiento son las 9 340 de la base más las 15 965 nuevas de `composicion.csv`. No hay imágenes
  corruptas.
- **Muestra de 8 imágenes nuevas** (seed 0), leídas como las recibe el modelo:
  - en `termico_ampliado`: tensor de 3 canales, los tres iguales a la térmica en gris (diferencia máxima 0);
  - en `fusion_ampliado`: tensor de 4 canales, R, G y B en 0 y el cuarto igual a la térmica (diferencia máxima 0).
- La creación del dataset escribió `labels/train.cache` y `labels/val.cache`, pero solo en las carpetas nuevas.
- Ultralytics avisó de lectura lenta del disco (16 MB/s) mientras verificaba; lo vigilaré en la primera época de C3.
- Bitácora: una fila con las cuentas de los dos datasets.
- **Para C2:** en `fusion_ampliado`, el 77 % de las imágenes de entrenamiento (10 863 de 14 110) ya llevan la RGB en
  0. Con el dropout de p = 0.3 de C2 encima, la RGB real quedaría en un 16 % de las imágenes de cada época
  (0.7 × 3 247 / 14 110). Por eso el usuario fijó p = 0 (C2, abajo).

## C2. Receta para objetos pequeños

Va en `scripts/fase7_entrenar.py`, con las secciones `c2` y `c3` de `configs/fase7.yaml`. El dropout está en
`scripts/modalidad.py`.

### Qué cambia frente a la fase 5

`scripts/entrenar.py` no cambia: se reutilizan sus comprobaciones previas (aplicaciones cerradas, enchufe, plan de
energía y potencia, con los valores de `configs/fase5.yaml`), el monitor, el registro por época y el inicio del cuarto
canal.

- **Mejor época por el mAP@0.5 de validación.**
  - El entrenador reemplaza `validate` de Ultralytics, cuyo fitness en 8.4.194 es solo el mAP@0.5:0.95.
  - Con eso, `best.pt`, `best_fitness` y la parada temprana (cuando la hay) van por `metrics/mAP50(B)`.
  - `last.pt` queda con la última época corrida.
  - `resumen.json` guarda la época elegida, la última y si paró antes. También comprueba que `best.pt` sea la elegida.
- **Dropout de modalidad** (`p_sin_rgb`, por corrida):
  - en la fusión, cada imagen de entrenamiento pierde la RGB con probabilidad p: sus 3 canales de color van en 0;
  - actúa al leer la imagen, así que en el mosaico cada una de las 4 imágenes se decide por separado;
  - nunca en la validación;
  - con p = 0, el entrenador deja el dataset de Ultralytics sin cambios y no gasta ningún número al azar.
- **Lo demás, como en la Tabla 8:**
  - imgsz 640, lote 16 y seed 0; las épocas, en C3 (primero 100 con `patience: 20`, luego 50 sin parada temprana);
  - `hsv_h = hsv_s = hsv_v = 0`;
  - 4 procesos de lectura y `cache: false`.
- **Optimizador fijo:** AdamW con lr0 = 0.002, momentum (beta1) 0.9 y `warmup_bias_lr = 0`.
  - Es justo lo que eligió `optimizer=auto` en la fase 5.
  - Hay que fijarlo porque `auto` elige por el número de iteraciones. Con los datasets ampliados son 221 lotes de 64 ×
    100 épocas = 22 100 iteraciones (con 50 épocas, 11 050), más de 10 000, y `auto` cambiaría a MuSGD con
    lr0 = 0.01.
  - Así, las corridas 2 y 4 solo cambian los datos. En las corridas base da lo mismo que `auto`: 5 100 iteraciones,
    AdamW con 0.002. `resumen.json` lo confirma en cada corrida.
- **Sin FHL 0405:** el script no entrena si en el entrenamiento o la validación aparece alguna imagen de FHL 0405/0406.
- **Registro:** al parar antes, la validación final de `best.pt` no se anota como una época más en `epocas.csv`.

### Decisión del usuario: p = 0 en `fusion_ampliado` (19 de noviembre de 2026)

Está anotada en la bitácora antes de C3, con sus palabras:

> p se cambia de 0.3 a 0 porque el 77 % de las imágenes de entrenamiento ya tienen la RGB en 0; así la corrida 4 solo
> cambia los datos frente a la base. El dropout queda como ablación posterior.

El dropout queda programado y verificado, con p = 0 en las cuatro corridas de C3 (`c3.corridas`).

### Verificación (`--verificar`, sin entrenar)

Se corrió con 8 imágenes del entrenamiento base de la fusión, que tienen RGB real (seed 0). Las salidas están en
`c2/verificacion_fitness.csv` y `c2/verificacion_dropout.csv`.

| Prueba | Imágenes | Resultado |
|---|---:|---|
| Criterio, con un validador simulado de 2 épocas: mAP@0.5 de 0.30 y 0.25, mAP@0.5:0.95 de 0.10 y 0.12 | — | Elige la época 1 (Ultralytics elegiría la 2). El `fitness` de Ultralytics sale de las métricas. Con `patience: 20`, paraba en la época 21; con la receta nueva (`patience: 0`), no para en 51 épocas sin mejora. |
| Entrenamiento con p = 0.3: la imagen leída, donde actúa el dropout | 8 | 1 sin RGB, la que tocaba por la semilla. La térmica, igual en las 8. Las otras 7, iguales al TIFF. |
| Entrenamiento con p = 1: el tensor con todos los aumentos (mosaico) | 8 | No llega nada de la RGB, solo el relleno gris de Ultralytics. La térmica, igual a la del mismo dataset sin dropout con las mismas semillas. |
| Entrenamiento con p = 0 | — | El entrenador deja el `YOLODataset` de Ultralytics. |
| Tensor sin aumentos, como entra al modelo, con p = 0.3 | 8 | 1 sin RGB. Las demás, iguales al TIFF en R, G, B y T. |
| Validación armada por el entrenador con p = 0.3 | 8 | Sin dropout: `YOLODataset`, y las 8 con su RGB. |
| Evaluación con la RGB en 0 (p = 1) | 8 | Las 8 sin RGB, con la térmica igual. |

- **Relleno:** lo que queda fuera de la imagen (letterbox y mosaico), Ultralytics lo rellena con gris 114 en los 4
  canales.
  - Por eso, con la RGB en 0, el modelo ve la RGB negra rodeada de gris.
  - En el mosaico, los píxeles con RGB distinta de 0 coinciden con el relleno del mismo tensor sin dropout: de 0 % a
    34.8 % de la imagen según el mosaico, con a lo más 0.3 puntos de diferencia, que son los bordes interpolados.
  - Pasa igual con las 10 863 imágenes sin pareja de `fusion_ampliado`. No se cambia: es lo que hace Ultralytics en
    todas las corridas.

### Evaluador: la prueba con la RGB en 0

Se agregó a `scripts/evaluar.py` la opción `--rgb-cero`.

- Los modelos de 4 canales (la fusión) reciben la RGB en 0: los 3 canales de color de cada imagen van en 0 al leerla,
  con el mismo `scripts/modalidad.py` y p = 1. La térmica queda igual. Los modelos de 3 canales no cambian.
- Las predicciones van a `<modelo>_rgb0/` y las salidas llevan el sufijo `_rgb0`. Así no se mezclan con las de
  siempre ni cuentan para "una sola vez".
- Sin la opción, el evaluador hace exactamente lo mismo que antes.
- **En la prueba** funciona ya con `--solo-predecir`. La evaluación completa de la prueba sigue esperando los umbrales
  por modelo de validación (F2), como antes.
- **En la fase 7 no se corre en la prueba** (FHL 0405). Solo se probó con `--solo-verificar` en validación.
  - `--modelos fusion termico`: la RGB en 0 va solo para la fusión.
  - `--modelos termico`: se niega, porque ningún modelo tiene 4 canales.

## C3. Corridas

Se corren con `scripts/fase7_entrenar.py --corrida NOMBRE`, en este orden: `termico_base`, `termico_ampliado`,
`fusion_base` y `fusion_ampliado`.

- **Receta común**, comprobada al mezclar `c3.base` con cada corrida:
  - seed 0 (`deterministic: true`) y lote 16;
  - **50 épocas, sin parada temprana (`patience: 0`) y `close_mosaic: 10`** (receta nueva, abajo);
  - imgsz 640, 4 procesos de lectura (`workers: 4`), `cache: false` y `hsv = 0`;
  - AdamW con lr0 = 0.002, momentum 0.9 y `warmup_bias_lr = 0`;
  - `p_sin_rgb = 0`.
- **Lo que cambia:** los datos, y el inicio del cuarto canal (`promedio`, solo en la fusión).
- **Decisiones previas** (19 de noviembre de 2026, en la bitácora):
  - el usuario confirma el optimizador fijo;
  - después de `termico_base_p20`, el usuario cambia la receta (abajo).
- **Cifra principal en C4:** la de la última época y el promedio de las 5 últimas de `results.csv`
  (`c3.ultimas_epocas`). `best.pt` (mayor mAP@0.5 de validación) va como dato secundario. `resumen.json` y la
  bitácora ya llevan las tres.

### Intentos que no entrenaron

| Fecha | Corrida | Comprobación que falló | Qué se hizo |
|---|---|---|---|
| 19 de noviembre de 2026, 10:57 | `termico_base` (la que luego fue `termico_base_p20`) | Chrome abierto (`cerrar_antes`). Salió con el código 3, antes de la prueba de potencia. | Nada se entrenó ni se escribió en la carpeta de la corrida. El registro está en `runs/fase7/termico_base_p20_intento1.log`. Se pide al usuario cerrar Chrome. |

### Corrida 1, receta anterior: `termico_base_p20` (19 de noviembre de 2026)

Se corrió como `termico_base`, con 100 épocas y `patience: 20`. Después se renombró a `termico_base_p20`: la carpeta
`runs/fase7/termico_base_p20/`, su registro y la copia en `reports/fase7/termico_base_p20/`. Su `resumen.json`,
`args.yaml` y su fila de entrenamiento en la bitácora conservan el nombre con que se corrió. Otra fila de la bitácora
la deja como evidencia de que `patience: 20` cortó el calendario. Se lanzó después de cerrar Chrome.

- **Comprobaciones:** enchufada, plan Performance, 97.5 W en la prueba previa (mediana) y AdamW con lr0 = 0.002, como
  se pidió.
- **Durante el entrenamiento:** límite aplicado de 85.5 W (mediana), pico de memoria de la GPU de 5 287 de 8 188 MiB,
  pico de RAM del 99.8 % y 43 s por época (mediana).
- **Paró por `patience` en la época 30:** 20 épocas seguidas sin superar la 10.
  - Las 30 épocas fueron con mosaico, porque `close_mosaic` actúa en las 10 últimas de 100.
  - La tasa de aprendizaje bajó poco, de 0.0020 a 0.0014, porque el descenso lineal está pensado para 100 épocas.
- **`best.pt` es la época 10.** `resumen.json` comprueba que coincide con la de mayor mAP@0.5 de `results.csv`.

| | Época | mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|
| Elegida (`best.pt`) | 10 | 0.384 | 0.174 | 0.550 | 0.402 |
| Validación final de `best.pt` (Ultralytics) | — | 0.383 | 0.173 | 0.546 | 0.396 |
| Última (`last.pt`) | 30 | 0.195 | 0.100 | 0.397 | 0.248 |

**mAP@0.5 de validación por época:**

| Épocas | Valores |
|---|---|
| 1–10 | 0.211, 0.314, 0.314, 0.263, 0.255, 0.237, 0.251, 0.355, 0.166, **0.384** |
| 11–20 | 0.230, 0.370, 0.233, 0.244, 0.185, 0.326, 0.215, 0.274, 0.227, 0.298 |
| 21–30 | 0.227, 0.194, 0.266, 0.193, 0.247, 0.240, 0.286, 0.280, 0.207, 0.195 |

- **Curva muy ruidosa:**
  - de la época 9 a la 10 sube 0.217 (de 0.166 a 0.384), y en la 11 vuelve a 0.230;
  - en las épocas 21–30 va de 0.193 a 0.286, con mediana 0.234;
  - las tres mejores son la 10 (0.384), la 12 (0.370) y la 8 (0.355).
- **Limitación:** elegir el máximo de una curva tan ruidosa sobre la misma validación da una cifra optimista. El 0.384
  es en parte una época con suerte, y C4 tiene que leerse con eso en cuenta.
- **Referencia, mismo dataset:** B2 (30 épocas con la receta de la fase 5) tuvo un máximo de 0.327 en la época 3 y
  0.189 en la última.

### Receta nueva, antes de las corridas 2 a 4 (decisión del usuario, 19 de noviembre de 2026)

- **Motivo:** `termico_base_p20` paró por `patience` en la época 30 de 100.
  - La tasa de aprendizaje seguía alta (0.0014 de 0.0020).
  - El mosaico estaba activo en las 30 épocas.
  - Así que no completó la receta.
- **Cambio, en las cuatro corridas:** 50 épocas, sin parada temprana (`patience: 0`) y `close_mosaic: 10`. Lo demás,
  igual: seed 0, lote 16 y AdamW con lr0 = 0.002.
  - En Ultralytics 8.4.194, `patience: 0` desactiva la parada temprana, porque `EarlyStopping` usa `patience or inf`.
  - La verificación de C2 se repitió con la receta nueva: no para en 51 épocas sin mejora.
- **Se siguen guardando** `best.pt` (por mAP@0.5) y `last.pt`.
- **Con 50 épocas:**
  - la tasa de aprendizaje baja de 0.002 a 0.00002 (`lrf: 0.01`) a lo largo de las 50;
  - las épocas 41 a 50 van sin mosaico.
- **Tiempo:** unos 36 min `termico_base` y unos 2.4 h `termico_ampliado` (50 épocas de unos 43 s y 175 s).

### RAM al entrenar

- **Configuración:** `cache: false` (las imágenes se leen del disco en cada lote) y `workers: 4`. El caché no está en
  RAM, así que, por la regla del usuario, no se cambia nada y el tiempo por época sigue igual.
- **Por qué llega al 99.8 %** (`monitor.csv` de `termico_base_p20`, 16 GB en total):
  - **Antes de entrenar ya había 9.3 GB usados (58 %).** Lo midió `psutil` con la laptop en reposo, sin ningún
    entrenamiento.
    - Son Windows y las aplicaciones abiertas: en ese momento Chrome (1.7 GB, vuelto a abrir), VS Code (0.7 GB),
      Discord (0.5 GB), WhatsApp y Copilot (0.3 GB).
    - Solo Chrome, ChatGPT y Roblox están en `cerrar_antes`.
  - **Al arrancar:** el proceso de entrenamiento con CUDA llega a 11.5 GB (72 %).
    - Los 4 procesos de lectura del entrenamiento lo suben a 13.4–15.3 GB.
    - En la primera validación, Ultralytics abre 8 más (`workers × 2`), y llega a 15.6 GB (97.7 %).
    - En Windows cada proceso de lectura es un Python nuevo que vuelve a cargar torch.
  - **A lo largo de la corrida:** mediana del 88.7 %, más del 95 % el 16.7 % del tiempo y más del 98 % solo el 1.6 %.
    - El pico (99.8 %) es un instante.
    - Mientras la GPU trabaja (uso ≥ 50 %), la mediana es del 88.4 %; en las validaciones y los cambios de época, del
      93.3 %.
  - No hubo errores, y Windows usó poco el archivo de paginación (7.9 % de 20 GB).
  - Igual que en la fase 5a (98.7–99.9 %).

## Comandos

```
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte auditar
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte ampliar
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte alineacion
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte clasificar
.venv\Scripts\python.exe scripts\fase7_marcar_puntos.py --config configs\fase7.yaml --rutas configs\rutas.yaml --vuelo 210924_FHL_Enterprise_0403
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte puntos
.venv\Scripts\python.exe scripts\fase7_c1_datasets.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte componer
.venv\Scripts\python.exe scripts\fase7_c1_datasets.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte construir
.venv\Scripts\python.exe scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --verificar
.venv\Scripts\python.exe scripts\evaluar.py --config configs\fase6.yaml --rutas configs\rutas.yaml --particion validacion --modelos fusion termico --rgb-cero --solo-verificar
.venv\Scripts\python.exe scripts\fase7_copiar.py --config configs\fase7.yaml --rutas configs\rutas.yaml
```
