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
| **e** | Realce de contraste. |
| **i** | Ver los píxeles sin suavizar. |
| **h** | Ocultar las cajas. |
| **q** o la X | Salir. |

### Guardado

- **Primer anotador:** guarda en `data/oclusion.csv`.
- **Segundo anotador:** guarda en `data/oclusion_segundo.csv`.
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
.venv\Scripts\python.exe scripts\anotar_oclusion.py --config configs\fase3.yaml --rutas configs\rutas.yaml --segundo
```

- **Sin opciones:** abre en la primera persona sin terminar.
- **Con `--persona N`:** abre en la persona N.
