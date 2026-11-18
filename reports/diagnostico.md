# Diagnóstico del mAP@0.5 de validación

18 de noviembre de 2026.

**Pregunta.** ¿Por qué el modelo de fusión da un mAP@0.5 de **0.374** en validación, cuando WiSARD reporta 0.977 en
térmica con YOLOv5? ¿Hay algo mal en el código o en los datos?

**Cómo se hizo:**
- **Nada de lo ya hecho cambió.** `runs/fase5`, las etiquetas, `data/datasets` y los configs de las fases cerradas
  solo se leyeron.
- **La prueba (FHL 0405) no se usa.** Solo se cuenta en el inventario (A1) y en la comprobación de que no comparte
  archivos con entrenamiento ni validación (A6).
- **Dónde está cada cosa:**
  - código: `scripts/diagnostico.py`;
  - configuración: `configs/diagnostico.yaml` (las rutas y los parámetros van en configs, como pide CLAUDE.md);
  - salidas: `runs/diagnostico/` (`a1` … `a6`, `datasets`, y una carpeta por corrida de B);
  - copia para git: `reports/diagnostico/` (ver "Archivos de apoyo" al final).
- **Bitácora:** las evaluaciones de A4 y las corridas de B tienen su fila en `reports/bitacora.csv`.

```
.venv\Scripts\python.exe scripts\diagnostico.py --config configs\diagnostico.yaml --rutas configs\rutas.yaml --parte inventario
   (y estado, tamanos, integridad, validar, hoja, b1_datos)
.venv\Scripts\python.exe scripts\entrenar.py --config configs\diagnostico.yaml --rutas configs\rutas.yaml --corrida b1_termico_aleatoria_30ep
.venv\Scripts\python.exe scripts\diagnostico.py --config configs\diagnostico.yaml --rutas configs\rutas.yaml --parte b_evaluar --corrida b1_termico_aleatoria_30ep
   (y --parte b_por_vuelo con la misma corrida; lo mismo con b2_termico_vuelo_30ep)
```

---

## A1. Inventario de WiSARDv1

**Tamaño de WiSARDv1:**
- 80 carpetas: 41 térmicas (IR) y 39 RGB (VIS).
- 17 parejas VIS–IR, con 34 carpetas. Las otras 46 no tienen pareja.
- Las 17 parejas salen de la regla de emparejamiento de CLAUDE.md, y coinciden con `data/pares.csv`.

**Qué se contó en cada carpeta:**
- **Resolución:** se leyó la cabecera de cada imagen.
- **Cajas:** cada línea no vacía de cada `.txt` cuenta como una caja, incluidas las repetidas.
- **`count.txt`:** 76 de las 80 carpetas tienen uno, que no es una etiqueta y no se cuenta.
- **Baker IR_2:** sus 609 `.txt` están **todos vacíos**. Por la regla de CLAUDE.md (".txt vacío = 0 cajas") cuentan
  como anotados, pero lo más probable es que la carpeta no esté anotada.

