# Actualizaciones incrementales desde 1.0.7

## Uso

1. Instalar 1.0.7 una vez con el ZIP completo desde Actualizar programa. No reemplazar archivos a mano.
2. En versiones siguientes descargar el ZIP cuyo nombre termine en `from-VERSION-patch.zip`, correspondiente a la versión instalada, y seleccionarlo desde el mismo botón.
3. Instalar los parches en orden. El programa rechaza una base distinta o modificada. Para reparar una instalación o saltar versiones se conserva el ZIP completo.

La sesión, la carpeta elegida y las descargas se conservan. Recuperar versión anterior funciona también después de un parche. Se necesita espacio local para preparar y respaldar una instalación completa, aunque la descarga sea pequeña. Si se actualizan librerías pesadas o FFmpeg, el parche puede ser mayor.

## Generación y publicación

- Aumentar la versión en mediadownloader/__init__.py en cada entrega.
- Windows Actions descarga la base de la última release compatible, conservada de forma persistente en GitHub Releases.
- Se mantienen FFmpeg y FFprobe de esa base por defecto; una actualización deliberada puede usar MEDIADOWNLOADER_REFRESH_FFMPEG=1.
- El portable completo siempre se construye y verifica para instalaciones nuevas y reparaciones. A partir de 1.0.8 se genera además un ZIP incremental y se prueba su aplicación y recuperación usando el actualizador Windows real.
- El archivo pequeño se publica por separado como artefacto MediaDownloader-parche y como asset `*-patch.zip` de la release. Al usuario que actualiza se le debe dar ese enlace, no el ZIP completo.
- No sobrescribir releases ya publicadas: los parches dependen de sus hashes exactos. No generar parches contra una recompilación aproximada de la base.
- Generación manual: `python tools/make_update.py NUEVO_PORTABLE PARCHE.zip NUEVA_VERSION --base BASE_EXTRAIDA`.

El schema 2 contiene hashes de la base y del destino completos, pero transporta solo archivos nuevos o diferentes. Los archivos eliminados se deducen de la diferencia de inventarios. El instalador verifica la base, reconstruye en staging, conserva archivos personales y usa el mismo intercambio transaccional, prueba de arranque y recuperación que el paquete completo. Los hashes verifican integridad; no son firmas de autenticidad.


## Canal online desde 1.0.8

El flujo normal es Actualizar programa → Buscar actualizaciones → Descargar e instalar. Se guarda la URL de canal en settings.json junto a las preferencias existentes; el ZIP local queda disponible en el mismo diálogo.

Un commit en main con una versión nueva inicia el workflow. El mismo número con tag existente no vuelve a publicar. La release se prepara como borrador con todos sus archivos, se descargan y verifican hashes y luego se publica latest.json como canal estable. El paquete completo permanece separado.

Desde 1.0.12, el pipeline genera y comprueba parches directos desde las dos versiones estables anteriores que admiten el canal online. Cada base se descarga desde su ZIP publicado exacto; su actualizador instalado aplica el parche y el nuevo comprueba la recuperación. Para 1.0.12 se cubren 1.0.10 y 1.0.11 sin instalar el paquete completo.

Recuperación: ejecutar el workflow actual desde main mediante workflow_dispatch y release_tag. El código corresponde al tag; las herramientas de compilación/publicación se toman de main, evitando repetir un workflow obsoleto. Una release completa existente se verifica y no se sobrescribe. Una release incompleta puede completarse sin crear otra con el mismo tag.

## Progreso y desbloqueo desde 1.0.10

La descarga muestra porcentaje, MiB recibidos, tiempo y falta de avance. La verificación tiene progreso por etapa y la instalación abre una ventana nativa que permanece visible hasta el reinicio o el error/recuperación.

Las versiones 1.0.8/1.0.9 podían perder la instalación pendiente si el hilo terminaba mientras se confirmaba. Si no reinician después de confirmar, cerrar el programa y abrir el asset `MediaDownloader-Repararactualizador.exe` de la release 1.0.10. Elegir el MediaDownloader.exe instalado y el ZIP incremental correspondiente a su versión, confirmar y esperar. Es el mismo instalador, con verificación, respaldo y recuperación; no un segundo mecanismo de actualización. Usar solo el EXE y los ZIPs publicados en el repositorio oficial.

