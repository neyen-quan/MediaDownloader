"""Windows x64 build. Run inside Python 3.12 with requirements-dev.txt installed."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mediadownloader import __version__
from mediadownloader.updater import build_package


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def get_ffmpeg():
    # gyan.dev is one of the Windows binary suppliers linked by ffmpeg.org/download.html.
    # Verify its published SHA-256 before using any executable; never disable HTTPS validation.
    cache = ROOT / "build" / "ffmpeg-download"
    cache.mkdir(parents=True, exist_ok=True)
    base = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    checksum = urllib.request.urlopen(base + ".sha256", timeout=60).read().decode().split()[0].lower()
    if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        raise RuntimeError("Invalid upstream FFmpeg checksum")
    archive = cache / "ffmpeg.zip"
    if not archive.exists() or hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != checksum:
        urllib.request.urlretrieve(base, archive)
    with archive.open("rb") as f:
        actual = hashlib.file_digest(f, "sha256").hexdigest()
    if actual != checksum:
        raise RuntimeError("FFmpeg SHA-256 mismatch; refusing to build")
    target = ROOT / "dist" / "MediaDownloader"
    licenses = target / "licenses" / "ffmpeg"
    licenses.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for executable in ("ffmpeg.exe", "ffprobe.exe"):
            names = [n for n in z.namelist() if n.endswith("/bin/" + executable)]
            if len(names) != 1:
                raise RuntimeError("Unexpected FFmpeg archive layout")
            with z.open(names[0]) as src, (target / executable).open("wb") as dst:
                shutil.copyfileobj(src, dst)
        for name in z.namelist():
            leaf = Path(name).name
            if leaf.lower() in {"license", "license.txt", "readme.txt"} and not name.endswith("/"):
                (licenses / leaf).write_bytes(z.read(name))
    (licenses / "ORIGEN.txt").write_text(
        f"Binarios: {base}\nSHA256: {checksum}\nFuente y receta: https://www.gyan.dev/ffmpeg/builds/\n"
        "FFmpeg: https://ffmpeg.org/ (GPL; build essentials de Gyan).\n", encoding="utf-8")
    run(str(target / "ffmpeg.exe"), "-version")
    run(str(target / "ffprobe.exe"), "-version")


def main():
    if sys.platform != "win32":
        raise SystemExit("El portable Windows debe compilarse en Windows, no se renombra un binario Linux.")
    # A console subsystem plus hide-early retains working stdout for isolated engine processes.
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
        "--hide-console", "hide-early", "--name", "MediaDownloader",
        "--collect-all", "gallery_dl", "--collect-all", "yt_dlp",
        "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtPdf", "main.py")
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "MediaDownloaderUpdater", "updater_entry.py")
    target = ROOT / "dist" / "MediaDownloader"
    shutil.copy2(ROOT / "dist" / "MediaDownloaderUpdater.exe", target)
    shutil.copy2(ROOT / "LEEME.txt", target)
    shutil.copy2(ROOT / "THIRD_PARTY.md", target)
    # Running the helper from this location automatically relocates it before replacing files.
    (target / "Recuperar version anterior.cmd").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0MediaDownloaderUpdater.exe" --root "%~dp0." --restore\r\n',
        encoding="ascii")
    # Retain dependency license metadata along with PyInstaller's bundled Qt libraries.
    import importlib.metadata as metadata
    for name in ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "gallery-dl", "yt-dlp", "requests", "certifi"):
        dist = metadata.distribution(name)
        for path in dist.files or []:
            if "dist-info" in str(path) and any(w in str(path).lower() for w in ("license", "copying", "notice")):
                origin = Path(dist.locate_file(path))
                if origin.is_file():
                    dest = target / "licenses" / name / Path(path).name
                    dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(origin, dest)
    get_ffmpeg()
    version = os.environ.get("MEDIADOWNLOADER_VERSION", __version__)
    archive = ROOT / "dist" / f"MediaDownloader-{version}-Windows-x64.zip"
    build_package(target, archive, version)
    digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Portable y actualización: {archive}")


if __name__ == "__main__":
    main()
