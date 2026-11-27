# Fase 10: evaluación final de la segunda versión en la prueba (FHL 0405)

**Este es el segundo uso de la prueba.**

- El primero fue la fase 8, el 21 de noviembre de 2026, con la primera versión, entrenada en la laptop.
- Este segundo uso, del 27 de noviembre de 2026, es con la segunda versión, entrenada en la estación del laboratorio.
- Se usa una vez por versión, como fija CLAUDE.md, y las cifras de las dos versiones no se mezclan en una misma
  comparación.
- La receta de la segunda versión se eligió solo con la validación (fase 9: control, R2, R3 y R4). Antes de este paso,
  ningún modelo de la estación había visto la prueba.

Configuración: `configs/fase10.yaml`. Código: `src/evaluacion/evaluar_prueba.py`, el de la fase 8, con el factor de
Bonferroni y los textos de fase tomados de la configuración, y `src/evaluacion/fase10_resumen.py`. Salidas:
`reports/fase10/`.

## Reglas, fijadas antes de predecir

Las fijó el usuario el 27 de noviembre de 2026. Se subieron a GitHub en un commit propio (`99fcb6d`), y los umbrales en
otro (`2fbd7b5`), los dos antes de predecir la prueba. `evaluar_prueba --parte prueba` comprueba que los umbrales están en
GitHub tal como están en el disco, y que los pesos son los mismos con que se fijaron (sha256).

- **Modelos:** los 9 `elegida.pt` (R1) de la receta del control, con los datos base: fusión, solo térmica y solo RGB, con
  las semillas 0, 1 y 2. Las semillas 1 y 2 de solo RGB, que colapsaron en la validación, también se evalúan.
- **Umbral por modelo y semilla:** el de mayor F2 en la validación, con la rejilla de la fase 8 (de 0.001 a 0.95). Si
  hay empate, el más alto. Se aplica sin cambios a la prueba.
- **Métricas, como en la fase 8:** recall, precisión, F2 y mAP@0.5.
  - Globales, sobre los 928 fotogramas y sobre los 310 anotados.
  - Por nivel (baja y severa), sobre los 310 anotados.
  - Todas con y sin las cajas dudosas.
  - **Cifra principal: el recall en la severa, sin las dudosas.**
- **Por modelo:** cada semilla, y el promedio con su desviación estándar entre las 3 semillas.
- **Comparaciones por semilla** (fusión s_k contra térmica s_k, y fusión s_k contra RGB s_k):
  - McNemar exacta con Bonferroni ×3;
  - el IC del 95 % de la diferencia de recall, por bootstrap de los 13 episodios (10 000 remuestreos, seed = 0);
  - en baja y en severa, sin las dudosas.
  - Una semilla cumple si p_Bonferroni < 0.05 y el IC excluye el 0 con el mismo signo.
  - **Una diferencia cuenta como demostrada solo si se cumple en las tres semillas.** Si se cumple en una o dos, es
    "no concluyente"; si en ninguna, "no demostrada".
  - RGB contra térmica va solo con IC.
- **La comparación principal de la tesis es fusión contra térmica.** Fusión contra RGB es complementaria.

## Umbrales (validación, antes de predecir la prueba)

`reports/fase10/umbrales.csv`. Ninguno quedó en el piso de la rejilla (0.001).

| Modelo | s0 | s1 | s2 |
|---|---:|---:|---:|
| Fusión | 0.10 | 0.03 | 0.05 |
| Solo térmica | 0.04 | 0.01 | 0.15 |
| Solo RGB | 0.30 | 0.15 | 0.15 |

El mAP@0.5 de validación de cada `elegida.pt` coincide con el de la fase 9.

## Resultados en la prueba (una sola vez, 27 de noviembre de 2026, 17:25 a 17:33)

Tablas en `reports/fase10/`:

