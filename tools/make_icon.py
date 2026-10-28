"""Build a multiresolution Windows ICO from the exact in-app vector identity."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from mediadownloader.appearance import logo_image


def make_icon(destination):
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not logo_image(size).save(buffer, "PNG"):
            raise RuntimeError("No se pudo generar el icono")
        buffer.close()
        images.append((size, bytes(data)))
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    payload = bytearray()
    for size, data in images:
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                                     1, 32, len(data), offset))
        payload.extend(data)
        offset += len(data)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(directory + payload)
    return destination


if __name__ == "__main__":
    make_icon(ROOT / "build" / "branding" / "MediaDownloader.ico")

