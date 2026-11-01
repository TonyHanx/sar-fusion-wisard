# Reglas de anotación de oclusión

Fase 3b, 1 de noviembre de 2026. Estas reglas valen para los dos anotadores.

## Qué se anota

- **Vuelo:** FHL 0405, la partición de prueba.
- **Fotogramas:** los que tienen posición múltiplo de 3 (0, 3, 6…). Son 310 fotogramas.
- **Personas:** cada caja térmica de WiSARD de esos fotogramas es una persona a anotar. En total son **498**.
- La lista fija está en `data/oclusion_personas.csv`. Cada persona se identifica por vuelo, posición e índice de su caja
  en la etiqueta térmica.
- **Segundo anotador:** anota una muestra al azar del 15 % (75 personas, seed=0), listada en
  `data/oclusion_muestra_segundo.csv`.
- **Plan del 1 de noviembre de 2026:**
  - El nivel sale de un λ RGB automático (`scripts/oclusion_auto.py`).
  - Para validarlo, el primer anotador anota a mano solo esas mismas 75 personas, con la herramienta en modo
    `--muestra`.
  - Primera anotación, con cajas: el kappa de Cohen entre el nivel automático y el manual (dos clases) dio 0.940.
  - Desde el 1 de noviembre de 2026 decide el kappa del automático contra el primer anotador **en modo simple, ronda
    2** (regla aclarada). Si es menor que 0.61, el nivel binario de las 498 se anota a mano en modo simple.
  - Las reglas de abajo no cambian.

## Cajas

1. **Caja completa:** una por persona. Es el cuerpo entero estimado según la postura (de pie, sentado o acostado),
   incluida la parte tapada.
   - Tiene **el mismo tamaño en las dos imágenes**, pero **se puede mover en cada una** para centrarla sobre la
     persona. Así λ no mezcla el error de alineación entre las cámaras con la oclusión.
   - Si la persona **no se ve en la RGB**, la completa RGB queda donde la pone la semejanza, es decir, en el mismo
     lugar que la térmica.
   - Decidido el 1 de noviembre de 2026.
2. **Caja visible RGB y caja visible térmica:** el rectángulo más ajustado a lo que se ve del cuerpo en cada imagen.
   Si no se ve nada, no hay caja y λ = 1.
3. **λ = 1 − área (visible ∩ completa) / área completa**, en cada imagen y con la completa de esa imagen.
4. **"Fuera de cuadro":** el cuerpo está cortado por el borde de la imagen. No cuenta como oclusión.
5. **"No es persona":** la caja térmica de WiSARD está mal. Se reporta aparte.
6. **Las sombras no son parte de la persona.**

El nivel de oclusión sale de λ en la RGB:

| Nivel | λ RGB |
|---|---|
| Baja | de 0 a 35 % |
| Moderada | de 35 a 70 % |
| Severa | más de 70 % |

El nivel se calcula en la Fase 4; la herramienta no lo muestra.

Desde el 1 de noviembre de 2026 el nivel tiene **dos clases**: **severa** si la persona no se ve en la RGB y **baja**
si se ve (en la muestra no hubo ninguna moderada). La tabla de arriba solo se usa para reportar la comparación.

## Modo simple (los dos anotadores)

Herramienta: `scripts/anotar_oclusion.py --segundo-simple` (segundo anotador, decidido el 1 de noviembre de 2026) y
`--primero-simple` (primer anotador, desde la ronda 2, también decidido el 1 de noviembre de 2026, para que los dos
usen el mismo criterio). Los dos modos muestran la misma pantalla y la misma regla.

- Para cada una de las 75 personas de la muestra, en el mismo orden, se ven la RGB alineada y la térmica, con la caja
  térmica de WiSARD de la persona en verde y las de las demás personas del fotograma en gris.
- No se dibujan cajas, no hay precarga (ni la caja RGB de WiSARD) y no se ve ninguna respuesta: ni las del otro
  anotador ni la anotación con cajas del primero. La herramienta solo lee el archivo propio, para retomar.
- Se responde con una tecla: **1** se ve en la RGB, **2** no se ve en la RGB, **3** no es persona.

### Regla: cuándo "se ve en la RGB"

Aclarada el 1 de noviembre de 2026, después de la ronda 1. La herramienta la muestra en pantalla.

- **"Se ve"** = reconoces **una parte del cuerpo** (ropa, cabeza, brazos o piernas) en la RGB **con el brillo
  normal, sin realce**.
- **Una mancha oscura, una sombra o una rama no cuentan.**
- **Si dudas, "no se ve".**
- El realce de contraste (**e**) está desactivado en este modo. El zoom (rueda, **+** / **−**) y los píxeles sin
  suavizar (**i**) sí se pueden usar.

### Qué cambió en la regla

