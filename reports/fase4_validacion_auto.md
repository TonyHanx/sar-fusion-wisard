# Fase 4: validación del nivel de oclusión automático

Fecha: 1 de noviembre de 2026. Generado con `scripts/fase4_validacion_auto.py` (configuración en `configs/fase3.yaml`,
sección `validacion_auto`). Tablas e imágenes en `reports/fase4_validacion_auto/`. No se tocó `data/` ni el dataset
original. Hay dos filas nuevas en la bitácora.

```
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

## Dos niveles

En la muestra anotada a mano no hay ninguna persona moderada (0 de 68): el λ RGB manual queda en 0 a 0.047 o en 1.
Por eso el nivel pasa a dos clases (decidido el 1 de noviembre de 2026):

| Nivel | Manual (primer anotador) | Automático (WiSARD) |
|---|---|---|
| **Severa** | La persona no se ve en la RGB (visible RGB "no visible") | No hay caja RGB de WiSARD a 3 alturas o menos |
| **Baja** | Se ve (tiene visible RGB) | Hay caja RGB de WiSARD a 3 alturas o menos |

- **Regla:** se usa el automático si el kappa de Cohen binario es de 0.61 o más.
- El kappa de 3 niveles (λ por áreas) se calcula solo para reportar la comparación.
- Las "no es persona" (7) y las "fuera de cuadro" (0) no entran.

## Resultado: kappa binario

| Comparación (68 personas) | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---:|---:|
| **Dos niveles (decidía; ver abajo)** | **0.940** (0.858 a 1) | 97.1 % | 2 |
| Tres niveles, λ por áreas (solo se reporta) | 0.675 (0.536 a 0.814) | 82.4 % | 12 |

- El IC es asintótico (statsmodels). En el binario, su límite superior da 1.022: se recorta a 1.
- **Decisión con esta anotación:** el kappa binario es de 0.61 o más, así que se iba a usar el nivel automático.
- **Ya no decide** (1 de noviembre de 2026): la decisión pasa al kappa del automático contra el primer anotador en modo
  simple de la ronda 2, con la regla aclarada. El 0.940 queda como resultado de la primera anotación, con cajas. Ver
  "Concordancia entre anotadores".

**Matriz de confusión, dos niveles** (filas: manual; columnas: automático):

| Manual \ automático | baja | severa | Total |
|---|---:|---:|---:|
| baja | 28 | 1 | 29 |
| severa | 1 | 38 | 39 |
| Total | 29 | 39 | 68 |

### Los 2 desacuerdos

Imágenes en `reports/fase4_validacion_auto/desacuerdos/` (vista de la herramienta y paneles sin cajas). La lista está
en `desacuerdos_dos_niveles.csv`.

| N.º | Fotograma, caja | Manual | Automático | Por qué |
|---:|---|---|---|---|
| 68 | 864, 2 de 2 | baja (se ve) | severa | El par tiene una sola caja RGB, la de la otra persona, a 23.9 alturas. El primer anotador ve en la RGB una forma oscura rojiza: falta la caja RGB en WiSARD. |
| 73 | 894, 2 de 3 | severa (no se ve) | baja | WiSARD tiene una caja RGB propia a 0.47 alturas (no es la de su vecina, la 74). El primer anotador no la ve. |

- La 68 es un error de las etiquetas RGB de WiSARD (falta una caja).
- La 73 es al revés: WiSARD marca a la persona en la RGB y el primer anotador no la vio. Queda por decidir a ojo quién
  tiene razón.
- Cualquiera de los dos resultados mantiene el kappa sobre 0.61.

## Tres niveles (solo se reporta)

| Manual \ automático | baja | moderada | severa |
|---|---:|---:|---:|
| baja | 18 | 9 | 2 |
| moderada | 0 | 0 | 0 |
| severa | 1 | 0 | 38 |

- 11 de los 12 desacuerdos son personas que el primer anotador ve enteras y el automático sube a moderada (9) o severa
  (2).
- La causa es la fórmula de áreas, λ = 1 − área RGB / área térmica. La caja RGB de WiSARD es más chica que la térmica
  (la térmica incluye el halo de calor), así que una persona visible queda con λ entre 0.35 y 0.74.
- Las 2 que pasan a severa:
  - La 68, sin caja RGB.
  - La 70 (fotograma 891), con λ 0.74 por áreas.
- La diferencia de λ (automático − manual) tiene media +0.108, media absoluta 0.127 y mediana 0.

## Nivel automático en FHL 0405

| Grupo | Personas | Severa | Baja |
|---|---:|---:|---:|
| Todas (928 fotogramas) | 1 501 | 976 (65.0 %) | 525 |
| 1 de cada 3 (310 fotogramas) | 498 | 323 (64.9 %) | 175 |
| Muestra | 75 | 46 | 29 |

El nivel automático está en `data/oclusion_auto.csv` (columna `sin_caja_rgb_cerca`: severa si es verdadera). Ese archivo
no cambió.

## Las 7 "no es persona" (para confirmar)

Mosaico en `reports/fase4_validacion_auto/no_es_persona.jpg` y lista en `no_es_persona.csv`. Cada fila trae:
- la RGB alineada;
- la térmica;
- la térmica con el realce de la herramienta (CLAHE, tecla `e`);
- la térmica con el contraste estirado en la zona (percentiles 1 a 99);
- esta última con las cajas térmicas de WiSARD.

Los triángulos amarillos señalan el centro de la caja.

| N.º | Fotograma, caja | Lo que se ve |
|---:|---|---|
| 30 | 429, 2 de 4 | El mismo objeto marrón (ver abajo) |
| 33 | 447, 1 de 4 | El mismo objeto marrón (ver abajo) |
| 36 | 453, 1 de 4 | El mismo objeto marrón (ver abajo) |
| 37 | 459, 1 de 4 | El mismo objeto marrón (ver abajo) |
| 38 | 462, 4 de 4 | El mismo objeto marrón (ver abajo) |
| 41 | 474, 3 de 4 | El mismo objeto marrón (ver abajo) |
| 46 | 501, 1 de 4 | La caja queda sin calor, al lado de una mancha compacta que tiene su propia caja de WiSARD (gris): la persona real está en la otra caja. |

- **30 a 41:** son el mismo objeto en los 6 fotogramas.
  - En la RGB es marrón claro y alargado. Parece madera: un tronco o un tocón.
  - En la térmica es una zona tibia con textura de follaje. No es una mancha compacta como la de las personas.
  - Es compatible con "no es persona", pero es el primer anotador quien lo confirma.
- **Consecuencias:**
  - Las 7 tienen nivel automático severa, porque no hay caja RGB cerca. En la muestra son 7 de las 46 severas
    automáticas (15 %).
  - La caja térmica de WiSARD de ese objeto es parte de las etiquetas de referencia de la prueba. Los fotogramas de
    429 a 474 tienen todos de 4 a 5 cajas, así que probablemente esté en unos 46 fotogramas seguidos.

## FHL 0405, fotogramas 58 a 64: posible desfase en el 60

Imagen en `reports/fase4_validacion_auto/fondo_0058-0064.jpg` (mezclas RGB alineada + térmica con el mismo recorte, de
57 a 65, y el 60 entero y por separado; abajo dice "peor" porque usa la imagen de la fase 2). Tabla de 50 a 72 en
`fondo_0058-0064.csv`.

**Dos medidas:**

1. **Fondo RGB-térmica** (la medida de la fase 2): correlación de fase de los gradientes de la RGB alineada contra la
   térmica. **No es fiable de 50 a 61 ni en 63** (respuesta < 0.10: en el bosque las dos cámaras no comparten bordes).
   - Solo el 62 da una medida fiable: (+1, +6) px, sin desfase.
   - El 64 queda justo debajo del umbral (0.082), con (0, +6).
2. **Salto entre fotogramas seguidos (nueva).** Se mide el movimiento desde el fotograma anterior dentro de cada
   cámara, RGB con RGB y térmica con térmica.
   - Dentro de una misma cámara la correlación sí es fiable (respuestas de 0.35 a 0.94).
   - La diferencia de los dos movimientos ("salto") es cuánto cambia el corrimiento de la RGB respecto de la térmica.
   - Un desfase solo en p da un salto en p y el contrario en p + 1.

| Pos. | Estado | Fondo RGB-térmica (px) | Salto (dx, dy) px | Personas: RGB − térmica (px) | Mediana (alturas) |
|---:|---|---|---|---|---:|
| 57 | excluido (desfase 55–57) | no fiable | (−2, −5) | (−6, −32) (+1, −35) | 1.31 |
| 58 | final | no fiable | (0, **+18**) | (0, −6) (−4, −12) | 0.41 |
| 59 | final | no fiable | (0, +6) | (−3, −3) (−2, −9) | 0.31 |
| **60** | final | no fiable | (−1, **−13**) | **(−4, −15) (0, −18)** | **0.76** |
| 61 | final | no fiable | (+1, **+11**) | (−4, −1) (+3, −9) | 0.31 |
| 62 | final | (+1, +6) | (+1, +1) | (−6, −2) (−4, −6) | 0.32 |
| 63 | final | no fiable | (**−22**, +1) | (−22, +22) (+5, 0) | 0.86 |
| 64 | final | no fiable | (+11, +8) no fiable | (−3, 0) (−2, −5) | 0.21 |
| 65 | excluido (desfase 65–67) | (−1, −18) | (0, **−22**) | (−4, −23) (0, −25) | 1.02 |
| 70 | final | (+2, 0) | (+1, **+24**) | (+2, 0) | 0.09 |
| 71 | final | (+2, −13) | (0, **−12**) | (−1, −13) | 0.60 |
| 72 | final | no fiable (0.096) | (0, −3) | (0, −14) | 0.63 |

- **El 60 parece desfasado, pero menos que los tramos excluidos.**
  - El salto lo muestra con medida fiable: la RGB se corre 13 px hacia arriba respecto de la térmica al pasar del 59
    al 60, y vuelve 11 px al pasar al 61.
  - Las dos personas lo confirman: −15 y −18 px en y (0.72 y 0.80 alturas), en la misma dirección que en 55–57 y 65–69.
  - Coincide con la persona 10 de la muestra (fotograma 60, caja 2). El primer anotador corrió su completa RGB 17 px
    hacia arriba.
  - Queda **por debajo de las reglas de la fase 2**: mediana de 0.76 alturas, que no pasa de 1, y unos 13 a 18 px, que
    no pasan de los 20 px de la extensión por el fondo.
- **58:** el salto de +18 es la vuelta del desfase 55–57.
- **63:** las señales se contradicen.
  - La térmica se mueve 22 px en x respecto de la RGB, y una persona se corre (−22, +22).
  - La otra persona queda alineada (+5, 0).
  - No se puede afirmar un desfase.
- **71 y 72** tienen un corrimiento parecido al del 60:
  - En el 71, el fondo fiable da −13 px y el salto −12.
  - La persona se corre −13 y −14 px (0.60 y 0.63 alturas).
  - Si se excluye el 60 por este criterio, lo coherente es revisar también 71–72.

**Si se excluyera el 60:**
- La prueba pasaría de 928 a 927 fotogramas.
- Los anotados, de 310 a 309.
- La persona 10 saldría de la muestra: quedarían 67 comparables.
- Es un acuerdo (baja y baja), así que el kappa binario apenas cambia.

## Modo simple

Primero lo usó solo el segundo anotador (ronda 1). Desde la ronda 2 lo usan los dos, con la misma pantalla y la misma
regla (decidido el 1 de noviembre de 2026).

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple
```