| Carpeta | Mod. | Resolución | Imágenes | Con .txt | .txt con cajas | Cajas | Pareja | Partición | En los 4 617 |
|---|---|---|---:|---:|---:|---:|---|---|---:|
| 200321_Baker_Phantom_VIS | VIS | 3840×2160 | 517 | 517 | 507 | 1020 | — | — | 0 |
| 200402_Carnation_Inspire_VIS | VIS | 4096×2160 | 544 | 544 | 509 | 1635 | — | — | 0 |
| 200402_Karen_Inspire_VIS | VIS | 2704×1520 (1914); 3840×2160 (312) | 2226 | 2226 | 1633 | 2921 | — | — | 0 |
| 200426_SkookumCreek_Mavic_Mini_VIS_0006 | VIS | 1920×1080 | 404 | 404 | 323 | 530 | — | — | 0 |
| 200426_SkookumCreek_Mavic_Mini_VIS_0007 | VIS | 1920×1080 | 1460 | 1460 | 1459 | 5065 | — | — | 0 |
| 200426_SkookumCreek_Mavic_Mini_VIS_0008 | VIS | 2720×1530 | 939 | 939 | 911 | 3892 | — | — | 0 |
| 200505_Bellingham_Mavic_Mini_VIS_0015 | VIS | 2720×1530 | 454 | 454 | 436 | 584 | — | — | 0 |
| 200505_Bellingham_Mavic_Mini_VIS_0016 | VIS | 2720×1530 | 303 | 303 | 285 | 321 | — | — | 0 |
| 200528_Everson_Mavic_Mini_VIS_0021 | VIS | 2720×1530 | 500 | 500 | 497 | 948 | — | — | 0 |
| 200528_Everson_Mavic_Mini_VIS_0028 | VIS | 2720×1530 | 336 | 336 | 249 | 492 | — | — | 0 |
| 200528_Everson_Mavic_Mini_VIS_0029 | VIS | 2720×1530 | 237 | 237 | 215 | 409 | — | — | 0 |
| 200528_Everson_Mavic_Mini_VIS_0031 | VIS | 2720×1530 | 400 | 400 | 374 | 1375 | — | — | 0 |
| 200614_SuddenValley_Phantom_VIS_0005 | VIS | 3840×2160 | 379 | 379 | 314 | 945 | — | — | 0 |
| 200614_SuddenValley_Phantom_VIS_0006 | VIS | 3840×2160 | 387 | 387 | 374 | 1316 | — | — | 0 |
| 200614_SuddenValley_Phantom_VIS_0012 | VIS | 3840×2160 | 41 | 41 | 41 | 159 | — | — | 0 |
| 200614_SuddenValley_Phantom_VIS_0013 | VIS | 3840×2160 | 63 | 63 | 57 | 102 | — | — | 0 |
| 200614_SuddenValley_Phantom_VIS_0014 | VIS | 3840×2160 | 235 | 235 | 231 | 754 | — | — | 0 |
| 200704_Baker_FLIR_IR_1 | IR | 640×512 | 912 | 912 | 873 | 994 | — | — | 0 |
| 200704_Baker_FLIR_IR_2 | IR | 640×512 | 1081 | 1081 | 1060 | 2026 | — | — | 0 |
| 200717_Mission_FLIR_VIS | VIS | 3840×2160 | 363 | 363 | 325 | 371 | — | — | 0 |
| 200910_Carnation_FLIR_IR_1 | IR | 640×512 | 183 | 183 | 86 | 237 | — | — | 0 |
| 200910_Carnation_FLIR_IR_2 | IR | 640×512 | 450 | 450 | 423 | 1230 | — | — | 0 |
| 200910_Carnation_FLIR_IR_3 | IR | 640×512 | 452 | 452 | 101 | 101 | — | — | 0 |
| 200910_Carnation_FLIR_IR_4 | IR | 640×512 | 452 | 452 | 61 | 61 | — | — | 0 |
| 200910_Carnation_FLIR_IR_5 | IR | 640×512 | 452 | 452 | 221 | 221 | — | — | 0 |
| 200910_Carnation_FLIR_IR_6 | IR | 640×512 | 452 | 452 | 204 | 208 | — | — | 0 |
| 200910_Carnation_FLIR_IR_7 | IR | 640×512 | 408 | 408 | 118 | 118 | — | — | 0 |
| 200929_Karen_FLIR_IR_1 | IR | 640×512 | 452 | 452 | 341 | 341 | — | — | 0 |
| 200929_Karen_FLIR_IR_2 | IR | 640×512 | 452 | 452 | 399 | 400 | — | — | 0 |
| 200929_Karen_FLIR_IR_3 | IR | 640×512 | 452 | 452 | 432 | 433 | — | — | 0 |
| 200929_Karen_FLIR_IR_4 | IR | 640×512 | 452 | 452 | 452 | 464 | — | — | 0 |
| 200929_Karen_FLIR_IR_5 | IR | 640×512 | 452 | 452 | 452 | 919 | — | — | 0 |
| 200929_Karen_FLIR_IR_6 | IR | 640×512 | 451 | 451 | 451 | 1291 | — | — | 0 |
| 210327_Airfield_FLIR_IR_1 | IR | 640×512 | 983 | 983 | 22 | 22 | — | — | 0 |
| 210327_Airfield_FLIR_IR_2 | IR | 640×512 | 922 | 922 | 413 | 499 | — | — | 0 |
| 210327_Airfield_FLIR_IR_3 | IR | 640×512 | 1062 | 1062 | 295 | 444 | — | — | 0 |
| 210327_Airfield_FLIR_IR_4 | IR | 640×512 | 1061 | 1061 | 83 | 83 | — | — | 0 |
| 210327_Airfield_FLIR_IR_5 | IR | 640×512 | 313 | 313 | 2 | 2 | — | — | 0 |
| 210327_Airfield_FLIR_IR_6 | IR | 640×512 | 1059 | 1059 | 195 | 195 | — | — | 0 |
| 210327_Airfield_FLIR_IR_7 | IR | 640×512 | 1059 | 1059 | 280 | 280 | — | — | 0 |
| 210327_Airfield_FLIR_IR_8 | IR | 640×512 | 415 | 415 | 97 | 97 | — | — | 0 |
| 210327_Airfield_FLIR_VIS_1 | VIS | 3840×2160 | 497 | 497 | 439 | 872 | — | — | 0 |
| 210327_Airfield_FLIR_VIS_2 | VIS | 3840×2160 | 249 | 249 | 221 | 348 | — | — | 0 |
| 210327_Airfield_FLIR_VIS_3 | VIS | 3840×2160 | 302 | 302 | 88 | 88 | — | — | 0 |
| 210327_Airfield_FLIR_VIS_4 | VIS | 3840×2160 | 572 | 572 | 75 | 76 | — | — | 0 |
| 210417_MtErie_Enterprise_IR_0004 | IR | 640×512 | 264 | 264 | 261 | 1006 | MtErie 0003 | entrenamiento | 236 |
| 210417_MtErie_Enterprise_IR_0006 | IR | 640×512 | 272 | 272 | 272 | 526 | MtErie 0005 | entrenamiento | 257 |
| 210417_MtErie_Enterprise_IR_0008 | IR | 640×512 | 172 | 172 | 172 | 292 | MtErie 0007 | validación | 169 |
| 210417_MtErie_Enterprise_VIS_0003 | VIS | 3840×2160 | 264 | 264 | 261 | 1022 | MtErie 0003 | entrenamiento | 236 |
| 210417_MtErie_Enterprise_VIS_0005 | VIS | 3840×2160 | 272 | 272 | 264 | 454 | MtErie 0005 | entrenamiento | 257 |
| 210417_MtErie_Enterprise_VIS_0007 | VIS | 3840×2160 | 172 | 172 | 164 | 294 | MtErie 0007 | validación | 169 |
| 210529_Carnation_Enterprise_IR_0024 | IR | 640×512 | 740 | 740 | 736 | 1714 | Carnation 0023 | — | 0 |
| 210529_Carnation_Enterprise_IR_0026 | IR | 640×512 | 1315 | 0 | 0 | 0 | Carnation 0025 | — | 0 |
| 210529_Carnation_Enterprise_VIS_0023 | VIS | 1920×1080 | 739 | 739 | 735 | 1942 | Carnation 0023 | — | 0 |
| 210529_Carnation_Enterprise_VIS_0025 | VIS | 1920×1080 | 1315 | 1315 | 1215 | 5247 | Carnation 0025 | — | 0 |
| 210812_Hannegan_Enterprise_IR_0054 | IR | 640×512 | 715 | 0 | 0 | 0 | Hannegan 0053 | — | 0 |
| 210812_Hannegan_Enterprise_IR_0056 | IR | 640×512 | 422 | 0 | 0 | 0 | Hannegan 0055 | — | 0 |
| 210812_Hannegan_Enterprise_VIS_0053 | VIS | 1920×1080 | 715 | 0 | 0 | 0 | Hannegan 0053 | — | 0 |
| 210812_Hannegan_Enterprise_VIS_0055 | VIS | 1920×1080 | 422 | 0 | 0 | 0 | Hannegan 0055 | — | 0 |
| 210924_FHL_Enterprise_IR_0127 | IR | 640×512 | 1008 | 0 | 0 | 0 | FHL 0126 | — | 0 |
| 210924_FHL_Enterprise_IR_0135 | IR | 640×512 | 273 | 273 | 136 | 211 | FHL 0134 | validación | 273 |
| 210924_FHL_Enterprise_IR_0402 | IR | 640×512 | 896 | 896 | 796 | 3122 | FHL 0401 | entrenamiento | 783 |
| 210924_FHL_Enterprise_IR_0404 | IR | 640×512 | 1417 | 1417 | 216 | 951 | FHL 0403 | — | 0 |
| 210924_FHL_Enterprise_IR_0406 | IR | 640×512 | 943 | 943 | 794 | 1534 | FHL 0405 | prueba | 928 |
| 210924_FHL_Enterprise_IR_0408 | IR | 640×512 | 1035 | 0 | 0 | 0 | FHL 0407 | — | 0 |
| 210924_FHL_Enterprise_IR_0410 | IR | 640×512 | 1299 | 0 | 0 | 0 | FHL 0409 | — | 0 |
| 210924_FHL_Enterprise_IR_0565 | IR | 640×512 | 982 | 982 | 712 | 1166 | FHL 0564 | — | 0 |
| 210924_FHL_Enterprise_IR_0567 | IR | 640×512 | 909 | 909 | 690 | 1095 | FHL 0566 | — | 0 |
| 210924_FHL_Enterprise_VIS_0126 | VIS | 1920×1080 | 1006 | 1004 | 995 | 1398 | FHL 0126 | — | 0 |
| 210924_FHL_Enterprise_VIS_0134 | VIS | 1920×1080 | 273 | 273 | 89 | 148 | FHL 0134 | validación | 273 |
| 210924_FHL_Enterprise_VIS_0401 | VIS | 1920×1080 | 897 | 897 | 804 | 3321 | FHL 0401 | entrenamiento | 783 |
| 210924_FHL_Enterprise_VIS_0403 | VIS | 1920×1080 | 1417 | 0 | 0 | 0 | FHL 0403 | — | 0 |
| 210924_FHL_Enterprise_VIS_0405 | VIS | 1920×1080 | 945 | 945 | 410 | 577 | FHL 0405 | prueba | 928 |
| 210924_FHL_Enterprise_VIS_0407 | VIS | 1920×1080 | 1035 | 1035 | 796 | 2022 | FHL 0407 | — | 0 |
| 210924_FHL_Enterprise_VIS_0409 | VIS | 1920×1080 | 1300 | 0 | 0 | 0 | FHL 0409 | — | 0 |
| 210924_FHL_Enterprise_VIS_0564 | VIS | 1920×1080 | 983 | 0 | 0 | 0 | FHL 0564 | — | 0 |
| 210924_FHL_Enterprise_VIS_0566 | VIS | 1920×1080 | 909 | 0 | 0 | 0 | FHL 0566 | — | 0 |
| 220109_Baker_Enterprise_IR_1 | IR | 640×512 | 2180 | 2180 | 1952 | 5261 | Baker | entrenamiento | 1971 |
| 220109_Baker_Enterprise_IR_2 | IR | 640×512 | 609 | 609 | 0 | 0 | — | — | 0 |
| 220109_Baker_Enterprise_VIS_1 | VIS | 1920×1080 | 2180 | 2180 | 2090 | 6012 | Baker | entrenamiento | 1971 |