| | Primer anotador, con cajas (`--muestra`) | Ronda 1 | Ronda 2 |
|---|---|---|---|
| Quién | primero | segundo | primero y segundo |
| "Se ve en la RGB" | sin definir: dibuja la visible RGB de lo que ve | sin definir | **la regla de arriba** |
| Realce (`e`) | disponible | disponible | **desactivado** |
| Precarga | visible RGB = caja RGB de WiSARD a 3 alturas o menos | ninguna | ninguna |
| Pantalla | la de las cajas | modo simple | modo simple, con la regla |

### Rondas

| Ronda | Regla | Primer anotador | Segundo anotador |
|---|---|---|---|
| 1 | ambigua | su anotación con cajas, `data/oclusion.csv` | `data/oclusion_segundo_simple_ronda1.csv` |
| 2 | aclarada | `data/oclusion_primero_simple_ronda2.csv` | `data/oclusion_segundo_simple_ronda2.csv` |

- En la ronda 2, cada anotador responde **las 75 personas completas**, desde cero, sin ver las respuestas del otro.
  La herramienta escribe en el archivo de su anotador en `modo_simple.ronda_actual` (`configs/fase3.yaml`).
- El kappa que decide la concordancia es el de la ronda 2: el primero contra el segundo, los dos en modo simple.
- La ronda 1 (kappa 0.507) y la anotación con cajas del primero se conservan y se reportan en
  `reports/fase4_validacion_auto.md`.

### Las 498 personas (nivel a mano)

El nivel automático no pasó la validación de la ronda 2 (kappa 0.427 contra el primero), así que el nivel binario de las
498 personas se anota a mano (decidido el 1 de noviembre de 2026).

- **Quién:** el primer anotador, en modo simple, con la misma pantalla y la misma regla de la ronda 2.
- **Las 75 de la muestra** no se vuelven a responder: son sus respuestas de la ronda 2
  (`data/oclusion_primero_simple_ronda2.csv`).
- **Las 423 que faltan:** `--primero-simple-resto`, en el orden de la lista (por fotograma).
  - Guarda en `data/oclusion_primero_simple_resto.csv`.
  - La ronda de la regla está en `oclusion.modo_simple.resto` (`configs/fase3.yaml`).
- **"No es persona":** quedan sin nivel. Todas, también las 10 en que coinciden los dos en la ronda 2, van a
  `configs/cajas_dudosas.yaml`.
  - Las etiquetas de prueba no se tocan.
- **Reanotación de la escena en sombra** (fotogramas 468 a 588), decidida el 1 de noviembre de 2026:
  - el primero vuelve a responder de una vez todas sus personas (muestra y resto, 94), en orden de fotograma y con la
    misma regla;
  - usa `--primero-simple-reanotar escena_sombra` y guarda en `data/oclusion_primero_simple_escena_sombra.csv`;
  - esas respuestas reemplazan las anteriores en el nivel final, y las anteriores se conservan.

## Cómo se aplican en la herramienta

La herramienta es `scripts/anotar_oclusion.py`.

- **Las dos imágenes comparten geometría.** La RGB está alineada con la térmica (640 × 512, semejanza congelada de la
  fase 2), así que una caja ocupa el mismo lugar en las dos.
- **La caja completa se dibuja una vez**, en cualquiera de las dos imágenes, y aparece en el mismo lugar en las
  dos (donde la pone la semejanza).
  - **Centrarla en cada imagen:** Mayús + arrastrar, o la herramienta **m**, mueve la completa de la imagen donde se
    arrastra. Con **m**, un clic la centra en ese punto. El tamaño no cambia.
  - **Ver la otra:** cada imagen muestra con una línea fina dónde está la completa de la otra imagen.
  - **Corrimiento:** el panel de información da el corrimiento de la completa RGB respecto de la térmica.
  - **Redibujarla:** si se redibuja en una imagen, cambia el tamaño en las dos; la otra conserva su centro.
  - **Volver a la semejanza:** **g** devuelve la completa RGB al lugar de la térmica.
  - **RGB no visible (r):** la completa RGB vuelve al lugar de la térmica, la sigue y no se puede mover.
- **Las visibles son de cada imagen.** La visible RGB se dibuja en la RGB y la visible térmica en la térmica.
- **Precarga del primer anotador:**
  - La visible térmica viene con la caja de WiSARD.
  - La visible RGB viene con la caja RGB de WiSARD más cercana a 3 alturas o menos, llevada a la térmica con la
    semejanza. Esto pasa en 175 de las 498 personas.
  - Las otras 323 empiezan con la visible RGB pendiente: hay que dibujarla o marcar "no visible".
  - **La precarga es un punto de partida.** Hay que revisarla y corregirla con estas mismas reglas.
- **Segundo anotador:** no tiene precarga ni ve las cajas de WiSARD ni las del primer anotador. La persona a anotar se
  señala con triángulos amarillos en los bordes de la vista.