- **Personas:** las 75 de la muestra, en su orden (el mismo para los dos).
- **Lo que ve:** la RGB alineada y la térmica, ampliadas alrededor de la persona, con la misma vista inicial que la
  herramienta.
  - Su caja térmica de WiSARD, en verde. En la RGB va donde la pone la semejanza.
  - Las demás cajas térmicas de WiSARD del fotograma, en gris.
  - Los triángulos amarillos que señalan a la persona.
- **Lo que no ve:**
  - No dibuja cajas.
  - No hay precarga: de la lista de personas solo se usan las cajas térmicas de WiSARD y las imágenes, no la caja RGB.
  - No lee ningún archivo de respuestas: ni `data/oclusion.csv` (la anotación con cajas del primero) ni los del otro
    anotador ni los de otras rondas. Solo lee el propio, para retomar.
- **Teclas:**
  - `1`: se ve en la RGB.
  - `2`: no se ve en la RGB.
  - `3`: no es persona.
  - Tras responder pasa a la siguiente sin responder.
  - `x` borra la respuesta, y `n` / `b` pasan a la siguiente o a la anterior.
  - Rueda o `+` / `-` para el zoom, flechas para mover la vista, `h` oculta las cajas y `q` sale.
  - `e` (realce de contraste) solo estuvo en la ronda 1. Desde la ronda 2 está desactivado.
