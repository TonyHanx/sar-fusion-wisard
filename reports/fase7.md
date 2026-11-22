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
| 19 de noviembre de 2026, 12:11 | `termico_base` (receta nueva) | Chrome abierto otra vez: se vio antes de lanzar, así que no se lanzó. | Se pidió al usuario cerrarlo. |
| 19 de noviembre de 2026, 13:04 | `termico_base` (receta nueva) | Pasó las comprobaciones (96.8 W) y entrenó 40 épocas. Claude Code detuvo el proceso en la época 41 de 50, la primera sin mosaico, porque la RAM del sistema estaba casi agotada. No fue un error del entrenamiento. | `results.csv` y `last.pt` llegan a la época 40. No hay `resumen.json`, `epocas.csv` ni `monitor.csv`, porque el script no llegó a escribirlos. Fila en la bitácora. No se usa ni se relanza sin confirmación del usuario. A pedido del usuario se renombró a `runs/fase7/termico_base_cortada/` (y su registro a `termico_base_cortada.log`), como `rgb_100ep_cortada` en la fase 5. |

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

### Antes de relanzar `termico_base` (19 de noviembre de 2026)

**Dónde se corre.** El usuario la corre en su propia ventana de PowerShell, fuera de Claude Code. Así no la corta la
protección de memoria de Claude Code. Las comprobaciones del script son las mismas.

**Guardado por época** (`scripts/fase7_entrenar.py`):
- `epocas.csv` y `monitor.csv` se escriben al final de cada época, en la carpeta de la corrida. Al terminar se
  escriben completos, como antes.
- Se escriben en un temporal que luego se renombra, así que un corte no deja un archivo a medias.
- Solo cambian los callbacks, que escriben archivos después de medir el tiempo de la época. El entrenamiento no
  cambia.
- Se probó sin entrenar, con un entrenador simulado de 3 épocas y el monitor real:
  - tras cada época, los dos archivos tienen las filas hasta esa época;
  - la validación final de `best.pt` no agrega una fila.

**`cache`:**
- En `configs/fase7.yaml` es `false`.
- También es `false` en `configs/fase5.yaml` y en `configs/diagnostico.yaml`, y en el `args.yaml` de todas las corridas
  anteriores: las de la fase 5, B1, B2, `termico_base_p20` y `termico_base_cortada`.
- `workers: 4` en todas, salvo `fusion_lote16_2ep` (8).
- No se cambian épocas ni workers.

### Pérdidas de entrenamiento y de validación, y el pico temprano

Datos: `results.csv` de cada corrida. La pérdida de validación es la que calcula Ultralytics en cada época, sobre los
442 fotogramas de validación. Las medianas son por tramo de 10 épocas.

**`termico_base_cortada`** (épocas 1 a 40 de 50, todas con mosaico):

| Épocas | mAP@0.5 | box (entren.) | cls (entren.) | box (val.) | cls (val.) |
|---|---:|---:|---:|---:|---:|
| 1–10 | 0.211 | 1.268 | 0.598 | 2.186 | 8.546 |
| 11–20 | 0.273 | 1.091 | 0.430 | 2.225 | 5.215 |
| 21–30 | 0.258 | 1.001 | 0.370 | 2.119 | 4.393 |
| 31–40 | 0.261 | 0.918 | 0.317 | 2.148 | 4.167 |

- **La pérdida de entrenamiento baja en todas las épocas.** La `box` va de 1.32 a 0.89, y la `cls`, de 1.33 a 0.30.
  La correlación de Spearman con la época es −1.00 en las dos.
- **La de validación no sube:**
  - la `box` queda plana, entre 2.01 y 2.46, con Spearman −0.03;
  - la `cls` baja de 8.5 a 4.2 (Spearman −0.55), con mucho ruido (3.6 a 14.5).
- **No es el sobreajuste clásico**, en que la validación empeora mientras el entrenamiento mejora.
  - El mAP@0.5 de validación sube en las primeras 10–15 épocas y después queda en una meseta de 0.26 (mediana),
    con saltos de época a época de hasta 0.16.
  - Lo que sí hay es una **brecha grande y constante**: en las épocas 31–40, la `box` es 2.15 en validación contra 0.92
    en entrenamiento, y la `cls`, 4.2 contra 0.32.
  - Desde la época 10–15, el modelo sigue ajustando los vuelos de entrenamiento sin mejorar en los de validación.
    Apunta a la diferencia entre esos vuelos (FHL 0134 y MtErie 0007, bajo el dosel), no a que memorice.
  - La parte sin mosaico (épocas 41–50) no llegó a correr.
- **En la térmica, el pico no se repite:**
  - las corridas térmicas tienen su máximo en épocas distintas: la 12 (0.391) en esta, la 10 (0.384) en
    `termico_base_p20` y la 3 (0.327) en B2;
  - las medianas por tramo no bajan después del máximo;
  - es una época alta dentro del ruido de una meseta, no un pico seguido de caída.
  - La época 1 de `termico_base_cortada` y de `termico_base_p20` da lo mismo (0.2115): es la misma semilla, y el
    calendario de la tasa solo se separa después.

**Las corridas RGB sí tienen un pico temprano, y luego caen:**

| Corrida | Épocas | Máximo de mAP@0.5 | Última | Medianas de mAP@0.5 por tramo de 10 épocas |
|---|---:|---|---:|---|
| `rgb_100ep_cortada` | 7 | 0.163 (época 2) | 0.062 | 0.063 |
| `rgb_100ep_cortada2` | 67 | 0.163 (época 2) | 0.010 | 0.076, 0.038, 0.040, 0.037, 0.029, 0.018, 0.014 |
| `fusion_100ep` (referencia) | 100 | 0.395 (época 27) | 0.245 | de 0.252 a 0.310, sin tendencia |

- **En las dos corridas RGB** el máximo es la época 2 (0.163), y después el mAP@0.5 baja casi sin parar: Spearman
  −0.59 en `rgb_100ep_cortada2`.
- **La pérdida de entrenamiento** de la RGB baja en todas las épocas (Spearman −1.00).
- **La de validación** no mejora: la `box` queda en 4.0–4.2 y la `cls`, en 6–9 con mucho ruido.
- Así que **en la RGB sí hay una divergencia sostenida**: mejora en los vuelos de entrenamiento y empeora en los de
  validación. Es lo más cercano a un sobreajuste de las tres modalidades.
- En la térmica y en la fusión, en cambio, la validación se queda en una meseta.

### Corrida 1 válida: `termico_base`, receta nueva (19 de noviembre de 2026)

Es la corrida de `termico_base` que se usa en C4. `termico_base_cortada` y `termico_base_p20` quedan como evidencia.

- **Dónde y cuándo:** la corrió el usuario en su propia ventana de PowerShell, fuera de Claude Code, de 13:36 a 14:12.
  Terminó con salida 0, y el script escribió su fila en la bitácora.
- **Comprobaciones previas:** las tres aplicaciones cerradas, límite aplicado de 99.0 W (mediana de 30 s) y 9 012 MiB
  de RAM usados antes de empezar.
- **Durante el entrenamiento:**
  - límite aplicado de 88.5 W (mediana), pico de memoria de la GPU de 5 287 de 8 188 MiB y 88 °C como máximo;
  - 42 s por época (mediana) y 36 min en total (2 158 s);
  - la época 41 tardó 53 s: los 11 s de más son los de volver a abrir los procesos de lectura al quitar el mosaico.
- **Se reproduce exactamente:** las épocas 1 a 40 son idénticas a las de `termico_base_cortada` en las 14 columnas de
  `results.csv` (pérdidas, métricas y tasas de aprendizaje, con diferencia 0). La época 1 también da lo mismo en
  `termico_base_p20` y en B2 (0.2115).
- **`best.pt` es la época 12.** `resumen.json` comprueba que coincide con la de mayor mAP@0.5 de `results.csv`.

| | Época | mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|
| **Última (`last.pt`)** | 50 | **0.223** | 0.111 | 0.400 | 0.272 |
| **Promedio de las 5 últimas** | 46–50 | **0.222** | 0.109 | 0.397 | 0.274 |
| `best.pt` (secundaria) | 12 | 0.391 | 0.190 | 0.472 | 0.437 |
| Validación final de `best.pt` (Ultralytics) | — | 0.390 | 0.190 | 0.470 | 0.436 |

**mAP@0.5 de validación por época:**

| Épocas | Valores |
|---|---|
| 1–10 | 0.211, 0.267, 0.227, 0.179, 0.178, 0.179, 0.210, 0.339, 0.182, 0.253 |
| 11–20 | 0.348, **0.391**, 0.279, 0.152, 0.255, 0.322, 0.238, 0.291, 0.219, 0.266 |
| 21–30 | 0.257, 0.203, 0.328, 0.187, 0.313, 0.245, 0.259, 0.347, 0.301, 0.244 |
| 31–40 | 0.311, 0.258, 0.314, 0.225, 0.257, 0.325, 0.294, 0.255, 0.264, 0.223 |
| 41–50 (sin mosaico) | 0.228, 0.221, 0.224, 0.200, 0.198, 0.203, 0.231, 0.225, 0.228, 0.223 |

**Comparación** (mismo dataset, `configs/termico.yaml`, y misma validación):

| Corrida | Receta | Máximo (época) | Última | Promedio de las 5 últimas | Mediana de las 10 últimas |
|---|---|---|---:|---:|---:|
| **`termico_base`** | 50 épocas, sin parada, `close_mosaic: 10` | 0.391 (12) | **0.223** | **0.222** | 0.223 |
| `termico_base_cortada` | la misma, cortada en la época 40 | 0.391 (12) | 0.223 (40) | 0.272 | 0.261 |
| `termico_base_p20` | 100 épocas, `patience: 20`; paró en la 30, todas con mosaico | 0.384 (10) | 0.195 | 0.242 | 0.234 |
| B2 | 30 épocas, receta de la fase 5 (`close_mosaic: 10`) | 0.327 (3) | 0.189 | 0.197 | 0.204 |

- **Contra B2:** +0.034 en la última época y +0.025 en el promedio de las 5 últimas. B2 tiene la misma época 1, pero su
  calendario es de 30 épocas.
- **Contra `termico_base_p20`:** +0.028 en la última, pero −0.020 en el promedio de las 5 últimas, porque las de
  `termico_base_p20` tenían mosaico.
- **Las 10 épocas sin mosaico** (41–50) dan una curva más estable pero más baja que las 10 anteriores:
  - mAP@0.5 de 0.273 de media (desviación 0.037, saltos de hasta 0.089) a 0.218 (desviación 0.013, saltos de hasta
    0.028);
  - baja sobre todo el recall (0.321 a 0.266); la precisión casi no cambia (0.408 a 0.394);
  - la pérdida de entrenamiento sigue bajando (`box` de 0.92 a 0.81), y la de validación sube un poco (`box` de 2.15
    a 2.32 y `cls` de 4.20 a 4.46). Es una señal leve de sobreajuste al final, aunque la comparación de las pérdidas
    de entrenamiento con y sin mosaico no es directa;
  - en B2 pasa lo mismo: mediana de 0.232 en las épocas 11–20 y de 0.204 en las 21–30, las sin mosaico.