- **Cuándo está terminada una persona:** cuando tiene la caja completa y las dos visibles resueltas (caja o "no
  visible"). También cuenta como terminada si está marcada "fuera de cuadro" o "no es persona".
- **Aviso:** si más del 10 % de una visible queda fuera de la completa de su imagen, la herramienta lo dice. En ese
  caso, revisa las dos cajas: casi siempre basta con centrar la completa de esa imagen.
- **Vista:** se centra en la persona. Cerca del borde del fotograma se corre lo justo para que la imagen llene el panel;
  los triángulos amarillos siguen marcando a la persona.
- **Cajas de WiSARD cortadas por el borde:** 6 cajas térmicas salen hasta 1 px del fotograma (posiciones 207, 219,
  333, 609 y 660). Hay que ver si la persona está cortada ("fuera de cuadro").

### Ratón y teclas

| Acción | Qué hace |
|---|---|
| Arrastrar con el botón izquierdo | Usa la herramienta activa. **c** = dibuja la completa; **v** = dibuja la visible de la imagen donde se dibuja; **m** = mueve la completa de esa imagen (un clic la centra). Al dibujar la completa, la herramienta pasa sola a visible. |
| Mayús + arrastrar (izquierdo) | Mueve la completa de esa imagen, con cualquier herramienta. |
| Arrastrar con el botón derecho | Dibuja siempre la visible de esa imagen. |
| **g** | Devuelve la completa RGB al lugar donde la pone la semejanza (el de la térmica). |
| **r** / **t** | No visible en la RGB / en la térmica. Pulsar otra vez lo quita. |
| **f** | Fuera de cuadro. |
| **p** | No es persona. |
| **u** | Deshacer. |
| **n** / **b** | Persona siguiente / anterior. |
| Espacio | Siguiente persona sin terminar. |
| Rueda, **+** / **−** | Zoom. |
| Flechas | Mover la vista. |
| **0** | Volver a la vista inicial. |
| **e** | Realce de contraste. Desactivado en el modo simple. |
| **i** | Ver los píxeles sin suavizar. |
| **h** | Ocultar las cajas. |
| **q** o la X | Salir. |

### Guardado

- **Primer anotador:** guarda en `data/oclusion.csv`, también con `--muestra`. Las personas que ya están en ese archivo
  y no son de la muestra (la persona 1) se conservan sin cambios.
- **Segundo anotador:** guarda en `data/oclusion_segundo.csv`.
- **Modo simple:** cada anotador guarda en su archivo de la ronda actual (`data/oclusion_primero_simple_ronda2.csv` o
  `data/oclusion_segundo_simple_ronda2.csv`), solo las personas respondidas, después de cada respuesta. Al abrir de
  nuevo, sigue en la primera sin responder.
  - Con `--primero-simple-resto`, igual, en `data/oclusion_primero_simple_resto.csv`.
  - Con `--primero-simple-reanotar escena_sombra`, igual, en `data/oclusion_primero_simple_escena_sombra.csv`.
- Se guarda después de cada cambio y al pasar de persona. Al abrir de nuevo, la herramienta sigue en la primera persona
  sin terminar.
- **No abras el CSV en Excel mientras anotas.** Excel bloquea el archivo y la herramienta no puede guardar. Si pasa,
  la herramienta avisa.
- **Coordenadas:** píxeles de las imágenes alineadas (640 × 512), continuas: el píxel i cubre [i, i + 1].
- **Qué guarda de la completa:** las dos completas (`completa_termica_*` y `completa_rgb_*`) y el corrimiento de la RGB
  respecto de la térmica (`completa_rgb_dx`, `completa_rgb_dy`).

### Comandos

```
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --persona 1
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --muestra
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo-simple
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-resto
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --primero-simple-reanotar escena_sombra
```

- **Con `--ajuste`:** primer anotador.
  - Abre solo las personas de la muestra con visible RGB, ordenadas de mayor a menor según cuánto se sale la visible
    de la completa. La lista es `data/oclusion_ajuste_visibles.csv` y la arma `scripts/corregir_oclusion.py`.
  - Si la persona está parcialmente tapada, se ajusta la visible RGB a lo que se ve. Si se ve entera, se pasa de largo.
  - Como todas están terminadas, la barra espaciadora pasa a la siguiente.
- **Con `--muestra`:** primer anotador, con la precarga, solo las 75 personas de la muestra. "Persona N de 75" cuenta
  dentro de la muestra; `--persona N` también.

- **Con `--primero-simple` / `--segundo-simple`:** primer / segundo anotador, modo simple, en la ronda actual (ver
  arriba).
- **Con `--primero-simple-resto`:** primer anotador, modo simple, las 423 personas que faltan de las 498 (ver "Las 498
  personas"). "Persona N de 423" cuenta dentro de esa lista; `--persona N` también.
- **Con `--primero-simple-reanotar NOMBRE`:** primer anotador, modo simple, todas las personas de un tramo de
  `oclusion.modo_simple.reanotaciones` (hoy, `escena_sombra`: fotogramas 468 a 588, 94 personas), en orden de
  fotograma.
- **Sin opciones:** abre en la primera persona sin terminar.
- **Con `--persona N`:** abre en la persona N.
