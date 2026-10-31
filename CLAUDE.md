# Contexto del proyecto (léelo siempre antes de trabajar)

Tesis de pregrado de Hans Quispe (Ingeniería de Sistemas, Universidad de Lima), curso Seminario de Investigación I.
Tema: detectar y localizar personas ocultas por vegetación en imágenes de dron, fusionando la imagen RGB y la térmica.

Pregunta central: ¿un detector que recibe RGB + térmica encuentra más personas que el mismo detector con una sola
cámara, cuando la vegetación tapa más del 70 % del cuerpo?

## Reglas de trabajo

- Trabaja **por fases**, según `FASES.md`. Al terminar una fase, detente, resume lo que hiciste y espera mi confirmación.
- **Nunca** modifiques, muevas ni borres nada dentro del dataset original.
- Nada de rutas ni hiperparámetros escritos a mano dentro del código: todo va en `configs/` y se pasa como argumento.
- Semilla fija `seed=0` en todo lo aleatorio.
- Cada entrenamiento o evaluación agrega una fila a `reports/bitacora.csv` (fecha, fase, modelo, configuración, resultado).
- Si algo no está claro o los datos no son como dice este archivo, **muéstrame ejemplos y pregúntame** antes de suponer.
- Ejecuta Python con el entorno virtual del proyecto (`.venv`).
- La memoria es limitada (16 GB de RAM y 8 GB en la GPU): procesa las imágenes por partes, nunca todas en memoria.
- Todos los entrenamientos se hacen con la laptop **enchufada**, en modo **Rendimiento** de Armoury Crate y con el
  plan de energía **Performance** de Windows. Antes de entrenar, verifica con `nvidia-smi` que el límite aplicado
  bajo carga (`enforced.power.limit`) sea de al menos 90 W; si no, detente y avísame.

## Equipo

- Laptop con Windows 11, Intel Core i7-13620H (10 núcleos, 16 hilos), 16 GB de RAM.
- GPU NVIDIA GeForce RTX 4070 Laptop GPU, 8 GB. Límite de potencia medido el 30 de octubre de 2026 con `nvidia-smi`
  (enchufada, modo Rendimiento): **hasta 100 W bajo carga** (80 W por defecto + hasta 20 W de Dynamic Boost; máximo
  configurable 120 W). El límite aplicado varía entre corridas (medianas de 92 a 100 W) según la temperatura y la
  carga de la CPU. Los 55 W anotados antes eran una lectura en modo de bajo consumo.
- Todos los entrenamientos que se reporten corren en esta misma laptop.
- Controlador NVIDIA 617.42 (CUDA 13.4), actualizado el 30 de octubre de 2026 (antes 555.97).

## Rutas

