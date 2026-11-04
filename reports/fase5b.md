# Fase 5b: entrenamiento de los tres modelos (100 épocas)

**Estado: detenida a pedido el 2 de noviembre de 2026 a las 13:27:15, para preparar una entrega.** La fusión está
completa; solo RGB quedó en la época 7 de 100 y solo térmica no empezó. Este reporte se completa al terminar los tres.

## Intentos

| Fecha y hora | Corrida | Resultado |
|---|---|---|
| 2 de noviembre de 2026, 12:03 | `fusion_100ep` | **No se entrenó.** Falló la comprobación de aplicaciones. |
| 2 de noviembre de 2026, 12:07 a 13:20 | `fusion_100ep` | **Completa**, 100 épocas. Comprobación previa 99.1 W. `best.pt` = época 8. |
| 2 de noviembre de 2026, 13:20 a 13:27 | `rgb_100ep` | **Detenida a mano** tras la época 7, a pedido. Comprobación previa 97.8 W. |

- **Parada de `rgb_100ep`:** se terminó el árbol de procesos justo después de que Ultralytics guardara `last.pt` de la
  época 7 (13:27:12). La época 8 iba en 14 de 203 lotes y se pierde.
  - `last.pt` se conserva con el optimizador y la EMA (`epoch=6` en el checkpoint, contado desde 0) para reanudar con
    `resume=True`.
  - No se escribieron `monitor.csv`, `epocas.csv` ni `resumen.json`, porque el proceso se terminó; las métricas por época
    están en `results.csv`. La parada está en la bitácora.
- **Archivos de la fusión para la entrega:** `reports/fase5b/fusion_100ep/` (copias de `results.csv`, `results.png`, las
  curvas PR y F1, las matrices de confusión, `args.yaml`, `resumen.json` y su fila de la bitácora). Las curvas y las
  matrices son de la validación final con `best.pt`.

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
- **Para retomar:** con ChatGPT, Chrome y Roblox cerrados, las corridas se lanzan una tras otra. La cadena se
  detiene si una comprobación falla.
  - La fusión ya está; falta decidir si `rgb_100ep` se reanuda desde `last.pt` o se empieza de nuevo.
    - `scripts/entrenar.py` todavía no reanuda: usa `exist_ok=False`, así que el comando de abajo falla mientras exista
      la carpeta.
    - Además, Ultralytics no guarda el estado del generador aleatorio. Una corrida reanudada no es idéntica a una
      corrida seguida.

  ```
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida fusion_100ep
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida rgb_100ep
  .venv\Scripts\python.exe scripts\entrenar.py --config configs\fase5.yaml --rutas configs\rutas.yaml --corrida termico_100ep
  ```
