# Fase 8: evaluación en la prueba (FHL 0405)

**Estado (21 de noviembre de 2026):** las reglas están confirmadas por el usuario y los pasos 1 y 2 están hechos:
- `rgb_base` se entrenó de 21:33 a 22:09 (`reports/fase7.md`, "Corrida 5 de C3: `rgb_base`");
- los umbrales están fijados en la validación y subidos a GitHub (abajo, "Paso 2").
- La prueba no se ha predicho ni medido con ningún modelo.
- Sus imágenes no se han leído.
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

## Paso 2: umbrales en la validación (21 de noviembre de 2026)

Fijados con `scripts/fase8_evaluar.py --parte umbrales` y subidos a GitHub antes de predecir la prueba.
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

## Comandos

```
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida rgb_base > runs\fase7\rgb_base.log 2>&1"
.venv\Scripts\python.exe scripts\fase8_evaluar.py --config configs\fase8.yaml --rutas configs\rutas.yaml --parte umbrales
```
