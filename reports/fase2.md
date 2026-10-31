# Fase 2. Alineación de la RGB con la térmica (en curso)

Fecha: 2026-10-31 · Estado: modelo decidido (**semejanza por vuelo**). Exclusiones explícitas aplicadas: quedan
**4 775 pares** (473 "solo térmica"). Regla de desfase relativa confirmada (radio de 3 alturas) pero **sin aplicar**:
sacaría 149 pares y quedarían 4 626. No se aplicó porque, de los 4 tramos nuevos revisados, 2 no son desfases (ver
"Regla de desfase"). La validación con los puntos manuales de FHL 0405 está pendiente: los marcas tú. Después siguen
los TIFF.

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
  25 px. Está **sin aplicar**: 2 de los 4 tramos nuevos de la hoja no son desfases (ver "Regla de desfase").
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

Sumadas a Carnation (739 pares) y al corte de Baker 2031–2179 (149), quedan **4 775 pares utilizables**, de los que
473 tienen persona solo en la térmica.

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

### Resultado por vuelo (semejanza, pares de evaluación)

| Vuelo | Pares con persona en ambas | Pares evaluados | Personas | Media (px) | Mediana (px) | Máximo (px) | Las personas usadas cubren | Zona de la RGB que ve la térmica |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MtErie 0003 | 261 | 131 | 505 | 8.9 | 4.3 | 84 | 29 % | x 0.19–0.84, y 0.05–0.98 |
| MtErie 0005 | 261 | 123 | 185 | 12.2 | 8.2 | 105 | 31 % | x 0.20–0.83, y 0.07–0.97 |
| MtErie 0007 | 164 | 80 | 119 | 8.2 | 5.7 | 147 | 6 % | x 0.17–0.86, y 0.02–0.99 |
| FHL 0134 | 75 | 36 | 66 | 1.8 | 1.5 | 5 | 1 % | x 0.19–0.83, y 0.06–0.97 |
| FHL 0401 | 745 | 367 | 1 441 | 10.1 | 4.8 | 243 | 65 % | x 0.19–0.83, y 0.06–0.98 |
| FHL 0405 | 400 | 196 | 260 | 8.0 | 4.8 | 304 | 49 % | x 0.18–0.84, y 0.05–0.98 |
| Baker | 1 924 | 920 | 2 136 | 7.8 | 4.6 | 143 | 63 % | x 0.18–0.83, y 0.06–0.98 |

La media la dominan los desfases (máximos de 84 a 304 px, salvo en FHL 0134); la mediana describe mejor la alineación del resto. Sin
estimar nada, con la franja nominal, las medianas son 4.7, 10.4, 6.3, 3.8, 6.7, 5.6 y 5.9 px. Estos números son
**antes** de aplicar la regla de desfase. En todos los vuelos la zona que ve la térmica es casi igual a la franja
nominal (x 0.18–0.84, y 0.06–0.98), como se espera de dos cámaras montadas juntas.

Avisos del script (criterios propuestos por mí, no son reglas):

- En MtErie 0007 y FHL 0134 las personas usadas cubren poco de la térmica (6 % y 1 %). Con la semejanza esto pesa
  menos que con la homografía, porque tiene la mitad de grados de libertad y el campo de visión sale sano.
- En MtErie 0005 la mediana es de 8.2 px, la más alta. Es un vuelo con giros y el último tercio tiene una media de
  17.7 px.

### Por qué semejanza y no homografía

Una homografía tiene 8 grados de libertad. Cuando todas las personas usadas están en una zona pequeña de la imagen,
fuera de esa zona la transformación queda sin determinar. Comparación con la misma partición (`comparacion_modelos.csv`):

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
| Error medio (px) | 8.9 | 9.3 | 11.2 | **9.8** |
| Error máximo (px) | 24.7 | 21.3 | 31.4 | 27.6 |

El error máximo es del punto 8, que está en el borde inferior. Sin él, la semejanza da 7.2 px de media. Estos puntos
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