- **Para C4:** la cifra principal (la última época y el promedio de las 5 últimas) cae en el tramo sin mosaico, que en
  las dos corridas térmicas queda unas 0.05 por debajo del tramo anterior. `best.pt` queda 0.17 por encima.

### RAM de `termico_base`

`monitor.csv`: 2 049 lecturas, una cada 1.1 s, de 13:36:20 a 14:12:22. RAM total: 15 996 MiB.

- **Pico de 99.8 % (15 971 MiB): una sola lectura, a las 13:37:26, en la validación de la época 1.**
  - Es cuando Ultralytics abre los 8 procesos de lectura de la validación, con los 4 del entrenamiento abiertos.
  - De 99 % o más: 5 lecturas, entre 13:37:24 y 13:37:32 (unos 7 s).
  - De 98 % o más: 9 lecturas, entre 13:37:22 y 13:37:32 (unos 10 s).
  - Después baja a 95–97 %.
- **No coincide con la época 41.** En la época 41 el máximo fue de 98.8 %:
  - a las 14:05:06 la GPU para: Ultralytics cierra los 4 procesos de lectura del entrenamiento para quitar el mosaico,
    y la RAM baja de 15.3 a 13.5 GB;
  - abre 4 nuevos, y en 10 s la RAM vuelve a 15.8 GB: 98.8 % a las 14:05:18, y 98 % o más en 4 lecturas de unos 7 s;
  - después queda en 97–98 % (mediana de 97.0 % en la época 41).
  - Es el mismo momento en que se cortó `termico_base_cortada` (época 41, 13:04).
- **En toda la corrida:** mediana de 92.9 %, 95 % o más el 26.3 % del tiempo y 98 % o más el 0.8 % (17 lecturas). En
  `termico_base_p20`, 88.7 %, 16.7 % y 1.6 %.
- No hubo errores, y el tiempo por época no cambió.

**¿`termico_ampliado` usaría más RAM?** Estimación, sin entrenar:
- `cache: false` en `configs/fase7.yaml`, así que las imágenes no se guardan en RAM. Cada proceso de lectura del
  entrenamiento guarda solo el búfer del mosaico, de hasta 128 imágenes (`min(n, 8 × lote, 1000)`). Son las mismas
  en los dos datasets, de 640 × 512 (cerca de 1 MB cada una, unos 125 MB por proceso).
- **Lo que crece es la lista de etiquetas y de archivos.** En Windows cada proceso de lectura recibe una copia del
  dataset por pickle:
  - 1.7 MiB con 3 247 imágenes y 7.6 MiB con 14 110, medido con los `YOLODataset` de entrenamiento construidos como en
    el entrenador;
  - unos 6 MiB más por proceso, y unos 30 MiB en total con el proceso principal y los 4 de lectura (0.2 % de los
    16 GB);
  - la validación es la misma (442 imágenes).
- **El número de procesos y los momentos de los picos son los mismos:** la primera validación y la época 41.
- **Así que el pico tendría que ser el mismo**, salvo lo que cambie de las aplicaciones abiertas, que mueve más (la
  RAM de antes de entrenar va de 9.0 a 9.3 GB entre corridas).
- **Lo que sí cambia es la duración:** unas 2.4 h, con la época 41 a unas 2 h de empezar.

**Archivo de paginación de Windows** (19 de noviembre de 2026):
- `C:\pagefile.sys` de 20 480 MB, administrado por Windows (puede crecer); el disco C: tiene 66 GB libres de 449.
- Uso actual de 1.1 GB, y máximo de 4.5 GB (22 %) desde el último arranque (12 de noviembre de 2026, 09:37). Ese
  máximo incluye todas las corridas de la fase 7.
- Límite de memoria comprometida de 36 476 MB (RAM más paginación); ahora en uso 15.3 GB (41 %).
- **Alcanza como respaldo para Windows:** los errores de memoria de Windows al abrir procesos aparecen cuando lo
  comprometido llega al límite, y quedan unos 15 GB por encima del máximo registrado.
- **No protege de la detención de Claude Code**, que mira la RAM física. Por eso las corridas se lanzan fuera de
  Claude Code.

### Corrida 2: `termico_ampliado` (19 de noviembre de 2026)

- **Dónde y cuándo:** la corrió el usuario en su PowerShell, fuera de Claude Code y con VS Code cerrado, de 14:39 a
  17:03. Terminó con salida 0, y el script escribió su fila en la bitácora.
- **Datos:** `data/fase7/datasets/termico_ampliado/`, con 14 110 imágenes de entrenamiento (3 247 de la base y 10 863
  nuevas) y la misma validación de 442 fotogramas.
- **Comprobaciones previas:** las tres aplicaciones cerradas, límite aplicado de 99.8 W y 6 995 MiB de RAM usados
  antes de empezar (9 012 en `termico_base`).
- **Durante el entrenamiento:**
  - límite aplicado de 88.2 W (mediana), pico de memoria de la GPU de 5 291 MiB y 87 °C como máximo;
  - 172 s por época (mediana; se estimaron 175) y 2 h 24 min en total (8 637 s).
- **`best.pt` es la época 9.** `resumen.json` comprueba que coincide con la de mayor mAP@0.5 de `results.csv`.

| | Época | mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|
| **Última (`last.pt`)** | 50 | **0.363** | 0.163 | 0.605 | 0.354 |
| **Promedio de las 5 últimas** | 46–50 | **0.361** | 0.162 | 0.617 | 0.366 |
| `best.pt` (secundaria) | 9 | 0.507 | 0.244 | 0.576 | 0.544 |
| Validación final de `best.pt` (Ultralytics) | — | 0.506 | 0.245 | 0.577 | 0.542 |

**mAP@0.5 de validación por época:**

| Épocas | Valores |
|---|---|
| 1–10 | 0.245, 0.333, 0.469, 0.345, 0.259, 0.348, 0.417, 0.429, **0.507**, 0.360 |
| 11–20 | 0.328, 0.461, 0.376, 0.390, 0.397, 0.420, 0.381, 0.393, 0.407, 0.338 |
| 21–30 | 0.398, 0.400, 0.323, 0.419, 0.387, 0.375, 0.394, 0.380, 0.375, 0.343 |
| 31–40 | 0.385, 0.351, 0.400, 0.354, 0.360, 0.365, 0.378, 0.405, 0.410, 0.422 |
| 41–50 (sin mosaico) | 0.402, 0.365, 0.376, 0.348, 0.350, 0.358, 0.360, 0.357, 0.367, 0.363 |

**`termico_base` frente a `termico_ampliado`** (misma receta y misma validación; solo cambian los datos):

| Cifra | `termico_base` | `termico_ampliado` | Diferencia |
|---|---:|---:|---:|
| mAP@0.5, promedio de las 5 últimas | 0.222 | **0.361** | +0.139 |
| mAP@0.5, `best.pt` | 0.391 (época 12) | **0.507** (época 9) | +0.116 |
| Recall, promedio de las 5 últimas | 0.274 | **0.366** | +0.091 |
| Recall, `best.pt` | 0.437 | **0.544** | +0.107 |

- **Caída desde `best.pt` hasta el promedio de las 5 últimas:**
  - en mAP@0.5 es menor: 0.146 (de 0.507 a 0.361, un 29 %), contra 0.169 (de 0.391 a 0.222, un 43 %);
  - en recall no: 0.178 (de 0.544 a 0.366), contra 0.163 (de 0.437 a 0.274);
  - la precisión, en cambio, sube al final (de 0.576 a 0.617).
- **La curva:** las medianas por tramo de 10 épocas son 0.354, 0.391, 0.384, 0.382 y 0.362. Después de la época 10 queda
  en una meseta de unas 0.38. `best.pt` (época 9, 0.507) es una época aislada: las de al lado dan 0.429 y 0.360.
- **El tramo sin mosaico baja menos que en `termico_base`:**
  - mAP@0.5 de 0.383 de media en las épocas 31–40 a 0.365 en las 41–50 (−0.018, contra −0.055 en `termico_base`);
  - recall de 0.375 a 0.362, y precisión de 0.581 a 0.625;
  - la pérdida de validación casi no cambia (`box` de 2.23 a 2.20 y `cls` de 3.30 a 3.40).
- **La mejora no se explica por más iteraciones.** `termico_ampliado` tiene 882 lotes por época, contra 203 en la base,
  así que en 50 épocas da 4.3 veces más pasos. Pero las tres corridas térmicas con el dataset base llegan a su máximo
  antes de la época 13 y después empeoran (no lo vuelven a alcanzar):

  | Corrida | Máximo (época, lotes) | Mejor después del máximo | Mediana después del máximo | Promedio de las 5 últimas | Lotes en total |
  |---|---|---:|---:|---:|---:|
  | `termico_base` | 0.391 (12, 2 436) | 0.347 | 0.250 | 0.222 | 10 150 |
  | `termico_base_p20` | 0.384 (10, 2 030) | 0.370 | 0.236 | 0.242 | 6 090 |
  | B2 | 0.327 (3, 609) | 0.306 | 0.217 | 0.197 | 6 090 |

  - Con la base, pasar de unos 2 000 lotes a 10 150 no sube el mAP@0.5: baja.
  - Con los mismos lotes, `termico_ampliado` ya va por encima:
    - en la época 3 (2 646 lotes) da 0.469, más que el máximo de `termico_base` en sus 10 150 lotes (0.391);
    - en sus primeras 11 épocas (9 702 lotes, menos que los 10 150 de `termico_base`), la mediana es 0.348, contra
      0.244 en las 50 épocas de `termico_base`.
  - Un matiz: la tasa de aprendizaje no está en el mismo punto del calendario con los mismos lotes, porque las dos
    corridas la bajan a lo largo de 50 épocas.

### RAM de `termico_ampliado`

`monitor.csv`: 8 199 lecturas, una cada 1.1 s, de 14:39:55 a 17:03:57.

- **Pico de 99.7 % (15 940 MiB): una sola lectura, a las 14:43:16, en la validación de la época 1.**
  - Es el mismo momento que en `termico_base` (99.8 %): cuando Ultralytics abre los 8 procesos de lectura de la
    validación.
  - Fue la única lectura de 98 % o más en toda la corrida.
- **En la época 41** (16:35:10 a 16:35:19, al quitar el mosaico), la RAM bajó de 12.7 a 10.8 GB al cerrar los 4
  procesos de lectura. Con los 4 nuevos subió hasta 14.3 GB (89.4 %), contra 98.8 % en `termico_base`.
- **En toda la corrida:** mediana de 83.0 %, y 95 % o más el 0.2 % del tiempo. En `termico_base` fueron 92.9 % y
  26.3 %.
