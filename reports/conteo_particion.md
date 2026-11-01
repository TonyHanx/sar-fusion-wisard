# Conteos para la partición y la anotación de oclusión

Fecha: 2026-11-01. Son conteos previos a la Fase 3, para la reunión con la asesora; **la partición todavía no se
creó**. Se cuentan los 4 617 pares finales (anotados y no excluidos).

Para regenerar:

```
.venv\Scripts\python.exe scripts\conteo_particion.py --config configs\conteo_particion.yaml --rutas configs\rutas.yaml
```

Tablas: `reports/conteo_particion_vuelos.csv` y `reports/conteo_particion_prueba.csv`.

## Qué se cuenta

- **Personas:** cajas de la térmica, que es la etiqueta de referencia. Se cuentan **por fotograma**: una persona que
  aparece en 100 fotogramas cuenta 100 veces.
  - En las térmicas de los pares finales no hay cajas repetidas.
  - Las 46 cajas repetidas que elimina la Fase 3a son otras: 31 de la RGB en pares finales, 1 de la RGB en pares
    excluidos y 14 de la térmica en pares excluidos.
- **Pares "solo térmica":** pares con alguna caja térmica y ninguna caja RGB.
- **Personas sin caja RGB cerca:** personas térmicas sin ninguna caja RGB, llevada a la térmica con la semejanza, a 3
  alturas o menos. Es el mismo radio de la regla de desfase. Incluye todas las personas de los pares "solo térmica" y,
  además, las que faltan en la RGB en pares donde otra persona sí se ve.
- **Episodio:** tramo de posiciones seguidas con alguna persona en la térmica.
  - Lo corta un par sin personas o un par excluido.
  - Como las exclusiones cortan tramos donde la persona sigue en el vídeo, también doy cuántos episodios quedan si
    los pares excluidos no cortan.

## Por vuelo

| Vuelo | Pares | Pares con persona | Personas | Pares "solo térmica" | Personas en pares "solo térmica" | Personas sin caja RGB cerca | Episodios | Episodios si los excluidos no cortan | Pares por episodio (mediana) | Episodio más largo (pares) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MtErie 0003 | 236 | 233 | 905 | 0 | 0 | 1 | 9 | 2 | 5 | 100 |
| MtErie 0005 | 257 | 257 | 494 | 8 | 16 | 61 | 6 | 1 | 23.5 | 160 |
| MtErie 0007 | 169 | 169 | 289 | 7 | 10 | 15 | 2 | 1 | 84.5 | 116 |
| FHL 0134 | 273 | 136 | 211 | 61 | 65 | 67 | 9 | 9 | 14 | 38 |
| FHL 0401 | 783 | 683 | 2 755 | 0 | 0 | 111 | 20 | 5 | 16 | 136 |
| **FHL 0405** | **928** | **779** | **1 501** | **394** | **837** | **976** | **18** | **13** | **30** | **146** |
| Baker | 1 971 | 1 888 | 5 186 | 1 | 1 | 116 | 9 | 3 | 21 | 1 221 |
| **Total** | **4 617** | **4 145** | **11 341** | **471** | **929** | **1 347** | **73** | **34** | | |

Carnation 0023/0024 no aparece porque salió entero en la fase 2.

**Lo que dicen estos números:**

- **Hay pocos episodios y son largos.** Son 73 en total, y 34 si las exclusiones no cortan. Baker es casi un solo
  episodio de 1 221 pares seguidos. Los fotogramas seguidos muestran a las mismas personas desde casi el mismo punto,
  así que para la partición importa más el número de vuelos y de episodios que el de fotogramas. Esto confirma que la
  partición debe hacerse por vuelo.
- **Las personas no visibles en la RGB se concentran en FHL 0405.** Ahí están 837 de las 929 personas en pares "solo
  térmica" (90 %) y 976 de las 1 347 personas sin caja RGB cerca (72 %). Le sigue FHL 0134, con 65 y 67.
- **MtErie 0003 casi no tiene personas tapadas** (1 sin caja RGB cerca). Sus 9 episodios salen sobre todo de los
  cortes por desfase: si las exclusiones no cortan, quedan 2.

## FHL 0405 (prueba propuesta): personas que habría que anotar

Por la regla de oclusión de CLAUDE.md, cada persona lleva dos cajas en cada imagen del par: cuerpo completo (estimado)
y parte visible. Son hasta 4 cajas por persona.

| Qué se anota | Fotogramas | Fotogramas con persona | **Personas a anotar** | De ellas, en pares "solo térmica" | De ellas, sin caja RGB cerca | Cajas a dibujar (hasta) | Episodios cubiertos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Todo | 928 | 779 | **1 501** | 837 (56 %) | 976 (65 %) | 6 004 | 18 de 18 |
| 1 de cada 3 fotogramas | 310 | 259 | **498** (498–503) | 278 (275–284) | 323 (323–328) | 1 992 | 18 de 18 |
| 1 de cada 5 fotogramas | 186 | 155 | **300** (297–303) | 167 (166–170) | 192 (192–202) | 1 200 | 17 de 18 |

- **Cómo se eligen los fotogramas:** por su posición en el vídeo (posición múltiplo de 3 o de 5, empezando en la 0).
  Entre paréntesis está el rango con los otros puntos de partida posibles (empezar en la 1, en la 2, etc.). Casi no
  cambia.
- **La proporción se mantiene:** con cualquier submuestreo, el 56 % de las personas a anotar están en pares "solo
  térmica" y el 65 % no tiene caja RGB cerca.
- **Qué se pierde con 1 de cada 5:** queda fuera 1 de los 18 episodios, uno de los cortos (los más cortos tienen de
  2 a 4 pares). Con 1 de cada 3 se cubren todos.
- **Qué indican las dos columnas de "solo térmica":** son las candidatas a oclusión severa, pero no son el nivel. El
  nivel sale de λ, medido en la RGB después de anotar. Una persona sin caja RGB puede estar tapada del todo o puede
  ser una caja que faltó en la anotación RGB.
- **Episodios:** FHL 0405 tiene 18, con una mediana de 30 pares; con 1 de cada 5 quedan unos 6 fotogramas anotados
  por episodio. Los 394 pares "solo térmica" forman 21 tramos.
