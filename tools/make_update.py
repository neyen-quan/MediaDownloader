"""Build full portable/update ZIP: python tools/make_update.py dist/MediaDownloader out.zip 1.0.1"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mediadownloader.updater import build_package, build_delta

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('portable')
    parser.add_argument('output')
    parser.add_argument('version')
    parser.add_argument('--base', help='Instalación base extraída del ZIP publicado; genera solo cambios')
    args = parser.parse_args()
    result = (build_delta(args.base, args.portable, args.output, args.version) if args.base else
              build_package(args.portable, args.output, args.version))
    print(f"Paquete {result['version']}: {len(result['files'])} archivos verificados.")
