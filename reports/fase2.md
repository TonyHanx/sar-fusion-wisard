# Fase 2. Alineación de la RGB con la térmica (en curso)

Fecha: 2026-10-31 · Estado: exclusiones aplicadas (**4 806 pares**). En curso: homografía automática de cada vuelo
a partir de los centros de las cajas, validada con los puntos manuales de MtErie 0003. Después siguen los TIFF.

## Decisiones tomadas el 2026-10-31

- **Carnation 0023/0024 se excluye de los tres modelos.** La RGB tiene zoom variable, cubre cerca del 11 % de la
  térmica y hay un posible desfase en la posición 470 (imágenes en `reports/alineacion/lado_a_lado/`). Está en
  `configs/fase1.yaml` como exclusión con su motivo. Quedan **4 851 pares** utilizables (473 con persona solo en la
  térmica) en 7 parejas de vuelos de 3 sitios.
- **Despegues, aterrizajes y cambios de zoom se excluyen**, con los límites confirmados a mano (ver abajo). Quedan
  **4 806 pares** (473 con persona solo en la térmica). Tabla por vuelo actualizada en
  `reports/tabla_pares_por_vuelo.csv` y `reports/fase1.md`.
- **Alineación automática:** en vez de marcar puntos en todos los vuelos, la homografía de cada vuelo se calcula con
  los centros de las cajas de los pares que tienen persona en las dos imágenes (RANSAC, seed=0), con la mitad de
  esos pares; la otra mitad mide la distancia entre centros. Se valida con los puntos manuales de MtErie 0003. Los
  vuelos con pocos pares útiles o error grande se marcan a mano.
- **TIFF de 4 canales con compresión deflate** (zlib con predictor). Orden de los canales en el archivo: B, G, R,
  térmica. Ultralytics lee el TIFF con OpenCV, que devuelve los canales en el orden del archivo, y con 4 canales no
  invierte BGR a RGB; guardado así, el modelo recibe R, G, B, térmica, igual que con 3 canales.
- **Las 46 cajas duplicadas** se eliminan en la Fase 3a, antes de crear los yaml de entrenamiento, y se anota cuántas
  eran por vuelo.

## Cómo se buscaron los despegues, aterrizajes y cambios de zoom

Primero se probaron tres métodos automáticos:

| Método | Script | Resultado |
|---|---|---|
| Escala RGB/térmica por fotograma, por correlación de bordes | `fase2_escala_por_fotograma.py` | Encuentra bien FHL 0401 0–10, pero marca 76 tramos, casi todos falsos (nieve y bosque sin bordes comunes) |
| Zoom relativo entre fotogramas consecutivos (ORB en cada cámara) | `fase2_zoom_temporal.py` | El acumulado deriva; los 6 saltos más grandes revisados a ojo (MtErie 0005 en 96 y 198, FHL 0405 en 222 y 916, Baker en 50 y 68) son falsas alarmas: la RGB y la térmica coinciden antes y después |
| Separación entre cajas de personas / residuo con la franja nominal | (análisis aparte) | Necesita 2 personas o más; pocos tramos y ruidosos |

Ninguno sirve solo. Los límites salen del **barrido visual** (`scripts/fase2_barrido.py`): un fotograma cada 10
posiciones en todos los pares anotados de los 7 vuelos (504 fotogramas, 25 hojas en `reports/alineacion/barrido/`,
8.4 MB; los excluidos llevan el rótulo en rojo). Cada celda
tiene la RGB recortada a la franja que ve la térmica, llevada al tamaño de la térmica, junto a la térmica. Si el zoom
cambia o el dron está en el suelo, las dos mitades dejan de coincidir. Los bordes se revisaron después fotograma a
fotograma.

## Tramos excluidos (confirmados el 2026-10-31)

Imágenes de cada borde (fotograma antes, borde y después; RGB completa con la franja en amarillo, RGB recortada y
térmica) en `reports/alineacion/bordes_tramos/`. Los tramos están en `configs/fase1.yaml` (exclusiones) y en
`bordes_tramos.tramos` de `configs/fase2.yaml` (imágenes).

