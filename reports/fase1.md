# Fase 1. Pares RGB-térmicos

Fecha: 2026-10-30, actualizado el 2026-10-31 (corte de Baker en 2031, exclusiones de la fase 2 y desfases de la regla relativa) · Dataset: `C:\Users\User\Downloads\WiSARDv1` (solo lectura; no se modificó nada).

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
- **Exclusiones** (en `configs/fase1.yaml`, con su motivo):
  - Baker VIS_1/IR_1, posiciones 2031 a 2179: en la térmica hay personas sin caja (ver la revisión más abajo).
  - Carnation 0023/0024 completo (posiciones 0 a 738), decidido el 2026-10-31 al empezar la fase 2: la RGB tiene
    zoom variable y cubre cerca del 11 % de la térmica, con un posible desfase en la posición 470. Se excluye de los
    tres modelos (ver `reports/fase2.md`).
  - Despegue de Baker (0 a 15), cambio de zoom de FHL 0401 (0 a 10) y aterrizaje de FHL 0401 (857 a 895),
    encontrados con el barrido visual de la fase 2 y confirmados el 2026-10-31 (ver `reports/fase2.md`).
  - Desfases entre cámaras (la térmica muestra otro instante) medidos con la distancia entre centros de las personas
    tras la alineación de la fase 2: MtErie 0005 (160 a 162) y Baker (620 a 626), en giros rápidos. El inicio de
    MtErie 0003 (0 a 11) se excluyó y se devolvió el mismo día: el desfase venía de la homografía.
  - Desfases de la fase 2 (2026-10-31), 155 pares:
    - 135 de la regla relativa: 41 tramos (133 pares) y 2 pares "solo térmica" vecinos. 4 tramos salen sin revisión y
      37 tras revisarlos a ojo; otros 4 se revisaron y se conservan.
    - 2 de FHL 0401 371–372.
    - 18 de la extensión de los tramos por el fondo corrido más de 20 px.

    Están en `configs/exclusiones_desfase.yaml`, que se genera desde `configs/revision_desfases.yaml` y que
    `configs/fase1.yaml` lee en `exclusiones_adicionales` (ver `reports/fase2.md`).

## Verificación de totales

| | Obtenido | Esperado | Diferencia |
|---|---:|---:|---:|
| Pares (todas las parejas de carpetas) | 14 839 | 14 839 | 0 |
| Pares con las dos imágenes anotadas | 5 739 | 5 739 | 0 |
| Pares anotados tras la exclusión de Baker | 5 590 | 5 590 | 0 |
| Pares con persona solo en la térmica (tras Baker) | 476 | 476 | 0 |
| Pares anotados tras excluir Carnation | 4 851 | 4 851 | 0 |
| Pares anotados tras excluir despegues, aterrizajes y cambios de zoom (aterrizaje desde 878) | 4 806 | 4 806 | 0 |
| Pares anotados tras adelantar el aterrizaje a 857 y excluir los desfases de los giros | 4 775 | 4 775 | 0 |
| Pares anotados tras excluir los desfases de la regla relativa (revisados a ojo) | 4 640 | 4 640 | 0 |
| Pares anotados tras excluir FHL 0401 371–372 y la extensión por el fondo | **4 620** | 4 620 | 0 |
| Pares con persona solo en la térmica (tras todas las exclusiones) | **471** | | |

- 80 carpetas, 17 parejas de carpetas. **8 de ellas están anotadas** (4 sitios); las otras 9 tienen al menos una de
  las dos carpetas sin `.txt`, y aportan los 9 100 pares sin anotar.
- Las exclusiones afectan a 1 119 pares:
  - 149 del final de Baker y 739 de Carnation;
  - 16 del despegue de Baker y 50 de FHL 0401 (11 del cambio de zoom y 39 del aterrizaje);
  - 10 de desfases en giros (MtErie 0005 3, Baker 7);
  - 155 de los desfases de la fase 2 (MtErie 0003 28, MtErie 0005 11, MtErie 0007 3, FHL 0401 63, FHL 0405 13,
    Baker 37).