- **Guarda** en el archivo de la ronda (ver la sección siguiente), después de cada respuesta. Columnas: `id`,
  `respuesta` (`se_ve_rgb`, `no_se_ve_rgb`, `no_es_persona`), `tiempo_s` y `guardado`. Al abrir de nuevo se retoma.
- **Columna `anotador`:** `segundo_simple` o `primero_simple`. La herramienta no abre un archivo del otro anotador.
- **Prueba:** `scripts/probar_anotar_oclusion.py` pasó de 59 a 71 comprobaciones con este modo, a 73 con la ronda 2 y a
  80 con `--primero-simple`. Todas correctas. Entre otras cosas, comprueba que los paneles del primero y del segundo
  son idénticos y que el primero solo lee la lista de personas y la muestra. Las capturas de los modos anteriores
  salieron idénticas.
- **Capturas:** `reports/oclusion/herramienta_segundo_simple.jpg` y `reports/oclusion/herramienta_primero_simple.jpg`,
  con la regla de la ronda 2 en pantalla.
- Las respuestas se pasan a los dos niveles: "se ve" = baja, "no se ve" = severa, y "no es persona" aparte. Los
  resultados están en la sección siguiente.

## Concordancia entre anotadores (dos clases)

Tres anotaciones de "se ve en la RGB" sobre las mismas 75 personas:

