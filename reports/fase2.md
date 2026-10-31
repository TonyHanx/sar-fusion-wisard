# Fase 2. Alineación de la RGB con la térmica (en curso)

Fecha: 2026-10-31 · Estado: exclusiones aplicadas (**4 806 pares**). Alineación automática calculada; **esperando
decisiones** sobre el modelo (homografía o semejanza), la validación con puntos manuales y los desfases (ver
"Alineación automática"). Después siguen los TIFF.

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
  medirá con la distancia entre centros y se mostrará con las superposiciones (resultado más abajo).

## Alineación automática con los centros de las cajas (2026-10-31)

Script: `scripts/fase2_homografias_cajas.py` (configuración en `homografias_cajas` de `configs/fase2.yaml`). Salidas
en `configs/homografias_cajas.yaml` y `reports/alineacion/homografias_cajas/`.

Método: en cada vuelo, los pares con persona en la RGB y en la térmica se reparten al azar (seed=0) en dos mitades.
Con la de calibración se emparejan las personas de las dos imágenes (algoritmo húngaro sobre la distancia entre
centros, empezando por la franja nominal) y se estima la transformación con RANSAC (umbral 8 px, tres vueltas de
emparejar y estimar). Con la de evaluación se mide la distancia entre el centro de cada caja térmica y el de su caja
RGB llevada a la térmica, en px térmicos (640 × 512). Se ignoran las cajas cortadas por el borde de la térmica, y las
cajas repetidas cuentan una vez.

### Resultado por vuelo (homografía, pares de evaluación)

| Vuelo | Pares con persona en ambas | Pares evaluados | Personas | Media (px) | Mediana (px) | Máximo (px) | Las personas usadas cubren |
|---|---:|---:|---:|---:|---:|---:|---:|
| MtErie 0003 | 261 | 127 | 494 | 10.4 | 3.7 | 87 | 26 % |
| MtErie 0005 | 264 | 125 | 193 | 15.9 | 9.8 | 401 | 29 % |
| MtErie 0007 | 164 | 80 | 119 | 11.2 | 7.1 | 116 | 4 % |
| FHL 0134 | 75 | 36 | 66 | 1.8 | 1.3 | 9 | 1 % |
| FHL 0401 | 766 | 375 | 1 457 | 10.7 | 5.1 | 240 | 63 % |
| FHL 0405 | 400 | 196 | 258 | 7.7 | 3.8 | 306 | 42 % |
| Baker | 1 931 | 926 | 2 127 | 8.6 | 4.7 | 491 | 52 % |

La media la dominan los desfases de los giros rápidos (máximos de 100 a 490 px); la mediana describe mejor la
alineación del resto. Con la franja nominal, sin estimar nada, las medianas son 4.7, 11.0, 6.3, 3.8, 6.8, 5.6 y 5.8 px.

### Problema: la homografía completa se deforma donde las personas ocupan poco espacio

Una homografía tiene 8 grados de libertad. Cuando todas las personas usadas están en una zona pequeña de la imagen,
fuera de esa zona la transformación queda sin determinar. La tabla muestra la zona de la RGB que ve la térmica según
cada modelo (esquinas de la térmica llevadas a la RGB; la franja nominal es x 0.18–0.84, y 0.06–0.98):

| Vuelo | Homografía | Semejanza (escala, giro y traslación) | Mediana homografía / semejanza (px) |
|---|---|---|---:|
| MtErie 0003 | x 0.19–0.81, y 0.15–1.00 (trapecio) | x 0.19–0.84, y 0.05–0.98 | 3.7 / 4.3 |
| MtErie 0005 | x 0.17–0.79, y 0.06–0.96 (trapecio) | x 0.19–0.83, y 0.07–0.98 | 9.8 / 8.3 |
| MtErie 0007 | x −0.28–0.74, **y −1.22–0.95** | x 0.17–0.86, y 0.02–0.99 | 7.1 / 5.7 |
| FHL 0134 | **x 0.26–1.26, y −0.57–0.99** | x 0.19–0.83, y 0.06–0.97 | 1.3 / 1.5 |
| FHL 0401 | x 0.18–0.82, y 0.07–0.97 | x 0.19–0.83, y 0.06–0.98 | 5.1 / 4.9 |
| FHL 0405 | x 0.19–0.84, y 0.09–0.99 | x 0.18–0.84, y 0.05–0.98 | 3.8 / 4.8 |
| Baker | x 0.18–0.82, y 0.07–0.98 | x 0.18–0.83, y 0.06–0.98 | 4.7 / 4.6 |

En FHL 0134 y MtErie 0007 la homografía no tiene sentido físico: la RGB alineada sale como un trapecio torcido (ver
`superposiciones_210417_MtErie_Enterprise_0007.jpg`). La distancia de evaluación no lo detecta, porque las personas
de evaluación están en la misma zona que las de calibración. La semejanza da en los 7 vuelos un campo de visión casi
igual a la franja nominal, con medianas parecidas. Es lo que se espera de dos cámaras montadas juntas y mirando en la
misma dirección. El modelo afín da resultados intermedios (`comparacion_modelos.csv`). Además, el resultado de RANSAC
cambia algo si solo cambia el orden de los pares de calibración: la mediana varía hasta 2.3 px en MtErie 0005 con la
homografía y 1.4 px con la semejanza. Con seed=0 y el mismo orden, el resultado es reproducible.

