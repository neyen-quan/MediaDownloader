# Verificación y aceptación

La versión 1.0.7 publicada es la base existente con instalador incremental. La 1.0.8 agrega consulta de canal y descarga online reutilizando ese instalador.

## Evidencia automatizada

La suite local y Windows comprueba HTTPS, parsing y restricciones del canal, SHA-256, versiones y producto, cancelación, archivos incompletos, inventario permitido, preferencias persistentes, selección/ZIP y multimedia sin recodificar. Los builds Windows comprueban los EXE reales, Shell/AppUserModelID, instalación, recuperación y rollback. El canal y los assets se descargan y verifican antes de anunciar una publicación como lista.

El workflow en main es la fuente de resultados observados de cada entrega; un estado pendiente o fallido no acredita el paquete. La aceptación con la PC no se infiere de una prueba headless.

## Prueba pendiente con el usuario

1. Confirmar la versión instalada en su ventana (no se puede leer remotamente desde este entorno).
2. Aplicar la transición por ZIP local con el instalador existente.
3. Abrir Actualizar programa, consultar GitHub y comprobar que recuerda el canal.
4. Publicar una versión de prueba pequeña y usar Descargar e instalar desde la PC.
5. Confirmar reinicio y versión nueva; carpeta elegida, sesión, descargas, logo y anclado conservados.
6. Volver a consultar y comprobar «Ya tenés la última versión».

No dar la prueba de aceptación por terminada hasta que el usuario confirme estos resultados. Las cookies y los archivos de configuración no se piden ni se publican.
