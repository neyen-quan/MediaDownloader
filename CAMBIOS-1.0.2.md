# MediaDownloader 1.0.2 — apertura sin terminal

- La interfaz usa un ejecutable Windows GUI, que no crea consola al abrirse.
- El motor se ejecuta en MediaDownloaderEngine.exe, dentro de la misma carpeta
  portable y con CREATE_NO_WINDOW. Sus salidas se redirigen a archivos internos.
- Ambos ejecutables comparten las dependencias para evitar duplicarlas.
- Se mantienen el diseño violeta, las descargas, la cancelación y el actualizador.

La prueba del portable comprueba el subsistema PE de ambos ejecutables, inicia
la interfaz y verifica las salidas de los motores ocultos. También se conserva
la prueba multimedia real con el motor empaquetado y la prueba de actualización.

Aplicar el ZIP completo desde Actualizar programa. Tras el reinicio, abrir siempre
MediaDownloader.exe. MediaDownloaderEngine.exe es un componente interno y no es
el acceso directo de la aplicación.

