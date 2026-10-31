# Fase 1. Pares RGB-térmicos

Fecha: 2026-10-30 · Dataset: `C:\Users\User\Downloads\WiSARDv1` (solo lectura; no se modificó nada).

Para regenerar:

```
.venv\Scripts\python.exe scripts\fase1_pares.py --config configs\fase1.yaml --rutas configs\rutas.yaml
```

Tarda unos 2 minutos: busca el `.txt` de cada uno de los 29 678 fotogramas emparejados (2 × 14 839). Solo lee
etiquetas, no imágenes.

## Reglas aplicadas

- **Carpetas:** la VIS con número N va con la IR con número N+1 del mismo `fecha_sitio_dron`. El número es el sufijo de
  4 dígitos de la carpeta; en `220109_Baker` se toma del primer archivo (`DJI_0582` con `DJI_0583`).
- **Fotogramas:** por posición en orden natural, hasta la longitud mínima de las dos carpetas.
- **Etiquetas:** un `.txt` vacío es 0 cajas; una imagen sin `.txt` no está anotada. Las cajas se cuentan por líneas no
  vacías (los `.txt` de WiSARD no terminan en salto de línea, así que `wc -l` cuenta una caja de menos).
- **Exclusión:** Baker VIS_1/IR_1, posiciones 2051 a 2179 (en la térmica hay personas sin caja). Configurada en
  `configs/fase1.yaml`.

## Verificación de totales

| | Obtenido | Esperado | Diferencia |
|---|---:|---:|---:|
| Pares (todas las parejas de carpetas) | 14 839 | 14 839 | 0 |
| Pares con las dos imágenes anotadas | 5 739 | 5 739 | 0 |
| Pares anotados tras la exclusión | **5 610** | 5 610 | 0 |
| Pares con persona solo en la térmica | 476 | 476 | 0 |

- 80 carpetas, 17 parejas de carpetas. **8 de ellas están anotadas** (4 sitios); las otras 9 tienen al menos una de
  las dos carpetas sin `.txt`, y aportan los 9 100 pares sin anotar.
- La exclusión de Baker afecta a 129 pares.
- No hay líneas de etiqueta mal formadas (5 campos, clase 0) en ninguna de las 17 parejas.

## Pares por vuelo (Tabla 9)

Archivo: `reports/tabla_pares_por_vuelo.csv`. Solo los vuelos con pares anotados. "Solo térmica" = al menos una caja
en la térmica y ninguna en la RGB, contado sobre los pares anotados no excluidos.

| Vuelo | Sitio | Pares anotados | Excluidos | Anotados tras la exclusión | Solo térmica |
|---|---|---:|---:|---:|---:|
| MtErie 0003/0004 | MtErie | 264 | 0 | 264 | 0 |
| MtErie 0005/0006 | MtErie | 272 | 0 | 272 | 8 |
| MtErie 0007/0008 | MtErie | 172 | 0 | 172 | 8 |
| Carnation 0023/0024 | Carnation | 739 | 0 | 739 | 3 |
| FHL 0134/0135 | FHL | 273 | 0 | 273 | 61 |
| FHL 0401/0402 | FHL | 896 | 0 | 896 | 1 |
| FHL 0405/0406 | FHL | 943 | 0 | 943 | **394** |
| Baker VIS_1/IR_1 | Baker | 2 180 | 129 | 2 051 | 1 |
| **Total** | | **5 739** | **129** | **5 610** | **476** |

En estos 8 vuelos todos los pares están anotados (pares = pares anotados). FHL reúne 456 de los 476 pares "solo
térmica" (96 %), 394 de ellos en FHL 0405/0406.

## Comprobaciones adicionales

- **Emparejamiento por posición = por número de archivo.** En los 8 vuelos anotados, la diferencia entre el número de
  archivo térmico y el RGB es constante en toda la secuencia (+1 en MtErie 0003/0004, 0 en los demás).
- **Parejas con distinto número de fotogramas** (se descartan los sobrantes del final):
  - Anotadas: Carnation 0023/0024 (739 / 740), FHL 0401/0402 (897 / 896), FHL 0405/0406 (945 / 943).
  - Sin anotar: FHL 0126/0127 (1 006 / 1 008), FHL 0409/0410 (1 300 / 1 299), FHL 0564/0565 (983 / 982).

## `data/pares.csv`

Una fila por par (14 839 filas). No va a GitHub.

| Columna | Contenido |
|---|---|
| `vuelo` | Nombre de la carpeta RGB sin `_VIS` (p. ej. `210924_FHL_Enterprise_0405`) |
| `sitio`, `fecha` | Tomados del nombre de la carpeta |
| `posicion` | Índice del fotograma dentro de la pareja (desde 0, orden natural) |
| `carpeta_rgb`, `carpeta_termica` | Carpetas del dataset |
| `ruta_rgb`, `ruta_termica` | Ruta relativa a la raíz del dataset (`configs/rutas.yaml`) |
| `cajas_rgb`, `cajas_termica` | Número de cajas; vacío si la imagen no tiene `.txt` |
| `anotado` | `True` si las dos imágenes tienen `.txt` |
| `excluido`, `motivo_exclusion` | Tramo de Baker |

## Observaciones

- La posición 2050 de Baker (la última que se conserva) tiene 3 cajas en la RGB y 1 en la térmica. El corte en 2051
  viene del análisis anterior; no lo cambié.
- En Carnation 0023/0024 la RGB tiene zoom: sus 3 pares "solo térmica" son probablemente personas fuera del encuadre
  RGB, no ocultas.
