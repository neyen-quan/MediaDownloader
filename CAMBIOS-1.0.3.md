# MediaDownloader 1.0.3 — icono del acceso anclado

La ventana de Windows registra explícitamente su nombre, identidad, comando de
apertura e icono para los accesos de la barra de tareas. Estos datos se establecen
antes de mostrar la ventana y antes de asignar la identidad a nivel de ventana.
Se incluye MediaDownloader.ico en la carpeta del programa y en el manifiesto.

La prueba de Windows abre el EXE con una ventana nativa y lee las propiedades
reales del Shell para comprobar nombre, destino e icono. Se mantienen las pruebas
de apertura sin consola, motores, multimedia y actualización/recuperación.

Tras actualizar: desanclar el acceso que tiene el icono de Python, abrir
MediaDownloader.exe y volver a anclar la ventana. Los accesos ya creados por
Windows conservan su configuración hasta que se vuelven a crear.

Las propiedades del Shell se verifican automáticamente. El aspecto final de un
acceso anclado depende también del Explorador y de su caché en la PC del usuario;
la prueba automatizada no reemplaza esa comprobación visual.

