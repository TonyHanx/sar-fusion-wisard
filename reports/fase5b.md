# Fase 5b: entrenamiento de los tres modelos (100 épocas)

**Estado: detenida antes de empezar.** No se entrenó ningún modelo.

## Intentos

| Fecha y hora | Corrida | Resultado |
|---|---|---|
| 2 de noviembre de 2026, 12:03 | `fusion_100ep` | **No se entrenó.** Falló la comprobación de aplicaciones. |

- El mensaje de `scripts/entrenar.py` fue: "No se entrena: cierra antes chatgpt, chrome, robloxplayerbeta
  (cerrar_antes en configs/fase5.yaml)".
- Las tres aplicaciones estaban abiertas. No las cerré yo, porque podían tener trabajo sin guardar.
- La comprobación de aplicaciones va antes de la de potencia, así que la de potencia no llegó a hacerse.
- No se creó la carpeta de la corrida ni se agregó una fila a la bitácora, porque no hubo entrenamiento.

## Preparado

- **Corridas en `configs/fase5.yaml`:** `fusion_100ep`, con el cuarto canal en promedio, `rgb_100ep` y
  `termico_100ep`.
  - 100 épocas, lote 16, 4 procesos de lectura, `seed=0` y `hsv=0`.
  - `close_mosaic=10`, el valor por omisión.
- **Suspensión:** con la laptop enchufada, el plan de energía no la suspende ni la hiberna (tiempo 0).
- **Para retomar:** con ChatGPT, Chrome y Roblox cerrados, las tres corridas se lanzan una tras otra. La cadena se
  detiene si una comprobación falla.

  ```
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_100ep
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida rgb_100ep
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida termico_100ep
  ```
