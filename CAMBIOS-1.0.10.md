# MediaDownloader 1.0.10

- Corrige la instalación pendiente perdida si la tarea terminaba durante el diálogo modal de confirmación. La regresión se verifica con un QMessageBox real y la finalización del hilo durante ese diálogo.
- Barra visible con porcentaje y MiB descargados; fases separadas de conexión, verificación del ZIP, validación de la base y preparación de archivos.
- Tiempo transcurrido y aviso de tiempo sin avance nuevo. Las fases sin porcentaje medible usan indicador de actividad.
- Ventana de instalación nativa Windows, sin nuevas dependencias pesadas: extracción, preparación, respaldo, instalación, prueba de arranque, recuperación y reinicio.
- Actualizador independiente opcional (mismo helper transaccional) para desbloquear 1.0.8/1.0.9 cuando su confirmación dejó la actualización pendiente. Solicita el EXE instalado y el ZIP local. No usa permisos de administrador ni cambia las preferencias.
- Parches directos desde 1.0.8 y 1.0.9. La sesión, los archivos y la identidad de Shell se conservan.
