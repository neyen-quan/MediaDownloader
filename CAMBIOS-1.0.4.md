# MediaDownloader 1.0.4

- Corrige un falso error de carrusel incompleto en publicaciones y reels con música. gallery-dl incluye la pista de audio adicional en su contador: ahora se enumera para validar la respuesta y se excluye de la lista de fotos/videos. El análisis no descarga esa pista.
- Conserva la comprobación de respuestas realmente incompletas e informa la cantidad recibida y esperada.
- Distingue los rechazos de sesión y los límites temporales de consultas al leer errores de Instagram.
- Conserva la sesión local ya importada, las descargas, el diseño y el icono.

Validación: regresiones ejecutan la enumeración real de gallery-dl con datos sintéticos de carrusel/reel con música y con una foto faltante. Las pruebas locales no sustituyen la comprobación del enlace real con la sesión local del usuario.

