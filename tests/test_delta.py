import json
import shutil
import zipfile

import pytest
from mediadownloader.updater import (MANIFEST, UpdateError, apply_update, build_delta,
    build_package, extract_package, locations, sha256, validate_package)
from test_updater import portable, rewrite


def setup_delta(tmp_path):
    source = portable(tmp_path / 'source', b'old')
    (source / 'licenses').mkdir()
    (source / 'licenses/obsolete.txt').write_text('old file')
    archive = tmp_path / 'base.zip'
    build_package(source, archive, '1.0.7')
    base = tmp_path / 'installed'; extract_package(archive, base)
    target = tmp_path / 'target'; shutil.copytree(source, target)
    (target / 'MediaDownloader.exe').write_bytes(b'new')
    (target / 'licenses/obsolete.txt').unlink()
    (target / 'licenses/added.txt').write_text('new file')
    patch = tmp_path / 'patch.zip'
    manifest = build_delta(base, target, patch, '1.0.8')
    return base, target, patch, manifest


def test_only_changes_shipped_and_update_restore_keep_personal_files(tmp_path):
    root, target, patch, manifest = setup_delta(tmp_path)
    with zipfile.ZipFile(patch) as z:
        assert set(z.namelist()) == {MANIFEST, 'MediaDownloader.exe', 'licenses/added.txt'}
    (root / 'personal.jpg').write_bytes(b'my download')
    assert apply_update(root, patch, health=lambda _: True) == 'updated'
    assert not (root / 'licenses/obsolete.txt').exists()
    assert (root / 'personal.jpg').read_bytes() == b'my download'
    assert json.loads((root / MANIFEST).read_bytes()) == manifest['target']
    for name, digest in manifest['target']['files'].items():
        assert sha256(root / name) == digest
    apply_update(root, restore=True, health=lambda _: True)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'old'
    assert (root / 'licenses/obsolete.txt').exists() and not (root / 'licenses/added.txt').exists()
    assert (root / 'personal.jpg').read_bytes() == b'my download'


@pytest.mark.parametrize('damage', ['version', 'missing', 'changed'])
def test_wrong_or_damaged_base_never_changes_live_files(tmp_path, damage):
    root, target, patch, manifest = setup_delta(tmp_path)
    if damage == 'version':
        m = manifest['base'].copy(); m['version'] = '1.0.6'
        (root / MANIFEST).write_text(json.dumps(m))
    elif damage == 'missing':
        (root / '_internal/dependency.dll').unlink()
    else:
        (root / '_internal/dependency.dll').write_bytes(b'modified')
    with pytest.raises(UpdateError):
        apply_update(root, patch, health=lambda _: True)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'old'
    assert not locations(root)[0].exists()


def test_delta_failed_start_restores_previous_bytes(tmp_path):
    root, target, patch, manifest = setup_delta(tmp_path)
    with pytest.raises(UpdateError, match='recuperó'):
        apply_update(root, patch, health=lambda _: False)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'old'
    assert (root / 'licenses/obsolete.txt').exists()
    assert not locations(root)[1].exists()


def test_delta_rejects_corrupt_payload_and_inconsistent_manifest(tmp_path):
    root, target, patch, manifest = setup_delta(tmp_path)
    corrupt = rewrite(patch, tmp_path / 'corrupt.zip', lambda f: f.update({'licenses/added.txt': b'tampered'}))
    with pytest.raises(UpdateError):
        validate_package(corrupt)
    def omit(f):
        m = json.loads(f[MANIFEST]); del m['files']['licenses/added.txt']
        del f['licenses/added.txt']; f[MANIFEST] = json.dumps(m).encode()
    corrupt = rewrite(patch, tmp_path / 'omitted.zip', omit)
    with pytest.raises(UpdateError):
        validate_package(corrupt)


def test_user_file_collision_is_rejected_before_swap(tmp_path):
    root, target, patch, manifest = setup_delta(tmp_path)
    (root / 'licenses/added.txt').write_bytes(b'personal')
    with pytest.raises(UpdateError, match='personal'):
        apply_update(root, patch, health=lambda _: True)
    assert (root / 'licenses/added.txt').read_bytes() == b'personal'
    assert (root / 'MediaDownloader.exe').read_bytes() == b'old'


def test_future_release_pipeline_builds_and_checks_small_patch(tmp_path, monkeypatch):
    from tools import delta_release
    root, target, patch, manifest = setup_delta(tmp_path)
    project = tmp_path / 'project'
    shutil.copytree(root, project / 'build/patch-base')
    shutil.copytree(target, project / 'dist/MediaDownloader')
    monkeypatch.setattr(delta_release, 'ROOT', project)
    monkeypatch.setattr(delta_release, '__version__', '1.0.8')
    def run(args, **kwargs):
        installed = args[args.index('--root') + 1]
        if '--restore' in args:
            apply_update(installed, restore=True, health=lambda _: True)
        else:
            apply_update(installed, args[args.index('--zip') + 1], health=lambda _: True)
    monkeypatch.setattr(delta_release.subprocess, 'run', run)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    build_package(project / 'dist/MediaDownloader', project / 'dist/MediaDownloader-1.0.8-Windows-x64.zip', '1.0.8')
    delta_release.build()
    output = project / 'dist/MediaDownloader-1.0.8-from-1.0.7-patch.zip'
    assert output.exists() and output.with_suffix('.zip.sha256').exists()
    with zipfile.ZipFile(output) as z:
        assert '_internal/dependency.dll' not in z.namelist()
    assert validate_package(output)['base']['version'] == '1.0.7'



def test_validation_reports_real_stages_and_can_cancel_before_swap(tmp_path):
    import threading
    root, target, patch, manifest = setup_delta(tmp_path)
    reports = []
    validate_package(patch, root, progress=lambda value, message: reports.append((value, message)))
    assert any('extrayendo' in msg for _, msg in reports)
    assert any('Validando instalación actual' in msg for _, msg in reports)
    assert any('Preparando nueva versión' in msg for _, msg in reports)
    assert all(-1 <= value <= 100 for value, _ in reports)
    cancel = threading.Event(); cancel.set()
    with pytest.raises(UpdateError, match='cancelada'):
        validate_package(patch, root, cancel=cancel)
    assert (root / 'MediaDownloader.exe').read_bytes() == b'old'
