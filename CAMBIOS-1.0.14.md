# MediaDownloader 1.0.14

- Corrige la finalización del actualizador: un bloqueo al limpiar un respaldo antiguo no convierte una instalación verificada en un supuesto fallo.
- Registra la instalación confirmada antes de la limpieza para no revertirla al retomar una operación pendiente.
- Reintenta bloqueos temporales de archivos durante el cambio de carpetas, la prueba de arranque, la limpieza y la apertura final.
- Conserva la identificación de respaldos parcialmente limpiados y vuelve a intentar su limpieza más adelante. La copia .previous sigue disponible.
- Distingue una instalación fallida de una instalación terminada cuya apertura automática fue bloqueada.
- Registra etapa, resultado y excepción detallada en el archivo local de errores del actualizador.
- Agrega pruebas de limpieza bloqueada, registro pendiente, recuperación posterior, error al confirmar y un bloqueo real de DLL mediante Win32.
