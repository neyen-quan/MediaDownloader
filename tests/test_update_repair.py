"""The repair bypasses a defective installed helper without replacing user data."""
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from mediadownloader import updater as u, update_channel
from test_updater import portable, rewrite
from test_channel import Response
from test_update_completion import installation_with_previous


def patch_fixture(tmp_path, changed_helper=True):
    source = portable(tmp_path / 'source', b'current')
    full = tmp_path / 'base.zip'
    u.build_package(source, full, '1.0.13')
    root = tmp_path / 'installed'
    u.extract_package(full, root)
    target = tmp_path / 'target'
    shutil.copytree(root, target)
    (target / 'MediaDownloader.exe').write_bytes(b'updated')
    if changed_helper:
        (target / 'MediaDownloaderUpdater.exe').write_bytes(b'fixed-helper')
    archive = tmp_path / 'patch.zip'
    manifest = u.build_delta(root, target, archive, '1.0.15')
    return root, archive, manifest


@pytest.mark.parametrize('changed_helper', [True, False])
def test_prepare_helper_uses_verified_target_bytes(tmp_path, changed_helper):
    root, archive, manifest = patch_fixture(tmp_path, changed_helper)
    helper = tmp_path / 'helper.exe'
    u.prepare_helper(root, archive, helper)
    assert u.sha256(helper) == manifest['target']['files']['MediaDownloaderUpdater.exe']
    assert helper.read_bytes() == (b'fixed-helper' if changed_helper else b'helper')


def test_corrupt_incoming_helper_is_not_executed(tmp_path):
    root, archive, _ = patch_fixture(tmp_path)
    bad = rewrite(archive, tmp_path / 'bad.zip',
                  lambda files: files.update({'MediaDownloaderUpdater.exe': b'corrupted'}))
    helper = tmp_path / 'helper.exe'
    with pytest.raises(u.UpdateError, match='hash'):
        u.prepare_helper(root, bad, helper)
    assert not helper.exists()
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'


def test_helper_rejects_wrong_installed_manifest(tmp_path):
    root, archive, _ = patch_fixture(tmp_path)
    installed = json.loads((root / u.MANIFEST).read_text())
    installed['version'] = '1.0.12'
    (root / u.MANIFEST).write_text(json.dumps(installed))
    with pytest.raises(u.UpdateError, match='base'):
        u.prepare_helper(root, archive, tmp_path / 'helper.exe')


def test_online_repair_downloads_exact_patch_and_preserves_installation_until_confirmed(tmp_path, monkeypatch):
    root, archive, manifest = patch_fixture(tmp_path)
    (root / 'personal.jpg').write_bytes(b'keep')
    feed = {'schema': 1, 'product': 'MediaDownloader', 'version': '1.0.15', 'patches': [{
        'from': '1.0.13', 'to': '1.0.15', 'url': 'https://github.com/test/app/patch.zip',
        'size': archive.stat().st_size, 'sha256': u.sha256(archive)}]}
    calls = []
    def response(url, cancel):
        calls.append(url)
        return Response(json.dumps(feed).encode() if url.endswith('latest.json') else archive.read_bytes())
    monkeypatch.setattr(update_channel, 'response', response)
    reports = []
    downloaded, result = u.online_repair(root, tmp_path / 'download', lambda *r: reports.append(r))
    assert result == manifest and u.sha256(downloaded) == u.sha256(archive)
    assert calls[0] == update_channel.DEFAULT_CHANNEL
    assert any('Descargando:' in text for _, text in reports)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'
    assert not u.locations(root)[0].exists()
    assert u.apply_update(root, downloaded, health=lambda _: True) == 'updated'
    assert (root / 'personal.jpg').read_bytes() == b'keep'


def test_unique_journal_ignores_stale_readonly_temporary_file(tmp_path):
    state = tmp_path / 'MediaDownloader.update-state.json'
    stale = state.with_suffix('.tmp')
    stale.write_text('stale')
    stale.chmod(stat.S_IREAD)
    try:
        u.journal(state, {'phase': 'prepared'})
        assert json.loads(state.read_text()) == {'phase': 'prepared'}
        assert stale.read_text() == 'stale'
    finally:
        stale.chmod(stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows read-only file deletion semantics')
def test_windows_readonly_backup_before_swap_no_longer_blocks_installation(tmp_path):
    root, backup, state, older = installation_with_previous(tmp_path)
    shutil.copytree(backup, older)
    dll = older / '_internal/dependency.dll'
    dll.chmod(stat.S_IREAD)
    from test_updater import package
    assert u.apply_update(root, package(tmp_path), health=lambda _: True) == 'updated'
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
    assert not state.exists() and not older.exists()


def test_preparation_failure_shows_exact_stage_and_file(tmp_path, monkeypatch):
    root, archive, _ = patch_fixture(tmp_path)
    (root / 'download.jpg').write_bytes(b'personal')
    copy = u.shutil.copy2
    def denied(source, target, *args, **kwargs):
        if Path(source).name == 'download.jpg':
            raise PermissionError(13, 'locked personal file', str(source))
        return copy(source, target, *args, **kwargs)
    monkeypatch.setattr(u.shutil, 'copy2', denied)
    monkeypatch.setattr(u, 'retry_filesystem', lambda action, *a, **k: action())
    assert u.helper_main(['--root', str(root), '--zip', str(archive), '--no-relaunch']) == 1
    log = root.with_name(root.name + '.update-error.txt').read_text(encoding='utf-8')
    assert 'Conservando archivo personal: download.jpg' in log
    assert str(root / 'download.jpg') in log
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'
