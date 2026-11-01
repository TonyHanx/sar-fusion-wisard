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
| **Dos niveles (decide)** | **0.940** (0.858 a 1) | 97.1 % | 2 |
| Tres niveles, λ por áreas (solo se reporta) | 0.675 (0.536 a 0.814) | 82.4 % | 12 |

- El IC es asintótico (statsmodels). En el binario, su límite superior da 1.022: se recorta a 1.
- **Decisión: el kappa binario es de 0.61 o más, así que se usa el nivel automático.**

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

## Segundo anotador: modo simple

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
```

- **Personas:** las 75 de la muestra, en su orden.
- **Lo que ve:** la RGB alineada y la térmica, ampliadas alrededor de la persona, con la misma vista inicial que la
  herramienta.
  - Su caja térmica de WiSARD, en verde. En la RGB va donde la pone la semejanza.
  - Las demás cajas térmicas de WiSARD del fotograma, en gris.
  - Los triángulos amarillos que señalan a la persona.
- **Lo que no ve:**
  - No dibuja cajas.
  - No hay precarga: de la lista de personas solo se usan las cajas térmicas de WiSARD y las imágenes, no la caja RGB.
  - No lee `data/oclusion.csv` ni `data/oclusion_segundo.csv`.
- **Teclas:**
  - `1`: se ve en la RGB.
  - `2`: no se ve en la RGB.
  - `3`: no es persona.
  - Tras responder pasa a la siguiente sin responder.
  - `x` borra la respuesta, y `n` / `b` pasan a la siguiente o a la anterior.
  - Rueda o `+` / `-` para el zoom, flechas para mover la vista, `e` contraste, `h` oculta las cajas y `q` sale.
- **Guarda** en `data/oclusion_segundo_simple.csv` después de cada respuesta. Columnas: `id`, `respuesta` (`se_ve_rgb`,
  `no_se_ve_rgb`, `no_es_persona`), `tiempo_s` y `guardado`. Al abrir de nuevo se retoma.
- **Prueba:** `scripts/probar_anotar_oclusion.py` pasa de 59 a 71 comprobaciones, todas correctas. Las capturas de los
  modos anteriores salieron idénticas.
- **Captura:** `reports/oclusion/herramienta_segundo_simple.jpg`.
- Sus respuestas se comparan con las del primer anotador en dos niveles: "se ve" = baja, "no se ve" = severa, y
  "no es persona" aparte.

## Cambios en el código

- `scripts/fase4_validacion_auto.py` (nuevo):
  - comparación de dos niveles con la de tres;
  - imágenes de los desacuerdos;
  - mosaico de las "no es persona";
  - revisión del fondo.
- `scripts/oclusion_auto.py`:
  - Sale `--comparar` (3 niveles): la comparación ahora está en el script nuevo.
  - `--revisar` acepta otra carpeta de salida y otro motivo, para las imágenes de los desacuerdos.
- `scripts/anotar_oclusion.py`: modo `--segundo-simple`. Las piezas comunes del panel (fondo, triángulos, cursor,
  rótulo), la carga de imágenes y la escritura atómica quedaron en métodos aparte, sin cambiar la herramienta.
- `configs/fase3.yaml`:
  - Sección `validacion_auto` (niveles, kappa mínimo, mosaico y revisión del fondo).
  - `oclusion.anotaciones_segundo_simple`.
  - Salen `kappa_minimo` y `comparacion` de `oclusion_auto`.

## Pendiente de decidir

1. **Fotograma 60:** ¿se excluye por desfase? Si se excluye, ¿también 71–72, que se corren lo mismo?
2. **Las 7 "no es persona":** ¿se confirman con el mosaico? Si se confirman 30 a 41, ¿qué se hace con la caja térmica
   de WiSARD de ese objeto en las etiquetas de la prueba, probablemente en los fotogramas 429 a 474?
3. **La 73:** ¿se ve o no en la RGB? No cambia la decisión.
4. **Dónde se evalúa por nivel:** el nivel automático existe para las 1 501 personas. ¿Las métricas por nivel siguen
   sobre los 310 fotogramas anotados o pasan a los 928? CLAUDE.md todavía dice los 310.
5. **FASES.md:** el mensaje de la fase 4 sigue hablando de λ y de tres niveles.
