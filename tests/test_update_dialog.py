import json
import shutil
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from mediadownloader import update_channel
from mediadownloader.core import Settings
from mediadownloader.gui import Window
from mediadownloader.update_dialog import UpdateDialog
from mediadownloader.updater import build_package, build_delta, extract_package, apply_update, sha256
from test_updater import portable
from test_gui import wait
from test_channel import Response


def test_buttons_download_confirm_apply_and_check_again(tmp_path, monkeypatch):
    monkeypatch.setattr('mediadownloader.update_dialog.__version__', '1.0.8')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    source = portable(tmp_path / 'source', b'old')
    full = tmp_path / 'full.zip'; build_package(source, full, '1.0.8')
    root = tmp_path / 'installed'; extract_package(full, root)
    target = tmp_path / 'new'; shutil.copytree(source, target)
    (target / 'MediaDownloader.exe').write_bytes(b'new')
    package = tmp_path / 'patch.zip'; build_delta(root, target, package, '1.0.9')
    (root / 'download.jpg').write_bytes(b'personal')
    settings = Settings('fixture-downloads', 'fixture-session.txt'); settings.save()
    feed = {'schema': 1, 'product': 'MediaDownloader', 'version': '1.0.9', 'patches': [
        {'from': '1.0.8', 'to': '1.0.9', 'url': 'https://github.com/test/app/releases/download/v1.0.9/patch.zip',
         'sha256': sha256(package), 'size': package.stat().st_size}]}
    def response(url, cancel):
        return Response(json.dumps(feed).encode() if url.endswith('latest.json') else package.read_bytes())
    monkeypatch.setattr(update_channel, 'response', response)
    monkeypatch.setattr('mediadownloader.update_dialog.sys.executable', str(root / 'MediaDownloader.exe'))
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show()
    dialog = UpdateDialog(window); dialog.show()
    confirmations = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: confirmations.append(args[2]) or QMessageBox.StandardButton.Yes)
    applied = []
    def launch(path):
        apply_update(root, path, health=lambda _: True)
        applied.append(path)
    monkeypatch.setattr(window, 'launch_update', launch)
    dialog.check_button.click()
    wait(app, lambda: window.task is None and dialog.info is not None)
    assert dialog.install.isEnabled() and '1.0.9' in dialog.available.text()
    dialog.install.click()
    wait(app, lambda: bool(applied) and window.task is None)
    assert len(confirmations) == 1
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
    assert (root / 'download.jpg').read_bytes() == b'personal'
    assert Settings.load() == settings
    monkeypatch.setattr('mediadownloader.update_dialog.__version__', '1.0.9')
    again = UpdateDialog(window); again.show(); again.check_button.click()
    wait(app, lambda: window.task is None and again.info is not None)
    assert 'Ya tenés la última versión' in again.message.text() and not again.install.isEnabled()
    again.close(); dialog.close(); window.close()


def test_real_nested_confirmation_cannot_lose_pending_install(tmp_path, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox
    from mediadownloader.update_dialog import UpdateDialog
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    app = QApplication.instance() or QApplication([])
    window = Window(); window.show()
    dialog = UpdateDialog(window); dialog.show()
    launched = []
    monkeypatch.setattr(window, 'launch_update', lambda path: launched.append(path))
    observed = []
    def accept_after_finished():
        # A real modal QMessageBox runs a nested Qt event loop. Keep it open
        # until task_finished has actually cleared the background task.
        box = app.activeModalWidget()
        if isinstance(box, QMessageBox) and window.task is None:
            observed.append(True)
            box.button(QMessageBox.StandardButton.Yes).click()
        else:
            QTimer.singleShot(10, accept_after_finished)
    QTimer.singleShot(10, accept_after_finished)
    dialog.run(lambda cancel, progress: ('fixture.zip', {'version':'99.0.0'}),
               lambda result: dialog.confirm(*result))
    wait(app, lambda: bool(launched))
    assert observed and launched == ['fixture.zip']
    assert window.task is None and window.after_task is None
    dialog.close(); window.close()


def test_progress_is_visible_and_unknown_phases_use_busy_bar(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    app = QApplication.instance() or QApplication([])
    window = Window(); dialog = UpdateDialog(window); dialog.show()
    dialog.report(42, 'Descargando: 4.2 / 10.0 MiB')
    assert dialog.bar.isVisible() and dialog.bar.value() == 42
    assert 'MiB' in dialog.progress.text()
    dialog.report(-1, 'Validando instalación actual…')
    assert dialog.bar.maximum() == 0 and 'Validando' in dialog.progress.text()
    import time
    dialog.last_advance = time.monotonic() - 9
    dialog.tick()
    assert 'Sin avance nuevo' in dialog.activity.text()
    dialog.operation_failed('fixture error')
    assert dialog.bar.maximum() == 100 and dialog.bar.value() == 0
    assert 'detenida' in dialog.progress.text()
    dialog.close(); window.close()