- Dataset original: `C:\Users\User\Downloads\WiSARDv1` (solo lectura).
- Proyecto: esta carpeta. Datos procesados en `data\` (no van a GitHub).
- Proyecto anterior, solo como consulta: `C:\Users\User\sar-fusion\reports\` (scripts `emparejamiento.py` y
  `analisis_pares.py`, y `resumen_wisard.md`). Se puede reutilizar código de ahí, pero los resultados se regeneran aquí.

## Lo que ya sabemos de WiSARDv1 (análisis del 28 y 29 de octubre de 2026)

- 80 carpetas planas, una por vuelo y modalidad: `AAMMDD_Sitio_Dron_VIS[_ID]` (RGB) e `..._IR[_ID]` (térmica).
- Cada imagen tiene un `.txt` con el mismo nombre en formato YOLO (`clase cx cy w h`, normalizado). Solo clase 0 = persona.
- Un `.txt` vacío significa 0 cajas, no "descartar". Una carpeta sin ningún `.txt` está sin anotar.
- Térmicas: 640 × 512. RGB: 1920 × 1080, 2720 × 1530, 3840 × 2160 o 4096 × 2160.
- **No hay** archivos `.yaml` de metadatos ni lista de pares. Las imágenes no tienen EXIF.
- **Emparejamiento:** la carpeta VIS con número N va con la IR con número N+1 del mismo `fecha_sitio_dron`
  (en `220109_Baker` el número sale del nombre de archivo: DJI_0582 con DJI_0583). Dentro de cada pareja, los
  fotogramas se emparejan **por posición** en orden natural, hasta la longitud mínima.
- Resultado esperado: 14 839 pares en total; 5 739 con las dos imágenes anotadas.
- **Exclusión:** Baker VIS_1/IR_1, posiciones 2031 a 2179 (en la térmica hay personas sin caja desde la 2031;
  revisado a mano el 30 de octubre de 2026, ver `reports/baker_corte/`; antes el corte era 2051). Tras excluirlas
  quedan 5 590 pares anotados en 8 parejas de vuelos de 4 sitios (MtErie, Carnation, FHL, Baker).
- **Exclusiones de la fase 2 (31 de octubre de 2026):** Carnation 0023/0024 completo, de los tres modelos (zoom
  variable en la RGB, que cubre cerca del 11 % de la térmica; posible desfase en la posición 470); despegue de Baker
  (0 a 15); cambio de zoom de FHL 0401 (0 a 10) y aterrizaje de FHL 0401 (857 a 895); desfases entre cámaras
  (la térmica muestra otro instante) en MtErie 0005 (160 a 162) y Baker (620 a 626); inicio de MtErie 0003 (0 a 11;
  con la semejanza no pasa de 21 px, pendiente de confirmar). Quedan
  **4 763 pares anotados** en 7 parejas de vuelos de 3 sitios (MtErie, FHL, Baker); 473 de ellos con persona solo en
  la térmica. Todas las exclusiones están en `configs/fase1.yaml`, con su motivo.
- **Regla de desfase (propuesta, sin aplicar):** excluir los tramos de 2 o más pares seguidos con alguna persona a más
  de 25 px entre cámaras tras la alineación, y los pares "solo térmica" a 2 posiciones o menos de ellos. Sacaría 243
  pares (241 + 2 "solo térmica"); quedarían 4 520. Ver `reports/fase2.md`.
- La térmica ve aproximadamente la franja central de la RGB (x de 0.18 a 0.84, y de 0.06 a 0.98; cerca del 60 % del
  área), salvo en **Carnation 0023/0024**, donde la RGB tiene zoom y la relación se invierte.
- 476 pares tienen persona en la térmica y ninguna en la RGB, casi todos de FHL (394 en FHL 0405/0406). Son los
  candidatos a oclusión severa.

## Decisiones fijas (no cambiar sin consultarme)

- **Detector:** YOLO26s de Ultralytics, con pesos preentrenados `yolo26s.pt`.
- **Tres modelos:** fusión temprana (4 canales: RGB alineada + térmica), solo RGB alineada y solo térmica.
- **Fusión temprana:** imagen TIFF de 4 canales, `channels: 4` en el yaml del dataset.
  Verificado: con 4 canales, la primera capa recibe los pesos preentrenados en los 3 canales de color y el cuarto
  queda al azar. Se probará también inicializar el cuarto canal con el promedio de los pesos de color.
- **Etiquetas de referencia:** las de la imagen térmica, para los tres modelos.
- **Alineación:** la RGB se recorta a la zona que ve la térmica y se lleva a 640 × 512. La transformación es una
  **semejanza por vuelo** (escala, giro y traslación; `cv2.estimateAffinePartial2D`) estimada con los centros de las
  cajas de personas de los pares con persona en las dos imágenes, con RANSAC y seed=0: la mitad de esos pares la
  estima y la otra mitad mide la distancia entre centros. Se valida con puntos de control marcados a mano y con
  superposiciones. La homografía completa se descartó porque se deforma donde las personas ocupan poco espacio
  (FHL 0134, MtErie 0007). Decidido el 31 de octubre de 2026.
- **Partición por vuelo** (cada vuelo en una sola partición). Se define en la fase 3. MtErie 0007 (bajo el dosel, con
  la cámara de frente) va en validación.
- **Oclusión:** solo en las personas de la partición de prueba. Dos cajas por persona en cada imagen del par: cuerpo
  completo (estimado) y parte visible. λ = 1 − área visible / área completa.
- **Niveles** según λ en la imagen RGB: baja (0 a 35 %), moderada (35 a 70 %), severa (más de 70 %).
- **Configuración base:** 100 épocas, imagen de 640, lote 16 (bajar si no entra en 8 GB; el mismo para los tres),
  optimizador y tasa de aprendizaje por defecto de Ultralytics para YOLO26 (registrar cuáles fueron).
- **Métricas:** recall, precisión (umbral de confianza 0.5), F2 y mAP@0.5, por nivel de oclusión, con script propio
  sobre pycocotools. Al evaluar un nivel, las personas de los otros niveles se marcan como ignoradas.
- **Prueba estadística:** McNemar (statsmodels) entre modelos dentro de cada nivel, corrección de Bonferroni, α = 0.05.

## Estructura del repositorio

```
configs/     yaml de datasets y de entrenamiento
scripts/     código de cada fase
data/        datos procesados (fuera de git)
reports/     tablas, figuras, resúmenes y bitácora
runs/        salidas de entrenamiento (fuera de git)
docs/        reglas de anotación y notas
```