- **Contra la estimación** (el mismo pico, en los mismos momentos, y unos 30 MiB más por la lista de etiquetas):
  - **momentos: coinciden** (la primera validación y la época 41);
  - **lo que ocupa el entrenamiento sobre la RAM de antes de empezar**, en las épocas 2–40: 5 918 MiB de mediana,
    contra 5 791 en `termico_base`. Son unos 130 MiB más, cuatro veces lo estimado, pero menos del 1 % de los 16 GB;
  - **el pico: coincide en el nivel (99.7 % contra 99.8 %), pero no por la razón que supuse.** Esperaba que bajara si
    había menos aplicaciones abiertas, y había 2 GB menos. Sin embargo, la apertura de los 8 procesos de la validación
    subió 3.3 GB sobre el entrenamiento de la época 1, contra 1.9 GB en `termico_base`.
  - Mi interpretación, que no está comprobada: al abrir los procesos de la validación, Windows deja que ocupen la RAM
    libre que haya y después la recorta. Así, ese pico llega cerca del 100 % aunque haya más memoria libre. Esa
    validación duró 21.7 s, contra 34.9 s en `termico_base`.
  - **Cerrar aplicaciones sí bajó el resto de la corrida**, pero no ese instante.

### Antes de `fusion_base` (19 de noviembre de 2026)

**De qué vuelo viene cada imagen de los datasets ampliados**, comprobado con los archivos y no con `composicion.csv`
(`scripts/fase7_origen.py`, sección `origen` de `configs/fase7.yaml`):
- **Enlace duro:** el identificador de archivo de cada imagen se busca entre los de `data/alineados/` (la base de la
  fase 2) y los de `data/fase7/{termica,fusion}/` (las nuevas de C1). Solo se miran metadatos.
- **Contenido:** los píxeles de la térmica de cada imagen (el PNG o la cuarta muestra del TIFF) se comparan con los de
  las 28 935 térmicas originales de las 40 carpetas IR del dataset WiSARD. Se pasan a gris como en la fase 2 y en C1.
- **FHL 0405/0406 no se leyó.** Se descarta porque cada imagen es igual a una original de otro vuelo, y porque ninguna
  enlaza a sus archivos.
- Tarda 70 s.

| Comprobación (los dos datasets, 29 104 imágenes) | Resultado |
|---|---|
| Con enlace a la base de la fase 2 o a las nuevas de C1 | 29 104 |
| Con su térmica igual a una original | 29 104 |
| Con originales iguales en más de un vuelo | 0 |
| Vuelo por el contenido distinto del vuelo por el enlace | 0 |
| TIFF con la térmica distinta del PNG del mismo nombre | 0 de 14 552 |
| TIFF nuevos con la RGB distinta de 0 (no hay pares reales aprobados) | 0 de 10 863 |
| Imágenes nuevas de MtErie 0007 o de FHL 0405 | **0** |
| Imágenes nuevas de MtErie 0005 | **15 en cada dataset** |

- 32 imágenes nuevas (16 en cada dataset) son iguales a dos fotogramas originales seguidos del mismo vuelo. El vídeo
  repite el fotograma, y las dos copias están en el entrenamiento.
- **MtErie 0007** (`IR_0008`) está solo en la validación: 169 de los 442 fotogramas, por la partición. No hay ninguna
  en el entrenamiento.
- **FHL 0405** no aparece en ninguna parte.
- **MtErie 0005** (`IR_0006`) sí está en el entrenamiento:
  - **257 imágenes de la base**: es un vuelo de entrenamiento de la partición, desde la fase 3;
  - **15 nuevas**, las posiciones 160–162, 202–204, 207–211, 220–221 y 226–227;
  - son pares anotados que la fase 2 excluyó por desfase entre la RGB y la térmica, y que C1 devolvió al
    entrenamiento: la fuente "excluido de entrenamiento", igual que 28 de MtErie 0003;
  - en `fusion_ampliado` llevan la RGB en 0;
  - no es un vuelo de validación ni de prueba, pero va contra lo que se esperaba. Quedó para que decidiera el usuario:
    se quedan (abajo).
  - `termico_ampliado` ya se entrenó con ellas. `fusion_base` usa el dataset de siempre (`configs/fusion.yaml`), así
    que no le afecta.

**Decisión del usuario (19 de noviembre de 2026): las 15 de MtErie 0005 se quedan** en `termico_ampliado` y en
`fusion_ampliado`. Motivo:
- MtErie 0005 es un vuelo de entrenamiento, así que no hay fuga hacia la validación ni hacia la prueba;
- la fase 2 las excluyó por el desfase entre la RGB y la térmica, que no afecta a una imagen solo térmica, y en
  `fusion_ampliado` llevan la RGB en 0;
- son el 0.1 % de las 14 110 imágenes de entrenamiento, y `termico_ampliado` ya se entrenó con ellas.

`scripts/fase7_origen.py` sigue saliendo con código 1 por esa comprobación; está anotado en `configs/fase7.yaml`.

**Sus etiquetas son las de la térmica**, comprobado con los archivos para todas las imágenes nuevas:
- En los dos datasets, la etiqueta de cada imagen nueva es un enlace duro a `data/fase7/etiquetas/` y tiene las mismas
  cajas que el `.txt` de la térmica original, sin las repetidas: 21 726 de 21 726 (10 863 en cada dataset).
- La original se toma por el contenido de la imagen (el hash de los píxeles de `origen_imagenes.csv`), no por
  `composicion.csv`.
- **Las 15 de MtErie 0005** tienen 32 cajas en cada dataset, iguales a las de sus `.txt` de `IR_0006` en las 15. La
  etiqueta es el mismo archivo en los dos datasets.
- De las 16 imágenes por dataset que son iguales a dos fotogramas originales seguidos, 14 tienen las mismas cajas en
  los dos `.txt`, y 2 no (Karen IR_5, posiciones 203 y 204). Su etiqueta es la del fotograma de su posición, el que
  usó C1.

**Vuelos de origen de las imágenes agregadas** (10 863, las mismas en `termico_ampliado` y en `fusion_ampliado`):

| Vuelo (carpeta IR) | Imágenes |
|---|---:|
| 200704_Baker_FLIR_IR_1 | 881 |
| 200704_Baker_FLIR_IR_2 | 1 064 |
| 200910_Carnation_FLIR_IR_1 a IR_7 | 105, 428, 170, 138, 266, 253 y 175 (1 535) |
| 200929_Karen_FLIR_IR_1 a IR_6 | 316, 407, 434, 452, 452 y 451 (2 512) |
| 210327_Airfield_FLIR_IR_1, 2, 3, 4, 6, 7 y 8 | 190, 503, 368, 215, 364, 432 y 159 (2 231) |
| 210529_Carnation_Enterprise_0023 (`IR_0024`) | 736 |
| 210924_FHL_Enterprise_0403 (`IR_0404`) | 216 |
| 210924_FHL_Enterprise_0564 (`IR_0565`) | 754 |
| 210924_FHL_Enterprise_0566 (`IR_0567`) | 731 |
| 210924_FHL_Enterprise_0401 (`IR_0402`), excluidas en la fase 2 | 113 |
| 220109_Baker_Enterprise_1 (`IR_1`), excluidas en la fase 2 | 47 |
| 210417_MtErie_Enterprise_0003 (`IR_0004`), excluidas en la fase 2 | 28 |
| 210417_MtErie_Enterprise_0005 (`IR_0006`), excluidas en la fase 2 | 15 |

La base de entrenamiento (3 247) es la de siempre: Baker 1 971, FHL 0401 783, MtErie 0005 257 y MtErie 0003 236.

**Receta de `fusion_base`**, mezclando `c3.base` con la corrida como hace el script, y comparada con lo que guardaron
los `resumen.json` de `termico_base` y `termico_ampliado`:
- **Los parámetros de Ultralytics son todos iguales:**
  - seed 0 (`deterministic: true`), lote 16 y 50 épocas;
  - AdamW con lr0 = 0.002, momentum 0.9 y `warmup_bias_lr = 0`;
  - `cache: false`, `workers: 4`, `patience: 0`, `close_mosaic: 10`, imgsz 640 y `hsv = 0`.
- **Solo cambian:**
  - los datos: `configs/fusion.yaml`, con `channels: 4`;
  - el inicio del cuarto canal: `promedio`. En las térmicas dice `azar`, pero no se usa con 3 canales.
- En las dos térmicas, `args.yaml` y el optimizador real (AdamW, 0.002) coinciden con eso.

**RAM esperada de `fusion_base`.** Corridas medidas con el mismo monitor, con 4 procesos de lectura y lote 16:

| Corrida | Canales | RAM antes (MiB) | Pico | Momento del pico | Mediana sin la época 1 (MiB) | Al quitar el mosaico |
|---|---:|---:|---:|---|---:|---:|
| `fusion_100ep` (fase 5, el mismo dataset) | 4 | 9 620 | 99.8 % | 1.ª validación | 13 796 | 94.1 % (época 91) |
| `fusion_azar_10ep` (fase 5) | 4 | 7 109 | 99.9 % | 1.ª validación | 14 868 | — |
| `fusion_promedio_10ep` (fase 5) | 4 | 6 479 | 99.5 % | época 2 | 15 303 | — |
| `termico_base` | 3 | 9 012 | 99.8 % | 1.ª validación | 14 857 | 98.8 % (época 41) |
| `termico_ampliado` | 3 | 6 995 | 99.7 % | 1.ª validación | 13 254 | 89.4 % (época 41) |
| B2 | 3 | 8 825 | 99.9 % | época 2 | 15 186 | — |

- **En teoría, el TIFF de 4 canales suma poco:**
  - el búfer del mosaico de cada proceso de lectura (128 imágenes) pasa de 1.0 a 1.3 MB por imagen, unos 160 MB más
    con los 4 procesos;
  - los lotes en camino, unos 50 MB más;
  - en total, del orden de 0.2–0.3 GB.
- **En las medidas no se nota.** Las diferencias entre corridas por lo que hay abierto, y por cómo Windows reparte la
  memoria, son de ±1 GB. `fusion_100ep`, con 9.6 GB antes, quedó más abajo (13.8 GB) que `termico_base` con 9.0 GB
  (14.9 GB).
- **Estimación:**
  - el mismo pico que en todas las corridas medidas (98.7–99.9 %), en la primera validación;
  - en la época 41, entre un 90 % y un 99 %, según la RAM de antes;
  - unos 36 min (`fusion_100ep`: 42.8 s por época).
- **Riesgos:**
  - no veo uno nuevo frente a las térmicas: ninguna de las 10 corridas medidas tuvo errores de memoria;
  - el archivo de paginación deja unos 15 GB de margen;
  - el único corte, `termico_base_cortada`, lo hizo Claude Code, y se evita corriéndola fuera;
  - lo que más acerca la época 41 al 99 % es tener más aplicaciones abiertas (98.8 % con 9.0 GB antes, 89.4 % con
    7.0 GB). Conviene correrla como `termico_ampliado`, con VS Code cerrado.

