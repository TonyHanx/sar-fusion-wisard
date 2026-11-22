# Fase 8: evaluación en la prueba (FHL 0405)

**Estado (21 de noviembre de 2026):** las reglas están confirmadas por el usuario y aún no se ha corrido nada.
- La prueba no se ha predicho ni medido con ningún modelo.
- Sus imágenes no se han leído.

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
| `rgb_base` (por entrenar) | 7 (C3, corrida 5) | base | `last.pt` | `best.pt` |
| `fusion_100ep` | 5/6 | base | `best.pt` (el que fijó la fase 6) | `last.pt` |

- **Las dos fusiones de la fase 7 también van con la RGB en 0**, con los dos pesos. Es descriptivo.
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
- De la fase 6 solo se compara la fusión.

## Pasos

Cada paso se detiene y espera al usuario.
1. **`rgb_base`** (corrida 5 de C3): la lanza el usuario en su PowerShell y se revisa como las otras corridas de C3.
2. **Umbrales en la validación:**
   - con las predicciones que ya existen, y las de `rgb_base`;
   - se escriben en `reports/fase8/umbrales.csv` y se suben a GitHub antes de predecir la prueba.
3. **Verificación de la prueba sin predecir:** fotogramas, personas, niveles, dudosas y bloques.
4. **Predicción y medida:** se predice la prueba con todos los modelos de una vez y se mide una sola vez.

## Comandos

```
$env:PYTHONIOENCODING = "utf-8"; cmd /c ".venv\Scripts\python.exe -u scripts\fase7_entrenar.py --config configs\fase7.yaml --rutas configs\rutas.yaml --corrida rgb_base > runs\fase7\rgb_base.log 2>&1"
```