Error de alineación por separado (semejanza, pares de evaluación): media 8.2 px, mediana 5.7, máximo 147, 80 pares
(119 personas). Por tercios del vuelo: 10.6 / 8.1 / 6.7 px. Las personas cubren solo el 6 % de la térmica, siempre
cerca de la línea del sendero. Con la homografía el tramo 23–55 parecía un desfase, pero era un error del modelo
deformado: con la semejanza desaparece. Con la regla de desfase saldrían 3 pares (2 de desfase y 1 "solo térmica"
vecino).

## Regla de desfase (confirmada, todavía sin aplicar)

### La regla

Para medir el desfase se usan todos los pares con persona en las dos imágenes (las dos mitades), con la semejanza de
cada vuelo:

1. Para cada persona térmica que no toca el borde se busca la caja RGB alineada **más cercana**. No se usa el
   emparejamiento húngaro. La distancia entre centros se divide por la altura de la caja térmica.
2. Las personas sin ninguna caja RGB a **3 alturas o menos** no cuentan: no son desfase y pueden estar tapadas.
3. Un par está desfasado si la **mediana** de sus personas que cuentan es **mayor que 1**, es decir, si se corren más
   que la altura de la persona.
4. Se excluyen los tramos de **2 o más pares desfasados seguidos**. Un par sin personas que cuenten corta el tramo.
   También se excluyen los pares "solo térmica" dentro de esos tramos o a **2 posiciones o menos**.

La primera versión (alguna persona a más de 25 px, con el emparejamiento húngaro) se descartó el 2026-10-31. No
tenía en cuenta el tamaño de las personas, y se disparaba con personas emparejadas mal o vistas en una sola cámara.

Medidas: de 10 075 personas térmicas en 3 773 pares, 9 715 tienen caja RGB a 3 alturas o menos. 3 735 pares tienen
al menos una persona que cuenta, y en 181 la mediana pasa de 1. Archivos: `personas_desfase.csv` (una fila por
persona), `distancia_por_par.csv`, `desfases.csv` (45 tramos), `exclusion_desfase_propuesta.csv` y
`sensibilidad_radio.csv`.

### Pares que saldrían

| Vuelo | Utilizables hoy | Desfase | "Solo térmica" vecinos | Salen | Quedarían | "Solo térmica" que quedarían |
|---|---:|---:|---:|---:|---:|---:|
| MtErie 0003 | 264 | 28 | 0 | 28 | 236 | 0 |
| MtErie 0005 | 269 | 16 | 1 | 17 | 252 | 7 de 8 |
| MtErie 0007 | 172 | 2 | 1 | 3 | 169 | 7 de 8 |
| FHL 0134 | 273 | 5 | 0 | 5 | 268 | 61 de 61 |
| FHL 0401 | 846 | 58 | 1 | 59 | 787 | 0 de 1 |
| FHL 0405 | 943 | 11 | 0 | 11 | 932 | 394 de 394 |
| Baker | 2 008 | 26 | 0 | 26 | 1 982 | 1 de 1 |
| **Total** | **4 775** | **146** | **3** | **149** | **4 626** | **470 de 473** |

**FHL 0405 por separado:** salen 11 pares en 4 tramos: 37–39, 47–48, 55–57 y 65–67, con medianas relativas de 1.2 a
1.4. Ninguno es "solo térmica", así que los 394 pares "solo térmica" de FHL 0405 se conservan. Los fotogramas de
marcado (30, 440 y 930) no caen en ningún tramo.

### Sensibilidad al radio de "cerca" (pares que salen)

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
en la RGB cuya caja más cercana es otra persona. La regla anterior se recalculó sobre los 4 775 pares de hoy, y por
eso da 242 y no 243.

### Hoja de ejemplos y revisión

`ejemplos_desfase.jpg` tiene 10 filas. Las 6 primeras son los tramos de la hoja anterior; las 4 últimas son tramos
nuevos de la regla relativa que la anterior no tenía. Cada fila muestra el par anterior, el peor y el siguiente, con
la RGB alineada mezclada con la térmica.