| Vuelo | Posiciones | Tipo | Pares | Cajas térmicas | Evidencia |
|---|---|---|---:|---:|---|
| Baker VIS_1/IR_1 | 0 a 15 | Despegue | 16 | 0 | 0–13: dron en el suelo (su estructura tapa la parte baja de la RGB); 14–15: despegando a ras de la nieve; 16: ya en el aire, con personas en las dos imágenes |
| FHL 0401/0402 | 0 a 10 | Cambio de zoom | 11 | 47 | En 0–10 las personas salen cerca de 1.6 veces más grandes en la RGB recortada que en la térmica; desde 11 coinciden |
| FHL 0401/0402 | 878 a 895 | Aterrizaje | 18 | 28 | El dron baja hasta el pasto; desde 878 las personas de las dos cámaras se separan hasta unos 35 px (a resolución térmica). El vídeo termina en 895 sin que se pose |

Salen 45 pares y quedan **4 806**. Ninguno de los 45 es "solo térmica", así que esa categoría queda en 473. Para el
aterrizaje propuse empezar en 885 (el pasto cercano ya llena la mitad inferior de la imagen); se adelantó a 878
porque desde ahí las personas se separan entre cámaras.

## Otras cosas que se vieron en el barrido (no se excluyen por ahora)

- **El dron sube o baja, pero las dos cámaras coinciden:** MtErie 0003 0–10 (sube), MtErie 0005 final y FHL 0405
  final (bajan). No son despegues ni aterrizajes: no se ve el suelo de cerca y la alineación se mantiene.
- **Cámara mirando la nieve de cerca sin personas:** Baker 525–619. Coincide; se conserva.
- **Cámara levantada hacia el horizonte:** FHL 0134 cerca de 22–35, FHL 0405 270–280. Coincide; se conserva.
- **Desfase en giros rápidos:** en MtErie 0005 160–161 y Baker 620 y 625 la térmica muestra un instante distinto del
  de la RGB (la RGB sale movida y las personas no caen en el mismo sitio). No es despegue, aterrizaje ni zoom. Se
  medirá con la distancia entre centros y se mostrará con las superposiciones.

## Puntos de control manuales (solo para validar y para los vuelos que fallen)

`scripts/marcar_puntos.py` sirve para marcar puntos a mano en tres fotogramas por vuelo, preconfigurados en
`marcado.fotogramas` de `configs/fase2.yaml` (parte estable, con detalles visibles en las dos cámaras). Hoy se usa
para validar el método automático con MtErie 0003, que tiene puntos marcados el 2026-10-31 en los fotogramas 0, 132
y 263 (5, 8 y 6 puntos), y queda para los vuelos en los que el método automático falle.

| Vuelo | Inicio | Mitad | Final |
|---|---:|---:|---:|
| MtErie 0003/0004 | 0 | 132 | 263 |
| MtErie 0005/0006 | 30 | 130 | 260 |
| MtErie 0007/0008 | 10 | 90 | 160 |
| FHL 0134/0135 | 10 | 150 | 262 |
| FHL 0401/0402 | 20 | 450 | 860 |
| FHL 0405/0406 | 30 | 440 | 930 |
| Baker VIS_1/IR_1 | 80 | 1040 | 1990 |

## Espacio en disco previsto

Con los 4 806 pares: RGB alineada en PNG (0.74 MB por par), térmica en gris en PNG (0.18 MB) y TIFF de 4 canales con
deflate (0.92 MB). Son unos **8.2 GiB** en total. Es una estimación hecha con muestras de cada vuelo. Libres: 105.7 GB.

## Pendiente

1. Homografía automática por vuelo con los centros de las cajas; distancia entre centros en la otra mitad; validación
   con los puntos manuales de MtErie 0003; MtErie 0007 (cámara de frente bajo el dosel) por separado; giros rápidos de
   MtErie 0005 160–161 y Baker 620 y 625.
2. Alinear y escribir los PNG y TIFF por partes; 10 superposiciones por vuelo.
