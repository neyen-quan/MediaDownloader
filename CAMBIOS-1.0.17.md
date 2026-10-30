# MediaDownloader 1.0.17

- Corrige el rechazo local de enlaces de Instagram con un nombre de usuario antes de `/p/`, `/reel/`, `/reels/` o `/tv/`.
- Normaliza esos enlaces al formato canónico, preserva mayúsculas, guiones y guiones bajos del código de publicación, y quita parámetros de seguimiento y `img_index`.
- El carrusel se analiza completo y conserva su orden, incluidas las fotos y videos mezclados.
- Mantiene historias, destacadas, sesión, datos y actualizador existentes; no agrega dependencias.

Verificación: regresión del enlace reportado, compatibilidad con el extractor fijado, rechazo de rutas y hosts no permitidos, y análisis completo de un carrusel de prueba. La descarga del contenido real desde Instagram queda pendiente de la sesión y acceso de la PC del usuario; las fixtures no acreditan ese acceso.