| Tramo | Regla anterior | Regla relativa |
|---|---|---|
| FHL 0405 27–28 | Excluía | No lo excluye |
| FHL 0401 140–142 | Excluía | Lo excluye |
| MtErie 0005 31–32 | Excluía | No lo excluye |
| Baker 1176–1178 | Excluía (una sola persona corrida) | No lo excluye |
| Baker 651–657 | Excluía | Excluye 652–654 |
| FHL 0401 626–628 | Excluía (personas mal emparejadas) | No lo excluye |

Revisé a mano los 4 tramos nuevos, con la medida de cada persona y recortes ampliados de la mezcla:

| Tramo nuevo | Mediana máx. | ¿Desfase real? | Lo que se ve |
|---|---:|---|---|
| FHL 0401 566–567 | 1.05 | **Sí, leve** | Las 5 personas se corren igual, unos (−12, −3) px. En esa parte del vuelo la mediana anda en 0.4–0.6; sube a 0.9–1.05 entre 564 y 567 y baja a 0.3 en la 570. Es un desfase pasajero, en el límite del umbral |
| FHL 0401 656–657 | 1.32 | **No** | Una sola persona. El fondo de la mezcla coincide (sin imagen doble). La caja RGB queda cada vez más arriba que la térmica (7 px en la 654, 14 px en la 657) y desde la 658 desaparece de la RGB. Es un cambio de la caja (quizá la persona empieza a taparse), no un desfase |
| FHL 0134 268–272 | 1.57 | **No** | La RGB tiene 1 caja y la térmica 2. La persona de la izquierda coincide (2–5 px). La de la derecha está bajo el dosel y solo se ve en la térmica: su caja RGB más cercana es la de su compañera, a unas 2–3 alturas (las personas miden ~10 px). Con 2 personas, la mediana es el promedio y pasa de 1. Es un caso de oclusión, justo lo que interesa conservar |
| FHL 0401 743–745 | 2.58 | **Sí** | Las 5 personas se corren a la vez hacia +x (de 12 a 47 px) y en la 745 se ve el agua doble. En la 741 y la 746 coinciden (1–5 px) |

Como 2 de los 4 tramos nuevos no son desfases, **la regla no se aplicó** (era la condición). Probé dos ajustes y
ninguno sirve:

- **a) Caja más cercana mutua** (cada caja RGB solo cuenta para la persona térmica que tiene más cerca). Ya no
  excluye FHL 0134 268–272, pero tampoco los dos desfases reales. Cuando las personas están juntas y todas se corren
  casi una distancia entre personas, la caja más cercana pasa a ser la de la vecina. Salen 131 pares.
- **a) + b) Mutua y al menos 2 personas por par.** No excluye ninguno de los 4 tramos. Salen 77 pares.

El mismo problema de FHL 0134 268–272 puede aparecer en tramos que no revisé: pares con 2 personas, una de ellas
visible solo en la térmica y cerca de la otra.

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
Son estimaciones hechas con muestras de cada vuelo. Con los 4 775 pares de hoy serían unos **8.2 GiB**, y con 4 626
(aplicando la regla), unos **7.9 GiB**. Libres en C: 118 GB.

## Pendiente

1. Decidir qué hacer con la regla de desfase, ya que 2 de los 4 tramos nuevos revisados no son desfases. Cuando se
   aplique, `exclusion_desfase_propuesta.csv` se pasa a las exclusiones de la Fase 1, se regeneran `pares.csv` y los
   totales, y se vuelve a estimar la semejanza sin esos pares.
2. Validación con tus puntos de FHL 0405 (volver a correr `fase2_homografias_cajas.py`).
3. Alinear y escribir los PNG y TIFF por partes, con 10 superposiciones por vuelo.
4. Para la Fase 3: la propuesta de partición de `FASES.md` incluye Carnation 0023, que ya está excluido.
