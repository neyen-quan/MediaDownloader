# MediaDownloader

Aplicación portable Windows 10/11 x64, en español, para fotos, carruseles, reels de Instagram y videos TikTok. Python 3.12 + PySide6/Qt; motores locales gallery-dl y yt-dlp, FFmpeg/FFprobe incluidos. No usa sitios de descarga intermediarios ni depende técnicamente de PhotoBatch.

## Instalar y actualizar

Instalación nueva: descargar el archivo `MediaDownloader-VERSION-Windows-x64.zip` de [Releases](https://github.com/neyen-quan/MediaDownloader/releases/latest), extraerlo completo y abrir MediaDownloader.exe. No se necesita Python.

Desde 1.0.8: **Actualizar programa → Buscar actualizaciones → Descargar e instalar**. La pantalla muestra versión instalada/disponible, permite guardar una URL de canal GitHub y ofrece **Instalar ZIP local**. El canal predeterminado es:

`https://github.com/neyen-quan/MediaDownloader/releases/latest/download/latest.json`

Transición desde 1.0.7: descargar el parche `MediaDownloader-1.0.8-from-1.0.7-patch.zip` e instalarlo con el botón Actualizar programa existente, sin extraer el ZIP. Desde ahí se usa la actualización online. Si la versión instalada es anterior, instalar primero 1.0.7 o el paquete completo compatible.

Los parches identifican la versión base. Si no hay un parche directo, el programa lo informa; nunca descarga el paquete completo de forma silenciosa. Paquetes completos y parches se publican por separado. Una modificación de dependencias puede aumentar el tamaño del parche.

## Uso y datos

Pegar enlace público → Analizar → elegir elementos → guardar visible/selección/todos/ZIP. Previsualizaciones automáticas, miniaturas compactas, visor vertical y zoom para fotos. Los originales se guardan sin recomprimir; FFmpeg combina audio/video sin recodificar y puede producir MKV.

Configuración, canal y sesión opcional viven en `%LOCALAPPDATA%/MediaDownloader`; las descargas quedan en la carpeta elegida. La sesión se importa desde un cookies.txt Netscape local. Nunca subir ese archivo al repositorio ni compartirlo. Las plataformas pueden exigir sesión, limitar consultas o cambiar sus motores.

## Integridad y recuperación

El canal solo admite HTTPS de GitHub y redirecciones a sus hosts de archivos; no recibe cookies de Instagram/TikTok. Se comprueban producto, versiones, tamaño y SHA-256 externo del ZIP, inventario interno, hashes, rutas permitidas y base instalada exacta. Se pide confirmación antes de instalar.

Se reutiliza un único actualizador: prepara una instalación en staging con los archivos locales sin cambios y el payload incremental, verifica el resultado y realiza un intercambio transaccional. Conserva una copia `.previous`, prueba el arranque y revierte si falla. **Recuperar versión anterior**, o `Recuperar version anterior.cmd` si la interfaz no abre. No mover carpetas durante el proceso. Se requiere espacio local para temporales y respaldo aunque el ZIP descargado sea pequeño.

Se conservan configuración, sesión, descargas, nombre/ruta del ejecutable, icono y AppUserModelID de Windows. Los accesos y anclados existentes siguen apuntando a la misma ubicación. Las pruebas automáticas de Shell no sustituyen la comprobación del anclado en la PC del usuario.

SHA-256 verifica integridad, no una firma del editor; no hay Authenticode. Usar un canal confiable.

## Desarrollo y compilación

Ver [BUILD.md](BUILD.md), [ACTUALIZACIONES.md](ACTUALIZACIONES.md) y [VERIFICACION.md](VERIFICACION.md). Código, pruebas y recursos están en main. Logo vectorial en mediadownloader/appearance.py; tools/make_icon.py genera el ICO multirresolución usado por el EXE y la barra de tareas.

Un commit en **main** con versión nueva publica automáticamente tag, release, portable completo, parche y latest.json después de pruebas Windows. Un commit con el mismo número ya etiquetado no genera otra release. La recuperación usa **Actions → Publicar MediaDownloader → Run workflow → release_tag**, desde main, para ejecutar las herramientas actuales sobre el código del tag. No crear releases manuales para el flujo normal.

## Licencia

Código propio: GPL-3.0-or-later, copyright 2026 neyen-quan. Ver LICENSE. Componentes y licencias en THIRD_PARTY.md; el portable incluye sus avisos en licenses/. Las licencias de terceros se conservan.
