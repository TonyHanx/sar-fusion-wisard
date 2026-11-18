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

**Lo que quedaría para `termico_ampliado`**, por sitio (`clasificacion/por_sitio.csv`), comparado con el entrenamiento
actual (diagnóstico, A3):

| Sitio | Fotogramas usados | Con persona | Personas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Airfield | 6 271 | 1 249 | 1 484 | 31 | 65 | 547 | 432 | 409 |
| Baker FLIR | 1 993 | 1 933 | 3 020 | 0 | 8 | 774 | 1 929 | 309 |
| Carnation FLIR | 2 849 | 1 214 | 2 175 | 0 | 0 | 8 | 304 | 1 863 |
| FHL (0404, 0565, 0567) | 2 040 | 1 618 | 3 212 | 2 | 86 | 548 | 1 158 | 1 418 |
| Karen | 2 555 | 2 502 | 3 819 | 0 | 3 | 384 | 859 | 2 573 |
| **Nuevo, total** | **15 708** | **8 516** | **13 710** | **33** | **162** | **2 261** | **4 682** | **6 572** |
| Entrenamiento actual | 3 247 | — | 9 340 | 22 | 159 | 1 459 | 2 411 | 5 289 |

- Las personas de menos de 12 px pasan de 181 a 376, y las de 12 a 20 px, de 1 459 a 3 720. En FHL 0134, el 22 % de las
  personas de validación mide de 8 a 12 px.
- 7 192 de los fotogramas nuevos (46 %) no tienen personas. 5 022 son de Airfield.
- **Tiempo:** el entrenamiento pasaría de 3 247 a unas 18 955 imágenes, unas 5.8 veces más.
  - Con 42–44 s por época hoy, serían unos 4 min por época: unas 7 h para 100 épocas. Con `patience=20` puede parar
    antes.
  - Lo confirmo con una medida antes de C3.

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
- **Puntos a mano: pendientes.** Hay que marcarlos tú, 2 fotogramas por vuelo y 6 puntos o más por fotograma.
  - Usa la herramienta de la fase 2, sin cambiarla, con `scripts/fase7_marcar_puntos.py`.
  - Fotogramas: los más nítidos cerca de 1/3 y 2/3 del rango (`c0.marcado.fotogramas`).
    - 0403: 63 y 156.
    - 0564: 345 y 663.
    - 0566: 227 y 681, donde se ven luces. Ahí la RGB se aclara 6 veces, solo en pantalla.
  - La sugerencia celeste es la de la fase 2: la franja nominal y luego la de tus propios puntos. No usa ninguna de las
    semejanzas que se miden, así que no te ancla a ellas.
  - Luego `--parte puntos` mide el error de las 3 semejanzas y la coherencia de los puntos (se quita uno y se ajusta con
    los demás).

### Preguntas abiertas de C0

1. ¿Confirmas la clasificación de las 26 carpetas y la regla de los huecos cortos?
2. **FHL 0566 (RGB de noche):** propongo usar su térmica en `fusion_ampliado` como térmica sin pareja (RGB en 0).
   - La RGB casi negra no aporta, y su alineación no se puede medir con el fondo. Con los puntos, quizá sí, en las
     luces.
   - Otra opción: incluirla con la semejanza de 0401.
3. **Carnation Enterprise 0023/0024** (739 pares anotados, 1 713 cajas térmicas): se excluyó de los tres modelos en la
   fase 2 por el zoom variable de la RGB.
   - Su térmica no tiene ese problema. ¿Entra en `termico_ampliado`?
   - En `fusion_ampliado` iría como térmica sin pareja.
4. **Pares excluidos de nuestros vuelos de entrenamiento:** son 365 anotados, con 575 cajas térmicas.
   - 149 son el tramo de Baker con personas sin caja en la térmica, y no se usan nunca.
   - El resto (desfases, despegue y aterrizaje) tiene la térmica bien. ¿Entran en `termico_ampliado` y, como térmica sin
     pareja, en `fusion_ampliado`?

### Comandos

```
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte auditar
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte ampliar
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte alineacion
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte clasificar
.venv\Scripts\python.exe scripts\fase7_marcar_puntos.py --config configs\fase7.yaml --rutas configs\rutas.yaml --vuelo 210924_FHL_Enterprise_0403
.venv\Scripts\python.exe scripts\fase7_c0_auditoria.py --config configs\fase7.yaml --rutas configs\rutas.yaml --parte puntos
.venv\Scripts\python.exe scripts\fase7_copiar.py --config configs\fase7.yaml --rutas configs\rutas.yaml
```
