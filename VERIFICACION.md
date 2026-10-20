# Verificación de la implementación — 20 de octubre de 2026

## Ejecutado en este entorno Linux

- Escritura de un archivo en el checkout, ejecución con Python y eliminación: OK.
- Lectura Git del HEAD remoto: OK, repositorio inicialmente con un README.
- Entorno virtual, dependencias fijadas y FFmpeg/FFprobe de desarrollo: disponibles.
- Suite local: **51 pruebas aprobadas**, sin pruebas omitidas en esa ejecución.
  Incluye GUI con motores simulados, selección y ZIP desde la interfaz, persistencia,
  descarga HTTPS real local con certificado verificado, carrusel mixto y cancelación.
- Pipeline DASH local con yt-dlp y FFmpeg reales: video H.264 y audio AAC presentes;
  hashes de ambas pistas comprimidas iguales antes/después. Sin recompresión.
- Actualizador: manifiesto, hashes, rutas peligrosas, archivo extra, colisiones,
  enlaces simbólicos, actualización, restauración, recuperación de interrupción,
  rollback por prueba de arranque fallida y conservación de archivos personales.
- Arranque de la interfaz Qt desde fuentes en modo offscreen: OK con backend de
  audio apto para este contenedor sin escritorio. El primer intento con detección
  automática de PipeWire falló; no se usa esa configuración para validar aquí.
- Empaquetado PyInstaller de comprobación para Linux: generado; arranque de Qt y
  entrada de gallery-dl / yt-dlp ejecutadas. Se repitieron las dos pruebas de
  pipeline multimedia usando el motor DASH empaquetado: ambas aprobadas.
  **No es el portable Windows.**

## Bloqueos observados

1. Git push devuelve `403 Permission to neyen-quan/MediaDownloader.git denied to hincharc`.
   Los cambios no se pueden subir con la conexión GitHub actual. Se requiere dar
   permiso de escritura a esa cuenta o reconectar una cuenta autorizada; la conexión
   debe permitir publicar archivos de workflows. No se necesitan tokens en el chat.
2. Las solicitudes a `www.instagram.com`, `www.tiktok.com` y `api.github.com` fallan
   con `ProxyError` en la red restringida actual. Los intentos de extracción pública
   no obtuvieron medios. Esto **no verifica** descargas reales ni demuestra que esos
   enlaces funcionen o fallen desde una PC particular.

Se guardaron en el borrador del entorno `install_script`, `start_skill` y los
destinos adicionales de red de GitHub API, FFmpeg e Instagram/TikTok y sus CDN.
El script de instalación se ejecutó y comprobó. Ese guardado no aplica cambios
de red, no sube código a GitHub y no publica el entorno: hace falta revisar y
guardar en la configuración del entorno y luego publicarlo. El acceso real se
debe volver a comprobar después de aplicar esos cambios.

## Preparado pero todavía NO ejecutado en Windows

El workflow Windows compila el portable completo y genera el ZIP compatible. Antes
de publicar un artefacto exige: pruebas esenciales, arranque de fuente, arranque
del EXE, ejecución de ambos motores desde el EXE, actualización externa esperando
el cierre del proceso, restauración, rollback ante un EXE inválido y otra prueba
multimedia con FFmpeg incluido.

**No hay un EXE Windows ni ZIP portable validado en esta entrega local.** No se pudo
iniciar Actions por el bloqueo de publicación. Los scripts de pruebas Windows son
implementación pendiente de ejecución, no evidencia de un resultado exitoso.

## Prueba de aceptación en una PC Windows

Después de una ejecución verde de Actions:

1. Extraer el ZIP completo y abrir el EXE sin Python instalado.
2. Analizar una foto, reel, carrusel de fotos y carrusel mixto de Instagram.
   Comprobar cantidad, orden y vista de cada elemento con enlaces vigentes propios.
3. Descargar TikTok y verificar audio audible y reproducción de la previsualización.
4. Guardar uno, varios y todos; abrir el ZIP y verificar nombres y contenido.
5. Cerrar/abrir y comprobar que recuerda la carpeta; probar sesión opcional si se exige.
6. Aplicar un ZIP de versión confiable, comprobar reinicio y recuperación anterior.
7. Comprobar advertencias SmartScreen, codecs de la PC, permisos y antivirus sin
   desactivar protecciones. Estos factores no los demuestra una prueba offscreen.

El estado es implementación local verificada con bloqueos externos para completar
la entrega Windows, no una aplicación final declarada lista para uso en tu PC.
