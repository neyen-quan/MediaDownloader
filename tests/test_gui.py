import os
import struct
import time
import zipfile
import zlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name != "nt":
    os.environ.setdefault("PULSE_SERVER", "127.0.0.1")
    os.environ.setdefault("QT_AUDIO_BACKEND", "null")
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from mediadownloader.core import Media
from mediadownloader.gui import Window


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + png_chunk(b"IEND", b""))


def wait(app, condition):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("La operación de interfaz no terminó")


def test_gui_analysis_preview_selection_download_and_remembered_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    items = [Media(i, "foto", "https://cdn.test/image", "png", "gallery-dl", "https://instagram.com/p/test/") for i in (1, 2, 3)]
    def analyze(url, cookies, cancel, progress):
        # Long enough to assert the GUI returns immediately and disables conflicting actions.
        time.sleep(0.1)
        return items
    def fetch(item, folder, cancel, progress, cookies=""):
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / item.filename; path.write_bytes(PNG)
        progress(100, "Listo")
        return path
    monkeypatch.setattr("mediadownloader.gui.engines.analyze", analyze)
    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show()
    window.url.setText("https://instagram.com/p/test/")
    window.analyze_button.click()
    assert window.task and not window.analyze_button.isEnabled()
    wait(app, lambda: window.task is None and len(window.items) == 3)
    # The first preview starts automatically after analysis.
    wait(app, lambda: window.task is None and 1 in window.previews)
    assert window.pixmap and not window.pixmap.isNull()
    assert window.list.count() == 3
    window.folder.setText(str(tmp_path / "downloads"))
    window.settings.destination = window.folder.text(); window.settings.save()
    window.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    window.download_zip.click()
    wait(app, lambda: window.task is None)
    with zipfile.ZipFile(tmp_path / "downloads" / "MediaDownloader.zip") as z:
        assert z.namelist() == ["002_foto.png", "003_foto.png"]
        assert z.read("002_foto.png") == PNG
    window.close()
    reopened = Window()
    assert reopened.folder.text() == str(tmp_path / "downloads")
    reopened.close()