| Anotación | Quién | "Se ve en la RGB" | Realce (`e`) | Precarga | Archivo |
|---|---|---|---|---|---|
| Con cajas (`--muestra`) | primero | sin definir; dibuja la visible RGB de lo que ve | disponible | visible RGB = caja RGB de WiSARD a 3 alturas o menos | `data/oclusion.csv` |
| Ronda 1, modo simple | segundo | sin definir | disponible | ninguna | `data/oclusion_segundo_simple_ronda1.csv` |
| Ronda 2, modo simple | primero y segundo | **regla aclarada** | **desactivado** | ninguna | `data/oclusion_primero_simple_ronda2.csv` y `data/oclusion_segundo_simple_ronda2.csv` |

**Qué cambió en la regla.**

- **Antes (con cajas y ronda 1):** "se ve" no tenía definición y se podía aclarar la imagen (tecla `e`).
  - El primero anotó con la caja RGB de WiSARD precargada y dibujó la visible RGB.
  - El segundo respondió sin precarga.
  - Casi todos los desacuerdos de la ronda 1 dependen de si se aclara la imagen (ver abajo).
- **Ronda 2:** "se ve" = reconoces una parte del cuerpo (ropa, cabeza, brazos o piernas) en la RGB con el brillo
  normal, sin realce. Una mancha oscura, una sombra o una rama no cuentan. Si dudas, "no se ve".
  - La regla está en `docs/reglas_anotacion.md` y la herramienta la muestra en pantalla.
  - El realce está desactivado.
  - **Los dos anotadores responden igual**: la misma pantalla, sin precarga ni cajas, y sin ver las respuestas del
    otro. Así los dos usan el mismo criterio (decidido el 1 de noviembre de 2026).

**Resultados:**

| Comparación | Ronda | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---|---:|---:|
| Automático contra primero con cajas (primera anotación; ya no decide) | — | 0.940 (0.858 a 1) | 97.1 % | 2 de 68 |
| Primero con cajas contra segundo | 1 | 0.507 (0.312 a 0.701) | 74.6 % | 16 de 63 |
| **Primero contra segundo, los dos en modo simple (decide la concordancia)** | 2 | pendiente | | |
| **Automático contra primero en modo simple (decide si se usa el automático)** | 2 | pendiente | | |
| Respuestas del primero que cambian entre las cajas y el modo simple | 2 | pendiente | | |