### Corrida 3: `fusion_base` (19 de noviembre de 2026)

- **Dónde y cuándo:** la corrió el usuario en su PowerShell, fuera de Claude Code, de 20:38 a 21:15. Terminó con
  salida 0, y el script escribió su fila en la bitácora.
- **Datos:** `configs/fusion.yaml`, el dataset de siempre en TIFF de 4 canales (3 247 imágenes de entrenamiento y
  442 de validación). El cuarto canal empieza con el promedio de los pesos de color (`max_dif_cuarto_vs_promedio_color`
  de 0 en `resumen.json`).
- **Comprobaciones previas:** enchufada, las tres aplicaciones cerradas, límite aplicado de 99.5 W y 7 186 MiB de RAM
  usados antes de empezar.
- **Durante el entrenamiento:** pico de memoria de la GPU de 5 327 MiB y 86 °C como máximo; 43 s por época (mediana) y
  37 min en total (2 226 s; se estimaron 36).
- **`best.pt` es la época 23.** `resumen.json` comprueba que coincide con la de mayor mAP@0.5 de `results.csv`.
- **El log no tiene advertencias ni errores.** Solo trae el aviso de que hay una versión nueva de Ultralytics (8.4.215),
  como en las térmicas. Sus 106 líneas que no son barras de progreso son las mismas que en `termico_base`, salvo los
  4 canales de la primera capa y las rutas.

