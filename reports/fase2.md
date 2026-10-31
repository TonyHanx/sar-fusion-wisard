# Fase 2. Alineación de la RGB con la térmica (en curso)

Fecha: 2026-10-31 · Estado: modelo decidido (**semejanza por vuelo**). Regla de desfase relativa **aplicada con
revisión a ojo**: de 45 tramos se excluyen 41 (135 pares) y se conservan 4. Quedan **4 640 pares** (471 "solo
térmica"); en FHL 0405, 932. La semejanza se volvió a estimar con esos pares. Al hacerlo apareció un tramo nuevo
(FHL 0401 371–372) que está **sin aplicar**, a la espera de tu decisión. La validación con los puntos manuales de
FHL 0405 está pendiente: los marcas tú. Después siguen los TIFF.

## Decisiones tomadas el 2026-10-31

- **Carnation 0023/0024 se excluye de los tres modelos.** La RGB tiene zoom variable y cubre cerca del 11 % de la
  térmica. Además puede haber un desfase en la posición 470 (imágenes en `reports/alineacion/lado_a_lado/`).
- **Despegues, aterrizajes y cambios de zoom se excluyen**, con los límites confirmados a mano (ver abajo).
- **Modelo de alineación: semejanza por vuelo** (escala, giro y traslación; 4 grados de libertad), estimada con los
  centros de las cajas de personas, con RANSAC y seed=0. Se valida con puntos manuales. La homografía completa se
  descartó porque se deforma donde las personas ocupan poco espacio (ver "Por qué semejanza").
- **El aterrizaje de FHL 0401 empieza en la 857** (antes 878). Desde ahí las personas de las dos cámaras se separan
  más de 25 px, medido con la semejanza.
- **Desfases entre cámaras excluidos:** MtErie 0005 160–162 y Baker 620–626. **MtErie 0003 0–11 se devolvió**: los
  28–40 px que reporté venían de la homografía; con la semejanza las personas están a 7–21 px.
- **Regla de desfase relativa para todo el vuelo**, con radio de "cerca" de 3 alturas (confirmada). Reemplaza la de
  25 px. **Se aplica con la opción 2 acotada:** los tramos en que todas las personas (2 o más) se corren más de 1
  altura salen sin revisión. Los demás se revisan a ojo, mirando también si el fondo está corrido, y lo mismo todos los
  tramos de FHL 0405, MtErie 0005 y MtErie 0007 (ver "Regla de desfase").
- **MtErie 0007 se conserva e irá en la partición de validación.** Es un vuelo **bajo el dosel con la cámara de
  frente**, no hacia abajo como los demás.
- **Validación manual:** en MtErie 0003 se descartan los puntos de inicio y final, porque se marcaron con la térmica
  cortada. Se conservan los de mitad. La validación se completa con FHL 0405 (fotogramas 30, 440 y 930).
- **TIFF de 4 canales con compresión deflate** (zlib con predictor), con los canales en el orden B, G, R, térmica.
  Ultralytics lee el TIFF con OpenCV, que devuelve los canales en el orden del archivo. Con 4 canales no invierte BGR
  a RGB, así que el modelo recibe R, G, B, térmica, igual que con 3 canales.
- **Las 46 cajas duplicadas** se eliminan en la Fase 3a, antes de crear los yaml de entrenamiento. Se anota cuántas
  había en cada vuelo.

## Cómo se buscaron los despegues, aterrizajes y cambios de zoom

Primero se probaron tres métodos automáticos:

| Método | Script | Resultado |
|---|---|---|
| Escala RGB/térmica por fotograma, por correlación de bordes | `fase2_escala_por_fotograma.py` | Encuentra bien FHL 0401 0–10, pero marca 76 tramos, casi todos falsos (nieve y bosque sin bordes comunes) |
| Zoom relativo entre fotogramas consecutivos (ORB en cada cámara) | `fase2_zoom_temporal.py` | El acumulado deriva. Revisé a ojo los 6 saltos más grandes (MtErie 0005 en 96 y 198, FHL 0405 en 222 y 916, Baker en 50 y 68): todos son falsas alarmas, porque la RGB y la térmica coinciden antes y después |
| Separación entre cajas de personas / residuo con la franja nominal | (análisis aparte) | Necesita 2 personas o más; encuentra pocos tramos y con mucho ruido |

Ninguno sirve por sí solo. Los límites salen del **barrido visual** (`scripts/fase2_barrido.py`): un fotograma cada
10 posiciones en todos los pares anotados de los 7 vuelos. Son 504 fotogramas en 25 hojas
(`reports/alineacion/barrido/`, 8.4 MB), y los excluidos llevan el rótulo en rojo. Cada celda muestra la RGB recortada
a la franja que ve la térmica, al mismo tamaño que la térmica, junto a la térmica. Si el zoom cambia o el dron está en
el suelo, las dos mitades dejan de coincidir. Después revisé los bordes fotograma a fotograma.

## Tramos excluidos (confirmados el 2026-10-31)

Todos están en `configs/fase1.yaml`, con su motivo. Las imágenes de los bordes de despegue, aterrizaje y cambio de zoom
están en `reports/alineacion/bordes_tramos/`. Cada una muestra el fotograma anterior al borde, el borde y el
siguiente: la RGB completa con la franja en amarillo, la RGB recortada y la térmica.

| Vuelo | Posiciones | Tipo | Pares | Cajas térmicas | Evidencia |
|---|---|---|---:|---:|---|
| Baker VIS_1/IR_1 | 0 a 15 | Despegue | 16 | 0 | 0–13: dron en el suelo (su estructura tapa la parte baja de la RGB). 14–15: despegando a ras de la nieve. 16: ya en el aire, con personas en las dos imágenes |
| FHL 0401/0402 | 0 a 10 | Cambio de zoom | 11 | 47 | En 0–10 las personas salen cerca de 1.6 veces más grandes en la RGB recortada que en la térmica; desde la 11 coinciden |
| FHL 0401/0402 | 857 a 895 | Aterrizaje | 39 | 70 | El dron baja hasta el pasto, con personas que caminan cerca. Desde la 857 las personas de las dos cámaras se separan más de 25 px (857: 25.3, 858: 31, de 861 a 880: de 24 a 59). En 852–856 la separación es de 7 a 15 px. El vídeo termina en la 895 sin que el dron se pose |
| MtErie 0005/0006 | 160 a 162 | Desfase | 3 | 4 | Giro rápido: 174, 51 y 37 px (159: 13; 163: 16) |
| Baker VIS_1/IR_1 | 620 a 626 | Desfase | 7 | 7 | Giro rápido: de 30 a 75 px, con todas las personas corridas en la misma dirección. En 618–619 no hay personas emparejadas; en la 627 vuelven a coincidir (2 px) |

Sumadas a Carnation (739 pares) y al corte de Baker 2031–2179 (149), quedaban **4 775 pares utilizables**, de los que
473 tenían persona solo en la térmica. Después salen los 41 tramos de la regla de desfase (135 pares, ver "Regla de
desfase"), que están en `configs/exclusiones_desfase.yaml`. Quedan **4 640**, con 471 "solo térmica".

**MtErie 0003 0–11 (el dron sube al empezar)** se excluyó y se devolvió el mismo día. Con la homografía las personas
quedaban separadas de 28 a 40 px. Con la semejanza están a 7–11 px en 0–9 y a 21 px en 10–11, y la franja nominal da
casi lo mismo (6–12 y 23 px). Ninguno de los tramos de esta tabla tiene pares "solo térmica". La tabla por
vuelo está en `reports/tabla_pares_por_vuelo.csv` y en `reports/fase1.md`.

## Otras cosas que se vieron en el barrido (no se excluyen)

- **El dron sube o baja, pero las dos cámaras coinciden:** MtErie 0005 final y FHL 0405 final (bajan). No son
  despegues ni aterrizajes: no se ve el suelo de cerca y la alineación se mantiene. Lo mismo pasa al inicio de
  MtErie 0003, que sube.
- **Cámara mirando la nieve de cerca, sin personas:** Baker 525–619. Las dos cámaras coinciden; se conserva.
- **Cámara levantada hacia el horizonte:** FHL 0134 cerca de 22–35 y FHL 0405 270–280. Coinciden; se conservan.

## Alineación con los centros de las cajas

Script: `scripts/fase2_homografias_cajas.py`, con la configuración en `homografias_cajas` de `configs/fase2.yaml`.
Las transformaciones se guardan en `configs/homografias_cajas.yaml` (una matriz 3 × 3 por vuelo, de píxeles de la
RGB original a píxeles de la térmica) y los informes en `reports/alineacion/homografias_cajas/`.

Método: en cada vuelo, los pares con persona en la RGB y en la térmica se reparten al azar (seed=0) en dos mitades.
Con la mitad de calibración se emparejan las personas de las dos imágenes (algoritmo húngaro sobre la distancia entre
centros, empezando por la franja nominal) y se estima la semejanza con RANSAC: umbral de 8 px y tres vueltas de
emparejar y estimar. Con la mitad de evaluación se mide la distancia entre el centro de cada caja térmica y el de su
caja RGB llevada a la térmica, en px térmicos (640 × 512). Se ignoran las cajas cortadas por el borde de la térmica, y
las cajas repetidas cuentan una vez.

### Resultado por vuelo (semejanza, pares de evaluación, con los 4 640 pares)

Es la semejanza vigente en `configs/homografias_cajas.yaml`, estimada de nuevo tras excluir los desfases (ver "Después
de aplicar"). Entre paréntesis, media y mediana con los 4 775 pares de antes.

| Vuelo | Pares con persona en ambas | Pares evaluados | Personas | Media (px) | Mediana (px) | Máximo (px) | Las personas usadas cubren | Zona de la RGB que ve la térmica |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MtErie 0003 | 233 | 116 | 451 | 5.8 (8.9) | 3.3 (4.3) | 34 | 36 % | x 0.19–0.83, y 0.07–0.98 |
| MtErie 0005 | 251 | 117 | 179 | 10.6 (12.2) | 7.7 (8.2) | 105 | 29 % | x 0.20–0.83, y 0.07–0.97 |
| MtErie 0007 | 162 | 79 | 118 | 8.5 (8.2) | 5.5 (5.7) | 149 | 9 % | x 0.18–0.85, y 0.03–0.99 |
| FHL 0134 | 75 | 36 | 66 | 1.8 (1.8) | 1.5 (1.5) | 5 | 1 % | x 0.19–0.83, y 0.06–0.97 |
| FHL 0401 | 689 | 342 | 1 346 | 8.5 (10.1) | 4.6 (4.8) | 168 | 64 % | x 0.19–0.83, y 0.06–0.97 |
| FHL 0405 | 389 | 193 | 255 | 6.2 (8.0) | 4.4 (4.8) | 52 | 39 % | x 0.18–0.83, y 0.06–0.98 |
| Baker | 1 898 | 910 | 2 155 | 7.1 (7.8) | 4.7 (4.6) | 71 | 62 % | x 0.18–0.83, y 0.06–0.98 |

La mediana describe mejor la alineación que la media, que suben los pocos pares que quedan con personas corridas o mal
emparejadas. Sin estimar nada, con la franja nominal, las medianas son 4.5, 9.5, 7.0, 3.8, 6.5, 5.5 y 5.8 px. En
todos los vuelos la zona que ve la térmica es casi igual a la franja nominal (x 0.18–0.84, y 0.06–0.98), como se
espera de dos cámaras montadas juntas.

Avisos del script (criterios propuestos por mí, no son reglas):

- En MtErie 0007 y FHL 0134 las personas usadas cubren poco de la térmica (9 % y 1 %). Con la semejanza esto pesa
  menos que con la homografía, porque tiene la mitad de grados de libertad y el campo de visión sale sano.
- En MtErie 0005 la mediana es de 7.7 px, la más alta. Es un vuelo con giros y el último tercio tiene una media de
  12.5 px.

### Por qué semejanza y no homografía

Una homografía tiene 8 grados de libertad. Cuando todas las personas usadas están en una zona pequeña de la imagen,
fuera de esa zona la transformación queda sin determinar. Comparación con la misma partición, hecha al decidir el
modelo con los 4 775 pares (`comparacion_modelos.csv` tiene ahora la de los 4 640):

| Vuelo | Zona que ve la térmica, homografía | Zona que ve la térmica, semejanza | Mediana homografía / afín / semejanza (px) |
|---|---|---|---:|
| MtErie 0003 | x 0.19–0.81, y 0.15–1.00 (trapecio) | x 0.19–0.84, y 0.05–0.98 | 3.7 / 3.5 / 4.3 |
| MtErie 0005 | x 0.21–0.83, y 0.06–0.97 (trapecio) | x 0.20–0.83, y 0.07–0.97 | 7.8 / 8.3 / 8.2 |
| MtErie 0007 | x −0.28–0.74, **y −1.22–0.95** | x 0.17–0.86, y 0.02–0.99 | 7.1 / 6.5 / 5.7 |
| FHL 0134 | **x 0.26–1.26, y −0.57–0.99** | x 0.19–0.83, y 0.06–0.97 | 1.3 / 1.5 / 1.5 |
| FHL 0401 | x 0.18–0.82, y 0.07–0.98 | x 0.19–0.83, y 0.06–0.98 | 5.1 / 4.9 / 4.8 |
| FHL 0405 | x 0.19–0.84, y 0.09–0.99 | x 0.18–0.84, y 0.05–0.98 | 3.8 / 4.5 / 4.8 |
| Baker | x 0.19–0.84, y 0.07–0.99 | x 0.18–0.83, y 0.06–0.98 | 4.3 / 4.9 / 4.6 |

En FHL 0134 y MtErie 0007 la homografía no tiene sentido físico: la RGB alineada sale como un trapecio torcido. La
distancia de evaluación no lo detecta, porque las personas de evaluación están en la misma zona que las de
calibración. La semejanza da en los 7 vuelos una zona casi igual a la franja nominal, con medianas parecidas. Además,
el resultado de RANSAC cambia algo si solo cambia el orden de los pares de calibración: la mediana varía hasta 2.3 px en
MtErie 0005 con la homografía y 1.4 px con la semejanza. Con seed=0 y el mismo orden, el resultado es reproducible.

### Validación con los puntos manuales

**MtErie 0003, solo la mitad (posición 132, 8 puntos)** (`validacion_manual.csv`):

| | Franja nominal | Homografía | Afín | Semejanza |
|---|---:|---:|---:|---:|
| Error medio (px), con los 4 640 pares | 8.9 | 11.4 | 11.4 | **11.9** |
| Error máximo (px), con los 4 640 pares | 24.7 | 28.8 | 32.4 | 32.4 |
| Error medio (px), con los 4 775 pares | 8.9 | 9.3 | 11.2 | 9.8 |
| Error máximo (px), con los 4 775 pares | 24.7 | 21.3 | 31.4 | 27.6 |

Con la semejanza reestimada el error medio sube de 9.8 a 11.9 px (ver "Después de aplicar"). El error máximo es del
punto 8, que está en el borde inferior. Con los 4 775 pares, sin él, la semejanza daba 7.2 px de media. Estos puntos
tienen una coherencia propia de unos 10 px: si se quita un punto, se ajusta una semejanza con los demás del mismo
fotograma y se mide dónde cae el punto quitado, queda a entre 5 y 14 px (33 px el punto 8). Por eso la validación no
distingue entre modelos con diferencias de pocos píxeles. Imagen: `puntos_manuales_210417_MtErie_Enterprise_0003.jpg`.

**Puntos descartados de MtErie 0003:** los de inicio (posición 0, 5 puntos) y final (263, 6 puntos) se marcaron con la
térmica cortada (la ventana no cabía en la pantalla por la escala del 125 %). No eran coherentes entre sí: el punto
quitado caía a 72–286 px en inicio y a 28–59 px en final. Siguen en
`configs/puntos_control/210417_MtErie_Enterprise_0003.yaml`, pero no se usan (`validacion_manual` en
`configs/fase2.yaml`).

**FHL 0405 (fotogramas 30, 440 y 930):** pendiente; los marcas tú. El fotograma 30 queda justo después del tramo
27–29, donde las personas están a 23–25 px. En el 30 están a 4.7 px. El 440 no tiene personas y el 930 tiene una a
6.6 px.

### MtErie 0007

Se conserva y va en la partición de **validación**. Es un vuelo **bajo el dosel con la cámara de frente**, no hacia
abajo: en todo el barrido (0 a 171) el dron avanza por un sendero de un bosque abierto de troncos delgados con
helechos. Hay 1 o 2 personas pequeñas y lejanas, casi siempre en la parte baja o en el borde izquierdo. No hay
despegue, aterrizaje ni cambio de zoom, y las dos cámaras muestran la misma escena.

Error de alineación por separado (semejanza reestimada, pares de evaluación): media 8.5 px, mediana 5.5, máximo 149,
79 pares (118 personas). Por tercios del vuelo: 11.0 / 8.3 / 7.1 px. Las personas cubren solo el 9 % de la térmica,
siempre cerca de la línea del sendero. Con la homografía el tramo 23–55 parecía un desfase, pero era un error del
modelo deformado: con la semejanza desaparece. Con la regla de desfase salieron 3 pares: 54–55, revisado a ojo (la
térmica se atrasa tras un paneo), y la 53, "solo térmica" vecina.

## Regla de desfase (aplicada el 2026-10-31, con revisión a ojo)

### La regla

Para medir el desfase se usan todos los pares con persona en las dos imágenes (las dos mitades), con la semejanza de
cada vuelo:

1. Para cada persona térmica que no toca el borde se busca la caja RGB alineada **más cercana**. No se usa el
   emparejamiento húngaro. La distancia entre centros se divide por la altura de la caja térmica.
2. Las personas sin ninguna caja RGB a **3 alturas o menos** no cuentan: no son desfase y pueden estar tapadas.
3. Un par está desfasado si la **mediana** de sus personas que cuentan es **mayor que 1**, es decir, si se corren más
   que la altura de la persona.
4. Un tramo son **2 o más pares desfasados seguidos**. Un par sin personas que cuenten corta el tramo. Con cada tramo
   excluido salen también los pares "solo térmica" que están dentro de él o a **2 posiciones o menos**.

La primera versión (alguna persona a más de 25 px, con el emparejamiento húngaro) se descartó el 2026-10-31. No
tenía en cuenta el tamaño de las personas, y se disparaba con personas emparejadas mal o vistas en una sola cámara.

Con la semejanza de los 4 775 pares, la regla encontró **45 tramos** (146 pares, más 3 "solo térmica" vecinos). En la
hoja de ejemplos, 2 de los 4 tramos nuevos no eran desfases (ver "Antes de aplicar"). Por eso no se aplicó tal cual.

### Cómo se aplicó: opción 2 acotada

Script: `scripts/fase2_revision_desfases.py`, con la configuración en `revision_desfases` de `configs/fase2.yaml`.
Primero clasifica los 45 tramos:

| Tipo | Qué es | Tramos | Pares | Qué se hace |
|---|---|---:|---:|---|
| Todas corridas | En cada par cuentan 2 personas o más, y todas pasan de 1 altura | 4 | 9 | Se excluyen sin revisión |
| Una persona | En cada par cuenta una sola persona | 11 | 32 | Revisión a ojo |
| Mixto | Unas personas coinciden y otras no, o alguna queda bajo el umbral | 30 | 105 | Revisión a ojo |

También había que revisar todos los tramos de FHL 0405, MtErie 0005 y MtErie 0007. Ninguno era "todas corridas", así
que ya estaban en la revisión. En total se revisaron **41 tramos (137 pares)**.

Para cada tramo revisado hay una imagen en `reports/alineacion/revision_desfases/`, con nombre
`NN_vuelo_desde-hasta.jpg`. Muestra la RGB alineada mezclada con la térmica en el par anterior, en los del tramo y en
el siguiente, todos con el mismo recorte, para ver si el fondo se corre. Debajo van la imagen completa del peor par y
su RGB alineada y su térmica por separado. Cada panel trae, por persona, la distancia relativa y el vector hasta la
caja RGB más cercana en px térmicos (`personas_tramos.csv`). Trae también el **desplazamiento del fondo**
(`fondo_tramos.csv`): la correlación de fase entre los gradientes de la RGB alineada y de la térmica (suavizado
gaussiano σ = 2, Sobel, ventana de Hanning). Con respuesta menor que 0.10 no es fiable: pasa en el bosque de FHL 0405
y en parte de la nieve de Baker. La medida se comprobó en casos conocidos:

- FHL 0401 742–746: +11, +18, +13 y +41 px, y +2 en la 746.
- MtErie 0003 53–57: de −14 a −39 px.
- Baker 620–627: hasta −65 px, y −2 en la 627.

**Criterio.** Se excluye un tramo si las personas que se ven en las dos cámaras se corren juntas en la misma
dirección, o si el fondo se corre igual. Se conserva si una persona coincide y la otra solo se ve en la térmica
(oclusión), con el fondo en su sitio.

Las decisiones, con su motivo, están en `configs/revision_desfases.yaml`. Con `--aplicar`, el script escribe
`configs/exclusiones_desfase.yaml` (los tramos excluidos y sus "solo térmica" vecinos), y `configs/fase1.yaml` lo lee
en `exclusiones_adicionales`. El resultado por tramo está en `revision.csv`.

### Resultado de la revisión

Los px son térmicos (640 × 512). "Fondo" es el desplazamiento del fondo y los signos indican la dirección.

| # | Vuelo | Posiciones | Pares | Tipo | Decisión | Motivo |
|---:|---|---|---:|---|---|---|
| 1 | MtErie 0003 | 44–50 | 7 | mixto | Excluir | RGB borrosa por un movimiento rápido; casi todas las personas se corren 28–66 px en la misma dirección; en la 51 coinciden |
| 2 | MtErie 0003 | 53–57 | 5 | mixto | Excluir | Todas se corren hacia arriba (−27 a −48 px); fondo −14 a −39 |
| 3 | MtErie 0003 | 62–63 | 2 | todas corridas | Excluir | Sin revisión |
| 4 | MtErie 0003 | 164–165 | 2 | mixto | Excluir | Todas unos +30 px en vertical; fondo +19 y +24 |
| 5 | MtErie 0003 | 171–172 | 2 | mixto | Excluir | Todas unos −45 px; fondo −42 y −40 |
| 6 | MtErie 0003 | 200–201 | 2 | mixto | Excluir | El grupo se corre 50–57 px; fondo −57 y −56; borrosa |
| 7 | MtErie 0003 | 206–210 | 5 | mixto | Excluir | Todas se corren 20–60 px; borrosa por el giro |
| 8 | MtErie 0003 | 214–216 | 3 | mixto | Excluir | 3 de 4 personas −25 a −42 px (la cuarta solo coincide con la caja de una vecina); fondo −23 a −35 |
| 9 | MtErie 0005 | 71–73 | 3 | mixto | **Conservar** | Una persona coincide (0.04–0.14 alturas); la otra está detrás de los árboles y solo se ve en la térmica: oclusión |
| 10 | MtErie 0005 | 85–87 | 3 | mixto | **Conservar** | Una persona coincide, tapada en parte por helechos; la otra solo en la térmica; fondo en su sitio. Se conserva también la 88 ("solo térmica") |
| 11 | MtErie 0005 | 202–204 | 3 | mixto | Excluir | Las dos personas −25 a −45 px; en la 205 coinciden |
| 12 | MtErie 0005 | 209–211 | 3 | una persona | Excluir | Fondo +20, −55 y −39; en la 212, en su sitio |
| 13 | MtErie 0005 | 220–221 | 2 | mixto | Excluir | Fondo +21 y +36; en la 222, +1 |
| 14 | MtErie 0005 | 226–227 | 2 | mixto | Excluir | Personas +39 a +47 px; fondo +36 y +20 |
| 15 | MtErie 0007 | 54–55 | 2 | una persona | Excluir | Paneo borroso; la persona térmica queda quieta de la 53 a la 55 y salta en la 56 (la térmica se atrasa). Sale también la 53 ("solo térmica") |
| 16 | FHL 0134 | 268–272 | 5 | mixto | **Conservar** | Una persona coincide (2–5 px); la otra está bajo el dosel y solo se ve en la térmica; el fondo es el mismo en la 267: oclusión |
| 17 | FHL 0401 | 125–126 | 2 | mixto | Excluir | Las 4 personas +18 a +41 px; borrosa; en la 124 y la 127 coinciden |
| 18 | FHL 0401 | 140–142 | 3 | mixto | Excluir | Todas unos (−20, −20) px, y el fondo igual |
| 19 | FHL 0401 | 156–160 | 5 | mixto | Excluir | Todas +25 a +35 px en vertical; fondo +24 a +30 |
| 20 | FHL 0401 | 298–302 | 5 | mixto | Excluir | Todas +20 a +24 px; fondo +23 y +24; en la 303, +6 |
| 21 | FHL 0401 | 355–356 | 2 | mixto | Excluir | Todas +28 a +42 px; fondo +27 y +41 |
| 22 | FHL 0401 | 382–383 | 2 | mixto | Excluir | Todas −30 a −39 px en x; fondo −38 y −29; en la 384 coinciden |
| 23 | FHL 0401 | 508–510 | 3 | todas corridas | Excluir | Sin revisión |
| 24 | FHL 0401 | 566–567 | 2 | mixto | Excluir | Leve y pasajero: las 5 personas a unos (−12, −3) px; fondo −22 a −24 de la 565 a la 568 |
| 25 | FHL 0401 | 574–575 | 2 | todas corridas | Excluir | Sin revisión |
| 26 | FHL 0401 | 577–580 | 4 | mixto | Excluir | Todas +16 a +48 px en x; fondo +20 a +41; en la 576 coinciden |
| 27 | FHL 0401 | 619–621 | 3 | una persona | Excluir | La caja RGB queda 23–26 px por encima de la térmica y el fondo se corre igual (−22 a −26; −8 en la 622). La otra persona térmica no tiene caja RGB (tapada) |
| 28 | FHL 0401 | 656–657 | 2 | una persona | **Conservar** | El fondo está en su sitio, igual que en los vecinos; la caja RGB sube poco a poco y desaparece en la 658: cambio de la caja u oclusión |
| 29 | FHL 0401 | 675–676 | 2 | todas corridas | Excluir | Sin revisión |
| 30 | FHL 0401 | 678–679 | 2 | una persona | Excluir | En la 679, las otras 4 personas (a más de 3 alturas, no cuentan) se corren todas unos +60 px en x; en la 680 coinciden |
| 31 | FHL 0401 | 687–688 | 2 | mixto | Excluir | Las 5 personas +11 a +29 px en x; fondo +14 y +25; en la 686 y la 689 coinciden |
| 32 | FHL 0401 | 743–745 | 3 | mixto | Excluir | Todas +12 a +47 px; fondo +11 a +41; agua doble en la 745 |
| 33 | FHL 0401 | 754–767 | 14 | mixto | Excluir | Todas se corren hacia abajo, más cuanto más abajo están en la imagen (+13 a +49 px); fondo +13 a +29. Parece más un fallo de la semejanza con la cámara inclinada que un desfase de tiempo, pero igual no coinciden. Sale también la 768 ("solo térmica") |
| 34 | FHL 0405 | 37–39 | 3 | mixto | Excluir | Las dos personas se corren igual hacia arriba (−16 a −26 px, una altura); en la 36 y la 40 coinciden; en el bosque el fondo no es fiable |
| 35 | FHL 0405 | 47–48 | 2 | mixto | Excluir | RGB borrosa por el movimiento; las dos personas se corren hacia +x (17 a 47 px); en la 46 y la 49 coinciden |
| 36 | FHL 0405 | 55–57 | 3 | mixto | Excluir | Todas hacia arriba (−18 a −35 px); en la 54 coinciden |
| 37 | FHL 0405 | 65–67 | 3 | mixto | Excluir | La persona que cuenta se corre −22 a −31 px; fondo −17 a −26 en vertical (+5 en la 64). La otra está bajo un árbol, solo en la térmica |
| 38 | Baker | 185–188 | 4 | mixto | Excluir | Las personas se corren +86 a +140 px; fondo +88 a +115; en la 189 coinciden |
| 39 | Baker | 512–513 | 2 | mixto | Excluir | Las dos personas +63 a +69 px en x; fondo +62 y +57 |
| 40 | Baker | 519–521 | 3 | una persona | Excluir | La persona tendida se corre de +88 a +150 px, cada vez más; fondo +144 y +188 |
| 41 | Baker | 618–619 | 2 | una persona | Excluir | Sigue el giro ya excluido (620–626): la persona RGB está en la línea de árboles y la térmica, 57–79 px más abajo |
| 42 | Baker | 633–634 | 2 | una persona | Excluir | −54 y −92 px en x; fondo −56 y −91 |
| 43 | Baker | 639–641 | 3 | una persona | Excluir | (+47 a +55, +34 a +44) px; fondo parecido |
| 44 | Baker | 652–654 | 3 | una persona | Excluir | −63 a −70 px en vertical; fondo −62 a −72 |
| 45 | Baker | 795–801 | 7 | una persona | Excluir | −35 a −47 px en x, cada vez más; fondo −32 a −52 |

**Resumen:** de los 41 tramos revisados se excluyen 37 y se conservan 4 (MtErie 0005 71–73 y 85–87, FHL 0134
268–272 y FHL 0401 656–657). Los 4 conservados tienen el fondo en su sitio: son personas tapadas en la RGB cuya caja
más cercana es la de otra persona, o un cambio de la caja. Sumados los 4 tramos "todas corridas", salen **41 tramos**.

### Pares que salen

| Vuelo | Utilizables antes | Tramos excluidos | Pares de desfase | "Solo térmica" vecinos | Salen | Quedan | "Solo térmica" que quedan |
|---|---:|---:|---:|---:|---:|---:|---:|
| MtErie 0003 | 264 | 8 | 28 | 0 | 28 | 236 | 0 |
| MtErie 0005 | 269 | 4 | 10 | 0 | 10 | 259 | 8 de 8 |
| MtErie 0007 | 172 | 1 | 2 | 1 | 3 | 169 | 7 de 8 |
| FHL 0134 | 273 | 0 | 0 | 0 | 0 | 273 | 61 de 61 |
| FHL 0401 | 846 | 16 | 56 | 1 | 57 | 789 | 0 de 1 |
| FHL 0405 | 943 | 4 | 11 | 0 | 11 | 932 | 394 de 394 |
| Baker | 2 008 | 8 | 26 | 0 | 26 | 1 982 | 1 de 1 |
| **Total** | **4 775** | **41** | **133** | **2** | **135** | **4 640** | **471 de 473** |

Aplicando la regla sin revisar habrían salido 149 pares; la revisión devuelve 14.

**FHL 0405 por separado:** salen 11 pares, los de sus 4 tramos (37–39, 47–48, 55–57 y 65–67). Los 4 son desfases
reales: las personas se corren juntas una altura y vuelven a coincidir en los pares vecinos. Ninguno es "solo
térmica", así que quedan **932 pares** y se conservan los **394 "solo térmica"**. Los fotogramas de marcado (30, 440 y
930) no caen en ningún tramo.

### Después de aplicar: la semejanza se volvió a estimar

Con los 4 640 pares se volvió a correr `fase2_homografias_cajas.py`, para que `configs/homografias_cajas.yaml` salga
de los mismos datos que se van a usar. Al quitar pares cambia el reparto al azar de las dos mitades (seed=0 sobre los
pares que quedan), así que la semejanza cambia aunque el método sea el mismo. Cambio medio de la transformación sobre
la térmica, con el máximo entre paréntesis:

- MtErie 0003: 5.0 px (9.3).
- MtErie 0007: 3.9 px (7.4).
- FHL 0405: 3.1 px (6.0).
- Baker: 1.8 px (3.0).
- FHL 0401 y MtErie 0005: 0.9 px (1.6).
- FHL 0134: 0.

La distancia de evaluación baja en casi todos los vuelos (ver la tabla de resultados por vuelo, más arriba): por
ejemplo, la media de MtErie 0003 pasa de 8.9 a 5.8 px y la de FHL 0405 de 8.0 a 6.2. Pero el error con los puntos
manuales de MtErie 0003 sube de 9.8 a 11.9 px. Con 8 puntos en un solo fotograma y una coherencia propia de unos
10 px, esa validación no distingue cambios de este tamaño. La validación con FHL 0405 lo dirá mejor.

Con la semejanza nueva, la regla marca **4 tramos** (51 pares con mediana mayor que 1):

- Los 3 que se conservaron en la revisión: MtErie 0005 71–73 y 85–87, y FHL 0134 268–272. FHL 0401 656–657 ya no
  sale.
- **Uno nuevo: FHL 0401 371–372.** En la 371 la mediana pasó de 0.99 a 1.02. Es un desfase real: las 4 personas y el
  fondo se corren juntos +15 px en la 370, +26 en la 371 y +65 en la 372. En la 369 coinciden (1 a 3 px). La 373 y la
  374 no tienen cajas térmicas, aunque la RGB tiene 3 personas. **No se aplicó**: lo decides tú.

Medidas con la semejanza nueva: 9 676 personas térmicas en 3 640 pares; 9 359 tienen caja RGB a 3 alturas o menos.
`ejemplos_desfase.jpg` se regeneró con los 4 640 pares. En sus 6 primeras filas, los tramos de la hoja anterior salen
como "no lo excluye", porque sus pares ya están excluidos o no pasan el umbral. Las 4 últimas son los 4 tramos de la
lista anterior. La hoja revisada antes de aplicar está en el commit `fe7376a`.

### Lo que la revisión no cubre

1. **Vecinos corridos por debajo del umbral.** Solo miré el par anterior y el siguiente de cada tramo. Varios siguen
   corridos, y el fondo se corre en la misma dirección, pero la mediana no pasa de 1 altura, así que se quedan:
   - FHL 0401: 297 (fondo +24 px; personas a 19–24 px, 0.9 alturas), 381 (fondo −33; personas a 16–35 px), 565 y
     568 (fondo −22 y −20; unos 13 px, 1.0 alturas), 742 (+11; 12–14 px) y 753 (+15; 12–14 px).
   - FHL 0405: 68 (fondo −21; 18 px, 0.8 alturas).
   - Baker: 184 (fondo +42; 41 px), 511 (46–48 px), 514 (49–55 px), 518 (fondo +39; 39–43 px), 632 (fondo −25;
     22 px), 642 (51 px), 651 (fondo −32; 36 px), 655 (fondo −45; 45 px) y 794 (fondo −30; 32 px).

   En Baker la cámara va inclinada y las personas son grandes: una altura son de 33 a 81 px. Por eso una persona de
   pie corrida 0.7 alturas en horizontal queda fuera de su caja térmica, y la regla no la cuenta como desfase.
2. **Desplazamientos de más de 3 alturas.** Las personas a más de 3 alturas de toda caja RGB no cuentan (pueden estar
   tapadas), así que un desfase muy grande se toma por oclusión.
   - El caso más claro es **MtErie 0005 206–208**. El fondo se corre +33, +103 y +104 px, y sigue en 209–211, que sí
     se excluyó. La persona corrida está a 4.5 alturas, así que no cuenta. La otra queda cerca de una caja RGB
     (0.4–0.7 alturas), y el par no sale.
   - En FHL 0401 677, dos personas están a 49 y 62 px de la caja RGB más cercana (3.8 y 4.1 alturas).
   - Los pares sin personas que cuenten tampoco se ven, como Baker 635 y 802 (fondo −74 y −57, no fiable).

### Sensibilidad al radio de "cerca" (antes de aplicar, con los 4 775 pares)

El radio de 3 alturas lo propuse yo y lo confirmaste. Se eligió porque desde unas 3 alturas el número de personas por
intervalo se aplana: es el fondo de personas cuya caja RGB más cercana es otra persona.

| Vuelo | Regla anterior (25 px) | 2 alturas | **3 alturas** | 4 alturas | 5 alturas | Sin límite |
|---|---:|---:|---:|---:|---:|---:|
| MtErie 0003 | 31 | 21 | **28** | 28 | 28 | 28 |
| MtErie 0005 | 15 | 7 | **17** | 17 | 20 | 41 |
| MtErie 0007 | 3 | 0 | **3** | 3 | 6 | 6 |
| FHL 0134 | 0 | 0 | **5** | 5 | 5 | 5 |
| FHL 0401 | 74 | 49 | **59** | 70 | 77 | 96 |
| FHL 0405 | 11 | 11 | **11** | 11 | 11 | 97 |
| Baker | 108 | 21 | **26** | 26 | 26 | 26 |
| **Total** | **242** | **109** | **149** | **160** | **173** | **299** |

Entre 3 y 5 alturas el total se estabiliza (149 a 173). Sin límite, FHL 0405 perdería 97 pares: son personas tapadas
en la RGB cuya caja más cercana es otra persona. `sensibilidad_radio.csv` tiene ahora la de los 4 640 pares.

### Antes de aplicar: hoja de ejemplos y revisión de 4 tramos nuevos

La hoja (commit `fe7376a`) tenía 10 filas: los 6 tramos de la hoja de la regla de 25 px y 4 tramos nuevos de la regla
relativa. De los 4 nuevos, FHL 0401 566–567 (leve) y FHL 0401 743–745 eran desfases. FHL 0401 656–657 (cambio de la
caja) y FHL 0134 268–272 (oclusión) no lo eran. Como esa era la condición, la regla no se aplicó entonces. Probé dos
ajustes y ninguno sirve:

- **a) Caja más cercana mutua** (cada caja RGB solo cuenta para la persona térmica que tiene más cerca). Ya no
  excluye FHL 0134 268–272, pero tampoco los dos desfases reales. Cuando las personas están juntas y todas se corren
  casi una distancia entre personas, la caja más cercana pasa a ser la de la vecina. Salen 131 pares.
- **a) + b) Mutua y al menos 2 personas por par.** No excluye ninguno de los 4 tramos. Salen 77 pares.

