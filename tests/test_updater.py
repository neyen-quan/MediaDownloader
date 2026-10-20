import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest
from mediadownloader.updater import (MANIFEST, UpdateError, build_package, extract_package,
    validate_package, apply_update, locations, journal, recover_interrupted, safe_name, update_lock)


def portable(folder, marker=b"new"):
    folder.mkdir()
    (folder / "MediaDownloader.exe").write_bytes(marker)
    (folder / "MediaDownloaderUpdater.exe").write_bytes(b"helper")
    (folder / "_internal").mkdir()
    (folder / "_internal" / "dependency.dll").write_bytes(b"dll")
    return folder


def package(tmp_path):
    source = portable(tmp_path / "source")
    archive = tmp_path / "patch.zip"
    build_package(source, archive, "1.0.1")
    return archive


def rewrite(original, target, change):
    with zipfile.ZipFile(original) as z:
        files = {i.filename: z.read(i) for i in z.infolist()}
    change(files)
    with zipfile.ZipFile(target, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return target


def test_build_validate_and_extract(tmp_path):
    archive = package(tmp_path)
    assert validate_package(archive)["version"] == "1.0.1"
    stage = tmp_path / "stage"
    extract_package(archive, stage)
    assert (stage / "MediaDownloader.exe").read_bytes() == b"new"


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/bad", "x\\bad", "x/../bad",
    "x//bad", "x/./bad", "NUL.txt", "COM1", "x:stream", "space ", "dot.", "x/CON", "a\x00b"])
def test_windows_path_rejection(name):
    with pytest.raises(UpdateError):
        safe_name(name)


def test_zip_slip_wrong_app_corruption_extra_and_case_collision(tmp_path):
    archive = package(tmp_path)
    def wrong_app(files):
        manifest = json.loads(files[MANIFEST]); manifest["application"] = "OtherApp"
        files[MANIFEST] = json.dumps(manifest).encode()
    for index, change in enumerate([
        lambda f: f.update({"../escape.txt": b"evil"}), wrong_app,
        lambda f: f.update({"MediaDownloader.exe": b"tampered"}),
        lambda f: f.update({"extra.exe": b"unexpected"}),
        lambda f: f.update({"mediadownloader.exe": b"duplicate"}),
    ]):
        bad = rewrite(archive, tmp_path / f"bad-{index}.zip", change)
        with pytest.raises(UpdateError):
            validate_package(bad)
    assert not (tmp_path / "escape.txt").exists()


def test_symlink_rejection(tmp_path):
    archive = package(tmp_path)
    with zipfile.ZipFile(archive, "a") as z:
        entry = zipfile.ZipInfo("link")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(entry, "../outside")
    with pytest.raises(UpdateError):
        validate_package(archive)


def test_update_restore_and_userdata_untouched(tmp_path):
    archive = package(tmp_path)
    root = portable(tmp_path / "MediaDownloader", b"old")
    user = tmp_path / "UserProfile"; user.mkdir()
    (user / "settings.json").write_bytes(b"config")
    (root / "my-download.jpg").write_bytes(b"download")
    assert apply_update(root, archive, health=lambda p: (p / "MediaDownloader.exe").read_bytes() == b"new") == "updated"
    backup, state = locations(root)
    assert (backup / "MediaDownloader.exe").read_bytes() == b"old"
    assert (backup / "my-download.jpg").read_bytes() == b"download"
    assert (root / "my-download.jpg").read_bytes() == b"download"
    assert (user / "settings.json").read_bytes() == b"config"
    assert not state.exists()
    assert apply_update(root, restore=True, health=lambda _: True) == "restored"
    assert (root / "MediaDownloader.exe").read_bytes() == b"old"


def test_failed_boot_rolls_back(tmp_path):
    archive = package(tmp_path)
    root = portable(tmp_path / "MediaDownloader", b"old")
    with pytest.raises(UpdateError, match="recuperó"):
        apply_update(root, archive, health=lambda _: False)
    assert (root / "MediaDownloader.exe").read_bytes() == b"old"
    assert not locations(root)[1].exists()


@pytest.mark.parametrize("phase,new_root", [("moving", False), ("swapping", True)])
def test_recover_after_process_interruption(tmp_path, phase, new_root):
    root = tmp_path / "MediaDownloader"
    backup, state = locations(root)
    portable(backup, b"old")
    if new_root:
        portable(root, b"new")
    journal(state, {"phase": phase})
    assert recover_interrupted(root)
    assert (root / "MediaDownloader.exe").read_bytes() == b"old"


def test_corrupt_package_does_not_touch_installation(tmp_path):
    root = portable(tmp_path / "MediaDownloader", b"old")
    archive = tmp_path / "not.zip"; archive.write_bytes(b"not a zip")
    with pytest.raises(UpdateError):
        apply_update(root, archive, health=lambda _: True)
    assert (root / "MediaDownloader.exe").read_bytes() == b"old"


def test_package_output_cannot_be_inside_source(tmp_path):
    root = portable(tmp_path / "source")
    with pytest.raises(UpdateError):
        build_package(root, root / "bad.zip", "1.0.0")
