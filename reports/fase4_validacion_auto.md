# Fase 4: nivel de oclusión (validación del automático y nivel final)

Fecha: 1 de noviembre de 2026. Generado con `scripts/fase4_validacion_auto.py` (configuración en `configs/fase3.yaml`,
sección `validacion_auto`) y, el nivel final, con `scripts/fase4_nivel.py` (sección `nivel_final`). Tablas e imágenes
en `reports/fase4_validacion_auto/`. La validación no tocó `data/`. El nivel final solo escribe
`data/oclusion_nivel.csv`. No se tocó el dataset original. Cada cálculo agrega una fila a la bitácora.

## Nivel final (con la escena en sombra reanotada)

**Fase 4 cerrada el 1 de noviembre de 2026**, con la escena en sombra reanotada.
- Es el nivel que usa la fase 6: `data/oclusion_nivel.csv`, generado con `scripts/fase4_nivel.py`.
- Antes de reescribirlo, el script guardó el anterior en `data/respaldos/oclusion_nivel_20261101-202246.csv`.
- Tablas en `reports/fase4_validacion_auto/nivel_final/`, y una fila nueva en la bitácora.

```
.venv\Scripts\python.exe scripts\fase4_nivel.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\fase4_cajas_dudosas.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

| Nivel | Muestra | Resto | Total | % | Fotogramas con alguna |
|---|---:|---:|---:|---:|---:|
| **Baja** (se ve en la RGB) | 32 | 152 | **184** | 36.9 % | 134 |
| **Severa** (no se ve en la RGB) | 33 | 234 | **267** | 53.6 % | 155 |
| **Sin nivel, dudosas** ("no es persona") | 10 | 37 | **47** | 9.4 % | 43 |
| Total | 75 | 423 | 498 | 100 % | 259 |

- **De dónde salen las respuestas:**
  - las 75 de la muestra, de la ronda 2;
  - las 423 restantes, de `--primero-simple-resto`;
  - las 94 de los fotogramas 468 a 588, de la reanotación, que reemplaza a las anteriores.
- **Las 47 sin nivel son cajas dudosas:**
  - las 10 de los dos anotadores. La 41 está en la escena y siguió como "no es persona";
  - 37 marcadas solo por el primero.
  - Las 6 "no es persona" solo del primero en la muestra (48, 51, 52, 54, 55 y 58) estaban en la escena, y ahora son
    "no se ve".
- **Cajas dudosas para la fase 6:** 47 anotadas + 84 seguidas por los fotogramas no anotados = **131** de las 1 501
  cajas térmicas del vuelo (ver "Cajas dudosas y su seguimiento").
- **Columnas nuevas de `data/oclusion_nivel.csv`:** `los_dos_no_es_persona`, `reanotacion` y `respuesta_anterior`.
  `caja_dudosa` quiere decir sin nivel.
- **Tiempo por persona:**
  - mediana de 0.9 s en las 498;
  - **0.65 s en la reanotación de la escena** (P25 a P75: 0.5 a 0.98 s; 21 de 94 en menos de 0.5 s). Ver
    "Limitaciones".
  - El máximo, 4 018 s, es la primera persona de la escena. La herramienta quedó abierta en ella desde que la abrí,
    así que no es tiempo de anotación.
- **Contra el automático** (solo informativo; no cambia la decisión): kappa 0.750 (IC 0.688 a 0.812), acuerdo 88.0 %,
  54 desacuerdos en 451. En la muestra da 0.661 (65 personas) y en el resto 0.765 (386).
- **Escena en sombra:** ahora "se ven" 2 de 19 en la muestra y 1 de 69 en el resto. Antes eran 8 de 13 y 1 de 56.

La sección siguiente, "Cierre de la fase 4: primera versión", queda como registro de antes de la reanotación.

## Cierre de la fase 4: primera versión (antes de la reanotación)

Primera versión del nivel final, antes de reanotar la escena en sombra. Se conserva como registro: el nivel que vale es
el de "Nivel final". Es el nivel del primer anotador en modo simple, con la regla aclarada, para las 498 personas de los
310 fotogramas anotados de FHL 0405 (1 de cada 3):
- las 75 de la muestra salen de su ronda 2 (`data/oclusion_primero_simple_ronda2.csv`);
- las 423 restantes salen de `--primero-simple-resto` (`data/oclusion_primero_simple_resto.csv`).

El nivel está en **`data/oclusion_nivel.csv`**, generado con `scripts/fase4_nivel.py` (configuración en la sección
`nivel_final` de `configs/fase3.yaml`). Las tablas están en `reports/fase4_validacion_auto/nivel_final/`, y la ejecución
agrega una fila a la bitácora. El script solo lee las respuestas: comprueba que las dos fuentes cubren las 498 sin
solaparse y que las 10 cajas dudosas son "no es persona".

```
.venv\Scripts\python.exe scripts\fase4_nivel.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

