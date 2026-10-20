# Verificación de la implementación — 20 de octubre de 2026

## Windows: portable generado y verificado

**Ejecución aprobada:** https://github.com/neyen-quan/MediaDownloader/actions/runs/39501504910

**Portable publicado:** https://github.com/neyen-quan/MediaDownloader/releases/tag/v1.0.0
El mismo ZIP aprobado se recuperó desde Actions, se verificó con su SHA-256 y
se publicó sin recompilar. El tag `v1.0.0` apunta al commit compilado.

La descarga pública se comprobó nuevamente desde este entorno: **166.151.987 bytes**,
**1.715 archivos** en el manifiesto y SHA-256
`faf18e3d2372e1476717cce11b4f24461c28779342a01b2dfc6d3993c772d94f`.
Se inspeccionaron las cabeceras PE AMD64 de la aplicación, el actualizador, FFmpeg
y FFprobe: son ejecutables Windows x64 reales, no binarios Linux renombrados.

**Código compilado:** `a782a14dfb5e11c21538afd9570f6b8c580e0550`, en la rama
`codex/mediadownloader-v1`, conservando el commit original `1f3674e` en su historial.

- Suite en Windows 2022, Python 3.12: **51 aprobadas, 0 fallos, 0 omitidas**.
- Etapa multimedia posterior: **2 aprobadas, 0 fallos, 0 omitidas**. Comprueba
  conservación del manifiesto y una descarga DASH funcional con el EXE empaquetado.
- `MediaDownloader.exe`: arranque real de la ventana Qt en modo offscreen,
  inicialización multimedia y ejecución de gallery-dl / yt-dlp desde el propio EXE.
- `MediaDownloaderUpdater.exe`: aplicación real de una actualización a una copia
  portable, espera del cierre del proceso padre, comprobación del arranque nuevo,
  restauración y rollback automático ante un ejecutable deliberadamente inválido.
- FFmpeg y FFprobe incluidos: ejecutados y utilizados para generar, descargar y
  combinar H.264/AAC. Las pistas comprimidas se comparan contra los fragmentos
  originales mediante exportación elemental con `-c copy`; no se recodifican.
- Entregado por Actions: `MediaDownloader-1.0.0-Windows-x64.zip` y su SHA-256,
  dentro del artefacto `MediaDownloader-Windows-x64`.

Se corrigieron dos problemas de la prueba para Windows: el directorio de trabajo
de FFmpeg al generar fragmentos DASH y la comparación a través del demultiplexado
del MPD, que variaba según la versión de FFmpeg. La comparación final usa los
fragmentos comprimidos originales y conserva las comprobaciones de ambas pistas.
Las ejecuciones anteriores fallidas no se cuentan como aprobadas ni se entregaron.

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

## Acceso y límites de red

1. El bloqueo inicial de escritura GitHub **fue resuelto**. La rama y sus cambios
   se publicaron y se ejecutó Actions; no queda un bloqueo de subida del programa.
2. La API de GitHub sigue bloqueada por el proxy de este contenedor. Se verificaron
   los estados en la web y se recuperaron los diagnósticos por Git, conservados en
   ramas `ci/` independientes del código de la aplicación.
3. Los intentos desde este contenedor a Instagram/TikTok fallaron por la red
   restringida. Los intentos de extracción pública
   no obtuvieron medios. Esto **no verifica** descargas reales ni demuestra que esos
   enlaces funcionen o fallen desde una PC particular.

Se guardaron en el borrador del entorno `install_script`, `start_skill` y los
destinos adicionales de red de GitHub API, FFmpeg e Instagram/TikTok y sus CDN.
El script de instalación se ejecutó y comprobó. El borrador no aplica por sí solo
los cambios de red. Esa configuración de desarrollo no es necesaria para abrir
el portable Windows, que lleva sus dependencias incluidas.

## Prueba de aceptación en una PC Windows

El arranque y la actualización automatizados ya están verificados. Queda la
aceptación con escritorio, sonido y enlaces reales desde la conexión de la PC:

1. Extraer el ZIP completo y abrir el EXE sin Python instalado.
2. Analizar una foto, reel, carrusel de fotos y carrusel mixto de Instagram.
   Comprobar cantidad, orden y vista de cada elemento con enlaces vigentes propios.
3. Descargar TikTok y verificar audio audible y reproducción de la previsualización.
4. Guardar uno, varios y todos; abrir el ZIP y verificar nombres y contenido.
5. Cerrar/abrir y comprobar que recuerda la carpeta; probar sesión opcional si se exige.
6. Aplicar un ZIP de versión confiable, comprobar reinicio y recuperación anterior.
7. Comprobar advertencias SmartScreen, codecs de la PC, permisos y antivirus sin
   desactivar protecciones. Estos factores no los demuestra una prueba offscreen.

Hay un ZIP Windows real con ejecutables verificados en Actions. Las pruebas con
servicios locales y ventana offscreen no acreditan el acceso a cualquier enlace
público ni sustituyen la aceptación interactiva y audible en una PC particular.