- `resultados.csv`: cada modelo y subconjunto, con IC;
- `mcnemar.csv`: McNemar por semilla;
- `resumen_modelos.csv`: promedio y desviación estándar entre semillas;
- `resumen_comparaciones.csv`: la regla de las tres semillas;
- `sensibilidad.csv`, `prediccion.csv` y `recall_por_nivel.png`.

**Recall por nivel, sin las dudosas** (310 fotogramas anotados; promedio ± desviación estándar entre las 3 semillas):

| Modelo | Nivel | Personas | s0 | s1 | s2 | Promedio ± DE |
|---|---|---:|---:|---:|---:|---:|
| Fusión | **severa** | 267 | 0.105 | 0.082 | 0.169 | **0.119 ± 0.045** |
| Solo térmica | **severa** | 267 | 0.199 | 0.199 | 0.509 | **0.302 ± 0.179** |
| Solo RGB | **severa** | 267 | 0.000 | 0.000 | 0.000 | **0.000 ± 0.000** |
| Fusión | baja | 184 | 0.728 | 0.674 | 0.815 | 0.739 ± 0.071 |
| Solo térmica | baja | 184 | 0.848 | 0.810 | 0.902 | 0.853 ± 0.046 |
| Solo RGB | baja | 184 | 0.060 | 0.266 | 0.049 | 0.125 ± 0.122 |

**Comparaciones** (diferencia de recall a − b; el IC del 95 % es por episodios; p con Bonferroni ×3):

| Comparación | Nivel | s0 | s1 | s2 | Resultado con las 3 semillas |
|---|---|---|---|---|---|
| **Fusión − térmica** (principal) | severa | −0.094 [−0.165, −0.046], p 0.0002: demostrada | −0.116 [−0.235, +0.009], p 0.0001: no concluyente (solo McNemar) | −0.341 [−0.400, −0.200], p < 0.0001: demostrada | **no concluyente** (2 de 3) |
| **Fusión − térmica** (principal) | baja | −0.120 [−0.329, −0.042]: demostrada | −0.136 [−0.281, −0.080]: demostrada | −0.087 [−0.344, −0.020], p 0.016: demostrada | **demostrada: la térmica supera a la fusión** |
| Fusión − RGB | severa | +0.105 [+0.042, +0.188]: demostrada | +0.082 [+0.037, +0.186]: demostrada | +0.169 [+0.094, +0.330]: demostrada | **demostrada: la fusión supera a la RGB** |
| Fusión − RGB | baja | +0.669 [+0.214, +0.805]: demostrada | +0.408 [+0.225, +0.513]: demostrada | +0.766 [+0.475, +0.849]: demostrada | **demostrada: la fusión supera a la RGB** |
| Térmica − RGB (solo IC) | severa | +0.199 [+0.122, +0.319] | +0.199 [+0.131, +0.341] | +0.509 [+0.441, +0.607] | el IC excluye el 0 en las 3 |
| Térmica − RGB (solo IC) | baja | +0.788 [+0.535, +0.872] | +0.543 [+0.449, +0.688] | +0.853 [+0.789, +0.889] | el IC excluye el 0 en las 3 |

**Lectura, con las reglas fijadas antes:**

- **Pregunta de la tesis, en la severa: la fusión no encuentra más personas que la térmica.**
  - En las tres semillas la térmica queda por encima: −0.09, −0.12 y −0.34.
  - En la semilla 1 el IC por episodios toca el 0, así que según la regla el resultado es "no concluyente" y no
    "demostrada".
  - La dirección es la misma que en la fase 8 (primera versión).
- **En la baja, la térmica supera a la fusión, demostrado en las tres semillas.**
- **La fusión supera a la RGB en los dos niveles**, demostrado en las tres semillas. La RGB da 0 en la severa en las
  tres semillas.
- **La dispersión entre semillas es grande.** La térmica en la severa va de 0.199 a 0.509 (la semilla 2, la de la época
  R1 10 y el umbral 0.15). Con una sola semilla, la conclusión podría haber cambiado.
- **Las semillas 1 y 2 de RGB colapsaron en la validación** y se evaluaron igual, como estaba fijado.
