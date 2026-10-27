# MediaDownloader 1.0.7 — transición a parches incrementales

- Acepta ZIPs de archivos modificados (schema 2), además de los portables completos anteriores.
- Comprueba versión y hashes de la base antes de instalar y verifica el inventario reconstruido antes del intercambio.
- Conserva respaldo, recuperación ante arranque fallido, archivos personales y sesión local.
- Publicación persistente en GitHub Releases para conservar bases exactas; generación y prueba automática de los futuros parches en Windows.
- FFmpeg se reutiliza desde la base publicada para evitar incluirlo de nuevo en cambios de interfaz.

Esta versión se instala con un ZIP completo una sola vez. Desde la siguiente, usar el archivo `from-VERSION-patch.zip` correspondiente a la versión instalada. Véase ACTUALIZACIONES.md.