- **Primer anotador con cajas:** "se ve" si tiene visible RGB; "no se ve" si la visible RGB es "no visible".
- **Aparte:** las "no es persona" de cualquiera de los dos (y las "fuera de cuadro" de las cajas del primero).
- **Salidas** de cada ronda en `reports/fase4_validacion_auto/entre_anotadores/ronda<N>/`: `respuestas.csv`,
  `kappa.csv`, `matriz.csv`, `tabla_completa.csv`, `desacuerdos.csv` e `imagenes/`. Cada ronda agrega una fila a la
  bitácora.

### Ronda 1 (regla ambigua)

Pedida el 1 de noviembre de 2026, cuando el segundo anotador terminó las 75 en modo simple. "Se ve en la RGB" no tenía
definición y el realce de contraste (`e`) estaba disponible.

```
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 1
```

- **Segundo anotador** (`data/oclusion_segundo_simple_ronda1.csv`, antes `data/oclusion_segundo_simple.csv`, sin
  cambios): 42 "se ve", 24 "no se ve" y 9 "no es persona".
- **Aparte:** 12 personas, y no hay ninguna "fuera de cuadro".
- **Salidas** en `reports/fase4_validacion_auto/entre_anotadores/ronda1/` (antes en `entre_anotadores/`; se volvieron a
  generar en una carpeta temporal y salieron idénticas).

| Comparación (63 personas) | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---:|---:|
| **Primer anotador contra segundo** | **0.507** (0.312 a 0.701) | 74.6 % | 16 |
| Primero contra automático (informativo) | 0.936 (0.848 a 1) | 96.8 % | 2 |
| Segundo contra automático (informativo) | 0.507 (0.312 a 0.701) | 74.6 % | 16 |

- Un kappa de 0.507 es un **acuerdo moderado** (0.41 a 0.60 en la escala de Landis y Koch). Queda por debajo de 0.61,
  el umbral que se usó para aceptar el automático.
- CLAUDE.md no fija qué hacer con este kappa.
- Las dos filas informativas usan las mismas 63 personas: el automático coincide con el primer anotador, no con el
  segundo.
- Que las filas 1 y 3 den lo mismo es casualidad.
  - El primero y el automático solo difieren en la 68 y la 73.
  - El segundo coincide con el primero en la 68 y con el automático en la 73.

**Matriz de confusión** (filas: primer anotador; columnas: segundo):

| Primero \ segundo | se ve | no se ve | Total |
|---|---:|---:|---:|
| se ve | 26 | 2 | 28 |
| no se ve | 14 | 21 | 35 |
| Total | 40 | 23 | 63 |

**Tabla completa, con las "no es persona":**

| Primero \ segundo | se ve | no se ve | no es persona |
|---|---:|---:|---:|
| se ve | 26 | 2 | 1 |
| no se ve | 14 | 21 | 4 |
| no es persona | 2 | 1 | 4 |

#### Los desacuerdos de la ronda 1

**Imágenes**, en `reports/fase4_validacion_auto/entre_anotadores/ronda1/imagenes/`:
- Por persona, la vista de la herramienta con las cajas del primer anotador y, debajo, los paneles sin cajas (RGB,
  térmica y RGB con realce). El encabezado dice qué respondió cada uno.
- `mosaico.jpg` las junta.
- `secuencia_0513.jpg` y `secuencia_0894.jpg` muestran la térmica alrededor de los dos fotogramas con dos personas en
  desacuerdo.

| Tipo | Personas (n.º y fotograma) |
|---|---|
| **El segundo la ve y el primero no (14)** | 39 (468), 40 (474), 42 (477), 43 (483), 44 (489), 49 (513), 52 (561), 53 (573), 54 (576), 56 (585), 57 (588), 63 (711), 71 (891), 73 (894) |
| **El primero la ve y el segundo no (2)** | 72 (894), 75 (900) |
| "No es persona" solo del primero (aparte) | 30 (429; el segundo: se ve), 33 (447; no se ve), 46 (501; se ve) |
| "No es persona" solo del segundo (aparte) | 26 (339), 29 (426), 47 (504), 48 (513), 59 (636) |
| "No es persona" de los dos (aparte) | 36, 37, 38 y 41 (el objeto marrón de 453 a 474) |

