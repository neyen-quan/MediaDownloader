# Componentes incluidos

La aplicación conecta directamente con Instagram y TikTok mediante motores locales.
No usa Snapinsta, Snaptik ni servicios de descarga intermediarios.

- PySide6 / Qt: LGPLv3 / GPLv3 / licencias de Qt. https://www.qt.io/licensing/
- gallery-dl: GPL-2.0-or-later. https://github.com/mikf/gallery-dl
- yt-dlp: Unlicense para el proyecto; algunas dependencias tienen licencias propias. https://github.com/yt-dlp/yt-dlp
- Requests y dependencias: consultar sus licencias incluidas. https://requests.readthedocs.io/
- FFmpeg/FFprobe: build essentials GPL de Gyan, proveedor listado por FFmpeg.
  https://www.gyan.dev/ffmpeg/builds/ y https://ffmpeg.org/download.html
- PyInstaller: GPL con excepción para los ejecutables generados. https://pyinstaller.org/

El portable conserva metadatos de licencias de las distribuciones instaladas en
`licenses/`, los avisos de FFmpeg y su SHA-256 de origen. Las bibliotecas Qt se
distribuyen dinámicamente dentro de `_internal/`; no se modifica su código.
Las fuentes y recetas de los componentes están en los proyectos enlazados.
La construcción no descarga ejecutables con verificación TLS deshabilitada.

