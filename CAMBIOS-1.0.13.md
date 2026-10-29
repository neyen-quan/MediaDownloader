# MediaDownloader 1.0.13

- Acepta enlaces de historias destacadas de Instagram con formato `/stories/highlights/ID/`, rechazados en 1.0.12.
- Consulta el conjunto indicado por su ID y muestra sus fotos y videos en orden para previsualizar, seleccionar y guardar individualmente o en ZIP.
- Reutiliza la sesión local importada y los motores existentes, incluido DASH cuando Instagram lo ofrece. No agrega dependencias.
- Mensajes específicos para destacadas eliminadas, vacías o no accesibles. Las historias antiguas guardadas en destacadas no se consideran vencidas por su edad.
- Pruebas con el extractor real fijado y respuestas API controladas: ID de destacada, conjunto mixto completo, enlaces compartidos/móviles y sesión requerida. Una descarga contra Instagram real requiere la sesión local y contenido accesible del usuario.
- Actualización online incremental desde 1.0.11 y 1.0.12, con bases publicadas exactas y conservación de configuración, sesión y descargas.
