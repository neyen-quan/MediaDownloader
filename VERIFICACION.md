# Verificación y aceptación

## Reparador 1.0.15 bloqueado en .older

La captura del usuario muestra WinError 5 en la carpeta `.older`, antes del intercambio. No identifica qué proceso o política de Windows retiene la carpeta; no se atribuye a un programa concreto. 1.0.16 elimina la limpieza obligatoria previa e incorpora pruebas de directorio bloqueado antes de preparar, registro legacy prepared, intercambio con retiro único, rollback y operaciones posteriores con limpieza todavía pendiente. Sigue siendo necesaria la prueba en la PC del usuario; no se afirma que ya haya instalado la versión nueva.

## Intento 1.0.13 → 1.0.14

El usuario corrigió la observación anterior: la instalación sigue en 1.0.13. Las destacadas funcionan en esa versión, lo que no acredita haber instalado 1.0.14. La captura ubica el error en la preparación de respaldo. No hay traceback local disponible y no se ha identificado el archivo exacto. 1.0.15 prueba fallos reproducibles de preparación con respaldos de solo lectura en Windows, temporales antiguos, helper entrante verificado, reparación online y diagnóstico de archivo/etapa. Su aceptación en esa PC queda pendiente.

## Incidencia de finalización observada en 1.0.13

El usuario mostró un aviso PermissionError del actualizador y luego la ventana de MediaDownloader 1.0.13 abierta. Esto acredita el arranque de esa versión, pero no identifica el archivo bloqueado ni confirma todavía la descarga real de destacadas o la conservación completa de datos.

Se reprodujo en pruebas el caso de una instalación aplicada y verificada cuyo helper informa fracaso al no poder borrar el respaldo antiguo. El aviso de las versiones anteriores solo guardaba el tipo de excepción y no permite atribuir con certeza la captura a una operación concreta. La corrección 1.0.14 separa confirmación, limpieza y apertura final, conserva el estado confirmado y mejora el diagnóstico. La prueba de aceptación en la PC sigue siendo necesaria.

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

## Entregas verificadas del canal online

- 1.0.8: Actions 40735767504 aprobado, 98 pruebas Windows, pruebas del portable y multimedia, parche desde 1.0.7 y canal público verificados. Parche: 33.647.768 bytes, SHA-256 `8e71c76fcdd46c6690ced9ed1b8f796c99b7508eecb06f42a99ba4c4b6ac2c90`.
- 1.0.9: Actions 40759332321 aprobado, versión de prueba online desde 1.0.8. Parche: 33.633.172 bytes, SHA-256 `858f949054f2bc2c5c8357cba35a61748289bba132079100e5d16cc802da9fd7`.
- Ambas releases contienen portable completo, parche incremental, checksums y latest.json. Las pruebas descargan assets y comprueban SHA-256 antes de publicar el canal estable.
- La descarga independiente del parche 1.0.8 desde el canal público también pasó validación externa e inventario interno.
- La prueba de aceptación en la PC del usuario sigue pendiente; no se ha observado su versión instalada ni su reinicio/datos locales desde este entorno.
