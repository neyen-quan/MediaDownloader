# MediaDownloader 1.0.19

- Admite videos individuales de YouTube: watch, youtu.be, Shorts, embed y directos finalizados. Conserva el ID del video y elimina seguimiento, listas y marcas de tiempo para descargar el video completo una sola vez.
- Arrastrar un enlace del navegador a la ventana o al campo Enlace inicia el análisis automáticamente. Pegar y Analizar continúa disponible. Un enlace por vez; no se reemplaza una operación en curso.
- Reutiliza selección, previsualización, guardado individual y ZIP. Descarga la mejor calidad disponible con audio y combina en MKV sin recomprimir.
- Actualiza yt-dlp a 2026.10.26 e incluye yt-dlp-ejs 0.8.0 y Deno 2.9.8 en el portable. No requiere instalar runtimes ni descargar scripts por separado.
- No descarga canales/listas completas ni graba directos en curso o programados. No evita restricciones de acceso o sesión.
- Mantiene parches directos desde 1.0.16, 1.0.17 y 1.0.18, usando sus paquetes exactos publicados y el actualizador existente.

Pruebas: enlaces reales y variantes, rutas rechazadas, arrastre Qt, bloqueo durante análisis, selección de formatos separados y copia exacta de audio/video mediante yt-dlp y FFmpeg. Windows verifica además ejecutables, scripts EJS y Deno incluidos, aplicación de parches y recuperación. El ejemplo aportado se pudo analizar sin sesión; el servidor de archivos devolvió una página de bloqueo desde el entorno de desarrollo. La descarga real en la PC del usuario queda pendiente de su confirmación.
