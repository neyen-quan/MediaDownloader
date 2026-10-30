# MediaDownloader 1.0.18

- Conserva la compatibilidad de 1.0.17 con enlaces de publicaciones, carruseles y reels precedidos por el nombre de usuario.
- Da prioridad explícita al espacio de rutas `/stories/`, para conservar historias y destacadas sin confundir un nombre de usuario con el tipo de publicación.
- Añade regresiones para el caso ambiguo `/stories/p/123/` y para un ID de historia no válido.

Las versiones publicadas conservan sus bytes inmutables. La descarga real del carrusel reportado debe comprobarse en la PC del usuario con su sesión local.
