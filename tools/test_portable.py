"""Exercise the actual generated Windows executables, including external updater."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import struct
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mediadownloader.updater import build_package, extract_package, sha256, locations


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
