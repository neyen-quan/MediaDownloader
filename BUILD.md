# Desarrollo y build reproducible

Requisitos de desarrollo: Python 3.12.10 x64 y dependencias fijadas en requirements-dev.txt. FFmpeg/FFprobe deben estar en PATH para las pruebas multimedia. Para crear el portable se requiere Windows x64; Linux solo permite desarrollar y ejecutar la suite, no generar un EXE Windows válido.

```sh
python -m venv .venv
# Windows: .venv/Scripts/activate; Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python main.py --smoke-test
```

Linux sin pantalla: QT_QPA_PLATFORM=offscreen, QT_AUDIO_BACKEND=null, QT_MEDIA_BACKEND=ffmpeg. La suite usa fixtures HTTPS, Qt y FFmpeg reales locales. No necesita sesiones ni cuentas de plataformas.

Windows: `python tools/build_windows.py`, `python tools/test_portable.py`. Los builds de Actions conservan los FFmpeg de la base publicada y las licencias. PyInstaller genera GUI sin consola, motor con salida redirigida oculta y actualizador independiente. Los motores y Qt vienen con el portable.

La identidad gráfica se genera desde mediadownloader/appearance.py y tools/make_icon.py; MediaDownloader.spec está versionado. No se necesitan recursos de una carpeta privada externa.

Para publicar, incrementar mediadownloader/__init__.py y subir los cambios a main. El pipeline usa la base publicada exacta, crea el parche y su canal, aplica y recupera el parche con el helper Windows, verifica las descargas publicadas y publica el canal al final. No usar recompilaciones aproximadas como base. No editar una release completa ya publicada.

Auditoría previa: `python tools/audit_source.py`. Nunca agregar datos de usuario, cookies, credenciales, claves, perfiles, descargas o builds al repositorio. Revisar también ejemplos y documentación. Los hashes, certificados y claves de las pruebas HTTPS se generan temporalmente y no son credenciales reales.