| Modalidad | Imágenes | Con .txt | .txt con cajas | Cajas |
|---|---:|---:|---:|---:|
| IR | 29 878 | 24 084 | 13 798 | 27 544 |
| VIS | 26 252 | 20 504 | 17 386 | 46 660 |

**Térmicas anotadas que quedan fuera de los 4 617 pares que usamos:**
- Son **19 467**, que es el 80.8 % de las 24 084 térmicas anotadas.
- 9 653 de ellas tienen al menos una caja, con 16 203 cajas en total.
- **De los 4 617 pares, 3 689 son de entrenamiento y validación.** El modelo entrena con 3 247 imágenes térmicas, el
  13.5 % de las anotadas.

| Sitio | Térmicas anotadas (total) | Con cajas (total) | Fuera de los 4 617 | Fuera, con cajas | Cajas fuera |
|---|---:|---:|---:|---:|---:|
| Airfield | 6 874 | 1 387 | 6 874 | 1 387 | 1 622 |
| Baker | 4 782 | 3 885 | 2 811 | 1 997 | 3 095 |
| Carnation | 3 589 | 1 950 | 3 589 | 1 950 | 3 890 |
| FHL | 5 420 | 3 344 | 3 436 | 1 746 | 3 612 |
| Hannegan | 0 | 0 | 0 | 0 | 0 |
| Karen | 2 711 | 2 527 | 2 711 | 2 527 | 3 848 |
| MtErie | 708 | 705 | 46 | 46 | 136 |
| **Total** | **24 084** | **13 798** | **19 467** | **9 653** | **16 203** |

| Por qué quedan fuera | Térmicas anotadas | Con cajas | Cajas |
|---|---:|---:|---:|
| Carpeta IR sin pareja VIS (Airfield, Karen, Carnation FLIR, Baker FLIR de 2020 y Baker IR_2) | 15 036 | 7 061 | 10 666 |
| En un par con la RGB sin anotar (FHL 0403, 0564 y 0566) | 3 308 | 1 618 | 3 212 |
| Par excluido (desfases, zoom de Carnation 0023, despegue, aterrizaje y tramo de Baker; incluye 15 de FHL 0405) | 1 122 | 973 | 2 324 |
| Sin par: pasa de la longitud mínima de la pareja | 1 | 1 | 1 |

---

## A2. Estado de las corridas de la noche del 3 al 4 de noviembre

**No terminaron ni solo RGB ni solo térmica.**
- A las 00:15 del 4 de noviembre se cortó la corriente y Windows suspendió la laptop.
- `rgb_100ep` quedó en la época 67. Se descartó y se movió a `runs/fase5/rgb_100ep_cortada2`.
- Solo térmica no empezó.
- La noche no se volvió a lanzar:
  - `reports/noche_log.txt` no tiene nada después del 4 de noviembre a las 05:57;
  - en `runs/fase5` no existen `rgb_100ep` ni `termico_100ep`;
  - `runs/noche/` solo tiene la salida de esa noche.

| Modelo | Corrida | Estado | Época del best.pt | best.pt: mAP@0.5 | mAP@0.5:0.95 | Precisión | Recall | Máx. mAP@0.5 (época) | mAP@0.5 de la última época |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Fusión | `fusion_100ep` | 100 de 100 épocas | 8 | 0.3740 | 0.1674 | 0.559 | 0.376 | 0.3951 (27) | 0.2452 (100) |
| Solo RGB | `rgb_100ep` | No existe. Hay dos cortadas: 7 y 67 épocas | (2)\* | (0.1628)\* | (0.0550)\* | (0.519)\* | (0.168)\* | (0.1628 (2))\* | (0.0098 (67))\* |
| Solo térmica | `termico_100ep` | No empezó | — | — | — | — | — | — | — |

\* **Solo RGB** viene de `rgb_100ep_cortada2`, en `results.csv` (época de mayor mAP@0.5:0.95 y la 67). No es un modelo
terminado y no se usa.

**Cómo leer la tabla:**
- **Época del best.pt:** Ultralytics 8.4.194 elige el `best.pt` por fitness, que es solo el mAP@0.5:0.95 (pesos
  `[0, 0, 0, 1]`).
- **Métricas del best.pt:** son las de la validación final de Ultralytics (`resumen.json`).
- **El máximo de mAP@0.5 de la fusión fue en la época 27**, pero esos pesos no se guardaron (`save_period=-1`). Solo
  hay `best.pt` (época 8) y `last.pt` (época 100).
- **La fusión llega a su mejor valor muy pronto y después baja:**
  - época 8 (`best.pt`): 0.374;
  - época 27: 0.395;
  - época 100: 0.245.
  - Solo RGB hace lo mismo y antes: 0.163 en la época 2 y 0.010 en la 67.

---

## A3. Tamaño de las personas

- **Cajas:** son las etiquetas térmicas sin cajas repetidas, en píxeles de 640 × 512 (`data/datasets/termico`).
- **Particiones:** entrenamiento y validación; la prueba no entra.
- **Lado mayor:** max(ancho, alto).
- **Tramos (QFDet):** son semiabiertos. Por ejemplo, "8–12" quiere decir 8 ≤ lado < 12. Importa porque los tamaños son
  píxeles enteros en el 95.7 % de los anchos y el 90.9 % de los altos.
- **RGB original:** el tamaño equivalente es el lado mayor térmico dividido por la escala de la semejanza congelada de
  cada vuelo (`configs/homografias_cajas.yaml`).

**Por partición** (cada medida da p10 / p50 / p90, en px):