**Lo que se ve en las imágenes** (con la RGB ampliada y, aparte, con el brillo estirado):

- **14 contra 2.** Los desacuerdos van casi todos en el mismo sentido: el segundo ve más.
  - 10 de los 14 son una sola escena, de los fotogramas 468 a 588 (39 a 57): la persona está en un hueco del dosel en
    sombra profunda.
  - Con el brillo normal, la RGB es casi negra dentro de la caja.
  - Al estirar solo los tonos oscuros aparece una mancha oscura o azulada dentro de la caja. Puede ser la persona con
    ropa oscura o solo sombra; a esta resolución no se puede asegurar.
- **WiSARD:** no tiene caja RGB en 13 de los 14; la excepción es la 73, que sí la tiene.
- **39, 42 y 44:** el primer anotador les había dibujado una visible RGB. Pasaron a "no visible" en la revisión antes
  del kappa, por ser pares "solo térmica".
- **72 y 75:** con el brillo normal solo se ve un punto blanco en el borde de la caja. Al estirar el brillo aparece una
  persona con ropa blanca y azul. WiSARD tiene caja RGB en las dos.
- **En resumen:** casi todos los desacuerdos dependen de si se aclara la imagen. La regla de anotación no decía si "se
  ve" es con el brillo normal o aclarando (tecla `e`, zoom). Por eso el 0.507 no se acepta tal cual y se aclara la
  regla para la ronda 2.

**Tiempo del segundo anotador:**
- Las 75 respuestas se guardaron entre las 15:02:51 y las 15:06:11.
- Mediana de 1.9 s por persona; el 75 % en 3.5 s o menos.
- Una en 0.0 s: la 47, marcada "no es persona" apenas apareció en pantalla. Puede ser una tecla de más. En la ronda 2
  la vuelve a responder.

### Ronda 2 (regla aclarada)

**Pendiente:** ninguno de los dos anotadores la hizo todavía.

**Cómo se hace:**

- Cada anotador responde **las 75 personas completas**, desde cero, en su archivo nuevo de la ronda 2
  (`oclusion.modo_simple.ronda_actual: 2` en `configs/fase3.yaml`):
  - primero: `data/oclusion_primero_simple_ronda2.csv`;
  - segundo: `data/oclusion_segundo_simple_ronda2.csv`.
- Ninguno ve las respuestas del otro, ni las de la ronda 1, ni la anotación con cajas. El primero no revisa a mano solo
  la 72 y la 75: responde las 75 con la regla nueva, como el segundo.