### Validación con los puntos manuales de MtErie 0003

| | Todos (19) | Inicio, pos 0 (5) | Mitad, pos 132 (8) | Final, pos 263 (6) |
|---|---:|---:|---:|---:|
| Error medio, homografía (px) | 41.5 (máx. 262) | 99.8 | 9.3 | 36.0 |
| Error medio, semejanza (px) | 37.7 | 89.0 | 9.8 | 32.2 |
| Error medio, franja nominal (px) | 36.1 | 84.5 | 8.9 | 31.9 |

Los puntos de inicio y de final no son coherentes entre sí. Prueba: se quita un punto, se ajusta una semejanza con
los demás puntos del mismo fotograma y se mide dónde cae el punto quitado. En inicio queda a 72–286 px y en final a
28–59 px. En mitad queda a 5–14 px, salvo el punto 8 (33 px, en el borde inferior). El punto 1 de inicio está en la
RGB en x = 0.03, fuera de la zona que ve la térmica según los tres modelos. Además, en la posición 0 las personas de
las dos cámaras están separadas unos 30 px (el dron está subiendo; ver "Desfases en todo el vuelo"). Solo los puntos
de mitad sirven como referencia, y su propia coherencia (~10 px) es del mismo orden que el error de la alineación
automática. Imagen: `puntos_manuales_210417_MtErie_Enterprise_0003.jpg`.

### MtErie 0007

En todo el barrido (0 a 171) el dron va bajo el dosel con la cámara mirando de frente, no solo en 0, 86 y 171. Es un
bosque abierto de troncos delgados con helechos, y el dron avanza por un sendero. Hay 1 o 2 personas pequeñas y
lejanas, casi siempre en la parte baja o en el borde izquierdo. No hay despegue, aterrizaje ni cambio de zoom, y las
dos cámaras muestran la misma escena.

Error de alineación por separado (pares de evaluación): homografía media 11.2 px, mediana 7.1, máximo 116, 80 pares
(119 personas); semejanza 8.2 / 5.7 / 147. Por tercios del vuelo (homografía): 19.9 / 8.8 / 9.2 px. Mediana relativa
a la altura de la caja térmica: 0.14. Las personas cubren solo el 4 % de la térmica (siempre cerca de la línea del
sendero), y por eso la homografía se deforma.

### Giros rápidos (todos sus pares, distancia máxima por par con la homografía)

| Vuelo | Posiciones y distancia (px) |
|---|---|
| MtErie 0005 | 158: 4.5 · 159: 13.7 · **160: 170** · **161: 51** · **162: 39** · 163: 17 |
| Baker | 618–619: sin personas emparejadas (la persona de la RGB sale por arriba) · **620: 80** · **621: 60** · **622: 49** · **623: 57** · **624: 64** · **625: 60** · **626: 26** · 627: 2.6 |

En los dos casos la térmica muestra un instante distinto del de la RGB. En Baker todas las personas aparecen corridas
en la misma dirección mientras la cámara gira, y en 627 vuelven a coincidir. Imágenes: `revisar_*.jpg`.

### Desfases en todo el vuelo

Con la homografía de cada vuelo se midió la distancia en todos los pares con persona en ambas (las dos mitades).
383 de los 3 739 pares (10 %) tienen alguna persona a más de 25 px. Hay 70 tramos de 2 o más pares seguidos por encima
de 25 px (`desfases.csv`). Los que revisé a ojo son de tres tipos:

- **Desfase temporal con la cámara girando** (todas las personas corridas igual): por ejemplo, Baker 282–295 y
  620–626.
- **Personas que caminan cerca del dron, con desfase:** FHL 0401 857–877. Aquí la separación empieza en la 857
  (857: 26 px, 858: 32, 862 a 877: de 24 a 60). En 852–856 está entre 6 y 15 px. El aterrizaje excluido empieza en la
  878.
- **Error del modelo:** MtErie 0007 23–55, por la homografía deformada.

También aparece MtErie 0003 0–11 (el dron sube al empezar; de 28 a 40 px), que en el barrido parecía coincidir.

Este método no puede revisar los pares sin persona en la RGB, entre ellos los 473 "solo térmica".

## Puntos de control manuales (para validar y para los vuelos que fallen)

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

1. Decidir el modelo (homografía o semejanza), qué hacer con la validación manual de MtErie 0003 y con los desfases
   (incluidos el inicio del aterrizaje de FHL 0401 y el inicio de MtErie 0003). Volver a calcular con lo que se decida.
2. Alinear y escribir los PNG y TIFF por partes; 10 superposiciones por vuelo.