| Partición | Cajas | Ancho | Alto | Lado mayor | Lado mayor en la RGB original | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---|---|---|---|---:|---:|---:|---:|---:|
| Entrenamiento | 9 340 | 8.0 / 24.0 / 66.0 | 16.0 / 33.0 / 86.0 | 17.0 / 36.0 / 87.0 | 32.4 / 88.3 / 176.0 | 22 (0.2 %) | 159 (1.7 %) | 1 459 (15.6 %) | 2 411 (25.8 %) | 5 289 (56.6 %) |
| Validación | 500 | 9.0 / 14.0 / 26.0 | 9.0 / 28.5 / 59.1 | 10.0 / 28.5 / 59.1 | 19.6 / 112.8 / 234.0 | 3 (0.6 %) | 112 (22.4 %) | 97 (19.4 %) | 55 (11.0 %) | 233 (46.6 %) |

**Por vuelo** (cada medida da p10 / p50 / p90, en px):

| Partición | Vuelo | Cajas | Ancho | Alto | Lado mayor | Lado mayor en la RGB original | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|
| Entrenamiento | Baker | 5 186 | 19.0 / 42.0 / 77.0 | 26.0 / 56.0 / 94.0 | 31.0 / 64.0 / 95.0 | 59.9 / 123.7 / 183.7 | 0 (0.0 %) | 0 (0.0 %) | 92 (1.8 %) | 440 (8.5 %) | 4 654 (89.7 %) |
| Entrenamiento | FHL 0401 | 2 755 | 6.0 / 11.0 / 20.0 | 13.0 / 20.0 / 29.0 | 13.0 / 21.0 / 30.0 | 24.8 / 40.0 / 57.2 | 22 (0.8 %) | 155 (5.6 %) | 1 184 (43.0 %) | 1 196 (43.4 %) | 198 (7.2 %) |
| Entrenamiento | MtErie 0003 | 905 | 8.5 / 13.0 / 20.0 | 17.8 / 22.8 / 27.7 | 18.0 / 22.8 / 28.4 | 69.8 / 88.3 / 110.3 | 0 (0.0 %) | 4 (0.4 %) | 181 (20.0 %) | 688 (76.0 %) | 32 (3.5 %) |
| Entrenamiento | MtErie 0005 | 494 | 21.0 / 33.0 / 68.0 | 25.0 / 71.0 / 161.0 | 27.0 / 71.5 / 161.0 | 103.1 / 273.0 / 614.8 | 0 (0.0 %) | 0 (0.0 %) | 2 (0.4 %) | 87 (17.6 %) | 405 (82.0 %) |
| Validación | MtErie 0007 | 289 | 12.0 / 18.0 / 29.0 | 27.0 / 45.0 / 67.0 | 27.0 / 45.0 / 67.0 | 106.9 / 178.2 / 265.3 | 0 (0.0 %) | 0 (0.0 %) | 1 (0.3 %) | 55 (19.0 %) | 233 (80.6 %) |
| Validación | FHL 0134 | 211 | 8.0 / 10.0 / 12.0 | 8.0 / 11.0 / 13.0 | 9.0 / 11.0 / 13.0 | 17.6 / 21.5 / 25.4 | 3 (1.4 %) | 112 (53.1 %) | 96 (45.5 %) | 0 (0.0 %) | 0 (0.0 %) |

| Vuelo | RGB original | Escala (px térmico por px RGB) | px RGB por px térmico |
|---|---|---:|---:|
| Baker | 1920×1080 | 0.5172 | 1.93 |
| FHL 0401 | 1920×1080 | 0.5247 | 1.91 |
| MtErie 0003 | 3840×2160 | 0.2578 | 3.88 |
| MtErie 0005 | 3840×2160 | 0.2619 | 3.82 |
| MtErie 0007 | 3840×2160 | 0.2526 | 3.96 |
| FHL 0134 | 1920×1080 | 0.5109 | 1.96 |

**Lo que se ve:**
- **Personas de menos de 12 px:**
  - en entrenamiento hay **181 de 9 340 (1.9 %)**;
  - en validación hay **115 de 500 (23.0 %)**, todas de FHL 0134, donde son 115 de 211 (54.5 %).
- **FHL 0134 no tiene ninguna persona de 20 px o más.** Su mediana es de 11 px, unos 21 px en su RGB de 1920 × 1080.
- **Baker pesa mucho en entrenamiento:** aporta el 55.5 % de las personas (5 186 de 9 340), con mediana de 64 px y el
  89.7 % de 32 px o más.
- **Lo que se ve de cada vuelo,** según 2 fotogramas por vuelo revisados a ojo:
  - Baker: nieve, campo abierto y vista oblicua.
  - FHL 0401: costa rocosa y agua.
  - MtErie 0003 y 0005: roca y sendero, vista oblicua y cenital.
  - **FHL 0134 (validación):** vista cenital sobre un dosel denso. La copa de los árboles sale clara (caliente) en la
    térmica.
  - **MtErie 0007 (validación):** dentro del bosque, con la cámara de frente entre troncos.
  - Ningún vuelo de entrenamiento se parece a estos dos.

---

## A4. Validación desglosada del modelo de fusión

**Pesos:**
- **`best.pt` (época 8).**
- **`last.pt` (época 100):** solo como referencia.
- **La época de mayor mAP@0.5 (27) no se puede evaluar,** porque sus pesos no se guardaron (`save_period=-1`).
- **Solo RGB y solo térmica no terminaron,** así que A4 solo se hace con la fusión.

**Cómo se calculó:**
- **Por vuelo y por "solo térmica":**
  - `model.val` con conf 0.001, imgsz 640 y lote 16, la misma configuración de `configs/fase6.yaml`;
  - cada subconjunto es un dataset propio en `runs/diagnostico/datasets/a4_fusion_*`, con enlaces duros a las mismas
    imágenes y etiquetas.
- **"Solo térmica":** los pares con persona en la térmica y ninguna caja RGB de WiSARD, según `data/pares.csv`. En
  validación son 61 de FHL 0134 y 7 de MtErie 0007.

### `model.val` por subconjunto

| Subconjunto | Imágenes | Personas | Sin persona | best.pt: mAP@0.5 | mAP@0.5:0.95 | P | R | last.pt: mAP@0.5 | mAP@0.5:0.95 | P | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Validación completa | 442 | 500 | 137 | 0.3749 | 0.1675 | 0.559 | 0.370 | 0.2500 | 0.1111 | 0.501 | 0.270 |
| MtErie 0007 | 169 | 289 | 0 | **0.6004** | 0.2740 | 0.678 | 0.522 | 0.3920 | 0.1966 | 0.608 | 0.353 |
| FHL 0134 | 273 | 211 | 137 | **0.0825** | 0.0305 | 0.278 | 0.166 | 0.0727 | 0.0149 | 0.396 | 0.152 |
| Solo térmica | 68 | 75 | 0 | 0.3412 | 0.1514 | 0.585 | 0.387 | 0.3288 | 0.0856 | 0.724 | 0.373 |
| Resto | 374 | 425 | 137 | 0.3873 | 0.1749 | 0.577 | 0.367 | 0.2424 | 0.1179 | 0.447 | 0.259 |

### mAP@0.5 por tamaño

- **Por qué no con `model.val`:** no puede dejar fuera solo una parte de las cajas de una imagen. Por eso el mAP@0.5
  por tramo se calcula con pycocotools sobre las mismas predicciones (las de `model.val` con conf 0.001 del subconjunto
  completo).
