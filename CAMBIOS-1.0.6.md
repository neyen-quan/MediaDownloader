# MediaDownloader 1.0.6

- Encabezado compacto con logo pequeño, nombre, versión y actualización. Se eliminan los textos promocionales.
- Enlace, Analizar, carpeta de destino y acceso a carpeta comparten una sola fila.
- El listado conserva las miniaturas y ahora muestra un tick oscuro sobre fondo verde para los elementos marcados.
- Los botones de descarga quedan debajo del listado, liberando altura para el visor.
- El visor utiliza la altura disponible de la ventana, sin el antiguo límite de 480 px. El marco es vertical: fotos entre 3:4 y 9:16 según sus proporciones; videos 9:16. Mantiene zoom, ajuste y arrastre para fotos, carga automática y geometría independiente de la resolución original.
- Se conserva la sesión local y la descarga de originales sin recompresión.

Verificación local: geometría del visor 3:4 y 9:16, altura aprovechada a 1280×900, fila única de entrada/destino, ancho mínimo a 980×760 y las regresiones previas de previsualización/descarga/actualización. Inspección visual de las ventanas a 980×760, 1280×900 y 1280×1024. El portable Windows se compila y comprueba mediante GitHub Actions.

