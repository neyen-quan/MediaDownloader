"""Build full portable/update ZIP: python tools/make_update.py dist/MediaDownloader out.zip 1.0.1"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mediadownloader.updater import build_package

if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Uso: python tools/make_update.py CARPETA_PORTABLE SALIDA.zip VERSION")
    result = build_package(*sys.argv[1:])
    print(f"Paquete {result['version']}: {len(result['files'])} archivos verificados.")