- **Regla de los tramos** (la de las áreas de COCO, con el lado mayor en lugar del área):
  - una persona fuera del tramo queda como ignorada;
  - una predicción fuera del tramo que no acierta tampoco cuenta.
- La columna "Todas" coincide casi con la de Ultralytics: 0.379 contra 0.375, porque COCO interpola en 101 puntos.
- En la tabla, el número entre paréntesis es la cantidad de personas.

`best.pt`:

| Subconjunto | Todas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|
| Validación completa | 0.379 (500) | 0.000 (3) | 0.102 (112) | 0.256 (97) | 0.227 (55) | 0.621 (233) |
| MtErie 0007 | 0.599 (289) | — (0) | — (0) | 0.000 (1) | 0.472 (55) | 0.647 (233) |
| FHL 0134 | 0.084 (211) | 0.000 (3) | 0.146 (112) | 0.330 (96) | — (0) | — (0) |
| Solo térmica | 0.346 (75) | 0.000 (3) | 0.168 (22) | 0.655 (40) | 0.084 (3) | 0.267 (7) |
| Resto | 0.390 (425) | — (0) | 0.084 (90) | 0.071 (57) | 0.244 (52) | 0.636 (226) |

`last.pt`:

| Subconjunto | Todas | <8 | 8–12 | 12–20 | 20–32 | ≥32 |
|---|---:|---:|---:|---:|---:|---:|
| Validación completa | 0.255 (500) | 0.000 (3) | 0.019 (112) | 0.285 (97) | 0.188 (55) | 0.418 (233) |
| MtErie 0007 | 0.393 (289) | — (0) | — (0) | 0.000 (1) | 0.387 (55) | 0.428 (233) |
| FHL 0134 | 0.074 (211) | 0.000 (3) | 0.040 (112) | 0.295 (96) | — (0) | — (0) |
| Solo térmica | 0.330 (75) | 0.000 (3) | 0.010 (22) | 0.632 (40) | 0.084 (3) | 0.241 (7) |
| Resto | 0.245 (425) | — (0) | 0.025 (90) | 0.087 (57) | 0.203 (52) | 0.426 (226) |

### Personas detectadas con `predict` (conf 0.25 y 0.5)

- **Cuándo una persona cuenta como detectada:** alguna predicción con esa confianza o más la cubre con IoU ≥ 0.5.
- **Emparejamiento:** voraz por confianza, como en COCO.
- **FP:** predicciones que no emparejan con ninguna persona.

| Grupo | Personas | best.pt, 0.25 | best.pt, 0.5 | last.pt, 0.25 | last.pt, 0.5 |
|---|---:|---:|---:|---:|---:|
| Validación completa | 500 | 152 (30.4 %; FP 84) | 92 (18.4 %; FP 22) | 116 (23.2 %; FP 88) | 89 (17.8 %; FP 51) |
| MtErie 0007 | 289 | 136 (47.1 %; FP 50) | 87 (30.1 %; FP 8) | 94 (32.5 %; FP 46) | 77 (26.6 %; FP 18) |
| FHL 0134 | 211 | **16 (7.6 %; FP 34)** | **5 (2.4 %; FP 14)** | 22 (10.4 %; FP 42) | 12 (5.7 %; FP 33) |
| Solo térmica | 75 | 15 (20.0 %; FP 10) | 4 (5.3 %; FP 0) | 24 (32.0 %; FP 9) | 13 (17.3 %; FP 6) |
| Resto | 425 | 137 (32.2 %; FP 74) | 88 (20.7 %; FP 22) | 92 (21.6 %; FP 79) | 76 (17.9 %; FP 45) |
| Tramo <8 | 3 | 0 (0.0 %) | 0 (0.0 %) | 0 (0.0 %) | 0 (0.0 %) |
| Tramo 8–12 | 112 | 4 (3.6 %) | 2 (1.8 %) | 0 (0.0 %) | 0 (0.0 %) |
| Tramo 12–20 | 97 | 12 (12.4 %) | 3 (3.1 %) | 22 (22.7 %) | 12 (12.4 %) |
| Tramo 20–32 | 55 | 19 (34.5 %) | 10 (18.2 %) | 18 (32.7 %) | 12 (21.8 %) |
| Tramo ≥32 | 233 | 117 (50.2 %) | 77 (33.0 %) | 76 (32.6 %) | 65 (27.9 %) |

**`predict` contra `model.val`:**
- No dan exactamente las mismas cajas:
  - con conf ≥ 0.25: 236 cajas con `predict` y 227 con `model.val` filtrado;
  - con conf ≥ 0.5: 114 contra 111.
- **Por qué:** en modo `rect`, `model.val` rellena cada imagen hasta 672 × 544, y `predict` la pasa a 640 × 512.
- **Los 4 canales llegan bien.** Si a `predict` se le da una lista de rutas, abre las imágenes con PIL en RGB y pierde
  el cuarto canal. Por eso las imágenes se le pasan en un `.txt`, y así las lee igual que la validación (los 4 canales
  del TIFF).

**Lo que se ve:**
- **La validación mezcla dos vuelos muy distintos:**
  - **MtErie 0007:** mAP@0.5 de 0.600;
  - **FHL 0134:** mAP@0.5 de 0.083, con 5 de 211 personas detectadas a 0.5.
- **FHL 0134 pesa mucho:** aporta el 42 % de las personas y el 62 % de las imágenes, y 137 de sus 273 imágenes no tienen
  persona.
- **El mAP@0.5 sube con el tamaño:**
  - 0.102 de 8 a 12 px;
  - 0.621 de 32 px o más.
- **Aun en MtErie 0007 y con personas de 32 px o más,** el mAP@0.5 es de 0.647 y solo se detecta la mitad (50.2 %) a
  conf 0.25.
- **Los pares "solo térmica" no son los más difíciles:** dan 0.341, contra 0.387 del resto. En FHL 0134, el "resto"
  tiene personas igual de pequeñas pero no tiene ninguna caja RGB.

---

## A5. Revisión visual

- **Hoja:** `runs/diagnostico/a5/hoja.png` (5174 × 2190 px), con cada par también suelto en `runs/diagnostico/a5/`.
- **Imágenes:** 16 de validación elegidas al azar con seed 0.
- **Colores:** cajas anotadas en verde y predicciones del `best.pt` de fusión (conf 0.25) en rojo, en la térmica y en
  la RGB alineada.

| Imagen | Anotadas | Predicciones | Aciertos | Confianzas |
|---|---:|---:|---:|---|
| MtErie 0007_0007 | 2 | 1 | 1 | 0.88 |
| MtErie 0007_0017 | 2 | 1 | 1 | 0.88 |
| MtErie 0007_0032 | 1 | 1 | 0 | 0.41 |
| MtErie 0007_0079 | 2 | 1 | 1 | 0.59 |
| MtErie 0007_0119 | 2 | 1 | 1 | 0.61 |
| MtErie 0007_0135 | 2 | 2 | 2 | 0.70, 0.32 |
| FHL 0134_0050 | 2 | 0 | 0 | |
| FHL 0134_0052 | 2 | 0 | 0 | |
| FHL 0134_0097 | 0 | 0 | 0 | |
| FHL 0134_0103 | 0 | 0 | 0 | |
| FHL 0134_0114 | 0 | 0 | 0 | |
| FHL 0134_0153 | 1 | 1 | 1 | 0.50 |
| FHL 0134_0185 | 0 | 0 | 0 | |
| FHL 0134_0194 | 0 | 0 | 0 | |
| FHL 0134_0230 | 0 | 0 | 0 | |
| FHL 0134_0259 | 1 | 0 | 0 | |

