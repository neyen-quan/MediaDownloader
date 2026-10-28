# MediaDownloader 1.0.5

- Carga automática de las fotos y miniaturas en segundo plano al analizar un enlace. El video seleccionado también se prepara automáticamente, sin iniciar su reproducción.
- La selección de otro elemento ya no requiere pulsar Cargar previsualización. Si una consulta falla, aparece Reintentar y la cola continúa con los demás elementos.
- Panel de imagen estable: sus dimensiones ya no dependen del tamaño de la foto. Se elimina el crecimiento acumulativo al cambiar de elemento.
- Barra de zoom de 25% a 200%, inicio en 80%, botón Ajustar (100% del panel), y arrastre para mover la foto ampliada. El zoom solo afecta la visualización.
- Lista más estrecha, miniaturas de 32 px y filas compactas. Los controles de reproducción solo se muestran para videos.
- La cola mantiene la selección actual al finalizar una carga anterior, prioriza la nueva selección y se cancela antes de cerrar o actualizar. Las descargas conservan los originales sin recompresión.

Verificación local: pruebas de carga automática de seis imágenes grandes, estabilidad de geometría al cambiar repetidamente de foto, zoom, selección durante una carga y cierre con una previsualización pendiente. La compilación y las comprobaciones del portable Windows se ejecutan en GitHub Actions.

