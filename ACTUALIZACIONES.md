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

Recuperación: ejecutar el workflow actual desde main mediante workflow_dispatch y release_tag. El código corresponde al tag; las herramientas de compilación/publicación se toman de main, evitando repetir un workflow obsoleto. Una release completa existente se verifica y no se sobrescribe. Una release incompleta puede completarse sin crear otra con el mismo tag.

## Progreso y desbloqueo desde 1.0.10

La descarga muestra porcentaje, MiB recibidos, tiempo y falta de avance. La verificación tiene progreso por etapa y la instalación abre una ventana nativa que permanece visible hasta el reinicio o el error/recuperación.

Las versiones 1.0.8/1.0.9 podían perder la instalación pendiente si el hilo terminaba mientras se confirmaba. Si no reinician después de confirmar, cerrar el programa y abrir el asset `MediaDownloader-Repararactualizador.exe` de la release 1.0.10. Elegir el MediaDownloader.exe instalado y el ZIP incremental correspondiente a su versión, confirmar y esperar. Es el mismo instalador, con verificación, respaldo y recuperación; no un segundo mecanismo de actualización. Usar solo el EXE y los ZIPs publicados en el repositorio oficial.