## Finalización desde 1.0.14

Las versiones anteriores podían mostrar PermissionError tras instalar y comprobar el arranque, al eliminar un respaldo antiguo o intentar reiniciar el programa. El mensaje genérico no identificaba la operación y podía contradecir la versión que luego abría.

El actualizador registra ahora una fase committed después de comprobar el arranque. La limpieza posterior es opcional: los bloqueos temporales se reintentan, un respaldo pendiente conserva su manifiesto y la próxima ejecución vuelve a limpiarlo sin deshacer una instalación confirmada. Una falla anterior a la confirmación conserva la recuperación transaccional. No se borran carpetas desconocidas: incluso un respaldo parcialmente limpiado debe identificarse mediante un manifiesto válido del producto, salvo un directorio ya vacío.

Los registros de fallos incluyen la etapa y la excepción con archivo/código de Windows cuando esté disponible. Se guardan localmente y no se suben al repositorio. La imposibilidad de volver a abrir el EXE después de instalar se comunica como tal, sin afirmar que falló el reemplazo de archivos.

## Reparación de preparación y transición desde 1.0.15

El usuario confirmó que 1.0.13 continúa instalada tras intentar 1.0.14. La captura muestra la fase de conservación/preparación, no la limpieza posterior a instalar. El aviso antiguo no permite identificar el archivo bloqueado. No atribuir esa captura a una causa concreta sin evidencia adicional.

Se corrigen dos fallos reproducibles de preparación: eliminación de archivos de respaldo con atributo de solo lectura en Windows, y colisión con un temporal de registro antiguo de nombre fijo. Las violaciones persistentes de acceso siguen deteniendo la instalación, conservando la base y mostrando la operación/archivo exactos. La copia de archivos personales reintenta bloqueos temporales y no omite archivos inaccesibles en silencio.

La interfaz nueva prepara el helper incluido en el ZIP verificado y comprueba su hash y versión base antes de ejecutarlo. Un helper no modificado se verifica contra el inventario de destino. La recuperación continúa usando el helper instalado. Desde la 1.0.13 el código de interfaz nuevo aún no existe: se usa una sola vez el reparador independiente actual, que ahora descarga el parche compatible del canal oficial sin pedir un ZIP manual. Luego se retoma el botón habitual. El programa y los datos del usuario no se sustituyen por una instalación completa.

## Carpeta de respaldo bloqueada desde 1.0.16

El reparador 1.0.15 seguía limpiando `.older` antes del intercambio. Un WinError 5 en esa carpeta bloqueaba la instalación. Se elimina esa dependencia: si el nombre fijo está ocupado o inaccesible, `.previous` se aparta a un hermano `.older-UUID`, registrado antes de moverlo. No se toca la carpeta antigua antes de comprobar el nuevo arranque. Los registros previos sin ese campo siguen usando el sufijo fijo; los nombres nuevos deben coincidir exactamente con el nombre de instalación y 32 dígitos hexadecimales. Se rechazan rutas externas, relativas o ajenas.

La limpieza solo ocurre después de confirmar el arranque, siempre verifica que cada carpeta pertenezca al producto, conserva las carpetas desconocidas y puede quedar pendiente entre actualizaciones sin revertir una instalación sana. Se prueban interrupciones y recuperación con los nombres nuevos, así como la recuperación de registros antiguos. En Windows se abre un directorio sin compartir DELETE antes de actualizar; tanto fuentes como reparador compilado deben instalar, recuperar y permitir otra operación mientras continúa el bloqueo.

Esta entrega mantiene un parche directo desde 1.0.13 además de las dos bases más recientes, descargadas de las releases exactas. Se entrega un reparador con versión en el nombre para distinguirlo del anterior; el reparador antiguo no incorpora esta corrección automáticamente.