**Corrió sin cargador en las épocas 31 a 41.** `monitor.csv` no registra si la laptop está enchufada, pero se ve en el
límite aplicado de la GPU, que baja a 55.0 W. Lo confirma el registro de Windows (Kernel-Power, evento 105, "Cambio de
fuente de energía"):

| Hora (Windows) | Evento | En `monitor.csv` | Época |
|---|---|---|---|
| 21:00:45 | se desconecta | 55 W desde las 21:00:46 | 31, a los 36 s |
| 21:01:27 | se conecta | 77 W a las 21:01:28 | 32 |
| 21:02:13 | se desconecta | 55 W desde las 21:02:15 | 33, al final |
| 21:08:12 | se conecta | 78 W a las 21:08:13 | 41, a los 18 s, poco después de abrir los procesos de lectura sin mosaico |

- **Duración:** 6 min 41 s con batería (42 s y 5 min 59 s), entre las 21:00:45 y las 21:08:12, con 46 s enchufada en
  medio.
- **Épocas:** de la 34 a la 40 enteras. En parte, la 31 (17 % de sus lecturas), la 32 (74 %), la 33 (22 %) y la 41
  (33 %).
- **Batería:** de 75.1 a 66.0 Wh según el registro de Windows (un 12 %).
- A las 21:47, media hora después de terminar, hubo otra desconexión de 2 s, ya sin entrenamiento.

| Mediana por época | Con cargador (épocas 11–30) | Sin cargador (32 y 34–40) | Cambio |
|---|---:|---:|---:|
| Límite aplicado de la GPU | 86.8 W | 55.0 W | −37 % |
| Consumo de la GPU | 83.3 W | 54.6 W | −34 % |
| Reloj de la GPU | 2 325 MHz | 1 660 MHz | −29 % |
| Temperatura de la GPU | 83 °C | 77 °C | −6 °C |
| Entrenamiento por época | 39.3 s | 43.9 s | +4.6 s (+12 %) |

- La GPU siguió ocupada (87–98 % de uso): fue más lenta, no se quedó esperando.
- La validación no cambió (unos 3 s por época).
- En total, las épocas 31–40 tardaron 41 s más.
- La época 41 tardó 52.7 s de entrenamiento, lo de siempre al quitar el mosaico: 50.4 s en `termico_base` y 54.4 s en
  la época 91 de `fusion_100ep`.
- Al reconectarla (épocas 42–50) volvió a 86.3 W y 39.0 s por época.
- La mediana del límite aplicado de toda la corrida, que va a `resumen.json` y a la bitácora (84.7 W), incluye ese
  tramo; sin él es 85.6 W.

**El entrenamiento es determinista, así que el corte no debería cambiar los resultados, solo los tiempos:**
- `args.yaml` tiene `deterministic: true`. Con eso, `init_seeds` de Ultralytics 8.4.194 (`utils/torch_utils.py`) fija
  las semillas y activa:
  - `torch.use_deterministic_algorithms(True, warn_only=True)`;
  - `torch.backends.cudnn.deterministic = True`;
  - `CUBLAS_WORKSPACE_CONFIG=:4096:8`.
- **`cudnn.benchmark` queda en `False`**, el valor por omisión de PyTorch (2.15).
  - En `init_seeds` la línea que lo activaría está comentada.
  - Ultralytics solo lo pone en `True` al predecir sobre vídeo en vivo (`LoadStreams`).
  - Los scripts del proyecto no lo tocan.
  - Así, cuDNN no elige los algoritmos midiendo tiempos, que es lo que podría cambiar con una GPU más lenta.
- **Con `warn_only`, PyTorch avisa en el log si usa una operación sin versión determinista.** No hay ningún aviso, ni
  aquí ni en `termico_base`.
- **Una GPU más lenta hace las mismas operaciones sobre los mismos datos, solo que en más tiempo:**
  - los procesos de lectura entregan los lotes en orden aunque tarden distinto;
  - el mosaico se quita por número de época, no por tiempo.
- **Comprobado en la práctica:**
  - `termico_base` repitió exactamente las épocas 1 a 40 de `termico_base_cortada` (diferencia 0 en las 14 columnas);
  - la época 1 de `fusion_base` es idéntica a la de `fusion_100ep` de la fase 5 (mismo dataset, semilla e inicio del
    cuarto canal), en todas las columnas de `results.csv` salvo el tiempo;
  - `fusion_promedio_10ep` da otra época 1 porque, con 10 épocas y `close_mosaic: 10`, entrenó sin mosaico desde el
    principio.
- **Lo que no se puede comprobar sin volver a entrenar:** que las épocas 31 a 41 den lo mismo con cargador. Haría falta
  repetir `fusion_base` enchufada (unos 36 min) y comparar `results.csv` fila por fila.

**Decisión del usuario (20 de noviembre de 2026): `fusion_base` queda válida y no se repite.** El tramo sin cargador va
como **limitación que solo afecta los tiempos**:
- **Qué pasó:** las épocas 31 a 41 corrieron sin cargador, 6 min 41 s entre las 21:00:45 y las 21:08:12. Es la única
  corrida de la fase 7 que no estuvo enchufada entera.
- **Qué cambió:**
  - las épocas 31 a 40 tardaron 41 s más;
  - la mediana del límite aplicado de la corrida bajó a 84.7 W en `resumen.json` y en la bitácora (85.6 W sin ese
    tramo).
- **Qué no cambia:** los resultados, porque el entrenamiento es determinista (arriba). Como no se repite, no hay una
  comparación fila por fila de las épocas 31 a 41 con cargador.

| | Época | mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|
| **Última (`last.pt`)** | 50 | **0.307** | 0.136 | 0.502 | 0.300 |
| **Promedio de las 5 últimas** | 46–50 | **0.317** | 0.138 | 0.494 | 0.322 |
| `best.pt` (secundaria) | 23 | 0.425 | 0.188 | 0.500 | 0.448 |
| Validación final de `best.pt` (Ultralytics) | — | 0.424 | 0.188 | 0.501 | 0.448 |

**mAP@0.5 de validación por época:**

| Épocas | Valores |
|---|---|
| 1–10 | 0.296, 0.246, 0.245, 0.252, 0.237, 0.147, 0.385, 0.243, 0.271, 0.193 |
| 11–20 | 0.272, 0.295, 0.257, 0.337, 0.352, 0.209, 0.286, 0.315, 0.283, 0.285 |
| 21–30 | 0.354, 0.278, **0.425**, 0.352, 0.284, 0.337, 0.409, 0.252, 0.305, 0.355 |
| 31–40 (sin cargador desde la 31) | 0.361, 0.360, 0.383, 0.337, 0.376, 0.317, 0.336, 0.351, 0.360, 0.298 |
| 41–50 (sin mosaico; con cargador desde la 41) | 0.378, 0.296, 0.309, 0.318, 0.300, 0.320, 0.341, 0.311, 0.307, 0.307 |

**`fusion_base` frente a `termico_base`** (misma receta, mismos pares y misma validación; solo cambia la entrada):

| Cifra | `termico_base` | `fusion_base` | Diferencia |
|---|---:|---:|---:|
| mAP@0.5, promedio de las 5 últimas | 0.222 | **0.317** | +0.095 |
| mAP@0.5, `best.pt` | 0.391 (época 12) | **0.425** (época 23) | +0.034 |
| Recall, promedio de las 5 últimas | 0.274 | **0.322** | +0.048 |
| Recall, `best.pt` | 0.437 | **0.448** | +0.011 |

- **Caída desde `best.pt` hasta el promedio de las 5 últimas:**
  - en mAP@0.5, 0.108 (de 0.425 a 0.317, un 25 %), contra 0.169 (43 %) en `termico_base` y 0.146 (29 %) en
    `termico_ampliado`;
  - en recall, 0.126 (de 0.448 a 0.322), contra 0.163 y 0.178.
- **La curva sube más tarde que en las térmicas:**
  - las medianas por tramo de 10 épocas son 0.245, 0.285, 0.345, 0.355 y 0.310;
  - el máximo es la época 23, y la segunda mejor, la 27 (0.409); las térmicas llegan al suyo antes de la época 13.
- **Sin mosaico baja:**
  - mAP@0.5 de 0.348 de media en las épocas 31–40 a 0.319 en las 41–50 (−0.029, contra −0.055 en `termico_base` y
    −0.018 en `termico_ampliado`);
  - recall de 0.366 a 0.336, y precisión de 0.518 a 0.469;
  - la pérdida de validación sube un poco (`box` de 2.89 a 3.01 y `cls` de 2.77 a 2.90).
- **Contra `fusion_100ep`** (fase 5, el mismo dataset con 100 épocas): el promedio de las 5 últimas pasa de 0.247 a
  0.317, y el máximo, de 0.395 (época 27) a 0.425.
- `termico_ampliado` sigue por encima de las dos (0.361 y 0.507).
- Es una sola semilla y la validación tiene dos vuelos. Entre épocas seguidas el mAP@0.5 salta hasta 0.24 (de 0.147 a
  0.385, épocas 6 y 7).

### RAM de `fusion_base`

`monitor.csv`: 2 105 lecturas, una cada 1.1 s, de 20:38:04 a 21:15:16.

- **Pico de 100.0 % (15 992 MiB): una sola lectura, a las 20:39:19, en la validación de la época 1** (de 20:39:02 a
  20:39:23).
  - Es el mismo momento que en las térmicas: cuando Ultralytics abre los 8 procesos de lectura de la validación.
  - Subió 2.9 GB sobre el entrenamiento de la época 1.
  - Hubo 2 lecturas de 99 % o más y 3 de 98 % o más, todas en esos 4 s.
  - No hubo errores: Windows lo cubre con el archivo de paginación.
- **En la época 41** (21:07:54 a 21:08:50, al quitar el mosaico), la RAM bajó de 14.2 a 12.0 GB al cerrar los 4
  procesos de lectura. Con los 4 nuevos subió hasta 15.5 GB (97.2 %), a las 21:08:18.
- **En toda la corrida:** mediana de 86.6 %, y 95 % o más el 15.6 % del tiempo. Fueron 92.9 % y 26.3 % en
  `termico_base`, y 83.0 % y 0.2 % en `termico_ampliado`.
- **Contra la estimación:**
  - **momento del pico: coincide** (la primera validación);
  - **nivel: 100.0 %**, una décima por encima del rango estimado (98.7–99.9 %). Es la primera corrida que llega a
    100.0 % en el monitor;
  - **época 41: 97.2 %**, dentro de lo estimado (90–99 %);
  - **lo que ocupa el entrenamiento sobre la RAM de antes de empezar**, en las épocas 2–40: 6 415 MiB de mediana, contra
    5 791 en `termico_base` y 5 918 en `termico_ampliado`. Son unos 0.5–0.6 GB más, el doble de lo que daba la teoría
    (0.2–0.3 GB), pero dentro de la variación entre corridas (en `fusion_100ep` fueron 4 176 MiB);
  - **tiempo:** 37 min, contra 36 estimados. La diferencia es el tramo sin cargador (41 s).

### Corrida 4: `fusion_ampliado` (20 de noviembre de 2026)

- **Dónde y cuándo:** la corrió el usuario en su PowerShell, fuera de Claude Code, de 15:11 a 17:38. Terminó con
  salida 0, y el script escribió su fila en la bitácora.
- **Datos:** `data/fase7/datasets/fusion_ampliado/`, en TIFF de 4 canales:
  - 14 110 imágenes de entrenamiento: las 3 247 de la base, con la RGB real, y 10 863 nuevas con la RGB en 0;
  - 1 597 sin persona y ninguna dañada, como en `termico_ampliado`;
  - la misma validación de 442 fotogramas.
- **Primera capa:** los canales de color son los preentrenados, y el cuarto empieza con su promedio
  (`max_dif_cuarto_vs_promedio_color` de 0 en `resumen.json`). `p_sin_rgb = 0`.
- **Comprobaciones previas:** enchufada, plan Performance y las tres aplicaciones cerradas. Límite aplicado de 97.7 W
  (de 96.6 a 99.4) y 8 519 MiB de RAM usados antes de empezar, contra 6 995 en `termico_ampliado` y 7 186 en
  `fusion_base`.
- **Durante el entrenamiento:**
  - límite aplicado de 89.4 W (mediana) y nunca por debajo de 70.0 W;
  - pico de memoria de la GPU de 5 291 MiB;
  - **89 °C como máximo, la temperatura más alta de la fase 7** (88 °C en `termico_base`): 83 lecturas de 88 °C o más
    y 2 de 89 °C, con una mediana de 85 °C;
  - 175 s por época (mediana; se estimaron 176) y 2 h 27 min en total (8 828 s);
  - la época 1 tardó 213.8 s, con 29.8 s de la primera validación, y la 41, la primera sin mosaico, 182.8 s de
    entrenamiento, contra 172.0 s de mediana.
- **`best.pt` es la época 3.** `resumen.json` comprueba que coincide con la de mayor mAP@0.5 de `results.csv`.
- **El log no tiene advertencias ni errores.** Solo trae el aviso de la versión nueva de Ultralytics. Sus 54 líneas que
  no son barras de progreso ni métricas por época son las mismas que en `fusion_base`, salvo los datos, el nombre y las
  rutas de la corrida.

**Estuvo enchufada toda la corrida:**
- **Registro de Windows** (Kernel-Power, evento 105, "Cambio de fuente de energía"): no hay ningún cambio entre las
  15:11 y las 17:38. El último es de las 14:52:36, 19 min antes de empezar, al salir de la suspensión, y la deja
  enchufada (`AcOnline=true`). Tampoco hay eventos de suspensión durante la corrida.
- **`monitor.csv`:** el límite aplicado no baja de 70.0 W en ninguna de las 8 338 lecturas. Sin cargador, en
  `fusion_base`, bajaba a 55.0 W.

| | Época | mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|
| **Última (`last.pt`)** | 50 | **0.338** | 0.166 | 0.590 | 0.354 |
| **Promedio de las 5 últimas** | 46–50 | **0.343** | 0.167 | 0.605 | 0.350 |
| `best.pt` (secundaria) | 3 | 0.475 | 0.185 | 0.579 | 0.458 |
| Validación final de `best.pt` (Ultralytics) | — | 0.475 | 0.186 | 0.579 | 0.458 |

**mAP@0.5 de validación por época:**

| Épocas | Valores |
|---|---|
| 1–10 | 0.305, 0.361, **0.475**, 0.352, 0.270, 0.232, 0.314, 0.442, 0.382, 0.277 |
| 11–20 | 0.368, 0.305, 0.298, 0.291, 0.291, 0.364, 0.357, 0.198, 0.323, 0.357 |
| 21–30 | 0.340, 0.342, 0.271, 0.304, 0.345, 0.451, 0.381, 0.288, 0.379, 0.377 |
| 31–40 | 0.378, 0.397, 0.343, 0.288, 0.304, 0.343, 0.339, 0.358, 0.379, 0.379 |
| 41–50 (sin mosaico) | 0.383, 0.365, 0.348, 0.338, 0.356, 0.354, 0.343, 0.342, 0.337, 0.338 |

**`fusion_base` frente a `fusion_ampliado`** (misma receta y misma validación; solo cambian los datos):

| Cifra | `fusion_base` | `fusion_ampliado` | Diferencia |
|---|---:|---:|---:|
| mAP@0.5, promedio de las 5 últimas | 0.317 | **0.343** | +0.026 |
| mAP@0.5, `best.pt` | 0.425 (época 23) | **0.475** (época 3) | +0.050 |
| Recall, promedio de las 5 últimas | 0.322 | **0.350** | +0.028 |
| Recall, `best.pt` | 0.448 | **0.458** | +0.010 |

- **Caída desde `best.pt` hasta el promedio de las 5 últimas:**
  - en mAP@0.5, 0.132 (de 0.475 a 0.343, un 28 %), contra 0.108 (25 %) en `fusion_base` y 0.146 (29 %) en
    `termico_ampliado`;
  - en recall, 0.108 (de 0.458 a 0.350), contra 0.126 y 0.178.
- **La curva es una meseta desde el principio:**
  - las medianas por tramo de 10 épocas son 0.333, 0.314, 0.344, 0.350 y 0.345;
  - en `fusion_base` subían de 0.245 a 0.355.
- **`best.pt` es una época aislada:**
  - la época 3 es la última del calentamiento (`warmup_epochs: 3`);
  - las épocas de al lado dan 0.361 y 0.352, y las siguientes mejores son la 26 (0.451) y la 8 (0.442);
  - en `termico_ampliado`, la época 3 también fue la segunda mejor (0.469).
- **Sin mosaico no baja:**
  - mAP@0.5 de 0.351 de media en las épocas 31–40 a 0.350 en las 41–50 (−0.001). Bajaba 0.029 en `fusion_base`, 0.055
    en `termico_base` y 0.018 en `termico_ampliado`;
  - recall de 0.377 a 0.363, y precisión de 0.526 a 0.585;
  - la pérdida de validación casi no cambia (`box` de 2.41 a 2.39 y `cls` de 2.45 a 2.48);
  - las épocas 41–50 van de 0.337 a 0.383 (rango de 0.046), contra 0.034 en `termico_base`, 0.054 en
    `termico_ampliado` y 0.082 en `fusion_base`.
- **Con los mismos lotes, la ampliada ya va por encima,** como en las térmicas:
  - en la época 3 (2 646 lotes) da 0.475, más que el máximo de `fusion_base` en sus 10 150 lotes (0.425, en la época
    23 y con 4 669 lotes);
  - en sus primeras 11 épocas (9 702 lotes), la mediana es 0.352, contra 0.308 en las 50 épocas de `fusion_base`;
  - el mismo matiz que en las térmicas: con los mismos lotes, la tasa de aprendizaje no está en el mismo punto del
    calendario.
- Es una sola semilla y la validación tiene dos vuelos. Entre épocas seguidas el mAP@0.5 salta hasta 0.16 (de 0.357 a
  0.198, épocas 17 y 18).

### RAM de `fusion_ampliado`

`monitor.csv`: 8 338 lecturas, una cada 1.1 s, de 15:11:37 a 17:38:51.

- **Pico de 99.9 % (15 982 MiB) a las 15:15:06, en la validación de la época 1** (de 15:14:55 a 15:15:24).
  - Es el mismo momento que en las otras tres corridas: cuando Ultralytics abre los 8 procesos de lectura de la
    validación.
  - Subió 1.95 GB sobre el entrenamiento de la época 1.
  - Hubo 12 lecturas de 98 % o más y 7 de 99 % o más. Todas están en esos 13 s (de 15:15:04 a 15:15:16).
  - Esa validación duró 29.8 s, contra 21.6 s en `fusion_base` y 21.7 s en `termico_ampliado`.
  - No hubo errores.
- **En la época 41** (desde las 17:09:38, al quitar el mosaico):
  - la RAM bajó de 14.0 a 11.1 GB al cerrar los 4 procesos de lectura;
  - con los 4 nuevos subió hasta 15.3 GB (95.4 %), a las 17:10:09;
  - fue 97.2 % en `fusion_base` y 89.4 % en `termico_ampliado`.
- **En toda la corrida:** mediana de 87.6 %, y 95 % o más el 0.6 % del tiempo.

  | Corrida | RAM antes (MiB) | Pico | Época 41 | Mediana | 95 % o más | Sobre la RAM de antes, épocas 2–40 (MiB) |
  |---|---:|---:|---:|---:|---:|---:|
  | `termico_base` | 9 012 | 99.8 % | 98.8 % | 92.9 % | 26.3 % | 5 791 |
  | `termico_ampliado` | 6 995 | 99.7 % | 89.4 % | 83.0 % | 0.2 % | 5 916 |
  | `fusion_base` | 7 186 | 100.0 % | 97.2 % | 86.6 % | 15.6 % | 6 413 |
  | `fusion_ampliado` | 8 519 | 99.9 % | 95.4 % | 87.6 % | 0.6 % | 5 461 |

- **Empezó con 1.3–1.5 GB más ocupados** que `termico_ampliado` y `fusion_base`. No sé qué había abierto.
- **El entrenamiento ocupó menos sobre esa RAM de antes** que en las otras tres: 5 461 MiB de mediana. Esto concuerda
  con la interpretación de `termico_ampliado`, que sigue sin comprobar: Windows ajusta lo que deja a los procesos según
  la RAM libre.
- **Lo que se esperaba:** el pico en la primera validación y la subida de la época 41. Las dos se cumplieron.

### Las cuatro corridas de C3

Las cuatro tienen la misma receta y la misma validación (FHL 0134 y MtErie 0007). Solo cambian la entrada (térmica o
fusión) y los datos de entrenamiento (base o ampliado).

| Cifra (validación) | `termico_base` | `termico_ampliado` | `fusion_base` | `fusion_ampliado` |
|---|---:|---:|---:|---:|
| Imágenes de entrenamiento | 3 247 | 14 110 | 3 247 | 14 110 |
| **mAP@0.5, última época (50)** | 0.223 | **0.363** | 0.307 | 0.338 |
| **mAP@0.5, promedio de las 5 últimas** | 0.222 | **0.361** | 0.317 | 0.343 |
| mAP@0.5:0.95, promedio de las 5 últimas | 0.109 | 0.162 | 0.138 | **0.167** |
| Recall, promedio de las 5 últimas | 0.274 | **0.366** | 0.322 | 0.350 |
| Precisión, promedio de las 5 últimas | 0.397 | **0.617** | 0.494 | 0.605 |
| mAP@0.5, `best.pt` (época) | 0.391 (12) | **0.507** (9) | 0.425 (23) | 0.475 (3) |
| Recall, `best.pt` | 0.437 | **0.544** | 0.448 | 0.458 |
| Caída de `best.pt` al promedio de las 5 últimas | 0.169 (43 %) | 0.146 (29 %) | 0.108 (25 %) | 0.132 (28 %) |
| Segundos por época (mediana) | 42 | 172 | 43 | 175 |
| Tiempo total | 36 min | 2 h 24 min | 37 min | 2 h 27 min |
| Límite aplicado de la GPU (mediana) | 88.5 W | 88.2 W | 84.7 W (con el tramo sin cargador) | 89.4 W |

**Efecto de cada cambio**, en el mAP@0.5 del promedio de las 5 últimas (y en `best.pt`):

| | Base | Ampliado | Ampliado − base |
|---|---:|---:|---:|
| Térmica | 0.222 (0.391) | 0.361 (0.507) | **+0.139** (+0.116) |
| Fusión | 0.317 (0.425) | 0.343 (0.475) | **+0.026** (+0.050) |
| Fusión − térmica | **+0.095** (+0.034) | **−0.018** (−0.032) | |

- **Con los datos de siempre, la fusión supera a la térmica:** +0.095 en el promedio de las 5 últimas y +0.034 en
  `best.pt`.
- **Con los datos ampliados, se invierte:** la térmica queda por encima en las dos cifras (−0.018 y −0.032 para la
  fusión).
  - Por época, `fusion_ampliado` queda debajo de `termico_ampliado` en 37 de las 50, con una diferencia media de
    −0.037; en las 10 últimas, de −0.014.
  - En mAP@0.5:0.95 las dos quedan casi iguales (0.167 contra 0.162).
  - Las diferencias de 0.018 a 0.037 son menores que los saltos de una época a la siguiente (hasta 0.16).
- **Ampliar los datos ayuda mucho más a la térmica (+0.139) que a la fusión (+0.026).**
- **Una explicación posible, sin comprobar:**
  - en `fusion_ampliado`, el 77 % de las imágenes de entrenamiento (10 863 de 14 110) llevan la RGB en 0;
  - en la validación, todas tienen la RGB real;
  - así, el modelo aprende sobre todo con la térmica sola y se valida con una entrada que vio solo en el 23 % de las
    imágenes.
  - Se puede probar en C4 con `evaluar.py --rgb-cero` en validación: si `fusion_ampliado` mejora con la RGB en 0, es la
    RGB real la que la empeora en la validación.
- **Es una sola semilla por corrida y la validación tiene dos vuelos.** Estas cifras son de la validación de
  Ultralytics. Las de C4 salen del evaluador propio.

## C4. Evaluación en validación

**Lo pedido** (21 de noviembre de 2026):
- evaluar las cuatro corridas de C3 en validación con el evaluador propio, con la cifra principal fijada (la última
  época y el promedio de las 5 últimas) y `best.pt` como secundaria;
- evaluar `fusion_base` y `fusion_ampliado` con la RGB en 0, para ver si la caída de la fusión ampliada viene de
  entrenar con el 77 % de las imágenes sin RGB;
- el recall por nivel de oclusión, sobre todo en la severa, con los intervalos por bootstrap y McNemar como en la fase 6.

### Reglas, fijadas por el usuario antes de evaluar (21 de noviembre de 2026)

Cuatro cosas no se podían hacer tal como estaban pedidas. Las decidió el usuario antes de ver ningún resultado y están en
`c4` de `configs/fase7.yaml`:

1. **Nivel de oclusión de la validación: a mano, en modo simple.**
   - Los niveles solo existían para la prueba (FHL 0405), que la fase 7 no toca.
   - La regla automática (sin caja RGB de WiSARD a 3 alturas o menos) se descartó en la fase 4 (kappa 0.427). En la
     validación daría 82 severas: 67 de FHL 0134, donde las personas miden 11 px de mediana, y 15 de MtErie 0007. Así,
     oclusión y tamaño quedarían mezclados.
   - Las 500 personas de los 442 fotogramas las anota el primer anotador, con la pantalla, las teclas y la regla de la
     ronda 2 del nivel a mano de la prueba:
     - `1`, se ve en la RGB: **baja**;
     - `2`, no se ve en la RGB: **severa**;
     - `3`, no es persona: **sin nivel** (caja dudosa, como en la prueba).
2. **Cifra principal: `last.pt` (época 50) con el evaluador propio**, con IC y McNemar.
   - Cada corrida guardó solo `last.pt` y `best.pt`: los pesos de las épocas 46 a 49 no existen. Con el evaluador propio
     no se puede calcular el promedio de las 5 últimas.
   - Al lado va el promedio de las 5 últimas de `results.csv` (validación de Ultralytics), sin IC.
   - `best.pt` va como secundaria, con IC y sin McNemar.
3. **Umbral de confianza: el de la fase 6.** Se fija por modelo y peso con el mayor F2 en la validación, en la rejilla
   de 0.05 a 0.95 con paso 0.05; si hay empate, el más alto.
   - Se elige con todas las personas de WiSARD, sin mirar la anotación de oclusión.
   - Las variantes con la RGB en 0 usan el umbral del mismo peso con la RGB real, para que solo cambie la entrada.
   - **Limitación:** el umbral se elige y se mide en la misma validación, así que el recall sale algo optimista. El sesgo
     es el mismo para todos los modelos.
4. **McNemar: 4 pares, con Bonferroni ×4 dentro de cada subconjunto**, solo con `last.pt`:
   - `fusion_base` contra `termico_base`, y `fusion_ampliado` contra `termico_ampliado` (fusión contra térmica);
   - `fusion_ampliado` con la RGB en 0 contra la misma con la RGB real, y lo mismo con `fusion_base`.
   - Los mismos 4 pares llevan diferencias con IC por bootstrap, con `last.pt` y con `best.pt`.

**Lo demás sigue la fase 6** (`configs/fase6.yaml`):
- IoU 0.5 y maxDets 100, con pycocotools;
- una persona está detectada si una predicción con confianza igual o mayor que el umbral de su modelo la empareja;
- bootstrap por episodios: 10 bloques en la validación, 10 000 remuestreos, seed 0 e intervalo percentil del 95 %;
- McNemar exacta, sin las cajas dudosas.

**Subconjuntos**, todos sobre los 442 fotogramas:
- **todas las personas**, con y sin las cajas dudosas;
- **baja** y **severa**: al evaluar un nivel, las personas del otro nivel y las "no es persona" se ignoran (iscrowd),
  como en la fase 6.

### Herramienta de anotación y lista de personas

**`scripts/fase7_c4_oclusion.py`** usa el modo simple de `scripts/anotar_oclusion.py` sin cambiarlo. Tiene dos ajustes,
porque la herramienta suponía un solo vuelo y la validación tiene dos:
- **la imagen cargada se reconoce por vuelo y fotograma.** La herramienta la reconocía solo por fotograma, y hay 77
  números de fotograma que están en los dos vuelos;
- **las otras cajas de WiSARD (gris) son las del mismo vuelo.** En el fotograma 0 de MtErie 0007 se habrían dibujado 4,
  dos de ellas de FHL 0134; ahora salen 2.

En pantalla se ve además el vuelo. Se probó dibujando la pantalla de una persona de cada vuelo con el mismo número de
fotograma, sin abrir la ventana.

**Lista fija** (`data/fase7/oclusion_validacion_personas.csv`): las cajas térmicas de las etiquetas de validación que lee
el evaluador, comprobadas contra `data/etiquetas/termica`, en orden de vuelo y fotograma.

| Vuelo | Personas | Fotogramas con persona | Fotogramas |
|---|---:|---:|---:|
| FHL 0134 | 211 | 136 | 273 |
| MtErie 0007 | 289 | 169 | 169 |
| **Total** | **500** | **305** | **442** |

El alto de la caja térmica tiene una mediana de 28.5 px (de 9.0 a 59.1 entre los percentiles 10 y 90).

### Corrección en `scripts/evaluar.py`: la opción `--rgb-cero` (C2)

- **El error:** la carpeta de las predicciones con la RGB en 0 llevaba el sufijo `_rgb0`, pero a Ultralytics se le pasaba
  el nombre sin el sufijo. Así, sus predicciones se habrían escrito en la carpeta de las de RGB real, y la de `_rgb0`
  habría quedado vacía.
- **No afectó a nada.** La opción nunca llegó a predecir: en C2 solo se probó con `--solo-verificar`, y no había ninguna
  carpeta `_rgb0`.
- **La corrección:** se pasa el nombre de la carpeta (`name=carpeta.name`). Sin `--rgb-cero` es el mismo nombre de
  antes.

### Predicciones (`scripts/fase7_c4_evaluar.py --solo-predecir`)

- **12 modelos** en `runs/fase7/c4/validacion/`: las 4 corridas con `last.pt` y con `best.pt`, y las 2 fusiones con la
  RGB en 0 con los dos pesos.
- **Cada variante con la RGB en 0 quedó en su carpeta**, con `rgb_cero` y sus pesos en `ultralytics.json`, y sus
  predicciones son distintas de las de la RGB real.
- **El mAP@0.5 que calcula Ultralytics** al predecir coincide con el de `results.csv` en `last.pt` (época 50) y en
  `best.pt`, con diferencias de hasta 0.004.
- Las métricas propias se calculan cuando esté anotada la oclusión, todas juntas.

### Anotación de la oclusión de la validación (21 de noviembre de 2026)

La hizo el primer anotador con `--parte anotar`, sin ver ninguna métrica de C4 ni las predicciones. `--parte nivel`
comprobó que estaban las 500 respuestas y escribió `data/fase7/oclusion_validacion_nivel.csv`.

| Vuelo | Baja (se ve en la RGB) | Severa (no se ve) | Sin nivel ("no es persona") | Total |
|---|---:|---:|---:|---:|
| FHL 0134 | 157 | 41 | 13 | 211 |
| MtErie 0007 | 283 | 5 | 1 | 289 |
| **Total** | **440** | **46** | **14** | **500** |

- **Hay solo 46 severas, y 41 son de FHL 0134.** En la prueba eran 267 de 451.
- **Tiempo:** mediana de 0.30 s por persona (0.4 s en FHL 0134 y 0.2 s en MtErie 0007), y 62 min en total con las
  pausas. En la prueba fue de 0.9 s.
- **Contra la regla automática** (solo referencia, no decide nada): kappa 0.513 en 486 personas.
  - De las 440 bajas a mano, el automático pone 37 en severa.
  - De las 46 severas, pone 13 en baja.
- **Las 14 "no es persona" son cajas dudosas**, y las cifras se calculan con y sin ellas.
  - La principal es sin ellas, igual que en McNemar.
  - Con ellas, el recall de todas las personas cambia 0.011 como mucho (`resultados.csv`).

### Salidas

`scripts/fase7_c4_evaluar.py` (2 min) escribe en `reports/fase7/c4/`:
- `umbrales.csv`: el F2, el recall y la precisión de cada umbral de la rejilla, por modelo;
- `resultados.csv`: las métricas con IC de los 12 modelos y las diferencias de los pares, por subconjunto, con y sin
  las dudosas;
- `mcnemar.csv`;
- `corridas.csv`: la cifra de `results.csv`;
- `recall_por_nivel.png`.

**`scripts/fase7_c4_desglose.py`** (nuevo y solo descriptivo, sin pruebas nuevas) escribe `bloques.csv`,
`remuestreos.csv`, `alto_por_nivel.csv`, `recall_por_vuelo.csv` y `discordantes_por_bloque.csv`.
- Lo agregué después de ver los resultados, para explicar por qué McNemar y el bootstrap no coinciden (ver "Fusión
  contra térmica").
- Usa los mismos umbrales, emparejamientos y remuestreos que la evaluación.

**Bitácora:** 1 fila del nivel, 12 de la evaluación (una por modelo) y 1 del desglose.

### Umbrales (F2 en validación)

| Corrida | `last.pt` | `best.pt` |
|---|---:|---:|
| `termico_base` | 0.05 | 0.20 |
| `termico_ampliado` | 0.05 | 0.15 |
| `fusion_base` | 0.05 | 0.05 |
| `fusion_ampliado` | 0.05 | 0.10 |

- **Con `last.pt`, los cuatro quedan en 0.05, el borde inferior de la rejilla.**
  - El F2 sigue subiendo al bajar el umbral. De 0.10 a 0.05 sube 0.012, 0.016, 0.021 y 0.006, en el orden de la tabla.
  - El máximo puede estar por debajo de 0.05, fuera de la rejilla de la fase 6.
- `fusion_base` con `best.pt` también queda en 0.05, con un F2 apenas 0.001 mayor que en 0.10 (0.492 contra 0.491).
- Con umbrales tan bajos, la precisión de `last.pt` queda entre 0.35 y 0.58.

### Resultados con `last.pt` (cifra principal)

- Todas las personas, sin las cajas dudosas (486).
- Entre paréntesis va el IC del 95 % por bootstrap de episodios.
- La última columna es el promedio de las 5 últimas épocas de `results.csv`: viene del validador de Ultralytics, sin
  IC y con todas las cajas.

| Modelo | Umbral | Recall | Precisión | F2 | mAP@0.5 | mAP@0.5, 5 últimas |
|---|---:|---:|---:|---:|---:|---:|
| `termico_base` | 0.05 | 0.290 (0.212 a 0.518) | 0.358 | 0.302 | 0.223 (0.119 a 0.427) | 0.222 |
| `termico_ampliado` | 0.05 | 0.362 (0.273 a 0.576) | **0.579** | **0.391** | **0.366** (0.300 a 0.526) | **0.361** |
| `fusion_base` | 0.05 | **0.401** (0.054 a 0.543) | 0.348 | 0.389 | 0.322 (0.016 a 0.485) | 0.317 |
| `fusion_base`, RGB en 0 | 0.05 | 0.088 (0.010 a 0.124) | 0.059 | 0.081 | 0.046 (0.001 a 0.070) | |
| `fusion_ampliado` | 0.05 | 0.383 (0.156 a 0.444) | 0.422 | 0.390 | 0.336 (0.090 a 0.465) | 0.343 |
| `fusion_ampliado`, RGB en 0 | 0.05 | 0.352 (0.298 a 0.469) | 0.461 | 0.369 | 0.314 (0.186 a 0.410) | |

- **El mAP@0.5 propio coincide con el de Ultralytics.**
  - Con todas las cajas da 0.227, 0.368, 0.314 y 0.338, contra 0.223, 0.365, 0.310 y 0.335 de su validador con
    `last.pt`.
  - La pequeña diferencia viene de cómo interpola la curva cada uno.
- **En mAP@0.5 el orden es el de C3:** `termico_ampliado`, `fusion_ampliado`, `fusion_base` y `termico_base`.
- **En recall, con el umbral de 0.05, las dos fusiones quedan arriba:** 0.401 y 0.383, contra 0.362 y 0.290 de las
  térmicas.
- **Los IC son muy anchos:** miden de 0.23 a 0.49 en los cuatro modelos. La razón está en "Fusión contra térmica".

**Recall por nivel**, sin las dudosas:

| Modelo | Baja (440) | Severa (46) | Severas detectadas |
|---|---:|---:|---:|
| `termico_base` | 0.286 (0.202 a 0.629) | 0.326 (0.071 a 0.538) | 15 |
| `termico_ampliado` | 0.375 (0.278 a 0.685) | 0.239 (0.000 a 0.480) | 11 |
| `fusion_base` | 0.420 (0.036 a 0.576) | 0.217 (0.000 a 0.333) | 10 |
| `fusion_base`, RGB en 0 | 0.084 (0.011 a 0.114) | 0.130 (0.000 a 0.212) | 6 |
| `fusion_ampliado` | 0.391 (0.110 a 0.460) | 0.326 (0.094 a 0.559) | 15 |
| `fusion_ampliado`, RGB en 0 | 0.359 (0.304 a 0.560) | 0.304 (0.071 a 0.525) | 14 |

Figura: `reports/fase7/c4/recall_por_nivel.png`.

### `best.pt` (secundaria)

| Modelo | Umbral | Recall | Precisión | F2 | mAP@0.5 | Recall en severa (46) |
|---|---:|---:|---:|---:|---:|---:|
| `termico_base` | 0.20 | 0.535 (0.457 a 0.722) | 0.363 | 0.489 | 0.396 (0.200 a 0.456) | 0.326 |
| `termico_ampliado` | 0.15 | **0.638** (0.521 a 0.902) | **0.416** | **0.576** | **0.513** (0.446 a 0.689) | **0.435** |
| `fusion_base` | 0.05 | 0.584 (0.182 a 0.741) | 0.308 | 0.495 | 0.435 (0.109 a 0.567) | 0.370 |
| `fusion_base`, RGB en 0 | 0.05 | 0.142 (0.037 a 0.248) | 0.377 | 0.162 | 0.123 (0.013 a 0.220) | 0.130 |
| `fusion_ampliado` | 0.10 | 0.556 (0.339 a 0.617) | 0.399 | 0.515 | 0.478 (0.196 a 0.595) | 0.326 |
| `fusion_ampliado`, RGB en 0 | 0.10 | 0.621 (0.563 a 0.817) | 0.232 | 0.465 | 0.447 (0.236 a 0.576) | 0.435 |

- `termico_ampliado` queda primero en las cinco cifras de los cuatro modelos con la RGB real.
- `best.pt` es la época con el mayor mAP@0.5:0.95 en esta misma validación (de la 3 a la 23, según la corrida).
  - Así, la cifra sale optimista dos veces: por la época y por el umbral.

### Fusión contra térmica: ¿diferencia real o ruido?

Diferencias de recall con `last.pt` (fusión − térmica), sin las dudosas. Llevan su IC y McNemar con Bonferroni ×4:

| Subconjunto | Par | Diferencia de recall (IC) | Solo la fusión / solo la térmica | p con Bonferroni |
|---|---|---:|---:|---:|
| Todas (486) | `fusion_base` − `termico_base` | +0.111 (−0.318 a 0.289) | 105 / 51 | **0.00007** |
| | `fusion_ampliado` − `termico_ampliado` | +0.021 (−0.300 a 0.155) | 84 / 74 | 1 |
| Baja (440) | `fusion_base` − `termico_base` | +0.134 (−0.353 a 0.313) | 104 / 45 | **0.000006** |
| | `fusion_ampliado` − `termico_ampliado` | +0.016 (−0.400 a 0.160) | 80 / 73 | 1 |
| Severa (46) | `fusion_base` − `termico_base` | −0.109 (−0.243 a −0.023) | 1 / 6 | 0.50 |
| | `fusion_ampliado` − `termico_ampliado` | +0.087 (0.000 a 0.222) | 5 / 1 | 0.88 |

Con `best.pt` (sin McNemar), en el mismo orden:
- todas: +0.049 (−0.518 a 0.273) y −0.082 (−0.509 a 0.066);
- severa: +0.043 (−0.190 a 0.127) y −0.109 (−0.167 a 0.000).

**En `fusion_base` contra `termico_base`, McNemar y el bootstrap no coinciden.** McNemar da una diferencia clara, y el IC
incluye el 0 con mucho margen. La razón está en cómo se reparten las personas.
- **MtErie 0007 es un solo episodio.**
  - Sus 169 fotogramas tienen persona, así que el vuelo entero es un bloque del bootstrap. Ese bloque tiene 288 de las
    486 personas (59 %).
  - FHL 0134 se reparte en los otros 9 bloques.
  - Cada bloque falta en el 35 % de los remuestreos (`remuestreos.csv`). Así, en un tercio de ellos no hay ninguna
    persona de MtErie 0007.
- **Los dos vuelos van en direcciones opuestas.** Viene de `recall_por_vuelo.csv` y `discordantes_por_bloque.csv`, y
  es descriptivo, sin prueba:

| Recall con `last.pt` | FHL 0134 (198) | MtErie 0007 (288) |
|---|---:|---:|
| `termico_base` | 0.379 | 0.229 |
| `termico_ampliado` | **0.515** | 0.257 |
| `fusion_base` | 0.152 | **0.573** |
| `fusion_base`, RGB en 0 | 0.051 | 0.115 |
| `fusion_ampliado` | 0.288 | 0.448 |
| `fusion_ampliado`, RGB en 0 | 0.389 | 0.326 |
| Alto de la caja térmica (mediana) | 11 px | 45 px |

  - De las 105 personas que solo detecta `fusion_base`, 102 son de MtErie 0007. De las 51 que solo detecta
    `termico_base`, 48 son de FHL 0134.
  - Con `fusion_ampliado` contra `termico_ampliado` pasa lo mismo:
    - en MtErie 0007, 61 contra 6 a favor de la fusión;
    - en FHL 0134, 68 contra 23 a favor de la térmica.
- **McNemar trata a las 486 personas como independientes.** Aquí 288 salen de un mismo episodio seguido.
  - Si la diferencia viene de un solo vuelo, McNemar no lo ve y su p sale muy pequeño.
  - El bootstrap por episodios sí lo tiene en cuenta, y por eso su IC es tan ancho.
- **Conclusión: en la validación, la diferencia entre fusión y térmica depende del vuelo y cae dentro del ruido del
  bootstrap.**
  - La fusión gana en MtErie 0007, donde las personas miden 45 px y casi todas se ven en la RGB.
  - La térmica gana en FHL 0134, donde miden 11 px.
  - Con dos vuelos no se puede decir cuál es mejor en general.
  - La significancia de McNemar en `fusion_base` refleja sobre todo un episodio de MtErie 0007.

### La prueba con la RGB en 0

| Recall con `last.pt` | RGB real | RGB en 0 | Diferencia (IC) | Solo con la RGB real / solo con la RGB en 0 | p con Bonferroni |
|---|---:|---:|---:|---:|---:|
| `fusion_base` | 0.401 | 0.088 | −0.313 (−0.432 a −0.036) | 157 / 5 | **1.2 × 10⁻³⁹** |
| `fusion_ampliado` | 0.383 | 0.352 | −0.031 (−0.100 a 0.166) | 56 / 41 | 0.62 |

- **Diferencias de mAP@0.5:**
  - `fusion_base`: −0.276 (−0.419 a −0.013);
  - `fusion_ampliado`: −0.022 (−0.119 a 0.163).
- **Con `best.pt`:**
  - `fusion_base` pierde 0.442 de recall (−0.565 a −0.113).
  - `fusion_ampliado` gana 0.066 (−0.023 a 0.459), pero con menos precisión (0.232 contra 0.399). Su mAP@0.5 baja 0.030.
- **`fusion_base` depende de la RGB.**
  - Sin ella pierde casi todo, en los dos vuelos: en FHL 0134 pasa de 0.152 a 0.051, y en MtErie 0007 de 0.573 a 0.115.
  - Siempre entrenó con la RGB real.
- **`fusion_ampliado` casi no depende de la RGB.**
  - Con la RGB en 0 conserva el 92 % de su recall y el 93 % de su mAP@0.5.
  - Es lo esperable si entrenó con el 77 % de las imágenes sin RGB: aprendió a detectar con la térmica sola.
- **La explicación de C3 no se confirma en el total.**
  - C3 decía que, si `fusion_ampliado` mejoraba con la RGB en 0, era la RGB real la que la empeoraba en la validación.
  - En el total no mejora: baja 0.031 en recall y 0.022 en mAP@0.5, dentro del ruido.
- **Por vuelo cambia, en direcciones opuestas** (descriptivo):
  - en FHL 0134, con la RGB en 0 detecta más: pasa de 0.288 a 0.389, con 34 personas que solo detecta así, contra 14;
  - en MtErie 0007 detecta menos: pasa de 0.448 a 0.326, con 7 contra 42.
  - En FHL 0134 la RGB real sí la empeora. Pero aun sin ella queda debajo de `termico_ampliado` (0.389 contra 0.515), así
    que la RGB no explica toda la diferencia con la térmica en ese vuelo.
- **La "caída" de C3 tampoco aparece clara con el evaluador propio.** `fusion_ampliado` contra `termico_ampliado` da
  +0.021 en recall y −0.031 en mAP@0.5, las dos dentro del ruido.

### Oclusión severa

- **Son 46 personas, 41 de FHL 0134**, repartidas en 7 bloques. El bloque 8 tiene 21.
- **Recall:**
  - con `last.pt`, de 0.217 a 0.326 (de 10 a 15 personas detectadas);
  - con `best.pt`, de 0.326 a 0.435.
- **Ningún par es significativo con McNemar.** Como mucho, 7 personas las detecta un solo modelo.
- **Un IC excluye el 0, pero no es robusto:** `fusion_base` − `termico_base`, −0.109 (−0.243 a −0.023).
  - Sale de 7 personas (1 contra 6), todas de FHL 0134, en los bloques 3, 6 y 8.
  - Los remuestreos que no incluyen ninguno de esos tres bloques dan 0. Son 248 de 10 000 (2.48 %), justo debajo del
    2.5 % que marca el límite del IC.
  - McNemar da p = 0.50 con Bonferroni.
  - Con su mAP@0.5 pasa lo mismo: −0.096 (−0.247 a −0.001).
- **Conclusión:** en la validación no hay evidencia de que la fusión detecte más o menos personas en oclusión severa que
  la térmica. Con 46 personas, casi todas de un vuelo, la validación no puede responder la pregunta central.

### Limitaciones de C4

1. **El umbral se elige y se mide en la misma validación.**
   - Recall, precisión y F2 salen optimistas. El mAP@0.5 no usa umbral, así que no se ve afectado.
   - En las reglas escribí que el sesgo es el mismo para todos los modelos. Es más exacto decir que va en la misma
     dirección para todos, pero su tamaño puede variar.
   - **Con `last.pt`**, los cuatro umbrales quedaron en 0.05, el borde de la rejilla, y el F2 seguía subiendo.
     - El umbral funciona casi como uno fijo, de 0.05 para todos.
     - Un umbral más bajo daría más recall, así que el recall queda limitado por la rejilla y no por el modelo.
   - **Con `best.pt`**, los umbrales van de 0.05 a 0.20. Además, `best.pt` ya se eligió con esta misma validación.
   - En la fase 6 el umbral se elegía en la validación y se aplicaba sin cambios a la prueba. Aquí no hay prueba, porque
     la fase 7 no usa FHL 0405/0406. Así, ninguna cifra de C4 es fuera de la muestra.
2. **Oclusión y tamaño quedan mezclados en FHL 0134.**
   - 41 de las 46 severas son de FHL 0134. Ahí las personas miden de 8 a 13 px de alto entre los percentiles 10 y 90,
     con mediana de 10 px en baja y 12 px en severa.
   - En MtErie 0007 la mediana es de 46 px en baja y 27 px en severa.
   - Comparar severa con baja en el total es casi comparar FHL 0134 con MtErie 0007: personas diminutas contra personas
     grandes, en otra escena y con otro ángulo de cámara. La diferencia entre niveles no se puede atribuir a la
     oclusión.
   - Dentro de FHL 0134 los dos niveles tienen casi el mismo alto. El recall de severa contra baja ahí (41 y 157
     personas, descriptivo) no muestra un patrón común:

     | Modelo | Severa | Baja |
     |---|---:|---:|
     | `termico_base` | 0.341 | 0.389 |
     | `termico_ampliado` | 0.268 | 0.580 |
     | `fusion_base` | 0.220 | 0.134 |
     | `fusion_ampliado` | 0.317 | 0.280 |

   - Lo mismo vale para fusión contra térmica. La fusión gana en el vuelo de personas grandes y la térmica en el de
     diminutas, pero tamaño, escena y vuelo van juntos y no se pueden separar con dos vuelos.
   - Decidir si una persona de 10 px "se ve en la RGB" es difícil, y la anotación de FHL 0134 carga con esa
     incertidumbre.
3. **La anotación:**
   - la hizo un solo anotador, sin un segundo que la revise;
   - la mediana fue de 0.30 s por persona, contra 0.9 s en la prueba;
   - se hizo sin ver ninguna métrica de C4, pero después de conocer las cifras de C3.
4. **Los 10 bloques del bootstrap son muy desiguales**, de 1 a 288 personas.
   - Los IC reflejan sobre todo qué vuelo entra en cada remuestreo.
   - Con tan pocos bloques, los percentiles son poco finos (ver la severa).
5. **McNemar supone personas independientes**, y aquí 288 de las 486 salen de un mismo episodio. Su p sale demasiado
   pequeño cuando la diferencia viene de un solo vuelo.
6. **Hay una semilla por corrida y dos vuelos de validación**, como ya se dijo en C3.

### Resumen de C4

- **Cifra principal (`last.pt`):** en mAP@0.5, `termico_ampliado` 0.366, `fusion_ampliado` 0.336, `fusion_base` 0.322 y
  `termico_base` 0.223.
  - Es el mismo orden que el promedio de las 5 últimas de `results.csv` (0.361, 0.343, 0.317 y 0.222).
  - En recall, con el umbral de 0.05, las fusiones quedan arriba (0.401 y 0.383, contra 0.362 y 0.290).
- **`best.pt`:** `termico_ampliado` queda primero en todo (mAP@0.5 0.513, recall 0.638).
- **Fusión contra térmica: dentro del ruido.**
  - McNemar da significativa la ventaja de `fusion_base` sobre `termico_base` (en todas y en baja), pero viene de un
    solo episodio de MtErie 0007. En FHL 0134 gana la térmica.
  - El IC por episodios incluye el 0 en todas y en baja, con los dos pares y con los dos pesos.
- **RGB en 0:**
  - `fusion_ampliado` aprendió a detectar casi solo con la térmica: sin RGB conserva el 92 % de su recall.
  - `fusion_base` depende de la RGB: conserva el 22 %.
  - La RGB real no empeora a `fusion_ampliado` en el total, pero sí en FHL 0134.
- **Severa:** son 46 personas, casi todas de FHL 0134, y no hay ninguna diferencia demostrable.

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
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida termico_base > runs\fase7\termico_base.log 2>&1"
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida termico_ampliado > runs\fase7\termico_ampliado.log 2>&1"
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida fusion_base > runs\fase7\fusion_base.log 2>&1"
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida fusion_ampliado > runs\fase7\fusion_ampliado.log 2>&1"
.venv\Scripts\python.exe scripts\evaluar.py --config configs\fase6.yaml --rutas configs\rutas.yaml --particion validacion --modelos fusion termico --rgb-cero --solo-verificar
.venv\Scripts\python.exe scripts\fase7_origen.py --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\fase7_copiar.py --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte preparar
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_c4_evaluar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --solo-predecir > runs\fase7\c4_predecir.log 2>&1"
.venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte anotar
.venv\Scripts\python.exe scripts\fase7_c4_oclusion.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte nivel
.venv\Scripts\python.exe scripts\fase7_c4_evaluar.py --config configs\fase7.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\fase7_c4_desglose.py --config configs\fase7.yaml --rutas configs\rutas.yaml
```