De ahí salió la opción 2 acotada: revisar a ojo lo que la regla no resuelve sola.

## Herramienta de marcado de puntos

`scripts/marcar_puntos.py` sirve para marcar puntos a mano en tres fotogramas por vuelo. Los fotogramas están
preconfigurados en `marcado.fotogramas` de `configs/fase2.yaml`, en la parte estable de cada vuelo. Hoy se usa solo
para validar.

Desde el 2026-10-31 la herramienta es **consciente del DPI**. Con la escala de pantalla de Windows al 125 %, la
ventana de 1800 px ocupaba unos 2250 y se cortaba. Ahora un píxel de la imagen es un píxel de la pantalla. Además, el
tamaño se recorta al área de trabajo (1920 × 1140 sin la barra de tareas): la ventana principal queda arriba a la
izquierda y la lupa debajo. Comprobado con FHL 0405: la ventana principal mide 1780 × 679 y la lupa 402 × 439; las dos
caben completas.

| Vuelo | Inicio | Mitad | Final |
|---|---:|---:|---:|
| MtErie 0003/0004 | 0 | 132 | 263 |
| MtErie 0005/0006 | 30 | 130 | 260 |
| MtErie 0007/0008 | 10 | 90 | 160 |
| FHL 0134/0135 | 10 | 150 | 262 |
| FHL 0401/0402 | 20 | 450 | 840 (antes 860, que ahora es aterrizaje) |
| FHL 0405/0406 | 30 | 440 | 930 |
| Baker VIS_1/IR_1 | 80 | 1040 | 1990 |

## Espacio en disco previsto

Por par: RGB alineada en PNG (0.74 MB), térmica en gris en PNG (0.18 MB) y TIFF de 4 canales con deflate (0.92 MB).
Son estimaciones hechas con muestras de cada vuelo. Con los 4 640 pares de hoy serían unos **8.0 GiB**. Libres en C:
110 GB (medido el 2026-10-31).

## Pendiente

1. Decidir sobre **FHL 0401 371–372**, el tramo nuevo que sale tras reestimar la semejanza (ver "Después de
   aplicar"). Si se agrega, conviene decidir antes cómo evitar que cada exclusión cambie el reparto de las mitades y
   mueva la semejanza.
2. Decidir si se hace algo con los vecinos que siguen corridos por debajo de 1 altura y con MtErie 0005 206–208 (ver
   "Lo que la revisión no cubre").
3. Validación con tus puntos de FHL 0405 (volver a correr `fase2_homografias_cajas.py`).
4. Alinear y escribir los PNG y TIFF por partes, con 10 superposiciones por vuelo.
5. Para la Fase 3: la propuesta de partición de `FASES.md` incluye Carnation 0023, que ya está excluido.
