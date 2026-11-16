import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from mediadownloader.core import Media, check_cancel
from mediadownloader.gui import Window


def wait(app, condition):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("La operación no terminó")


def make_window(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.show()
    return app, window


def test_cached_video_export_keeps_actual_container(tmp_path, monkeypatch):
    monkeypatch.setattr(Window, "queue_preview", lambda self: None)
    app, window = make_window(tmp_path, monkeypatch)
    try:
        window.analyzed([Media(1, "video", "https://cdn.test/video", "mp4", "yt-dlp", "source")])
        cached = Path(window.cache.name) / "video" / "original.mkv"
        cached.parent.mkdir()
        cached.write_bytes(b"original-video-container")
        window.previews[1] = cached
        window.folder.setText(str(tmp_path / "downloads"))
        window.download("one")
        wait(app, lambda: window.task is None)
        files = list((tmp_path / "downloads").iterdir())
        assert [file.name for file in files] == ["001_video.mkv"]
        assert files[0].read_bytes() == cached.read_bytes()
    finally:
        window.close()


def test_cancel_is_quiet_and_resets_indeterminate_progress(tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr("mediadownloader.gui.QMessageBox.warning", lambda *args: warnings.append(args))
    app, window = make_window(tmp_path, monkeypatch)

    def action(cancel, progress):
        progress(-1, "Analizando enlace…")
        cancel.wait(3)
        check_cancel(cancel)
        raise AssertionError("La tarea no fue cancelada")

    try:
        window.start(action, lambda _: None)
        wait(app, lambda: window.progress.maximum() == 0)
        window.cancel_button.click()
        wait(app, lambda: window.task is None)
        assert not warnings
        assert window.progress.maximum() == 100
        assert window.progress.value() == 0
        assert window.analyze_button.isEnabled()
        assert not window.cancel_button.isEnabled()
    finally:
        window.close()


def test_bulk_selection_emits_no_per_item_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(Window, "queue_preview", lambda self: None)
    app, window = make_window(tmp_path, monkeypatch)
    try:
        changed = QSignalSpy(window.list.itemChanged)
        items = [Media(i, "foto", "https://cdn.test/image", "jpg", "gallery-dl", "source")
                 for i in range(1, 501)]
        window.analyzed(items)
        assert changed.count() == 0
        assert window.list.currentRow() == 0
        window.mark(False)
        assert changed.count() == 0
        assert "0 de 500" in window.selection_label.text()
        assert not window.download_selected.isEnabled() and not window.download_zip.isEnabled()
        assert window.download_all.isEnabled() and window.download_one.isEnabled()
        window.list.item(10).setCheckState(Qt.CheckState.Checked)
        assert "1 de 500" in window.selection_label.text()
        assert window.download_zip.isEnabled()
        window.mark(True)
        assert changed.count() == 1
        assert "500 de 500" in window.selection_label.text()
    finally:
        window.close()


def test_replacing_source_releases_previous_preview_files(tmp_path, monkeypatch):
    def fetch(item, folder, cancel, progress, cookies=""):
        folder.mkdir()
        path = folder / item.filename
        path.write_bytes(b"unpreviewable-but-downloadable-original")
        return path

    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app, window = make_window(tmp_path, monkeypatch)
    try:
        window.analyzed([Media(1, "foto", "https://cdn.test/first", "jpg", "gallery-dl", "first")])
        wait(app, lambda: bool(window.previews) and window.preview_task is None)
        previous = window.previews[1]
        window.analyzed([Media(1, "foto", "https://cdn.test/second", "jpg", "gallery-dl", "second")])
        wait(app, lambda: bool(window.previews) and window.preview_task is None)
        assert not previous.parent.exists()
        assert window.previews[1].exists()
        assert (Path(window.cache.name) / "checked.png").exists()
    finally:
        window.close()
        wait(app, lambda: not window.isVisible())


def test_late_preview_cannot_repopulate_a_replaced_source(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    folders = []

    def fetch(item, folder, cancel, progress, cookies=""):
        folder.mkdir()
        folders.append(folder)
        if item.source == "old":
            entered.set()
            assert release.wait(3)
        path = folder / item.filename
        path.write_bytes(item.source.encode())
        return path

    monkeypatch.setattr("mediadownloader.gui.engines.fetch", fetch)
    app, window = make_window(tmp_path, monkeypatch)
    try:
        window.analyzed([Media(1, "foto", "https://cdn.test/old", "jpg", "gallery-dl", "old")])
        wait(app, entered.is_set)
        window.analyzed([Media(1, "foto", "https://cdn.test/new", "jpg", "gallery-dl", "new")])
        assert folders[0].exists(), "El worker todavía está usando esta carpeta"
        release.set()
        wait(app, lambda: bool(window.previews) and window.preview_task is None)
        assert window.previews[1].read_bytes() == b"new"
        assert not folders[0].exists()
    finally:
        release.set()
        window.close()
        wait(app, lambda: not window.isVisible())
