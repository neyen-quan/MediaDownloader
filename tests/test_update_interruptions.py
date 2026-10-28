import pytest
from mediadownloader.updater import locations, journal, recover_interrupted, apply_update, UpdateError
from test_updater import portable, package


@pytest.mark.parametrize("phase", ["prepared", "moving"])
def test_interruption_before_renaming_current_keeps_current_and_previous(tmp_path, phase):
    root = portable(tmp_path / "MediaDownloader", b"current")
    backup, state = locations(root)
    older = portable(tmp_path / "MediaDownloader.older", b"previous")
    journal(state, {"phase": phase})
    assert not recover_interrupted(root)
    assert (root / "MediaDownloader.exe").read_bytes() == b"current"
    assert (backup / "MediaDownloader.exe").read_bytes() == b"previous"
    assert not older.exists() and not state.exists()


def test_personal_file_conflicting_with_new_app_file_blocks_without_data_loss(tmp_path):
    archive = package(tmp_path)
    root = portable(tmp_path / "MediaDownloader", b"current")
    # A manifest distinguishes an old managed DLL from a user file added later.
    from mediadownloader.updater import MANIFEST, read_manifest
    import json, hashlib
    files = {"MediaDownloader.exe": hashlib.sha256(b"current").hexdigest(),
             "MediaDownloaderUpdater.exe": hashlib.sha256(b"helper").hexdigest()}
    (root / MANIFEST).write_text(json.dumps({"application": "MediaDownloader", "schema": 1,
                                            "version": "1.0.0", "files": files}))
    with pytest.raises(UpdateError, match="personal"):
        apply_update(root, archive, health=lambda _: True)
    assert (root / "MediaDownloader.exe").read_bytes() == b"current"
    assert (root / "_internal" / "dependency.dll").read_bytes() == b"dll"


def test_existing_unrelated_backup_directory_is_never_deleted(tmp_path):
    archive = package(tmp_path)
    root = portable(tmp_path / "MediaDownloader", b"current")
    backup, _ = locations(root)
    backup.mkdir(); (backup / "personal.txt").write_text("personal")
    with pytest.raises(UpdateError, match="datos ajenos"):
        apply_update(root, archive, health=lambda _: True)
    assert (backup / "personal.txt").read_text() == "personal"
    assert (root / "MediaDownloader.exe").read_bytes() == b"current"

