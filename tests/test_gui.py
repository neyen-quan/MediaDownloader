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
    wait(app, lambda: not window.isVisible())
    reopened = Window()
    assert reopened.folder.text() == str(tmp_path / "downloads")
    reopened.close()


def test_auto_previews_stable_geometry_zoom_and_fast_selection(tmp_path, monkeypatch):
    from PySide6.QtGui import QImage, QColor
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    source = tmp_path / "large.png"
    image = QImage(1800, 2700, QImage.Format.Format_RGB32)
    image.fill(QColor("#7952ac")); image.save(str(source))
    items = [Media(i, "foto", "https://cdn.test/image", "png", "gallery-dl", "source") for i in range(1, 7)]
    calls = []
    def fetch(item, folder, cancel, progress, cookies=""):
        import shutil
        calls.append(item.index)
        time.sleep(0.04)
        folder.mkdir(parents=True)
        path = folder / item.filename
        shutil.copy2(source, path)
        return path
    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show(); app.processEvents()
    window.analyzed(items)
    wait(app, lambda: len(window.previews) == 6 and window.preview_task is None)
    assert sorted(calls) == list(range(1, 7))
    assert window.list.isEnabled() and window.download_zip.isEnabled()
    assert all(not window.list.item(i).icon().isNull() for i in range(6))
    assert window.list.visualItemRect(window.list.item(0)).height() < 70
    assert window.zoom.value() == 80
    before = window.image.size()
    minimum = window.centralWidget().minimumSizeHint()
    for i in [1, 2, 3, 4, 5, 0] * 4:
        window.list.setCurrentRow(i); app.processEvents()
        assert window.image.size() == before
        assert window.centralWidget().minimumSizeHint() == minimum
    small = window.image.image_rect().size()
    window.zoom.setValue(150); app.processEvents()
    assert window.image.image_rect().width() > small.width()
    assert window.image.size() == before
    assert window.zoom_label.text() == "150%"
    window.list.setCurrentRow(2); app.processEvents()
    assert window.zoom.value() == 150 and window.image.size() == before
    window.resize(1100, 800); app.processEvents()
    assert window.image.image_rect().width() > 0
    window.close(); wait(app, lambda: not window.isVisible())


def test_preview_result_does_not_jump_back_to_old_selection(tmp_path, monkeypatch):
    import threading
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    release = threading.Event()
    entered = threading.Event()
    def fetch(item, folder, cancel, progress, cookies=""):
        entered.set()
        if not release.wait(3):
            raise AssertionError("test did not release preview")
        folder.mkdir(parents=True)
        path = folder / item.filename; path.write_bytes(PNG)
        return path
    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show()
    window.analyzed([Media(i, "foto", "https://cdn.test/x", "png", "gallery-dl", "source") for i in (1, 2)])
    wait(app, entered.is_set)
    assert window.list.isEnabled()
    window.list.setCurrentRow(1)
    release.set()
    wait(app, lambda: len(window.previews) == 2 and window.preview_task is None)
    assert window.list.currentRow() == 1 and "Elemento 2" in window.details.text()
    window.close(); wait(app, lambda: not window.isVisible())


def test_closing_cancels_preview_before_cleaning_cache(tmp_path, monkeypatch):
    import threading
    from mediadownloader.core import check_cancel
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    entered = threading.Event()
    def fetch(item, folder, cancel, progress, cookies=""):
        entered.set()
        cancel.wait(3)
        check_cancel(cancel)
        raise AssertionError("preview was not cancelled")
    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show()
    window.analyzed([Media(1, "foto", "https://cdn.test/x", "png", "gallery-dl", "source")])
    wait(app, entered.is_set)
    cache = window.cache.name
    window.close()
    wait(app, lambda: not window.isVisible())
    assert window.preview_task is None and not os.path.exists(cache)


def test_compact_toolbar_and_portrait_preview_use_window_height(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    app = QApplication.instance() or QApplication([])
    window = Window(); window.resize(1280, 900); window.show()
    for _ in range(5):
        app.processEvents()
    assert window.url.mapTo(window, window.url.rect().topLeft()).y() == window.folder.mapTo(window, window.folder.rect().topLeft()).y()
    assert window.url.mapTo(window, window.url.rect().topLeft()).y() < 110
    assert window.content_split.height() > 480
    assert window.image.height() > 400
    assert abs(window.stack.width() / window.stack.height() - 3 / 4) < 0.01
    before = window.content_split.size()
    window.portrait.set_ratio(9 / 16)
    app.processEvents()
    assert abs(window.stack.width() / window.stack.height() - 9 / 16) < 0.01
    assert window.content_split.size() == before
    window.resize(980, 760)
    for _ in range(5):
        app.processEvents()
    assert window.url.width() >= 130 and window.folder.width() >= 130
    assert window.stack.width() <= window.portrait.width()
    assert window.stack.height() <= window.portrait.height()
    window.close()

