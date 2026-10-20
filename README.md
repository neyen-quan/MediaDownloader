# MediaDownloader

Aplicación independiente para Windows 10/11 x64, con interfaz en español.
No tiene relación técnica con PhotoBatch. La compresión de imágenes queda fuera de esta versión.

**Distribución:** ZIP portable con `MediaDownloader.exe` y sus dependencias,
generado mediante GitHub Actions. El workflow solo entrega el artefacto después
de comprobar el arranque del ejecutable, los motores y el actualizador en Windows.
Ver [VERIFICACION.md](VERIFICACION.md) para los resultados y las pruebas pendientes en una PC.

## Descargar y abrir

1. Descargá [MediaDownloader-1.0.0-Windows-x64.zip](https://github.com/neyen-quan/MediaDownloader/releases/download/v1.0.0/MediaDownloader-1.0.0-Windows-x64.zip).
   Los archivos **Source code** de GitHub son el código fuente, no el programa.
2. Extraé **todo el ZIP portable** en una carpeta propia. Abrí `MediaDownloader.exe`.
   Conservá `_internal`, FFmpeg y el actualizador junto al ejecutable.
3. No se necesita instalar Python, FFmpeg ni herramientas de desarrollo.

[Versión publicada y checksum](https://github.com/neyen-quan/MediaDownloader/releases/tag/v1.0.0)
· [Compilación y pruebas aprobadas](https://github.com/neyen-quan/MediaDownloader/actions/runs/39501504910).

También está en **Actions → Windows portable → una ejecución exitosa**, artefacto
**MediaDownloader-Windows-x64**. GitHub envuelve esos artefactos en otro ZIP;
adentro está el ZIP portable completo y su checksum.

Los tags `v*` publican el mismo artefacto probado en GitHub Releases. La ausencia de
artefacto o un workflow rojo significa que la compilación no pasó la verificación.
No distribuyas un ZIP de fuentes como si fuera el programa.

## Uso

- Pegá un enlace público de una publicación/reel/carrusel de Instagram o un video
  de TikTok. Tocá **Analizar**.
- Los elementos aparecen en su orden, incluidas fotos y videos mezclados.
  Seleccioná una fila y tocá **Cargar previsualización**. La primera se carga
  automáticamente. Play/Pausa reproduce el video con audio.
- Marcá uno, varios o todos; elegí una carpeta y guardá el visible, los marcados,
  todos o los marcados como ZIP. Los nombres `001`, `002`, etc. mantienen el orden
  original incluso si solo elegís algunos. No se reemplazan archivos existentes.
- Se recuerda la carpeta. Las tareas de red trabajan fuera del hilo de interfaz;
  **Cancelar** detiene los procesos y conserva las descargas ya completadas.
- Los videos se cargan completos para previsualizarlos; esto puede usar tiempo y
  espacio temporal. El caché de previsualización se elimina al cerrar.

### Motores y calidad

`gallery-dl` enumera Instagram, incluyendo carruseles mixtos. Las fotos se guardan
tal como las entrega la plataforma. Los MPD/DASH de Instagram pasan a `yt-dlp`, que
elige las mejores representaciones disponibles. `yt-dlp` también analiza y descarga
TikTok, exigiendo una pista de audio para considerar exitosa esa descarga.

FFmpeg combina o cambia el contenedor **sin recodificar**, sin ampliar resolución
y sin compresión de imágenes. Los videos procesados se guardan como MKV para
conservar los códecs disponibles. La selección no limita resolución ni bitrate.
La calidad realmente accesible depende de la publicación, la plataforma, la IP y
la sesión; el programa no puede inventar calidad ni asegurar acceso sin sesión.
Las imágenes se escalan solo en pantalla para previsualizarlas, sin modificar el archivo.

No hay Snapinsta, Snaptik, servidores propios ni intermediarios de descarga.

### Sesión local opcional

**Sesión local** importa un `cookies.txt` Netscape previamente exportado desde tu
navegador. No se solicitan contraseñas ni se instala un navegador automatizado.
La copia permanece en `%LOCALAPPDATA%\MediaDownloader\cookies.txt`; las cookies
solo se envían a sus dominios correspondientes mediante los motores locales.
**Quitar sesión** elimina la copia. Las cookies son sensibles: no las compartas.

Las plataformas pueden exigir sesión incluso para contenido público. Las cookies
no evitan CAPTCHA, bloqueos de IP, límites regionales ni permisos; pueden vencer.
No se garantiza poder descargar cualquier enlace público en cualquier momento.

## Actualización y recuperación

**Actualizar programa** recibe el ZIP portable completo de una versión nueva.
No es una descarga automática ni un parche binario diferencial. Comprueba:

- Identidad `MediaDownloader`, esquema y versión del manifiesto.
- Inventario exacto y SHA-256 de todos los archivos.
- Ausencia de rutas absolutas, `..`, ADS, nombres reservados Windows, enlaces,
  cifrado, duplicados y colisiones de mayúsculas/minúsculas.
- Límites de 20.000 archivos y 4 GiB descomprimidos.

El helper independiente espera el cierre del proceso, prepara los archivos y
conserva la instalación anterior en `<carpeta>.previous`. Ejecuta el programa nuevo
en modo de prueba de arranque; ante fallo o timeout vuelve a la copia anterior.
La interfaz ofrece **Recuperar versión anterior**. Si no abre, cerrá el programa y
ejecutá `Recuperar version anterior.cmd`. Un registro transaccional permite
recuperar un cambio de carpetas interrumpido. Si falta la carpeta principal tras
un corte, el recuperador también funciona desde la carpeta `.previous`.

Configuración y sesión viven en el perfil del usuario; descargas, archivos
personales dentro del portable y configuración se conservan. Un conflicto entre
un archivo personal y un nuevo archivo del programa impide actualizar hasta que
se mueva el archivo personal. Elegí preferentemente una carpeta de descargas
separada. Dejá espacio para la versión nueva, la copia anterior y temporales.

**Los hashes prueban integridad, no autenticidad del editor.** Usá solo paquetes de
una fuente confiable. El ejecutable no incluye firma Authenticode. No se requiere
desactivar SmartScreen ni el antivirus.

## Desarrollo

Python 3.12, FFmpeg y FFprobe en PATH. Solo quien desarrolla necesita estas herramientas.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python main.py
python -m pytest -q
```

En Linux sin escritorio: `QT_QPA_PLATFORM=offscreen`, `QT_MEDIA_BACKEND=ffmpeg`,
`QT_AUDIO_BACKEND=null`, `PULSE_SERVER=127.0.0.1`. En este contenedor también se
necesitan `LOCALAPPDATA` y `XDG_CACHE_HOME` en rutas escribibles. Esto no configura
el audio del portable Windows ni reemplaza una prueba audible en una PC.

### Generar futuros ZIP compatibles

En Windows x64, con las dependencias anteriores:

```sh
python tools/build_windows.py
python tools/test_portable.py
```

`build_windows.py` descarga FFmpeg essentials desde el proveedor enlazado por
ffmpeg.org, verifica su SHA-256 publicado y conserva licencias y datos de origen.
Un fallo TLS o de checksum aborta. PyInstaller genera la aplicación y un helper
independiente; no se intenta compilar un EXE Windows desde Linux.

Para una nueva versión, cambiá `mediadownloader/__init__.py`, actualizá los motores
si corresponde, ejecutá las pruebas y generá el portable. Para empaquetar una
carpeta portable ya compilada:

```sh
python tools/make_update.py dist/MediaDownloader dist/MediaDownloader-1.0.1-Windows-x64.zip 1.0.1
```

No agregues cookies, configuración de usuarios ni descargas a la carpeta que se
empaqueta. El ZIP incluye `mediadownloader-update.json`; no lo escribas manualmente.
Ese mismo ZIP sirve como instalación inicial y como actualización.

El workflow `.github/workflows/windows.yml` ejecuta pruebas, compila, inicia el
EXE real, verifica ambos motores congelados y prueba actualización, recuperación
y rollback por un ejecutable inválido. Solo sube el portable si todo pasa.

Las pruebas de red locales usan HTTPS con certificado verificado y un servidor
controlado; la prueba multimedia genera un DASH real y compara hashes de pistas
comprimidas antes y después del mux. No confundirlas con acceso real a las plataformas.

## Límites de esta entrega

- Windows x64; no incluye instalador, macOS/Linux para usuarios finales ni firma digital.
- No incluye compresión Squoosh, perfiles completos, stories, lives ni descargas privadas.
- Los cambios de Instagram/TikTok pueden requerir nuevos motores mediante otro ZIP.
- Las pruebas de arranque automáticas no demuestran reproducción audible, SmartScreen,
  interacción de escritorio o acceso real desde tu conexión. Eso requiere una PC Windows.

Ver [LEEME.txt](LEEME.txt) para las instrucciones incluidas en el portable y
[THIRD_PARTY.md](THIRD_PARTY.md) para componentes y licencias.