**Lo que se ve en las 16:**
- **Cajas mal anotadas o desplazadas: no vi ninguna.**
  - Las verdes caen sobre la persona en la térmica y, con la semejanza, también en la RGB alineada.
  - En FHL 0134 son cuadrados de unos 10 px sobre manchas calientes redondas: cabeza y hombros vistos desde arriba.
- **Personas sin caja: en FHL 0134_0114, probablemente sí.**
  - En el borde inferior, hacia (360, 495), hay dos manchas calientes con la misma forma que las personas anotadas en
    0050. Siguen ahí en los fotogramas 0112 a 0116, sin caja.
  - FHL 0134 no tiene ninguna caja entre 0073 y 0141.
  - En 0250 a 0252 sí se anotan personas cortadas por el borde (cajas de 8 × 2 y 9 × 5 px). Por eso la omisión parece
    una etiqueta que falta, y no un criterio.
- **Personas no detectadas:**
  - **FHL 0134:** las personas de 8 a 13 px bajo el dosel (0050, 0052 y 0259) no tienen predicción. Alrededor, la copa
    de los árboles está tan caliente como ellas. En 0153 hay una detectada, con 0.50.
  - **MtErie 0007:** se pierde la persona más lejana y en parte tapada por un tronco (0007, 0017 y 0079), aunque se ve
    en las dos cámaras.
- **Grupos:** en 0119 hay dos personas que caminan juntas. El modelo pone una sola caja para las dos: acierta una y
  pierde la otra.
- **Falsos positivos típicos:**
  - En 0032, una mancha caliente en el borde izquierdo (un tronco al sol) es un FP, y la persona del sendero no se
    detecta.
  - En las 16 no hay ningún FP en las 7 imágenes de FHL 0134 sin persona.

**Los 84 FP de la validación completa** (`best.pt`, conf 0.25), revisados en un mosaico:

| Vuelo | FP | Solapan una persona con IoU 0.1–0.5 | Sin persona cerca, en el borde | Sin persona cerca |
|---|---:|---:|---:|---:|
| MtErie 0007 | 50 | 18 | 14 | 18 |
| FHL 0134 | 34 | 1 | 2 | 31 |

- **MtErie 0007:**
  - **Solapan una persona (18):** son personas reales con la caja corrida o una caja para dos personas. Con 0.5, 5 de
    los 8 FP son de este tipo.
  - **Sin persona cerca (18):** casi todos son **troncos al sol**, que en la térmica salen como franjas claras
    verticales (de 11 × 34 a 13 × 66 px), más algunas manchas en el suelo.
- **FHL 0134:** 29 de los 31 sin persona cerca son 3 objetos que aparecen en varios fotogramas seguidos:
  - un objeto alargado (13–14 × 24–28 px), caliente y también claro en la RGB, en 0053–0076 (16 FP);
  - otro en 0222–0226 (5 FP);
  - ramas secas en 0266–0272 (8 FP).
  - Parecen madera muerta al sol. En el de 0053–0076 no se puede descartar a ojo que sea una persona.
- **El único FP de FHL 0134 que solapa una persona** (0266) es una caja de 12 × 18 sobre una persona anotada de 9 × 11,
  con IoU 0.46. Con personas de 10 px, correrse 2 px en x y en y ya deja el IoU en 0.47.

---

## A6. Integridad de los datasets

- **Cómo se comprobó:** se pasó `verify_image_label` de Ultralytics (la misma función que usa al cargar) por cada
  imagen de entrenamiento y validación de los tres datasets, sin escribir cachés.
- **Las cachés existentes:** se compararon con el hash que calcula Ultralytics, y están al día.

| Dataset | Split | Imágenes (esperadas) | Cajas (esperadas) | Etiquetas encontradas | Sin etiqueta | Vacías (sin persona) | Corruptas | Avisos | Caché al día |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| fusion | train | 3 247 (3 247) | 9 340 (9 340) | 3 247 | 0 | 186 | 0 | 0 | sí |
| fusion | val | 442 (442) | 500 (500) | 442 | 0 | 137 | 0 | 0 | sí |
| rgb | train | 3 247 (3 247) | 9 340 (9 340) | 3 247 | 0 | 186 | 0 | 0 | sí |
| rgb | val | 442 (442) | 500 (500) | 442 | 0 | 137 | 0 | 0 | sí |
| termico | train | 3 247 (3 247) | 9 340 (9 340) | 3 247 | 0 | 186 | 0 | 0 | sí |
| termico | val | 442 (442) | 500 (500) | 442 | 0 | 137 | 0 | 0 | sí |

