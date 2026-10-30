"""Exercise the actual generated Windows executables, including external updater."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import struct
import json
import stat
import ctypes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mediadownloader.updater import build_package, build_delta, extract_package, sha256, locations, prepare_helper, journal, recover_interrupted


def main():
    if os.name != "nt":
        raise SystemExit("Esta prueba debe ejecutarse en Windows con los .exe reales.")
    archive = next((ROOT / "dist").glob("MediaDownloader-*-Windows-x64.zip"))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="MediaDownloader-portable-test-") as temp:
        temp = Path(temp)
        root = temp / "MediaDownloader"
        manifest = extract_package(archive, root)
        exe = root / "MediaDownloader.exe"
        # PE subsystem 2 (Windows GUI) cannot allocate a startup console.
        # Subsystem 3 is reserved for the engine, always launched with CREATE_NO_WINDOW.
        def subsystem(path):
            with path.open("rb") as source:
                source.seek(0x3c)
                pe_offset = struct.unpack("<I", source.read(4))[0]
                source.seek(pe_offset)
                assert source.read(4) == b"PE\x00\x00"
                source.seek(pe_offset + 24 + 68)
                return struct.unpack("<H", source.read(2))[0]
        worker = root / "MediaDownloaderEngine.exe"
        assert subsystem(exe) == 2, "GUI executable would create a terminal"
        assert subsystem(worker) == 3, "Engine must retain redirected standard streams"
        subprocess.run([str(exe), "--smoke-test"], check=True, timeout=90)
        progress_report = temp / 'progress.json'
        subprocess.run([str(root / 'MediaDownloaderUpdater.exe'), '--root', str(root),
                        '--no-relaunch', '--progress-report', str(progress_report)], check=True, timeout=45)
        states = json.loads(progress_report.read_text(encoding='utf-8'))
        assert all(s['visible'] for s in states), states
        assert states[1]['position'] == 45 and states[2]['position'] == 100, states
        assert states[1]['text'] == 'Verificando archivos…', states
        # Use the actual frozen updater to apply a tiny patch that omits all DLLs/FFmpeg.
        delta_target = temp / "delta-target"; shutil.copytree(root, delta_target)
        (delta_target / "licenses/PATCH-TEST.txt").write_text("incremental update")
        delta_zip = temp / "incremental.zip"
        delta = build_delta(root, delta_target, delta_zip, "99.0.0-test")
        assert set(delta["files"]) == {"licenses/PATCH-TEST.txt"}
        delta_helper = temp / "delta-helper.exe"
        shutil.copy2(root / "MediaDownloaderUpdater.exe", delta_helper)
        subprocess.run([str(delta_helper), "--root", str(root), "--zip", str(delta_zip),
                        "--no-relaunch"], check=True, timeout=240)
        assert (root / "licenses/PATCH-TEST.txt").exists()
        subprocess.run([str(delta_helper), "--root", str(root), "--restore", "--no-relaunch"],
                       check=True, timeout=240)
        assert not (root / "licenses/PATCH-TEST.txt").exists()
        # Exercise a real Windows HWND and read back the exact Shell pinning properties.
        # Offscreen Qt handles cannot test Windows taskbar metadata.
        shell_report = temp / "shell-properties.json"
        native_env = os.environ.copy()
        native_env["QT_QPA_PLATFORM"] = "windows"
        subprocess.run([str(exe), "--smoke-test", "--shell-report", str(shell_report)],
                       env=native_env, check=True, timeout=90)
        shell_properties = json.loads(shell_report.read_text(encoding="utf-8"))
        assert shell_properties == {
            "command": subprocess.list2cmdline([str(exe.resolve())]),
            "icon": str((root / "MediaDownloader.ico").resolve()) + ",0",
            "name": "MediaDownloader",
            "id": "Neyen.MediaDownloader.Desktop",
        }, shell_properties
        for engine in ("gallery-dl", "yt-dlp"):
            result = subprocess.run([str(worker), "--engine", engine, "--version"],
                                    check=True, timeout=45, capture_output=True, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.stdout.strip(), f"Frozen engine {engine} did not execute"
        # The previous process must release its EXE/DLL handles before a Windows update can swap directories.
        parent = subprocess.Popen([str(exe), "--smoke-test"])
        helper = temp / "MediaDownloaderUpdater.exe"
        shutil.copy2(root / helper.name, helper)
        subprocess.run([str(helper), "--root", str(root), "--zip", str(archive),
                        "--parent", str(parent.pid), "--no-relaunch"], check=True, timeout=240)
        parent.wait(timeout=90)
        assert locations(root)[0].is_dir()
        for name, digest in manifest["files"].items():
            assert sha256(root / name) == digest, name
        subprocess.run([str(exe), "--smoke-test"], check=True, timeout=90)
        subprocess.run([str(helper), "--root", str(root), "--restore", "--no-relaunch"], check=True, timeout=240)
        # A real pre-existing read-only backup previously failed before the swap.
        # Exercise the incoming verified helper and its compiled error handling.
        older = root.with_name(root.name + '.older')
        shutil.copytree(locations(root)[0], older)
        (older / 'MediaDownloader.exe').chmod(stat.S_IREAD)
        (older / 'mediadownloader-update.json').chmod(stat.S_IREAD)
        incoming = temp / 'incoming-helper.exe'
        prepare_helper(root, archive, incoming)
        subprocess.run([str(incoming), '--root', str(root), '--zip', str(archive),
                        '--no-relaunch'], check=True, timeout=240)
        assert not older.exists()
        assert sha256(exe) == manifest['files']['MediaDownloader.exe']
        # Reproduce the failed repair: an old directory cannot be deleted before
        # staging, and the previous attempt left a prepared journal beside it.
        older.mkdir()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        locked = kernel.CreateFileW(str(older), 0x80, 3, None, 3, 0x02000000, None)
        assert locked not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
        try:
            try:
                older.rmdir()
            except PermissionError:
                pass
            else:
                raise AssertionError('Directory deletion was not actually locked')
            journal(locations(root)[1], {'phase': 'prepared'})
            subprocess.run([str(incoming), '--root', str(root), '--zip', str(archive),
                            '--no-relaunch'], check=True, timeout=240)
            assert sha256(exe) == manifest['files']['MediaDownloader.exe']
            assert json.loads(locations(root)[1].read_text())['phase'] == 'committed'
            # Even the next operation must work while the stale folder is locked.
            subprocess.run([str(incoming), '--root', str(root), '--restore',
                            '--no-relaunch'], check=True, timeout=240)
        finally:
            kernel.CloseHandle(locked)
        assert recover_interrupted(root) is False
        assert not older.exists() and not locations(root)[1].exists()
        # Deliberately broken executable with a valid manifest tests post-update startup rollback.
        broken = temp / "broken"; shutil.copytree(root, broken)
        (broken / "MediaDownloader.exe").write_bytes(b"not a Windows executable")
        broken_zip = temp / "broken.zip"; build_package(broken, broken_zip, "0.0.0-test")
        result = subprocess.run([str(helper), "--root", str(root), "--zip", str(broken_zip),
                                 "--no-relaunch"], timeout=240)
        assert result.returncode != 0, "Broken release unexpectedly passed"
        assert sha256(exe) == manifest["files"]["MediaDownloader.exe"]
        subprocess.run([str(exe), "--smoke-test"], check=True, timeout=90)
    print("PASS: Windows EXE startup, frozen engines, update, restore and failed-start rollback")


if __name__ == "__main__":
    main()

