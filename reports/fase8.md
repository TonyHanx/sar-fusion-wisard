# Fase 8: evaluación en la prueba (FHL 0405)

**Estado (21 de noviembre de 2026): fase 8 terminada.** El usuario pidió hacer los pasos 2, 3 y 4 seguidos.
- `rgb_base` se entrenó de 21:33 a 22:09 (`reports/fase7.md`, "Corrida 5 de C3: `rgb_base`").
- Los umbrales se fijaron en la validación y se subieron a GitHub antes de tocar la prueba (commit `ae9d867`).
- La prueba se comprobó sin predecir, y después se predijo y se midió **una sola vez** (abajo, "Resultados en la
  prueba").
- **`rgb_base` es débil en la validación:** mAP@0.5 de 0.032 con `last.pt` y de 0.160 con `best.pt` (época 1), en la
  validación de Ultralytics. Las corridas de solo RGB de la fase 5 hicieron lo mismo. Las reglas no cambian.

La configuración está en `configs/fase8.yaml`, aparte de `configs/fase7.yaml`, para que la fase 7 siga sin nombrar la
prueba.

## Reglas confirmadas

El usuario confirmó la propuesta con dos cambios:
1. se entrena un modelo de solo RGB (`rgb_base`), y `fusion_base` contra `rgb_base` entra en McNemar (Bonferroni ×3);
2. una diferencia solo cuenta como demostrada si McNemar y el bootstrap por episodios coinciden.

Además, pidió agregar a las limitaciones el sitio y el día de los vuelos de entrenamiento (abajo).

### Modelos y pesos

| Modelo | Fase | Datos | Peso principal | Secundario |
|---|---|---|---|---|
| `termico_base` | 7 (C3) | base | `last.pt` | `best.pt` |
| `termico_ampliado` | 7 (C3) | ampliado | `last.pt` | `best.pt` |
| `fusion_base` | 7 (C3) | base | `last.pt` | `best.pt` |
| `fusion_ampliado` | 7 (C3) | ampliado | `last.pt` | `best.pt` |
| `rgb_base` | 7 (C3, corrida 5) | base | `last.pt` | `best.pt` |
| `fusion_100ep` | 5/6 | base | `best.pt` (el que fijó la fase 6) | `last.pt` |

- **Las dos fusiones de la fase 7 también van con la RGB en 0**, con los dos pesos. Es descriptivo.
- **`last.pt` es el principal de todos los modelos de la fase 7, también de `rgb_base`, y `best.pt` va como
  secundario.** Lo confirmó el usuario el 21 de noviembre de 2026, después de ver que `rgb_base` se hunde en la
  validación.
- **De la fase 6 solo existe la fusión.**
  - `rgb_100ep` se cortó dos veces y se descartó.
  - `termico_100ep` nunca se entrenó: la noche del 3 al 4 de noviembre se cortó la corriente, y después vino el
    diagnóstico.
- **`rgb_base` repite la receta y los datos base de `termico_base` y `fusion_base`:** 50 épocas, AdamW con lr0 0.002,
  `close_mosaic` 10, seed 0 y 3 canales.
  - Solo hay versión base, porque el ampliado no tiene RGB en el 77 % de sus imágenes.
  - Está en `c3.corridas.rgb_base` de `configs/fase7.yaml`.
- **La prueba se predice con los datasets de la fase 3a** (`configs/{termico,rgb,fusion}.yaml`, split test): las
  mismas imágenes alineadas y las mismas etiquetas térmicas.

### Umbral de confianza

Se mantiene la regla de la fase 6: por modelo y peso, el mayor F2 en la validación; si hay empate, el más alto; y se
aplica sin cambios a la prueba.

- **La rejilla se amplía hacia abajo:** 0.001, 0.002, 0.005, 0.01, 0.02, 0.03 y 0.04, y luego de 0.05 a 0.95 con paso
  0.05.
  - Por qué: en C4, con `last.pt`, los cuatro umbrales quedaron en 0.05, el borde, y el F2 seguía subiendo.
  - 0.001 es el piso, porque las predicciones se guardan desde esa confianza.
- **Las variantes con la RGB en 0 usan el umbral de su modelo con la RGB real.**
- **`fusion_100ep` usa la misma regla.** La fase 6 nunca fijó sus umbrales.
- **Los umbrales se escriben en `reports/fase8/umbrales.csv` y se suben a GitHub antes de predecir la prueba.**
- **Sensibilidad, solo descriptiva:** las cifras de la prueba también con el umbral de la rejilla anterior.

### McNemar y criterio

**Familia de McNemar:** `last.pt`, sin las cajas dudosas, en baja (184) y severa (267), con Bonferroni ×3 dentro de cada
nivel.

| Par | Pregunta |
|---|---|
| `fusion_base` − `rgb_base` | fusión contra solo RGB, mismos datos y receta |
| `fusion_base` − `termico_base` | fusión contra solo térmica, mismos datos y receta |
| `fusion_ampliado` − `termico_ampliado` | lo mismo con los datos ampliados |

- En la fase 6 el tercer par era RGB contra térmica. Ahora queda solo con IC.
- **La comparación principal de la tesis es fusión contra térmica** (los dos últimos pares). **Fusión contra RGB es
  complementaria.** Lo decidió el usuario el 21 de noviembre de 2026, después de ver `rgb_base`. Los tres pares siguen
  en la familia de McNemar con Bonferroni ×3.

**Criterio, que cambia la regla de la fase 6 por lo que se vio en C4.** Una diferencia solo cuenta como demostrada si se
cumplen las dos condiciones:
- McNemar con Bonferroni da p < 0.05;
- el IC del 95 % por bootstrap de episodios de la diferencia de recall excluye el 0, con el mismo signo.

Si solo se cumple una, se reporta como "no concluyente". La fase 6 se basaba solo en McNemar.

**Por qué se cambia** (C4, `reports/fase7.md`):
- en la validación, McNemar dio significativa a `fusion_base` sobre `termico_base` (p = 0.00007). Pero 102 de las 105
  personas que solo detectaba la fusión eran de un solo episodio, MtErie 0007, y el IC por episodios incluía el 0;
- la misma persona se repite en fotogramas seguidos: las 500 personas de la validación forman de 69 a 121 tramos. En la
  prueba se anotó 1 de cada 3 fotogramas, y las personas también se repiten entre fotogramas anotados;
- McNemar supone personas independientes, y el bootstrap por episodios no.

**Solo con IC por bootstrap**, sin McNemar, con los dos pesos:
- RGB contra térmica (base);
- el efecto de ampliar los datos, en la térmica y en la fusión;
- las fusiones con la RGB en 0;
- y la comparación con la fase 6 (abajo).

### Comparación con la fase 6

- **La única referencia es `fusion_100ep`.** Se compara cada peso con el mismo tipo de peso: `last.pt` con `last.pt` y
  `best.pt` con `best.pt`.
- **La cifra "de la fase 6" es `fusion_100ep` con `best.pt`**, el peso que fijó `configs/fase6.yaml`.
- **`fusion_base` − `fusion_100ep` aísla la receta.**
  - Son los mismos datos, el mismo inicio del cuarto canal, el mismo optimizador y el mismo `close_mosaic`.
  - Cambian las épocas: 50 en vez de 100.
  - En `best.pt` también cambia el criterio de la mejor época: mAP@0.5 en la fase 7 y mAP@0.5:0.95 en la fase 5.
- **`fusion_ampliado` − `fusion_100ep` suma la receta y los datos.**

### Lo que no cambia de la fase 6

- IoU 0.5 y maxDets 100.
- El bootstrap: 13 bloques en FHL 0405, 10 000 remuestreos, seed 0.
- Los subconjuntos: todos los 928 fotogramas y los 310 anotados, con y sin las 131 cajas dudosas; baja y severa en los
  310 anotados.
- La prueba se evalúa una sola vez.

### Limitaciones declaradas antes de ver la prueba

- Hay una semilla por corrida.
- **Vuelos del mismo sitio y día que la prueba** (FHL, 24 de septiembre de 2021):
  - el entrenamiento base ya incluye FHL 0401, de ese mismo día;
  - el ampliado suma FHL 0404, 0565 y 0567;
  - ninguno rompe la partición por vuelo, pero **favorece a los modelos ampliados al compararlos con los base en la
    prueba**;
  - **no favorece a la comparación de fusión contra térmica (ni contra RGB) dentro del mismo dataset**, porque los dos
    modelos de cada par ven los mismos vuelos.
- La prueba tiene 13 bloques para el bootstrap, y sus personas se repiten entre fotogramas anotados.
- El umbral se elige en dos vuelos de validación que se comportan distinto (C4).
- `rgb_base` se entrena después de ver C4 en la validación, aunque antes de tocar la prueba.
- **El modelo de solo RGB se hunde en la validación desde la época 1**, igual que en la fase 5:
  - mAP@0.5 de 0.160 en la época 1 y de 0.032 en la 50 (validación de Ultralytics);
  - y eso aunque el 90 % de las personas de la validación se ven en la RGB (440 de 486, con el nivel a mano de C4);
  - la causa probable, sin comprobar, es que la RGB no se transfiere entre vuelos;
  - por eso, fusión contra RGB es una comparación complementaria, y la principal es fusión contra térmica.
- De la fase 6 solo se compara la fusión.

## Pasos

Cada paso se detiene y espera al usuario.
1. **`rgb_base`** (corrida 5 de C3): la lanza el usuario en su PowerShell y se revisa como las otras corridas de C3.
   **Hecho el 21 de noviembre de 2026.**
2. **Umbrales en la validación:**
   - con las predicciones que ya existen, y las de `rgb_base`;
   - se escriben en `reports/fase8/umbrales.csv` y se suben a GitHub antes de predecir la prueba.
3. **Verificación de la prueba sin predecir:** fotogramas, personas, niveles, dudosas y bloques.
4. **Predicción y medida:** se predice la prueba con todos los modelos de una vez y se mide una sola vez.

Los pasos 2 a 4 se hicieron seguidos el 21 de noviembre de 2026, a pedido del usuario, sin detenerse entre ellos.

## Paso 2: umbrales en la validación (21 de noviembre de 2026)

Fijados con `src/evaluacion/evaluar_prueba.py --parte umbrales` y subidos a GitHub antes de predecir la prueba.
- Salen de las 500 personas de WiSARD en los 442 fotogramas de la validación, con la rejilla ampliada (26 umbrales).
- Están en `reports/fase8/umbrales.csv`, con el sha256 de los pesos y de las predicciones. El F2 de cada umbral está
  en `umbrales_rejilla.csv`.
- Las predicciones de `rgb_base` se hicieron en este paso (`runs/fase8/validacion/`). Las demás se reutilizaron: las de
  C4 y las de la fase 6, hechas con la misma versión de Ultralytics (8.4.194).
- **Ningún umbral quedó en el piso (0.001).** Con `last.pt`, los seis bajan del 0.05 de la rejilla anterior.

| Modelo | Peso | Umbral | F2 | Recall | P | Rejilla anterior: umbral (recall) |
|---|---|---:|---:|---:|---:|---|
| `termico_base` | `last.pt` | 0.02 | 0.314 | 0.316 | 0.306 | 0.05 (0.290) |
| `termico_ampliado` | `last.pt` | 0.005 | 0.434 | 0.440 | 0.410 | 0.05 (0.362) |
| `fusion_base` | `last.pt` | 0.04 | 0.386 | 0.402 | 0.331 | 0.05 (0.390) |
| `fusion_ampliado` | `last.pt` | 0.03 | 0.403 | 0.406 | 0.390 | 0.05 (0.382) |
| `rgb_base` | `last.pt` | 0.04 | 0.093 | 0.104 | 0.065 | 0.05 (0.092) |
| `fusion_100ep` | `last.pt` | 0.01 | 0.330 | 0.340 | 0.294 | 0.05 (0.296) |
| `termico_base` | `best.pt` | 0.20 | 0.485 | 0.528 | 0.367 | igual |
| `termico_ampliado` | `best.pt` | 0.15 | 0.573 | 0.630 | 0.420 | igual |
| `fusion_base` | `best.pt` | 0.05 | 0.492 | 0.576 | 0.311 | igual |
| `fusion_ampliado` | `best.pt` | 0.10 | 0.514 | 0.552 | 0.404 | igual |
| `rgb_base` | `best.pt` | 0.10 | 0.209 | 0.208 | 0.212 | igual |
| `fusion_100ep` | `best.pt` | 0.03 | 0.436 | 0.470 | 0.337 | 0.05 (0.442) |

- Las variantes con la RGB en 0 usan el umbral de su modelo con la RGB real.
- Estas cifras son de la validación con el umbral elegido en ella misma, así que son optimistas. Solo sirven para fijar
  el umbral.

## Paso 3: comprobación de la prueba sin predecir

`--parte verificar` salió bien:
- `umbrales.csv` es igual al de GitHub (`origin/main`);
- los 12 pesos son los mismos con que se fijaron los umbrales (sha256);
- cada modelo recibe los canales con que entrenó: 3 en la térmica y en la RGB, y 4 en la fusión;
- las etiquetas de prueba de los tres datasets son las mismas;
- todo coincide con lo esperado: 928 fotogramas, 310 anotados, 1 501 personas, baja 184, severa 267, sin nivel 47,
  131 dudosas y 13 bloques;
- no había ninguna predicción ni ninguna salida de la prueba.

## Resultados en la prueba (paso 4, 21 de noviembre de 2026)

`--parte prueba`:
- predijo los 16 modelos en 325 s: 6 modelos con 2 pesos, más las 2 fusiones con la RGB en 0 con los 2 pesos;
- midió una sola vez, en 599 s en total;
- salidas en `reports/fase8/`: `resultados.csv`, `mcnemar.csv`, `sensibilidad.csv`, `prediccion.csv` y
  `recall_por_nivel.png`;
- predicciones en `runs/fase8/prueba/`;
- **control:** con las dudosas, el mAP@0.5 propio coincide con el de Ultralytics (por ejemplo, 0.468 en `termico_base`
  con `last.pt`, y 0.4682 en Ultralytics).

### Cifra principal: peso principal, sin las cajas dudosas

`last.pt` en la fase 7 y `best.pt` en `fusion_100ep`. Recall con el umbral de cada modelo, e IC del 95 % por bootstrap
de episodios (13 bloques, 10 000 remuestreos).

| Modelo | Todos los 928 (1 370 personas) | Baja (184) | **Severa (267)** | mAP@0.5, todos |
|---|---:|---:|---:|---:|
| `termico_base` | 0.536 [0.367, 0.718] | 0.826 [0.576, 0.908] | **0.337** [0.213, 0.441] | 0.511 |
| `termico_ampliado` | **0.628** [0.453, 0.811] | **0.913** [0.729, 0.968] | **0.442** [0.293, 0.578] | **0.614** |
| `fusion_base` | 0.380 [0.168, 0.621] | 0.734 [0.372, 0.863] | **0.154** [0.077, 0.250] | 0.384 |
| `fusion_ampliado` | 0.374 [0.124, 0.660] | 0.761 [0.260, 0.919] | **0.124** [0.062, 0.278] | 0.371 |
| `rgb_base` | 0.104 [0.000, 0.232] | 0.283 [0.000, 0.408] | **0.004** [0.000, 0.017] | 0.062 |
| `fusion_100ep` (fase 6, `best.pt`) | 0.264 [0.043, 0.536] | 0.636 [0.173, 0.805] | **0.030** [0.007, 0.113] | 0.258 |
| `fusion_base` con la RGB en 0 | 0.292 | 0.647 | 0.056 | 0.288 |
| `fusion_ampliado` con la RGB en 0 | 0.586 | 0.880 | 0.401 | 0.618 |

- **Los 310 anotados** (451 personas) dan casi lo mismo que los 928: 0.537, 0.634, 0.390, 0.384, 0.118 y 0.277.
- **Con las dudosas** (1 501 personas en los 928), el recall baja en todos: 0.491, 0.578, 0.349, 0.342, 0.095 y
  0.242.
- **Precisión en todos los 928:** 0.585, 0.553, 0.676, 0.573, 0.155 y 0.530.

### McNemar y criterio (familia confirmada, `last.pt`, sin las dudosas, Bonferroni ×3)

| Nivel | Par | Solo A | Solo B | Diferencia de recall [IC 95 %] | p con Bonferroni | Resultado |
|---|---|---:|---:|---|---:|---|
| Baja | `fusion_base` − `rgb_base` | 86 | 3 | +0.451 [+0.258, +0.568] | 1 × 10⁻²¹ | **demostrada** (gana la fusión) |
| Baja | `fusion_base` − `termico_base` | 7 | 24 | −0.092 [−0.256, −0.022] | 0.010 | **demostrada** (gana la térmica) |
| Baja | `fusion_ampliado` − `termico_ampliado` | 1 | 29 | −0.152 [−0.492, −0.042] | 2 × 10⁻⁷ | **demostrada** (gana la térmica) |
| Severa | `fusion_base` − `rgb_base` | 40 | 0 | +0.150 [+0.071, +0.244] | 5 × 10⁻¹² | **demostrada** (gana la fusión) |
| Severa | `fusion_base` − `termico_base` | 6 | 55 | −0.184 [−0.222, −0.108] | 2 × 10⁻¹⁰ | **demostrada** (gana la térmica) |
| Severa | `fusion_ampliado` − `termico_ampliado` | 1 | 86 | −0.318 [−0.376, −0.190] | 3 × 10⁻²⁴ | **demostrada** (gana la térmica) |

**Las seis diferencias quedan demostradas: McNemar y el IC por episodios coinciden en todas.**
- **Comparación principal, fusión contra térmica: la térmica sola detecta más personas que la fusión**, con los dos
  datasets y en los dos niveles.
  - En la oclusión severa, la fusión encuentra 0.18 menos de recall con los datos base y 0.32 menos con los ampliados.
  - Así, la respuesta a la pregunta de la tesis es **no**: con la vegetación tapando más del 70 % del cuerpo, la fusión
    temprana de este trabajo encuentra menos personas que la térmica sola.
- **Complementaria, fusión contra RGB:** la fusión detecta más que la RGB sola, en los dos niveles. Con `rgb_base`
  hundido (limitación declarada), esta comparación dice poco.
- **Va en contra de la validación (C4):** allí McNemar daba a `fusion_base` por encima de `termico_base`, por un solo
  episodio, y el IC incluía el 0. En la prueba, la térmica gana con IC que excluye el 0.

### Descriptivo (solo con IC, sin McNemar)

En todos los 928 y en la severa, sin las dudosas, con `last.pt`:

| Diferencia de recall | Todos los 928 | Severa |
|---|---|---|
| `termico_base` − `rgb_base` | +0.431 [+0.341, +0.532] | +0.333 [+0.204, +0.437] |
| `termico_ampliado` − `termico_base` (ampliar, térmica) | +0.093 [+0.049, +0.150] | +0.105 [+0.022, +0.188] |
| `fusion_ampliado` − `fusion_base` (ampliar, fusión) | −0.006 [−0.060, +0.050] | −0.030 [−0.066, +0.037] |
| `fusion_base` con la RGB en 0 − `fusion_base` | −0.088 [−0.180, −0.020] | −0.097 [−0.183, −0.025] |
| `fusion_ampliado` con la RGB en 0 − `fusion_ampliado` | **+0.212** [+0.117, +0.301] | **+0.277** [+0.188, +0.322] |
| `fusion_base` − `fusion_100ep` (`last.pt` con `last.pt`) | +0.066 [+0.025, +0.146] | +0.041 [+0.009, +0.108] |
| `fusion_ampliado` − `fusion_100ep` (`last.pt` con `last.pt`) | +0.060 [−0.013, +0.160] | +0.011 [−0.045, +0.143] |

- **La RGB real empeora a `fusion_ampliado` en la prueba.** Con la RGB en 0 su recall en la severa pasa de 0.124 a
  0.401, cerca de `termico_ampliado` (0.442). `fusion_ampliado` aprendió a detectar con la térmica (C4), y en FHL 0405
  la RGB la confunde.
- **`fusion_base` sí depende de la RGB:** con la RGB en 0 baja en los dos niveles.
- **Ampliar los datos ayuda a la térmica** (+0.09 a +0.11, con IC que excluye el 0) y **no a la fusión**.
  - Recordatorio de las limitaciones: los vuelos ampliados son del mismo sitio y día que la prueba.
- **Contra la fase 6:** `fusion_base` supera a `fusion_100ep` con `last.pt` y con `best.pt` (+0.181 [+0.108, +0.248]
  en los 928). La cifra de la fase 6 (`fusion_100ep`, `best.pt`) da 0.264 en los 928 y 0.030 en la severa.
- **Con `best.pt`** (secundaria), las conclusiones son las mismas:
  - la térmica supera a la fusión, con IC que excluye el 0 en los dos datasets y en los dos niveles;
  - las cifras son más altas: `termico_ampliado` da 0.713 en los 928 y 0.584 en la severa.
- **`rgb_base` con `best.pt` es aún peor que con `last.pt`:** 0.035 en los 928 y 0 en la severa, con 241 423
  predicciones.

### Sensibilidad del umbral (`sensibilidad.csv`, sin IC)

Recall en la severa con la rejilla anterior (0.05 en todos los `last.pt`) y con 0.5:

| Modelo | Umbral de F2 | Rejilla anterior | 0.5 |
|---|---:|---:|---:|
| `termico_base` | 0.337 | 0.311 | 0.157 |
| `termico_ampliado` | 0.442 | 0.371 | 0.225 |
| `fusion_base` | 0.154 | 0.139 | 0.037 |
| `fusion_ampliado` | 0.124 | 0.124 | 0.056 |

El orden no cambia con ningún umbral: la térmica queda por encima de la fusión en los tres.

### Limitaciones (declaradas antes de ver la prueba, y lo que se ve ahora)

- Hay una semilla por corrida, y los umbrales se eligieron en dos vuelos de validación que se comportan distinto.
- La prueba tiene 13 bloques. Los IC de los 928 son anchos (más de 0.5 en las fusiones), aunque los de las
  diferencias emparejadas son más estrechos.
- Los vuelos ampliados son del mismo sitio y día que la prueba. Eso favorece a los ampliados frente a los base, pero no
  a la fusión frente a la térmica dentro del mismo dataset.
- `rgb_base` se hunde en la validación y también en la prueba. Fusión contra RGB es complementaria.
- **Que la RGB empeore a la fusión es una observación, sin comprobar por qué.** Una posibilidad es la escena oscura bajo
  el dosel de FHL 0405, como en la escena en sombra de la fase 4.

## Comandos

```
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u -m src.entrenamiento.entrenar_fase7 --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida rgb_base > runs\fase7\rgb_base.log 2>&1"
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte umbrales
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte verificar
.venv\Scripts\python.exe -m src.evaluacion.evaluar_prueba --config configs\fase8.yaml --rutas configs\rutas.yaml --parte prueba
```