- No hay líneas de etiqueta mal formadas (5 campos, clase 0) en ninguna de las 17 parejas.

## Pares por vuelo (Tabla 9)

Archivo: `reports/tabla_pares_por_vuelo.csv`. Solo los vuelos con pares anotados. "Solo térmica" = al menos una caja
en la térmica y ninguna en la RGB, contado sobre los pares anotados no excluidos.

| Vuelo | Sitio | Pares anotados | Excluidos | Anotados tras las exclusiones | Solo térmica |
|---|---|---:|---:|---:|---:|
| MtErie 0003/0004 | MtErie | 264 | 28 | 236 | 0 |
| MtErie 0005/0006 | MtErie | 272 | 14 | 258 | 8 |
| MtErie 0007/0008 | MtErie | 172 | 3 | 169 | 7 |
| Carnation 0023/0024 | Carnation | 739 | **739** | 0 | 0 |
| FHL 0134/0135 | FHL | 273 | 0 | 273 | 61 |
| FHL 0401/0402 | FHL | 896 | 113 | 783 | 0 |
| FHL 0405/0406 | FHL | 943 | 13 | 930 | **394** |
| Baker VIS_1/IR_1 | Baker | 2 180 | 209 | 1 971 | 1 |
| **Total** | | **5 739** | **1 119** | **4 620** | **471** |

En estos 8 vuelos todos los pares están anotados (pares = pares anotados). Carnation queda en la tabla con todos sus
pares excluidos. FHL reúne 455 de los 471 pares "solo térmica" (97 %), 394 de ellos en FHL 0405/0406. Los 3 pares
"solo térmica" de Carnation salieron con su exclusión, y con la regla de desfase salieron 2 más (MtErie 0007 53 y
FHL 0401 768).

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
| `excluido`, `motivo_exclusion` | Tramos excluidos y su motivo (`configs/fase1.yaml`) |

## Revisión del corte de Baker

El análisis anterior excluía desde la posición 2051, donde la térmica pasa a 0 cajas. Revisé a mano las posiciones
2030 a 2060 (imágenes lado a lado en `reports/baker_corte/`, generadas con `scripts/fase1_baker_corte.py`; las
impares 2031 a 2039 se revisaron aparte):

| Posición | Térmica | ¿Persona visible sin caja? |
|---|---|---|
| 2030 | 2 cajas (persona de azul y persona sentada junto al trineo) | No |
| **2031** | 1 caja (solo la de azul) | **Sí**: la persona sentada se ve claramente (gorro, mascarilla, torso) |
| 2032 a 2037 | 1 caja | Dudoso: la persona sentada está en el borde derecho, solo se ven fragmentos |
| 2038 a 2050 | 1 caja | Sí; en 2044 está de cuerpo entero dentro del encuadre |
| 2051 en adelante | 0 cajas | Sí, las dos personas |

Las anotaciones térmicas se van perdiendo antes del final del vídeo: la caja de la persona sentada desaparece entre
2030 y 2031 y no vuelve, y la de la persona de azul dura hasta 2050. **El corte se adelantó a 2031** (confirmado el
2026-10-31): se excluyen 149 pares en vez de 129 y quedan 5 590 en vez de 5 610. Los 20 pares que salen tienen 2 o 3
cajas en la RGB y 1 en la térmica, así que la categoría "solo térmica" no cambia (476).

La zona amarilla de las imágenes (lo que ve la térmica según el ajuste de etiquetas, x de 0.18 a 0.84) se queda corta
por la derecha en Baker: la persona sentada está a la derecha de 0.84 en la RGB y aun así aparece en la térmica. La
alineación de la fase 2 debe corregirlo.

## Observaciones

- En Carnation 0023/0024 la RGB tiene zoom: sus 3 pares "solo térmica" eran probablemente personas fuera del encuadre
  RGB, no ocultas. El vuelo quedó excluido en la fase 2.