| Nivel | Muestra | Resto | Total | % | Fotogramas con alguna |
|---|---:|---:|---:|---:|---:|
| **Baja** (se ve en la RGB) | 38 | 152 | **190** | 38.2 % | 141 |
| **Severa** (no se ve en la RGB) | 21 | 221 | **242** | 48.6 % | 151 |
| **Sin nivel** ("no es persona") | 16 | 50 | **66** | 13.3 % | 60 |
| Total | 75 | 423 | 498 | 100 % | 259 |

- 259 de los 310 fotogramas anotados tienen alguna persona. Los otros 51 no tienen cajas térmicas.
- **Las 66 "no es persona"** incluyen las 10 de los dos anotadores. Las otras 56 las marcó solo el primero: 6 de la
  muestra y 50 del resto. Todas van a `configs/cajas_dudosas.yaml` (ver "Cajas dudosas: las 66 y su seguimiento").
  - Están entre los fotogramas 102 y 714. 35 están entre 423 y 525, casi en cada fotograma anotado.
  - 52 están en pares "solo térmica", y para 65 el automático da severa.
  - Lista en `nivel_final/no_es_persona.csv`.
- **Columnas de `data/oclusion_nivel.csv`:**
  - la persona: `orden`, `id`, `vuelo`, `posicion`, `indice_caja` y `cajas_en_fotograma`;
  - su caja térmica de WiSARD en px: `ter_x0` a `ter_y1`. `indice_caja` es la línea de
    `data/etiquetas/termica/<vuelo>/<vuelo>_<posicion>.txt`;
  - `en_muestra`, `respuesta` y **`nivel`** (`baja`, `severa`, o vacío si es "no es persona");
  - `no_es_persona`, `caja_dudosa`, `archivo_respuesta` y `tiempo_s`.

**Tiempo por persona** (`tiempo_s`: el tiempo con la persona en pantalla, sumando las veces que se volvió a ella):

| Personas | N | Mediana | P25 a P75 | P90 | Menos de 0.5 s |
|---|---:|---:|---|---:|---:|
| Muestra (ronda 2) | 75 | 1.4 s | 0.7 a 2.3 s | 3.2 s | 9 (todas "se ve") |
| Resto | 423 | **0.9 s** | 0.6 a 1.4 s | 2.9 s | 51 (31 "se ve", 20 "no se ve") |
| Total | 498 | **1.0 s** | 0.6 a 1.6 s | 3.1 s | 60 |

- El máximo, 3 068 s, es la primera persona del resto (fotograma 0). La herramienta quedó abierta en ella desde que
  la abrí hasta que empezaste a anotar: no es tiempo de anotación. La mediana no cambia.
- El máximo de la muestra, 153 s, también es su primera persona.
- Las respuestas en menos de 0.5 s son informativas.

**Comparación con el automático** (solo informativa; no cambia nada). Comparables = sin las "no es persona":

| Personas | Comparables | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---:|---|---:|---:|
| **Las 498** | 432 | **0.716** (0.649 a 0.782) | 86.1 % | 60 |
| Muestra (ronda 2) | 59 | 0.427 (0.207 a 0.646) | 71.2 % | 17 |
| Resto | 373 | 0.760 (0.692 a 0.827) | 88.5 % | 43 |

| A mano \ automático | baja (caja RGB de WiSARD cerca) | severa (sin caja RGB cerca) | Total |
|---|---:|---:|---:|
| baja | 152 | 38 | 190 |
| severa | 22 | 220 | 242 |
| sin nivel ("no es persona") | 1 | 65 | 66 |
| Total | 175 | 323 | 498 |

- De los 60 desacuerdos, 38 son personas que se ven sin caja RGB de WiSARD cerca. Las otras 22 no se ven, pero
  WiSARD tiene caja RGB.
- En las 498, el kappa (0.716) pasa de 0.61, y en la muestra (0.427) no. La regla, fijada antes de la ronda 2,
  decidía con la muestra, así que el nivel final sigue siendo el manual. Este dato no reabre esa decisión.
- **La muestra y el resto difieren en la escena en sombra** (fotogramas 468 a 588), donde WiSARD no tiene caja RGB
  para ninguna persona (`nivel_final/automatico_por_tramo.csv`):

  | Escena en sombra (468 a 588) | Personas | Se ve | No se ve | No es persona |
  |---|---:|---:|---:|---:|
  | Muestra (ronda 2) | 20 | **8** | 5 | 7 |
  | Resto | 74 | **1** | 55 | 18 |

  - Son los mismos fotogramas, intercalados: en la muestra, 8 de 13 comparables "se ven"; en el resto, 1 de 56.
  - Fuera de esa escena, el kappa contra el automático es 0.575 en la muestra (46) y 0.734 en el resto (317).
  - Las 8 de la muestra no se revisaron, tal como se decidió. Habrían quedado en el nivel final como "baja", con un
    criterio distinto del resto en la misma escena.
  - **Decidido después** (1 de noviembre de 2026): se reanota la escena entera de una vez. Esas respuestas
    reemplazan el nivel final de la escena y los kappas de la ronda 2 no cambian. Ver "Reanotación de la escena en
    sombra".
  - El resto se anotó después de conocer los resultados de la ronda 2 (ver "Limitaciones").

