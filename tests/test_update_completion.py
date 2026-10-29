"""A cleanup/access failure must never misreport or revert a committed update."""
import ctypes
import json
import os
from pathlib import Path

import pytest

from mediadownloader import updater as u
from test_updater import portable, package


def installation_with_previous(tmp_path):
    root = portable(tmp_path / 'MediaDownloader', b'current')
    backup, state = u.locations(root)
    portable(backup, b'older')
    manifest = u.build_package(backup, tmp_path / 'older.zip', '1.0.0')
    (backup / u.MANIFEST).write_text(json.dumps(manifest), encoding='utf-8')
    return root, backup, state, root.with_name(root.name + '.older')


def immediate(action, *args, **kwargs):
    return action()


def test_temporary_access_denial_is_retried_with_progress(monkeypatch):
    attempts = []
    reports = []
    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError('temporary sharing violation')
        return 'done'
    monkeypatch.setattr(u.time, 'sleep', lambda _: None)
    assert u.retry_filesystem(operation, lambda *report: reports.append(report)) == 'done'
    assert len(attempts) == 3 and len(reports) == 2
    assert all(report[0] == -1 for report in reports)


@pytest.mark.parametrize('error', [PermissionError('persistent denial'), FileNotFoundError('missing file')])
def test_persistent_or_unrelated_filesystem_errors_are_not_hidden(error):
    def operation():
        raise error
    with pytest.raises(type(error)):
        u.retry_filesystem(operation, timeout=0)


@pytest.mark.parametrize('blocked_part', ['old-backup', 'journal'])
def test_locked_cleanup_keeps_healthy_install_and_later_recovery_does_not_roll_back(tmp_path, monkeypatch, blocked_part):
    root, backup, state, older = installation_with_previous(tmp_path)
    archive = package(tmp_path)
    locked = False
    real_rmtree, real_unlink = u.shutil.rmtree, Path.unlink
    def health(path):
        nonlocal locked
        locked = True
        assert (path / 'MediaDownloader.exe').read_bytes() == b'new'
        return True
    def rmtree(path, *args, **kwargs):
        if locked and blocked_part == 'old-backup' and Path(path) == older / '_internal':
            raise PermissionError('old backup is locked')
        return real_rmtree(path, *args, **kwargs)
    def unlink(path, *args, **kwargs):
        if locked and blocked_part == 'journal' and path == state:
            raise PermissionError('journal is locked')
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(u, 'retry_filesystem', immediate)
    monkeypatch.setattr(u.shutil, 'rmtree', rmtree)
    monkeypatch.setattr(Path, 'unlink', unlink)
    (root / 'personal.jpg').write_bytes(b'keep my download')
    assert u.apply_update(root, archive, health=health) == 'updated'
    assert json.loads(state.read_text())['phase'] == 'committed'
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (root / 'personal.jpg').read_bytes() == b'keep my download'
    if blocked_part == 'old-backup':
        # Earlier files may have been deleted, but the ownership marker survives.
        assert (older / u.MANIFEST).is_file()
        (older / 'MediaDownloader.exe').unlink(missing_ok=True)
        assert not (older / 'MediaDownloader.exe').exists()
    assert u.recover_interrupted(root) is False
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new' and state.exists()
    locked = False
    assert u.recover_interrupted(root) is False
    assert not older.exists() and not state.exists()
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'


def test_failure_to_record_commit_still_rolls_back(tmp_path, monkeypatch):
    root, backup, state, older = installation_with_previous(tmp_path)
    archive = package(tmp_path)
    journal = u.journal
    def denied_commit(path, value):
        if value['phase'] == 'committed':
            raise PermissionError('commit journal denied')
        journal(path, value)
    monkeypatch.setattr(u, 'journal', denied_commit)
    with pytest.raises(PermissionError):
        u.apply_update(root, archive, health=lambda _: True)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'current'
    assert (backup / 'MediaDownloader.exe').read_bytes() == b'older'
    assert not state.exists() and not older.exists()


def test_pending_cleanup_never_deletes_an_unidentified_old_directory(tmp_path, monkeypatch):
    root = portable(tmp_path / 'MediaDownloader', b'healthy')
    older = root.with_name(root.name + '.older')
    older.mkdir()
    (older / 'personal.txt').write_text('do not delete')
    state = u.locations(root)[1]
    u.journal(state, {'phase': 'committed'})
    monkeypatch.setattr(u, 'retry_filesystem', immediate)
    assert u.recover_interrupted(root) is False
    assert (older / 'personal.txt').read_text() == 'do not delete'
    assert (root / 'MediaDownloader.exe').read_bytes() == b'healthy'
    assert state.exists()
    with pytest.raises(u.UpdateError, match='datos ajenos'):
        u.apply_update(root, package(tmp_path), health=lambda _: True)
    assert (older / 'personal.txt').read_text() == 'do not delete'


@pytest.mark.skipif(os.name != 'nt', reason='Requires real Windows file sharing semantics')
def test_real_windows_locked_dll_after_health_check_defers_cleanup_without_failure(tmp_path):
    root, backup, state, older = installation_with_previous(tmp_path)
    archive = package(tmp_path)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handles = []
    def health(path):
        # Open only after the folder swap, making the cleanup lock deterministic.
        # Share reads/writes, but deny deletion exactly as Windows processes can.
        handle = kernel.CreateFileW(str(older / '_internal/dependency.dll'),
                                    0x80000000, 3, None, 3, 0x80, None)
        assert handle not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
        handles.append(handle)
        return True
    try:
        assert u.apply_update(root, archive, health=health) == 'updated'
        assert (root / 'MediaDownloader.exe').read_bytes() == b'new'
        assert json.loads(state.read_text())['phase'] == 'committed'
        assert (older / u.MANIFEST).exists()
        assert (backup / 'MediaDownloader.exe').read_bytes() == b'current'
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
    assert u.recover_interrupted(root) is False
    assert not state.exists() and not older.exists()
    assert (root / 'MediaDownloader.exe').read_bytes() == b'new'


def test_failure_log_records_phase_and_traceback(tmp_path, monkeypatch):
    root = portable(tmp_path / 'MediaDownloader')
    def denied(*args, progress, **kwargs):
        progress(-1, 'Respaldando la versión actual…')
        raise PermissionError(13, 'sharing violation', 'fixture-locked.dll')
    monkeypatch.setattr(u, 'apply_update', denied)
    assert u.helper_main(['--root', str(root), '--no-relaunch']) == 1
    log = root.with_name(root.name + '.update-error.txt').read_text(encoding='utf-8')
    assert 'Etapa: Respaldando la versión actual' in log
    assert 'Traceback' in log and 'PermissionError' in log and 'fixture-locked.dll' in log


def test_relaunch_denial_does_not_claim_installation_failed(tmp_path, monkeypatch):
    root = portable(tmp_path / 'MediaDownloader')
    monkeypatch.setattr(u, 'apply_update', lambda *args, **kwargs: 'updated')
    monkeypatch.setattr(u, 'retry_filesystem', immediate)
    def denied(*args, **kwargs):
        raise PermissionError('temporary executable lock')
    monkeypatch.setattr(u.subprocess, 'Popen', denied)
    if os.name == 'nt':
        monkeypatch.setattr(ctypes.windll.user32, 'MessageBoxW', lambda *args: 1)
    assert u.helper_main(['--root', str(root)]) == 1
    log = root.with_name(root.name + '.update-error.txt').read_text(encoding='utf-8')
    assert 'La instalación terminó' in log and 'Resultado: updated' in log
    assert 'No se pudo aplicar' not in log and 'No se pudo completar' not in log
