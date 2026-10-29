# MediaDownloader 1.0.12

- Enlaces de historias de Instagram: historia puntual por ID o historias activas de una cuenta.
- Fotos y videos en la misma lista y visor, selección, descarga individual y ZIP existentes. Los videos con manifiesto DASH reutilizan el motor de máxima calidad y combinación sin recodificación.
- Reutiliza la sesión local. Explica si falta, venció, fue rechazada o la historia dejó de estar disponible. No incluye historias eliminadas/vencidas ni destacadas.
- Parches online directos desde 1.0.10 y 1.0.11, verificados contra las bases publicadas exactas; paquete completo separado.
- Pruebas con el extractor real fijado y respuestas API controladas: selección exacta del ID, fotos/videos mezclados, DASH, sesión sin vencimiento y errores sin exponer datos privados. La validación de una descarga real en Instagram requiere una historia accesible y la sesión local del usuario.