**Las cifras de esta sección son las de antes de la reanotación de la escena en sombra.** Las finales están en "Nivel
final".

## Reanotación de la escena en sombra (después del cierre)

Decidida el 1 de noviembre de 2026, al ver la diferencia entre la muestra y el resto en esa escena (ver "Cierre de la
fase 4"). **Hecha el 1 de noviembre de 2026.**

- **Qué se reanota:** todas las personas de los fotogramas 468 a 588, de la muestra y del resto juntas (94: 20 y 74), en
  orden de fotograma y de una vez. Se usan la misma pantalla y la misma regla de la ronda 2, sin realce.
- **Herramienta:** `--primero-simple-reanotar escena_sombra`, con su propio archivo,
  `data/oclusion_primero_simple_escena_sombra.csv`. Retoma si se cierra, y no lee ningún otro archivo de respuestas.
  El tramo está en `oclusion.modo_simple.reanotaciones` (`configs/fase3.yaml`).

  ```
  .venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-reanotar escena_sombra
  ```

- **Qué reemplaza:** el nivel final de esas 94 personas (`scripts/fase4_nivel.py`).
  - **Los kappas de la ronda 2 no cambian:** salen de `data/oclusion_primero_simple_ronda2.csv`, que no se toca.
  - Si falta el archivo de la reanotación, `fase4_nivel.py` se detiene.
- **Las respuestas anteriores se guardan:**
  - siguen en `data/oclusion_primero_simple_ronda2.csv` y `data/oclusion_primero_simple_resto.csv`, que no se tocan;
  - en el nivel final quedan en la columna `respuesta_anterior`, junto con `reanotacion` y `archivo_respuesta`;
  - antes de reescribir `data/oclusion_nivel.csv`, el script guarda una copia del anterior en `data/respaldos/`;
  - los cambios quedan en `nivel_final/reanotacion_escena_sombra.csv` y en `reanotacion_escena_sombra_tabla.csv`.
- **Las 10 "no es persona" de los dos** quedan sin nivel aunque la reanotación las cambie, porque así se decidió. El
  script lo avisa. En la escena está la 41 (fotograma 474).
- **Después de la reanotación** se corrieron `scripts/fase4_nivel.py` y `scripts/fase4_cajas_dudosas.py`. Las cifras
  están en "Nivel final".
- Lo probé con una reanotación simulada sobre una copia de los datos. Reemplaza las 94, guarda la copia del nivel
  anterior y avisa si cambia una de las 10.

**Resultado:** cambian 29 de las 94 respuestas (`nivel_final/reanotacion_escena_sombra.csv` y
`reanotacion_escena_sombra_tabla.csv`).

| Personas | Anterior \ nueva | Se ve | No se ve | No es persona |
|---|---|---:|---:|---:|
| Muestra (20) | se ve | 2 | 6 | 0 |
| | no se ve | 0 | 5 | 0 |
| | no es persona | 0 | 6 | 1 |
| Resto (74) | se ve | 0 | 1 | 0 |
| | no se ve | 1 | 53 | 1 |
| | no es persona | 0 | 14 | 4 |

- **En total:** 3 "se ve", 85 "no se ve" y 6 "no es persona". Antes eran 9, 60 y 25.
- **La diferencia entre muestra y resto se reduce:** "se ven" 2 de 19 en la muestra (antes 8 de 13) y 1 de 69 en el
  resto (antes 1 de 56).
- **La 41** (fotograma 474, "no es persona" de los dos) siguió como "no es persona". No hubo aviso.
- **Tiempo:** mediana de 0.65 s por persona (ver "Limitaciones").

## Cajas dudosas y su seguimiento

Decidido el 1 de noviembre de 2026:
- todas las personas sin nivel ("no es persona") van a `configs/cajas_dudosas.yaml`;
- las etiquetas de prueba no se tocan;
- para el cálculo "sin ellas" de la fase 6, cada caja se sigue también por los fotogramas no anotados.

El yaml lo genera `scripts/fase4_cajas_dudosas.py` (sección `cajas_dudosas` de `configs/fase3.yaml`) a partir de
`data/oclusion_nivel.csv`, así que no se edita a mano. Tablas e imagen en `reports/fase4_validacion_auto/cajas_dudosas/`.

**Seguimiento:**
- Empieza en cada caja anotada (dudosa o con nivel) y va hacia adelante y hacia atrás, fotograma a fotograma, hasta el
  fotograma anotado siguiente, sin incluirlo, porque tiene su propia respuesta.
- En cada paso toma la caja térmica de WiSARD más cercana por el centro. Tiene que ser mutua y estar a 1 altura o menos
  (la mayor de las dos).
- Entre fotogramas seguidos, las cajas se mueven una mediana de 0.24 alturas, y el 75 % hasta 0.69.
- Si falta un fotograma (par excluido), se corta.

**Regla para las cajas seguidas** (fijada el 1 de noviembre de 2026, antes de ver las cifras nuevas):
- Cada caja seguida toma la respuesta del fotograma anotado más cercano del mismo objeto, contado en fotogramas por la
  cadena. Es dudosa si esa caja anotada es dudosa, y no lo es si tiene nivel.
- Si hay empate de distancia, va como dudosa.
- **En conflicto** quiere decir que la caja se enlaza a la vez con una caja dudosa y, del otro lado, con una persona con
  nivel. La regla las resuelve: la que está a 1 fotograma de la caja dudosa queda dudosa, y la que está a 1 de la
  persona queda como persona.

**Resultado final**, con la escena reanotada:

| Umbral | Anotadas | Seguidas dudosas | Total dudosas | En conflicto | Conflicto → dudosa | Conflicto → persona | Empates |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.5 alturas | 47 | 59 | 106 | 34 | 17 | 17 | 0 |
| **1 altura (el que se usa)** | 47 | **84** | **131** | 46 | 23 | 23 | 0 |
| 1.5 alturas | 47 | 88 | 135 | 52 | 26 | 26 | 0 |

- **131 cajas dudosas** de las 1 501 cajas térmicas del vuelo de prueba: 47 anotadas y 84 seguidas.
- Las 84 seguidas son:
  - 61 que solo se enlazan con cajas dudosas;
  - 23 en conflicto que quedan dudosas por estar más cerca de la caja dudosa.
- **Los conflictos bajan de 39 pares a 23** con la reanotación. Cada par tiene 2 cajas en medio: 1 queda dudosa y 1
  como persona.
  - Lista en `cajas_dudosas/conflictos.csv`.
  - Todas las cajas enlazadas con alguna dudosa, con sus enlaces y la decisión, en `cajas_dudosas/seguimiento.csv`.
  - El mosaico `cajas_dudosas/conflictos.jpg` muestra, por par, los 4 fotogramas: rojo = dudosa, verde = persona.
- Con esta separación no hubo empates.
- Persiste el caso **165 ↔ 168**, que no está en la escena: una persona de ropa azul en el borde del fotograma,
  respondida "no es persona" en 165 y "se ve" en 168.

**Antes de la reanotación y de la regla** (registro): 66 anotadas + 78 seguidas = 144, y otras 78 cajas en conflicto en
39 pares (222 si se contaban). El mosaico de entonces mostraba que el seguimiento iba sobre el mismo objeto y que lo que
cambiaba era la respuesta.

## Limitaciones

Las declara el reporte, decididas el 1 de noviembre de 2026:
- **Tiempo por persona:** la mediana fue de 0.9 s en las 423 del resto, tal como se anotaron (1.4 s en la muestra).
  - Una respuesta tan rápida deja poco tiempo para mirar.
  - 51 respuestas del resto tardaron menos de 0.5 s.
- **Tiempo en la reanotación de la escena en sombra:** la mediana fue de 0.65 s por persona (P25 a P75: 0.5 a
  0.98 s), y 21 de las 94 respuestas tardaron menos de 0.5 s.
  - En esa escena la RGB es casi negra dentro de las cajas.
- **El resto se anotó después de conocer los resultados de la ronda 2.** El primer anotador ya sabía:
  - los desacuerdos de la escena en sombra;
  - que el automático no pasó.

  Esas 423 respuestas no son independientes de ese conocimiento. La reanotación de la escena en sombra también se hace
  después.
- **Concordancia entre anotadores:** el kappa de 0.623 se acepta, pero su IC 95 % es ancho (0.40 a 0.85, con 55
  personas). Ya estaba declarado así.


## Decisión sobre el nivel automático

Con la regla fijada el 1 de noviembre de 2026 antes de la ronda 2, decide el kappa binario del automático contra el
primer anotador en modo simple de la ronda 2 (regla aclarada):

| Comparación | Kappa (IC 95 %) | Acuerdo |
|---|---|---:|
| **Automático contra primero en modo simple, ronda 2 (decide)** | **0.427** (0.207 a 0.646) | 71.2 % (59 personas) |
| Primero contra segundo, los dos en modo simple, ronda 2 (concordancia) | 0.623 (0.400 a 0.846) | 83.6 % (55 personas) |
| Automático contra primero con cajas (primera anotación) | 0.940 (0.858 a 1) | 97.1 % (68 personas) |

- **0.427 es menor que 0.61: no se usa el nivel automático.** El nivel binario de las 498 personas (1 de cada 3) se
  anota a mano en modo simple.
- El 0.940 queda como resultado de la primera anotación, con cajas. Su posible explicación es un sesgo de anclaje por
  la precarga (ver "Decisiones tras la ronda 2").
- 8 de los 17 desacuerdos son de una sola escena en sombra (fotogramas 468 a 588), donde la RGB es casi negra dentro
  de la caja y el primero respondió "se ve". Detalle en "Ronda 2". No se revisan.

```
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml
```

## Decisiones tras la ronda 2

Decididas el 1 de noviembre de 2026, con los resultados de la ronda 2.

- **Escena en sombra (fotogramas 468 a 588): no se revisa.** La regla se aplica tal como quedó fijada, y las 8 "se ve"
  del primero en esa escena quedan como están.
  - El kappa sin esa escena (0.575) y con esas 8 cambiadas a "no se ve" (0.695) es solo un análisis de sensibilidad.
  - No decide nada.
- **Concordancia entre anotadores: se acepta el 0.623**, porque pasa el 0.61 de la regla.
  - El IC 95 % (0.40 a 0.85, con 55 personas) va como **limitación**.
  - El IC es ancho y empieza en 0.40, así que no descarta un acuerdo solo moderado.
- **Nivel a mano de las 498 personas:** lo anota el primer anotador en modo simple, con la misma pantalla y la misma
  regla de la ronda 2.
  - Las 75 de la muestra son sus respuestas de la ronda 2 (`data/oclusion_primero_simple_ronda2.csv`).
  - Las 423 que faltan se anotan con el modo nuevo `--primero-simple-resto`.
  - Van en un archivo propio, `data/oclusion_primero_simple_resto.csv`, y la herramienta retoma si se cierra. Ver
    "Modo simple".
- **Las 10 "no es persona" en que coinciden los dos** (22, 26, 27, 29, 30, 33, 36, 37, 38 y 41; fotogramas 321 a 474):
  - las etiquetas de prueba **no se tocan**;
  - sus cajas térmicas de WiSARD están en `configs/cajas_dudosas.yaml`, con el archivo de etiquetas, la línea y la caja
    en px de cada una;
  - quedan **sin nivel**;
  - en la fase 6, las métricas se calculan **con y sin ellas**.
- **El 0.940 con cajas** queda como resultado de la primera anotación.
  - Su posible explicación es un **sesgo de anclaje por la precarga** (ver "3. Respuestas del primero que cambian
    entre las cajas y el modo simple").

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
  simple de la ronda 2, con la regla aclarada. El 0.940 queda como resultado de la primera anotación, con cajas.
- Con la ronda 2 (0.427), **no se usa el nivel automático**. Ver "Decisión sobre el nivel automático".

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
no cambió. **No se usa** desde la ronda 2 (kappa 0.427 contra el primero en modo simple): queda como referencia.

## Las 7 "no es persona" de la anotación con cajas

Desde la ronda 2:
- 6 de estas 7 (30 a 41, el objeto marrón) están entre las 10 "no es persona" en que coinciden los dos anotadores.
  Están en `configs/cajas_dudosas.yaml`.
- La 46 no: en la ronda 2 el primero responde "no se ve" y el segundo "se ve".

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
  - Las etiquetas no se tocan. `configs/cajas_dudosas.yaml` tiene solo sus cajas de los fotogramas anotados (ver
    "Pendiente de decidir").

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
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-resto
```

- **Personas:** las 75 de la muestra, en su orden (el mismo para los dos). Con `--primero-simple-resto`, las 423 que
  faltan de las 498 (ver abajo).
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
- **Prueba:** `scripts/probar_anotar_oclusion.py` pasó de 59 a 71 comprobaciones con este modo, a 73 con la ronda 2, a
  80 con `--primero-simple`, a 92 con `--primero-simple-resto` y a 102 con
  `--primero-simple-reanotar`. Todas correctas. Entre otras cosas, comprueba que los
  paneles del primero y del segundo son idénticos y que el primero solo lee la lista de personas y la muestra. Las
  capturas de los modos anteriores salieron idénticas.
- **Capturas:** `reports/oclusion/herramienta_segundo_simple.jpg` y `reports/oclusion/herramienta_primero_simple.jpg`,
  con la regla de la ronda 2 en pantalla.
- Las respuestas se pasan a los dos niveles: "se ve" = baja, "no se ve" = severa, y "no es persona" aparte. Los
  resultados están en la sección siguiente.

**Las 423 que faltan (`--primero-simple-resto`).** Para el nivel a mano de las 498, decidido el 1 de noviembre de 2026.

- **Personas:** las 423 de `data/oclusion_personas.csv` que no son de la muestra, en el orden de la lista (por
  fotograma). Con las 75 de la muestra suman las 498.
- **Pantalla y regla:** las del modo simple de la ronda 2 (`oclusion.modo_simple.resto.ronda` en
  `configs/fase3.yaml`). La cabecera dice "modo simple, resto de las 498, regla de la ronda 2".
- **Guarda** en `data/oclusion_primero_simple_resto.csv`, con `anotador` = `primero_simple`, después de cada respuesta.
  Al abrir de nuevo retoma en la primera sin responder.
- **No lee** ningún archivo de respuestas salvo el propio.
  - No acepta un archivo con personas de la muestra ni uno del segundo.
  - Las 75 de la muestra no se vuelven a responder: el nivel de esas es el de `data/oclusion_primero_simple_ronda2.csv`.
- **Captura:** `reports/oclusion/herramienta_primero_simple_resto.jpg`.

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
| **Primero contra segundo, los dos en modo simple (decide la concordancia)** | 2 | **0.623** (0.400 a 0.846) | 83.6 % | 9 de 55 |
| **Automático contra primero en modo simple (decide si se usa el automático)** | 2 | **0.427** (0.207 a 0.646) | 71.2 % | 17 de 59 |
| Respuestas del primero que cambian entre las cajas y el modo simple | 2 | 0.483 (el primero contra sí mismo) | | 26 de 75 cambian |

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

Hecha el 1 de noviembre de 2026. Cada anotador respondió las 75 personas en modo simple, desde cero, sin ver las
respuestas del otro ni las de la ronda 1 ni la anotación con cajas. Regla aclarada en pantalla y realce desactivado.

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
.venv\Scripts\python.exe scripts\fase4_validacion_auto.py --config configs\fase3.yaml --rutas configs\rutas.yaml --partes entre_anotadores --ronda 2
```

| Anotador | Archivo | Se ve | No se ve | No es persona | Hora | Mediana por persona |
|---|---|---:|---:|---:|---|---:|
| Primero | `data/oclusion_primero_simple_ronda2.csv` | 38 | 21 | 16 | 16:50:12 a 16:52:37 | 1.4 s |
| Segundo | `data/oclusion_segundo_simple_ronda2.csv` | 39 | 22 | 14 | 16:41:28 a 16:43:31 | 1.3 s |

- Salidas en `reports/fase4_validacion_auto/entre_anotadores/ronda2/`. Hay una fila nueva en la bitácora.
- Respuestas en menos de 0.5 s: 9 del primero y 6 del segundo. Todas están entre las personas 4 y 17 (fotogramas 9 a
  198, personas a la vista), donde los dos y el automático dicen "se ve".

#### 1. Primero contra segundo, los dos en modo simple (decide la concordancia)

55 personas comparables. Van aparte 20 por ser "no es persona" de alguno de los dos.

| Comparación | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---:|---:|
| **Primero contra segundo, modo simple** | **0.623** (0.400 a 0.846) | 83.6 % | 9 de 55 |
| Primero (modo simple) contra automático (informativo) | 0.451 (0.228 a 0.675) | 72.7 % | 15 de 55 |
| Segundo (ronda 2) contra automático (informativo) | 0.561 (0.356 a 0.765) | 78.2 % | 12 de 55 |
| Primero con cajas contra segundo de la ronda 2 (informativo) | 0.607 (0.419 a 0.795) | 80.0 % | 12 de 60 |

- Un kappa de 0.623 queda apenas sobre 0.61 ("acuerdo considerable", 0.61 a 0.80 en la escala de Landis y Koch). El
  IC es ancho y empieza en 0.40.
- **Se acepta según la regla** (decidido el 1 de noviembre de 2026). El IC va como limitación.
- Sube respecto de la ronda 1 (0.507), pero las dos rondas no son del todo comparables: en la ronda 1 el primero era su
  anotación con cajas.

**Matriz de confusión** (filas: primero; columnas: segundo):

| Primero \ segundo | se ve | no se ve | Total |
|---|---:|---:|---:|
| se ve | 33 | 4 | 37 |
| no se ve | 5 | 13 | 18 |
| Total | 38 | 17 | 55 |

**Tabla completa, con las "no es persona":**

| Primero \ segundo | se ve | no se ve | no es persona |
|---|---:|---:|---:|
| se ve | 33 | 4 | 1 |
| no se ve | 5 | 13 | 3 |
| no es persona | 1 | 5 | 10 |

| Tipo | Personas (n.º y fotograma) |
|---|---|
| **El primero la ve y el segundo no (4)** | 28 (420), 32 (444), 39 (468), 53 (573) |
| **El segundo la ve y el primero no (5)** | 46 (501), 49 (513), 71 (891), 72 (894), 73 (894) |
| "No es persona" de los dos (10; en `configs/cajas_dudosas.yaml`) | 22 (321), 26 (339), 27 (378), 29 (426), 30 (429), 33 (447), 36 (453), 37 (459), 38 (462), 41 (474) |
| "No es persona" solo del primero (6) | 48 (513), 51 (555), 52 (561), 54 (576), 55 (579), 58 (588) |
| "No es persona" solo del segundo (4) | 21 (258), 35 (450), 59 (636), 66 (729) |

Imágenes de los desacuerdos y de las "no es persona" de uno solo en `ronda2/imagenes/`.

#### 2. Automático contra el primero en modo simple (decide si se usa el automático)

59 personas: todas menos las 16 que el primero marca "no es persona".

| Comparación | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---:|---:|
| **Automático contra primero, modo simple** | **0.427** (0.207 a 0.646) | 71.2 % | 17 de 59 |
| Automático contra primero con cajas (primera anotación) | 0.940 (0.858 a 1) | 97.1 % | 2 de 68 |

| Primero (modo simple) \ automático | baja (caja RGB de WiSARD cerca) | severa (sin caja RGB cerca) | Total |
|---|---:|---:|---:|
| se ve | 25 | 13 | 38 |
| no se ve | 4 | 17 | 21 |
| Total | 29 | 30 | 59 |

**Decisión** (regla fijada el 1 de noviembre de 2026, antes de la ronda 2): el kappa es 0.427, menor que 0.61. **No se
usa el nivel automático: el nivel binario de las 498 personas (1 de cada 3) se anota a mano en modo simple.** El script
lo escribe en `ronda2/automatico.csv` y en la bitácora.

**Los 17 desacuerdos** (imágenes en `ronda2/imagenes_automatico/`):

| Tipo | Personas (n.º y fotograma) |
|---|---|
| El primero la ve y WiSARD no tiene caja RGB cerca (13) | 15 (144), 21 (258), 28 (420), 32 (444), 39 (468), 40 (474), 42 (477), 43 (483), 44 (489), 53 (573), 56 (585), 57 (588), 68 (864) |
| El primero no la ve y WiSARD tiene caja RGB (4) | 59 (636), 72 (894), 73 (894), 75 (900) |

**Lo que se ve en las imágenes:**

- **8 de los 13 son de la escena en sombra profunda de los fotogramas 468 a 588:** 39, 40, 42, 43, 44, 53, 56 y 57.
  - El segundo también dice "se ve" en 6 de ellas: 40, 42, 43, 44, 56 y 57.
  - Con el brillo normal, la RGB dentro de la caja es casi negra, como en la ronda 1 (por ejemplo, la 42 y la 57). La
    térmica muestra una mancha caliente.
  - En las imágenes no se distingue una parte del cuerpo. La regla aclarada dice que una mancha oscura o una sombra
    no cuentan y que, si hay duda, "no se ve".
  - En esa misma escena, con imágenes parecidas (caja RGB negra y mancha caliente en la térmica), el primero respondió
    8 "se ve", 5 "no se ve" y 6 "no es persona". No cuento la 41, que es el objeto marrón.
- **Análisis de sensibilidad** (no decide nada):
  - Sin las personas de los fotogramas 468 a 588, el kappa queda en 0.575 (46 personas).
  - Si esas 8 fueran "no se ve", sería 0.695.
  - **Las 8 no se revisan:** la regla se aplica tal como quedó fijada (decidido el 1 de noviembre de 2026).
- **72 y 75:** ahora "no se ve". Con el brillo normal solo se ve un punto blanco en el borde de la caja. WiSARD tiene caja
  RGB en las dos.
- **68:** el primero la ve, como con las cajas; WiSARD no tiene su caja RGB.

#### 3. Respuestas del primero que cambian entre las cajas y el modo simple

**26 de 75.** El primero contra sí mismo, en las dos clases (58 personas, informativo): kappa 0.483.

| Cajas \ modo simple | se ve | no se ve | no es persona |
|---|---:|---:|---:|
| se ve | 26 | 3 | 0 |
| no se ve | 12 | 17 | 10 |
| no es persona | 0 | 1 | 6 |

| Cambio | Personas (n.º y fotograma) |
|---|---|
| No se ve → se ve (12) | 15 (144), 21 (258), 28 (420), 32 (444), 39 (468), 40 (474), 42 (477), 43 (483), 44 (489), 53 (573), 56 (585), 57 (588) |
| No se ve → no es persona (10) | 22 (321), 26 (339), 27 (378), 29 (426), 48 (513), 51 (555), 52 (561), 54 (576), 55 (579), 58 (588) |
| Se ve → no se ve (3) | 59 (636), 72 (894), 75 (900) |
| No es persona → no se ve (1) | 46 (501) |

- Las 12 que pasan a "se ve" no tienen caja RGB de WiSARD cerca. 25 de los 26 cambios se alejan del nivel
  automático; solo la 46 se acerca.
- **39, 42 y 44** tenían una visible RGB dibujada en la primera anotación. Pasaron a "no visible" en la revisión antes
  del kappa, por ser pares "solo térmica" (sin caja RGB de WiSARD). Ahora vuelven a "se ve".
- **Posible sesgo de anclaje por la precarga (explicación del 0.940):**
  - En la anotación con cajas, la visible RGB venía precargada con la caja RGB de WiSARD, que es la misma que usa el
    nivel automático.
  - El primero pudo anclarse a ella: aceptarla cuando estaba y no buscar a la persona en la RGB cuando no estaba.
  - Además, la revisión antes del kappa usó como criterio que el par no tuviera cajas RGB.
  - Las dos cosas acercan la respuesta del primero al automático por construcción, y el kappa sube.
  - Sin precarga (modo simple), el acuerdo baja de 0.940 a 0.427, y 25 de los 26 cambios se alejan del automático. Es
    lo que se esperaría con anclaje.
  - Es una hipótesis: no se puede separar del cambio de regla, porque la ronda 2 también aclaró qué es "se ve".
- Imágenes en `ronda2/imagenes_cambios_primero/`; lista en `ronda2/cambios_primero.csv` (con el segundo y el
  automático) y tabla en `ronda2/cambios_primero_tabla.csv`.

#### El segundo, de la ronda 1 a la 2 (informativo)

15 de 75 respuestas cambian. El segundo contra sí mismo, en las dos clases (59 personas): kappa 0.767.

| Cambio | Personas |
|---|---|
| Se ve → no se ve (4) | 39, 52, 53, 63 |
| No se ve → se ve (2) | 15, 72 |
| → no es persona (7) | 21, 22, 27, 33, 35, 66 (antes "no se ve"); 30 (antes "se ve") |
| No es persona → no se ve (2) | 47, 48 |

Lista en `ronda2/cambios_segundo.csv`. La 47, respondida en 0.0 s en la ronda 1, ahora es "no se ve" (los dos).

#### Las dos rondas

| Ronda | Regla | Primero | Comparables | Kappa (IC 95 %) | Acuerdo | Desacuerdos |
|---|---|---|---:|---|---:|---:|
| 1 | ambigua | cajas | 63 | 0.507 (0.312 a 0.701) | 74.6 % | 16 |
| 2 | aclarada | modo simple | 55 | 0.623 (0.400 a 0.846) | 83.6 % | 9 |

En `entre_anotadores/rondas.csv`.

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
  - `--primero-simple-resto`: el primero, en modo simple, sobre las 423 personas de la lista que no son de la muestra.
    Tiene su propio archivo.
- `scripts/probar_anotar_oclusion.py`: 12 comprobaciones más para `--primero-simple-resto` (92 en total) y 10 para
  `--primero-simple-reanotar` (102 en total). Todas correctas.
- `scripts/anotar_oclusion.py --primero-simple-reanotar NOMBRE`: reanotación en modo simple de un tramo de
  `oclusion.modo_simple.reanotaciones`.
- `scripts/fase4_nivel.py` (nuevo): el nivel final, con las reanotaciones y una copia del anterior en `data/respaldos/`.
- `scripts/fase4_cajas_dudosas.py` (nuevo): genera `configs/cajas_dudosas.yaml` con el seguimiento por los fotogramas
  no anotados y la regla del fotograma anotado más cercano.
- `configs/cajas_dudosas.yaml` (nuevo, generado): las cajas dudosas, anotadas y seguidas.
- `configs/fase3.yaml`:
  - Sección `validacion_auto` (niveles, kappa mínimo, mosaico, revisión del fondo y `entre_anotadores`).
  - `oclusion.modo_simple`: `ronda_actual` y, por ronda, la regla y el archivo de cada anotador que la responde en
    modo simple (antes, `oclusion.anotaciones_segundo_simple`).
  - Salen `kappa_minimo` y `comparacion` de `oclusion_auto`.
  - `oclusion.modo_simple.resto` (ronda de la regla y archivo) y `oclusion.cajas_dudosas`.

## Pendiente de decidir

Ya decidido el 1 de noviembre de 2026 (ver "Decisiones tras la ronda 2", "Nivel final" y las secciones que siguen):
- en la ronda 2, la escena en sombra no se revisó;
- las 423 que faltan las anotó el primero con `--primero-simple-resto`;
- se acepta la concordancia de 0.623, con el IC como limitación;
- la escena en sombra se reanotó entera, y esas respuestas reemplazan el nivel final de la escena;
- el nivel final está en `data/oclusion_nivel.csv`: baja 184, severa 267 y 47 sin nivel (dudosas);
- todas las "no es persona" van a `configs/cajas_dudosas.yaml`, y se siguen por los fotogramas no anotados. Cada caja
  seguida toma la respuesta del fotograma anotado más cercano, y los empates van como dudosas. Total: 131 cajas;
- **fotograma 60: no se excluye**, por desfase residual bajo los límites de la regla (tampoco 71–72);
- las limitaciones de "Limitaciones".

Pendiente: nada de la fase 4. La sección de la fase 4 en `FASES.md` ya describe lo hecho (dos niveles, sin λ).

Cerrados:
- La 73 queda con la respuesta del primero ("no se ve", severa).
- Las métricas por nivel van sobre los 310 fotogramas anotados, los únicos con nivel, como dice CLAUDE.md. Las
  globales van sobre los 928 y sobre los 310.
