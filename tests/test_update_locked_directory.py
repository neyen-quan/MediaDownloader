"""A stale backup directory must never be a prerequisite for installation."""
import json
import os
from pathlib import Path
import shutil

import pytest

from mediadownloader import updater as u
from test_updater import portable, package
from test_update_completion import installation_with_previous, immediate


def fixture_with_stale_backup(tmp_path):
    root, backup, state, older = installation_with_previous(tmp_path)
    shutil.copytree(backup, older)
    (older / 'personal.jpg').write_bytes(b'older personal copy')
    (root / 'personal.jpg').write_bytes(b'current personal file')
    return root, backup, state, older


@pytest.mark.parametrize('stage_of_denial', ['enumerate', 'remove-directory'])
def test_locked_older_before_prepare_does_not_block_install_or_following_update(tmp_path, monkeypatch, stage_of_denial):
    root, backup, state, older = fixture_with_stale_backup(tmp_path)
    archive = package(tmp_path)
    real_iterdir, real_rmdir = Path.iterdir, Path.rmdir
    locked = True
    def iterdir(path):
        if locked and path == older and stage_of_denial == 'enumerate':
            raise PermissionError(13, 'Access denied', str(path))
        return real_iterdir(path)
    def rmdir(path):
        if locked and path == older and stage_of_denial == 'remove-directory':
            raise PermissionError(13, 'Access denied', str(path))
        return real_rmdir(path)
    monkeypatch.setattr(Path, 'iterdir', iterdir)
    monkeypatch.setattr(Path, 'rmdir', rmdir)
    monkeypatch.setattr(u, 'retry_filesystem', immediate)
    health_calls = []
    def healthy(path):
        # No attempted pre-commit cleanup may alter the blocked old backup.
        assert (older / 'personal.jpg').read_bytes() == b'older personal copy'
        health_calls.append(path)
        return True
    assert u.apply_update(root, archive, health=healthy) == 'updated'
    assert health_calls == [root]
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (root / 'personal.jpg').read_bytes() == b'current personal file'
    assert json.loads(state.read_text())['phase'] == 'committed'
    # A pending cleanup must not block the *next* update either.
    assert u.apply_update(root, archive, health=lambda _: True) == 'updated'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'new'
    locked = False
    assert u.recover_interrupted(root) is False
    assert not state.exists() and not older.exists()
    assert not list(root.parent.glob(root.name + '.older-*'))


@pytest.mark.parametrize('phase', ['prepared', 'moving', 'swapping', 'committed'])
def test_unique_retired_backup_recovers_at_each_swap_boundary(tmp_path, phase):
    root, backup, state, stale = fixture_with_stale_backup(tmp_path)
    retired = root.with_name(root.name + '.older-' + 'a' * 32)
    backup.rename(retired)
    if phase in {'swapping', 'committed'}:
        root.rename(backup)
        portable(root, b'new')
    u.journal(state, {'phase': phase, 'retired': retired.name})
    assert u.recover_interrupted(root) is (phase == 'swapping')
    assert (root / 'MediaDownloader.exe').read_bytes() == (b'new' if phase == 'committed' else b'current')
    assert (backup / 'MediaDownloader.exe').read_bytes() == (b'current' if phase == 'committed' else b'older')
    if phase != 'committed':
        assert (stale / 'personal.jpg').read_bytes() == b'older personal copy'
    assert not state.exists() and not retired.exists()


@pytest.mark.parametrize('name', ['../personal', '/outside', 'Other.older-' + 'a' * 32,
                                 'MediaDownloader.older-invalid'])
def test_tampered_retired_path_is_rejected_without_touching_files(tmp_path, name):
    root, backup, state, older = fixture_with_stale_backup(tmp_path)
    u.journal(state, {'phase': 'committed', 'retired': name})
    with pytest.raises(u.UpdateError, match='ruta de respaldo'):
        u.recover_interrupted(root)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'older'
    assert (older / 'personal.jpg').read_bytes() == b'older personal copy'


def test_health_failure_with_locked_stale_older_restores_both_current_and_previous(tmp_path, monkeypatch):
    root, backup, state, older = fixture_with_stale_backup(tmp_path)
    real = Path.iterdir
    monkeypatch.setattr(Path, 'iterdir', lambda p: (_ for _ in ()).throw(
        PermissionError('locked stale directory')) if p == older else real(p))
    with pytest.raises(u.UpdateError, match='recuperó'):
        u.apply_update(root, package(tmp_path), health=lambda _: False)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'older'
    assert (older / 'personal.jpg').read_bytes() == b'older personal copy'
    assert not state.exists() and not list(root.parent.glob(root.name + '.older-*'))


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows directory deletion lock')
def test_real_windows_directory_locked_before_update_is_nonfatal(tmp_path):
    from tools.windows_test_support import deny_directory_delete
    root, backup, state, older = fixture_with_stale_backup(tmp_path)
    with deny_directory_delete(older):
        with pytest.raises(PermissionError) as denied:
            u.remove_old_backup(older)
        assert denied.value.winerror == 5  # Match the actual reported error exactly.
        assert u.apply_update(root, package(tmp_path), health=lambda _: True) == 'updated'
        assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
        assert (backup / 'MediaDownloader.exe').read_bytes() == b'current'
        assert json.loads(state.read_text())['phase'] == 'committed'
    assert u.recover_interrupted(root) is False
    assert not older.exists() and not state.exists()