- El realce (`e`) está desactivado: si se pulsa, la herramienta avisa y no cambia la imagen. El zoom y `i` (píxeles sin
  suavizar) siguen disponibles.

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
```

**Cuando estén las dos**, el cálculo de la ronda 2 (se detiene si falta alguna de las 75 en cualquiera de los dos
archivos):

```
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 2
```

Salidas en `entre_anotadores/ronda2/`:

1. **Primero contra segundo, los dos en modo simple (el que decide):** `kappa.csv` (primera fila), `matriz.csv`,
   `tabla_completa.csv`, `desacuerdos.csv` e `imagenes/`. Van aparte las "no es persona" de cualquiera de los dos.
2. **Automático contra el primero en modo simple (decide si se usa el automático):** `automatico.csv`,
   `automatico_matriz.csv`, `automatico_desacuerdos.csv` e `imagenes_automatico/`.
   - Se calcula sobre todas las personas que el primero no marca "no es persona", igual que el 0.940 con las cajas.
   - **Regla de decisión**, fijada el 1 de noviembre de 2026 antes de la ronda 2: si el kappa es de 0.61 o más, se usa
     el nivel automático; si no, el nivel binario de las 498 personas se anota a mano en modo simple. El script
     escribe la decisión en `automatico.csv` y en la bitácora.
3. **Respuestas del primero que cambian entre las cajas y el modo simple:** `cambios_primero.csv` (con lo que dijeron
   el segundo y el automático), `cambios_primero_tabla.csv` (cajas contra modo simple, con las "no es persona") e
   `imagenes_cambios_primero/`. Incluye el kappa del primero contra sí mismo, solo informativo.

Solo informativo:

- en `kappa.csv`, cada anotador contra el automático y el primero con cajas contra el segundo de la ronda 2;
- `cambios_segundo.csv`: las respuestas del segundo que cambian de la ronda 1 a la 2, y el kappa del segundo contra sí
  mismo;
- `entre_anotadores/rondas.csv`: el kappa entre anotadores de cada ronda, con qué anotación del primero se usó.

Se probó con archivos de ronda 2 simulados, en una carpeta temporal; la bitácora y `data/` no se tocaron. También se
probó que la ronda 1 sigue saliendo idéntica y que el script se detiene con un mensaje claro si falta el archivo de un
anotador, si está incompleto o si es del otro anotador.

## Cambios en el código

- `scripts/fase4_validacion_auto.py` (nuevo):
  - comparación de dos niveles con la de tres;
  - imágenes de los desacuerdos;
  - mosaico de las "no es persona";
  - revisión del fondo;
  - concordancia entre anotadores (`--partes entre_anotadores`), por ronda (`--ronda N`, por omisión la ronda
    actual), con las salidas en `entre_anotadores/ronda<N>/`. Con el primero en modo simple, también el automático
    contra él y sus cambios respecto de las cajas. Desde la ronda 2, la comparación con la anterior.
- `scripts/oclusion_auto.py`:
  - Sale `--comparar` (3 niveles): la comparación ahora está en el script nuevo.
  - `--revisar` acepta otra carpeta de salida y otro motivo (uno para todas o uno por persona), para las imágenes de
    los desacuerdos.
- `scripts/anotar_oclusion.py`: modo `--segundo-simple`. Las piezas comunes del panel (fondo, triángulos, cursor,
  rótulo), la carga de imágenes y la escritura atómica quedaron en métodos aparte, sin cambiar la herramienta.
  - Para la ronda 2: la regla aclarada en pantalla, el número de ronda en el encabezado, `e` desactivado y escritura en
    el archivo del anotador en `modo_simple.ronda_actual`.
  - `--primero-simple`: el mismo modo para el primer anotador.
- `configs/fase3.yaml`:
  - Sección `validacion_auto` (niveles, kappa mínimo, mosaico, revisión del fondo y `entre_anotadores`).
  - `oclusion.modo_simple`: `ronda_actual` y, por ronda, la regla y el archivo de cada anotador que la responde en
    modo simple (antes, `oclusion.anotaciones_segundo_simple`).
  - Salen `kappa_minimo` y `comparacion` de `oclusion_auto`.

## Pendiente de decidir

1. **Fotograma 60:** ¿se excluye por desfase? Si se excluye, ¿también 71–72, que se corren lo mismo?
2. **Las 7 "no es persona":** ¿se confirman con el mosaico? Si se confirman 30 a 41, ¿qué se hace con la caja térmica
   de WiSARD de ese objeto en las etiquetas de la prueba, probablemente en los fotogramas 429 a 474?
3. **La 73:** ¿se ve o no en la RGB? No cambia la decisión.
4. **Dónde se evalúa por nivel:** el nivel automático existe para las 1 501 personas. ¿Las métricas por nivel siguen
   sobre los 310 fotogramas anotados o pasan a los 928? CLAUDE.md todavía dice los 310.
5. **FASES.md:** el mensaje de la fase 4 sigue hablando de λ y de tres niveles.
6. **Concordancia entre anotadores:** la ronda 1 (0.507) no se acepta tal cual; la regla está aclarada ("se ve" = con
   el brillo normal) y los dos anotadores responden la ronda 2 en modo simple. Falta la ronda 2. Después:
   - ¿qué se hace si el primero contra el segundo queda por debajo de 0.61?
   - Decidido el 1 de noviembre de 2026: si se usa el automático lo decide el kappa del automático contra el primero
     en modo simple de la ronda 2 (0.61 o más: el automático; si no, las 498 a mano en modo simple). El 0.940 con
     cajas queda como resultado de la primera anotación.
7. **La 47** (0.0 s en la ronda 1): se vuelve a responder en la ronda 2.
