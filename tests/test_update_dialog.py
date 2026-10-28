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