- **Avisos:**
  - 0 avisos de `verify_image_label`: ninguna etiqueta corrupta, ninguna repetida (Ultralytics avisa "duplicate labels
    removed") y ninguna imagen sin etiqueta;
  - 0 mensajes en las cachés.
- **Sin persona:** 186 imágenes de entrenamiento y 137 de validación tienen el `.txt` vacío. Ultralytics las toma como
  fondo.
- **Train, val y test no comparten ningún archivo:**
  - 0 nombres repetidos entre splits, en los tres datasets;
  - los tres datasets reparten igual las mismas imágenes;
  - 0 imágenes originales de WiSARD en dos splits;
  - 0 contenidos iguales (md5) entre las 4 617 térmicas y entre las 4 617 RGB alineadas, ni siquiera dentro de un mismo
    split.
  - Por split: 3 247 / 442 / 928.

---

## B. Experimentos cortos (solo térmica)

**Configuración común:**
- YOLO26s desde `yolo26s.pt`, solo térmica (el gris repetido en 3 canales), seed 0, 30 épocas, lote 16;
- lo demás, igual que la Tabla 8: imgsz 640, `hsv_h=hsv_s=hsv_v=0`, 4 procesos de lectura y
  `optimizer=auto` (AdamW, lr0 0.002);
- con `close_mosaic=10` por omisión, las últimas 10 épocas van sin mosaico.
- Corren con `scripts/entrenar.py` y `configs/diagnostico.yaml`, con las mismas comprobaciones de aplicaciones, potencia
  y plan de energía.

**B1: los vuelos.** Son **6, no 7.** De los 7 vuelos que usamos, los que no son FHL 0405 son Baker, MtErie 0003, 0005 y
0007, y FHL 0134 y 0401. Son los 3 689 pares de entrenamiento y validación.

**B1: el reparto.**
- Se reparten al azar por fotograma, 60/20/20 (seed 0, `numpy.random.default_rng(0).permutation`).
- El dataset (enlaces duros a las mismas imágenes y etiquetas de `data/datasets/termico`) y el reparto están en
  `runs/diagnostico/datasets/b1_termico_aleatoria/`, con `reparto.csv`.

| Vuelo | train | val | test |
|---|---:|---:|---:|
| Baker | 1 200 | 378 | 393 |
| FHL 0134 | 142 | 68 | 63 |
| FHL 0401 | 467 | 156 | 160 |
| MtErie 0003 | 145 | 49 | 42 |
| MtErie 0005 | 159 | 50 | 48 |
| MtErie 0007 | 100 | 37 | 32 |
| **Imágenes** | **2 213** | **738** | **738** |
| **Cajas** | **5 979** | **1 928** | **1 933** |

**Tiempos estimados** (de `termico_tiempo_3ep`: 39 s de entrenamiento y 3 s de validación por época, con 3 247 y 442
imágenes):

| Experimento | Estimado |
|---|---|
| B1 | ≈ 19 min |
| B2 | ≈ 23 min |
| B3 | ≈ 1.5 a 2 h. El lote 16 a 1280 casi seguro no entra en 8 GB: a 640 ya pide 4.4 GB, y a 1280 serían unos 17 GB. Habría que bajarlo, y eso cambia la configuración. **No se corrió: espera confirmación.** |

**Comprobaciones antes de entrenar:**
- **Primer intento de B1 (09:16): falló.** La potencia dio 89.1 W de mediana (de 82.6 a 92.7 W), y la regla pide 90 W
  o más. La laptop estaba enchufada, en Performance y con las aplicaciones cerradas. No se entrenó y se avisó.
- **Con tu autorización, se reintentó** hasta 3 veces por corrida, cada 5 min, como `noche.ps1`. Pasaron a la primera:
  - **B1 (09:17):** 98.5 W, de 95.6 a 99.3 W;
  - **B2 (09:35):** 96.0 W, de 92.5 a 98.1 W.
- El registro completo está en `runs/diagnostico/b_salida.log`.

| Corrida | Duración | Límite al entrenar (mediana) | Pico de memoria GPU | Pico de RAM | Lote final | Optimizador |
|---|---:|---:|---:|---:|---:|---|
| B1 `b1_termico_aleatoria_30ep` | 16.5 min (991.6 s) | 86.7 W | 5 339 MiB | 99.6 % | 16 | AdamW, lr0 0.002 |
| B2 `b2_termico_vuelo_30ep` | 21.9 min (1 315.3 s) | 88.0 W | 5 287 MiB | 99.9 % | 16 | AdamW, lr0 0.002 |

### Resultados de B1 y B2

- **Cómo se evaluó:** `model.val` del `best.pt` de cada corrida, con conf 0.001 e imgsz 640 (`evaluacion.json` de
  cada corrida).
- **Con qué split se eligió el `best.pt`:** en B1, con su validación aleatoria, así que su prueba aleatoria no
  intervino. En B2, con nuestra validación, que es la misma donde se mide.

| Experimento | Partición | Evaluado en | Época del best.pt | mAP@0.5 | mAP@0.5:0.95 | Precisión | Recall | mAP@0.5 de la época 30 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| B1 | Al azar por fotograma, 60/20/20 | su prueba aleatoria (738 imágenes, 1 933 personas) | 30 | **0.9853** | 0.7531 | 0.981 | 0.959 | — |
| B1 | Al azar por fotograma, 60/20/20 | su validación aleatoria (738, 1 928) | 30 | 0.9827 | 0.7640 | 0.984 | 0.962 | 0.9832 |
| B2 | Por vuelo (la nuestra) | nuestra validación (442, 500) | 3 | **0.3282** | 0.1581 | 0.411 | 0.410 | 0.1886 |

**Curvas de validación** (mAP@0.5 por época, de `results.csv`):

| Época | 1 | 2 | 5 | 10 | 15 | 20 | 25 | 30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1 | 0.857 | 0.885 | 0.919 | 0.963 | 0.979 | 0.979 | 0.983 | 0.983 |
| B2 | 0.212 | 0.204 | 0.210 | 0.266 | 0.216 | 0.158 | 0.205 | 0.189 |

**Por vuelo:**
- `model.val` del mismo `best.pt` sobre cada vuelo (`por_vuelo.csv` de cada corrida).
- **"Con vecino de train":** fracción de los fotogramas del split que tienen uno de entrenamiento del mismo vuelo a 1
  posición, o a 2 o menos. Dos fotogramas a 1 posición son casi la misma imagen.

| Experimento | Split | Vuelo | Imágenes | Personas | mAP@0.5 | mAP@0.5:0.95 | Recall | Con vecino de train a 1 | A 2 o menos |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| B1 | prueba | Baker | 393 | 1 031 | 0.9945 | 0.8322 | 0.983 | 0.830 | 0.969 |
| B1 | prueba | FHL 0401 | 160 | 546 | 0.9735 | 0.6960 | 0.947 | 0.812 | 0.956 |
| B1 | prueba | MtErie 0003 | 42 | 162 | 0.9756 | 0.5287 | 0.933 | 0.833 | 0.976 |
| B1 | prueba | MtErie 0005 | 48 | 91 | 0.9641 | 0.7074 | 0.956 | 0.771 | 1.000 |
| B1 | prueba | **FHL 0134** | 63 | 52 | **0.9375** | 0.5535 | 0.904 | 0.857 | 0.968 |
| B1 | prueba | **MtErie 0007** | 32 | 51 | **0.8573** | 0.4591 | 0.843 | 0.750 | 1.000 |
| B2 | validación | **FHL 0134** | 273 | 211 | **0.3364** | 0.1507 | 0.560 | — | — |
| B2 | validación | **MtErie 0007** | 169 | 289 | **0.3675** | 0.1886 | 0.322 | — | — |

- **El vecino de entrenamiento:** en B1, el 82.1 % de los 738 fotogramas de su prueba tiene uno de entrenamiento a 1
  posición, y el 97.0 % a 2 o menos (máximo 4).
- B1 en su validación aleatoria, por vuelo, está en `runs/diagnostico/b1_termico_aleatoria_30ep/por_vuelo.csv`.

**Lo que se ve:**
- **El código está bien.** Con la misma receta que nuestra solo térmica y con menos imágenes de entrenamiento (2 213
  contra 3 247), el reparto al azar por fotograma da **0.985**, del orden del 0.977 de WiSARD.
- **Con el reparto por vuelo, la misma receta da 0.328.**
- **Las personas de 11 px de FHL 0134 sí se detectan** cuando hay fotogramas vecinos del mismo vuelo en entrenamiento:
  0.938 en B1, contra 0.336 en B2. El tamaño por sí solo no explica el resultado.
- **B2 es la primera medida de solo térmica en nuestra partición,** pero no reemplaza a `termico_100ep`: son 30 épocas
  en vez de 100. Aun así:
  - **FHL 0134:** solo térmica da 0.336 y la fusión (`best.pt`, época 8) da 0.083;
  - **MtErie 0007:** al revés, 0.368 contra 0.600.
  - No es una comparación en igualdad de condiciones (30 contra 100 épocas, `best.pt` de las épocas 3 y 8, una sola
    semilla). Se anota como algo a mirar en la fase 6, no como resultado.

### B3

**No se corrió.** Espera tu confirmación, y además hay que decidir el lote, porque el 16 no entra a 1280.

---

## Resumen

| Experimento | Partición | Resolución | mAP@0.5 | Recall |
|---|---|---:|---:|---:|
| Fusión, fase 5b (`best.pt`, época 8, 100 épocas) | Por vuelo: nuestra validación | 640 | 0.3749 | 0.370 |
| … solo FHL 0134 | Por vuelo | 640 | 0.0825 | 0.166 |
| … solo MtErie 0007 | Por vuelo | 640 | 0.6004 | 0.522 |
| B1: solo térmica, 30 épocas (`best.pt`, época 30) | Al azar por fotograma: su prueba | 640 | **0.9853** | 0.959 |
| B2: solo térmica, 30 épocas (`best.pt`, época 3) | Por vuelo: nuestra validación | 640 | **0.3282** | 0.410 |
| B3: solo térmica, 30 épocas | Por vuelo | 1280 | no se corrió | — |
| WiSARD, YOLOv5, térmica (dato citado, no medido aquí) | el del artículo | — | 0.977 | — |

- Las métricas son las de `model.val` de Ultralytics, con conf 0.001.
- El recall es el de Ultralytics, en su punto de F1 máximo.

**Causas, ordenadas según cuánto explican la diferencia:**

1. **El protocolo de partición explica casi toda la diferencia.**
   - Con la misma receta, solo térmica da **0.985** con el reparto al azar por fotograma (B1) y **0.328** con el
     reparto por vuelo (B2): 0.657 de diferencia. Entre 0.374 y 0.977 hay 0.603.
   - Con el reparto al azar, el 82.1 % de los fotogramas de prueba tiene un fotograma casi igual (±1 posición) en
     entrenamiento.
2. **Los vuelos de validación son de un tipo de escena que no está en entrenamiento.**
   - Con la misma receta, FHL 0134 da 0.938 si sus fotogramas vecinos están en entrenamiento (B1) y 0.336 si no
     (B2). MtErie 0007 da 0.857 contra 0.368.
   - En validación hay una vista cenital sobre un dosel denso y la vista desde dentro del bosque. Entrenamiento está
     dominado por Baker, en la nieve, con el 55.5 % de las personas.
3. **Las personas de FHL 0134 son diminutas, y casi no hay así en entrenamiento.**
   - Tienen 11 px de mediana: el 54.5 % de FHL 0134 mide menos de 12 px, contra el 1.9 % de entrenamiento.
   - Con la fusión, el mAP@0.5 es de 0.102 entre 8 y 12 px y de 0.621 de 32 px para arriba.
   - FHL 0134 aporta el 42 % de las personas y el 62 % de las imágenes de validación. Ahí la fusión da 0.083, contra
     0.600 en MtErie 0007.
   - El tamaño importa sobre todo junto con la causa 2: con fotogramas vecinos en entrenamiento, las mismas personas
     de 11 px dan 0.938.
4. **Las métricas llegan a su máximo muy pronto y después bajan.**
   - En la fusión, el `best.pt` es de la época 8 (0.374). El máximo de mAP@0.5 es de la época 27 (0.395), pero esos
     pesos no se guardaron. En la época 100 baja a 0.245.
   - En B2, el `best.pt` es de la época 3 (0.328), y en la época 30 baja a 0.189.
   - Entre el `best.pt` y el máximo de la fusión hay 0.021 (0.374 contra 0.395). Cambia poco el valor que se reporta y
     no explica la distancia con la literatura.
5. **La fusión en FHL 0134, solo como indicio.** Ahí solo térmica (B2) da 0.336 y la fusión 0.083. Falta compararlas
   en igualdad de condiciones, porque B2 tiene 30 épocas y la fusión 100.
6. **Las etiquetas y la medida pesan poco.**
   - Hay alguna persona sin caja, como dos en el borde de FHL 0134 en los fotogramas 0112 a 0116.
   - Con IoU 0.5 en cajas de 10 px, correrse 2 px ya deja fuera una detección, pero eso explica solo 1 de los 34 FP
     de FHL 0134.

**Lo que se descartó:**
- **Errores de código o de datos:** A6 dio 0 avisos, 0 corruptas, 0 cajas repetidas y 0 archivos compartidos entre
  splits. Los conteos son exactos (3 247 / 9 340 y 442 / 500), y las cajas caen bien sobre las personas.
- **La cantidad de datos, como causa principal:** B1 entrena con menos imágenes que B2 (2 213 contra 3 247) y llega a
  0.985. Igual queda el dato de que usamos el 13.5 % de las 24 084 térmicas anotadas de WiSARD (A1).

---

## Archivos de apoyo

**Qué es esta carpeta:**
- `reports/diagnostico/` es una copia de las salidas livianas de `runs/diagnostico/`, porque `runs/` no va a git.
- La genera `scripts/diagnostico.py --parte copiar`, con la sección `copiar` de `configs/diagnostico.yaml`.
- No se suben los pesos (`*.pt`), los datasets de enlaces duros ni las imágenes de `data/`, que por la regla del
  proyecto no va a GitHub.
- Las corridas de la fase 5b (fusión) están en `reports/fase5b/fusion_100ep/`.

| Carpeta | Qué hay |
|---|---|
| `a1/` | `inventario.csv` (las 80 carpetas), `termicas_fuera.csv` (una fila por térmica anotada fuera de los 4 617, con el motivo), `tablas.md` y `resumen.json` |
| `a2/` | `estado.json` y `results.csv` de las dos corridas de solo RGB cortadas |
| `a3/` | `cajas.csv` (una fila por persona de entrenamiento y validación, con ancho, alto, lado mayor y tramo) y `tablas.md` |
| `a4/` | `val.csv`, `tramos.csv` y `detectadas.csv`; predicciones de `model.val` (`fusion_{best,last}/todas/predictions.json`) y de `predict` (`predict_fusion_*_conf*.json`); `tablas.md` |
| `a5/` | `hoja.png` (16 pares: térmica y RGB alineada; anotadas en verde, predicciones en rojo) y `hoja.csv` |
| `a5/revision/` | Imágenes de la revisión a ojo, hechas fuera del script: `zoom_*.png` (ampliaciones de la hoja), `fp_0007.png` y `fp_0134.png` (los 84 FP a conf 0.25), `sospechas.png` y `fhl0134_112_116.png` (manchas sin caja en FHL 0134), y `vuelos.png` (2 fotogramas por vuelo) |
| `a6/` | `conteos.csv`, `avisos.csv`, `choques.csv` y `resumen.json` |
| `datasets/b1_termico_aleatoria/` | `b1.yaml` y `reparto.csv` (split de cada fotograma de B1) |
| `b1_termico_aleatoria_30ep/` y `b2_termico_vuelo_30ep/` | Todo lo de la corrida menos los pesos: `args.yaml`, `results.csv`, curvas, lotes de entrenamiento y validación, `resumen.json`, `monitor.csv`, `evaluacion.json` y `por_vuelo.csv` |
| `*.log` | Salida de A4 (`a4_salida.log`), de las corridas de B con las comprobaciones (`b_salida.log`) y de la evaluación por vuelo |
