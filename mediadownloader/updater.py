"""Validated full-package updates with transactional swap and automatic rollback.

SHA-256 verifies integrity, not publisher authenticity. Only install trusted ZIPs.
This module deliberately has no application/Qt dependencies: the helper is standalone.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

APPLICATION = "MediaDownloader"
MANIFEST = "mediadownloader-update.json"
MAX_SIZE = 4 * 1024**3
MAX_FILES = 20000
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class UpdateError(Exception):
    pass


def safe_name(name):
    if not isinstance(name, str) or not name or "\\" in name or name.startswith("/"):
        raise UpdateError("El ZIP contiene una ruta no permitida.")
    parts = name.split("/")
    if any(p in {"", ".", ".."} or p[-1:] in {".", " "} or
           any(ord(c) < 32 or c in '<>:"|?*' for c in p) or
           p.split(".")[0].upper() in RESERVED for p in parts):
        raise UpdateError("El ZIP contiene nombres de archivo inseguros para Windows.")
    if len(name) > 220:
        raise UpdateError("El ZIP contiene una ruta demasiado larga.")
    return PurePosixPath(name)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(raw):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise UpdateError("El manifiesto contiene claves repetidas.")
            result[key] = value
        return result
    try:
        manifest = json.loads(raw, object_pairs_hook=unique_pairs)
        if manifest["application"] != APPLICATION or manifest["schema"] != 1:
            raise ValueError()
        if not isinstance(manifest["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", manifest["version"]):
            raise ValueError()
        files = manifest["files"]
        if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
            raise ValueError()
        names = set()
        for name, digest in files.items():
            safe_name(name)
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError()
            if name.casefold() in names or name.casefold() == MANIFEST:
                raise ValueError()
            names.add(name.casefold())
        if not {"MediaDownloader.exe", "MediaDownloaderUpdater.exe"} <= files.keys():
            raise ValueError()
        return manifest
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        raise UpdateError("El ZIP no es un paquete válido de MediaDownloader (manifiesto incompatible).") from None


def inspect_archive(z):
    infos = z.infolist()
    if len(infos) > MAX_FILES + 1 or sum(i.file_size for i in infos) > MAX_SIZE:
        raise UpdateError("El paquete supera los límites de tamaño o cantidad de archivos.")
    names = set()
    for info in infos:
        safe_name(info.filename)
        mode = (info.external_attr >> 16) & 0xFFFF
        if info.is_dir() or stat.S_ISLNK(mode) or info.flag_bits & 1:
            raise UpdateError("No se admiten directorios explícitos, enlaces ni archivos cifrados en el ZIP.")
        if info.filename.casefold() in names:
            raise UpdateError("El ZIP contiene archivos duplicados.")
        names.add(info.filename.casefold())
    try:
        info = z.getinfo(MANIFEST)
        if info.file_size > 4 * 1024 * 1024:
            raise UpdateError("El manifiesto es demasiado grande.")
        manifest = read_manifest(z.read(MANIFEST))
    except KeyError:
        raise UpdateError("El ZIP no corresponde a MediaDownloader: falta el manifiesto.") from None
    if {i.filename for i in infos} != set(manifest["files"]) | {MANIFEST}:
        raise UpdateError("El contenido del ZIP no coincide con su manifiesto.")
    return manifest


def extract_package(archive, stage):
    """Only extract into a new, empty directory; never call ZipFile.extractall."""
    stage = Path(stage)
    if stage.exists() and any(stage.iterdir()):
        raise UpdateError("La carpeta temporal de actualización no está vacía.")
    stage.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as z:
            manifest = inspect_archive(z)
            for name, expected in manifest["files"].items():
                target = stage.joinpath(*safe_name(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                with z.open(name) as source, target.open("xb") as dest:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        h.update(block)
                        dest.write(block)
                if h.hexdigest() != expected:
                    raise UpdateError(f"El paquete está dañado: no coincide la verificación de {name}.")
            (stage / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
            return manifest
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        raise UpdateError("No se pudo leer o extraer el ZIP. Comprobá el espacio libre y los permisos.") from e


def validate_package(archive):
    with tempfile.TemporaryDirectory(prefix="MediaDownloader-check-") as stage:
        return extract_package(archive, Path(stage))


def build_package(root, output, version):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents:
        raise UpdateError("Guardá el ZIP fuera de la carpeta que estás empaquetando.")
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise UpdateError("No se pueden empaquetar enlaces simbólicos.")
        if p.is_file() and p.name != MANIFEST:
            name = p.relative_to(root).as_posix()
            safe_name(name)
            files[name] = sha256(p)
    manifest = {"application": APPLICATION, "schema": 1, "version": version, "files": files}
    read_manifest(json.dumps(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".part")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
            for name in files:
                z.write(root / name, name)
            z.writestr(MANIFEST, json.dumps(manifest, indent=2))
        validate_package(temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def locations(root):
    root = Path(root).resolve()
    return (root.parent / (root.name + ".previous"),
            root.parent / (root.name + ".update-state.json"))


def check_backup_path(path):
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir() or not all(
                (path / name).is_file() for name in ("MediaDownloader.exe", "MediaDownloaderUpdater.exe")):
            raise UpdateError(f"La carpeta reservada {path.name} contiene datos ajenos al programa. Movela antes de actualizar.")
        if (path / MANIFEST).exists():
            read_manifest((path / MANIFEST).read_bytes())


def journal(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


@contextmanager
def update_lock(root):
    path = root.parent / (root.name + ".update.lock")
    with path.open("a+b") as f:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0); f.write(b"0"); f.flush(); f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateError("Ya hay una actualización en curso.") from None
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def recover_interrupted(root):
    """Only our own deterministic sibling paths are accepted, never paths from JSON."""
    backup, state = locations(root)
    older = root.parent / (root.name + ".older")
    if not state.exists():
        return False
    try:
        phase = json.loads(state.read_text(encoding="utf-8"))["phase"]
    except (OSError, ValueError, KeyError):
        raise UpdateError("El registro de actualización está dañado; conservá las carpetas actual y .previous.") from None
    if phase in {"prepared", "moving"} and root.exists():
        if older.exists() and not backup.exists():
            older.rename(backup)
        state.unlink()
        return False
    if backup.exists():
        failed = root.parent / (root.name + ".failed")
        check_backup_path(backup)
        check_backup_path(failed)
        if root.exists():
            if failed.exists():
                shutil.rmtree(failed)
            root.rename(failed)
        backup.rename(root)
        if older.exists():
            older.rename(backup)
        state.unlink()
        return True
    raise UpdateError("La actualización quedó interrumpida y no se encontró la copia anterior.")


def smoke(root):
    try:
        result = subprocess.run([str(root / "MediaDownloader.exe"), "--smoke-test"], cwd=root,
                                timeout=60, creationflags=0x08000000 if os.name == "nt" else 0)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def managed_files(root):
    manifest = root / MANIFEST
    if manifest.exists():
        return set(read_manifest(manifest.read_bytes())["files"]) | {MANIFEST}
    # Only for first installs predating the manifest format. Never assume arbitrary files are app files.
    return {"MediaDownloader.exe", "MediaDownloaderUpdater.exe", MANIFEST} | {
        p.relative_to(root).as_posix() for p in (root / "_internal").rglob("*") if p.is_file()}


def preserve_user_files(root, stage):
    managed, replacement = managed_files(root), managed_files(stage)
    replacement_folded = {n.casefold() for n in replacement}
    for source in root.rglob("*"):
        if source.is_symlink():
            raise UpdateError("La carpeta portable contiene enlaces. Mové tus descargas fuera del programa antes de actualizar.")
        if not source.is_file():
            continue
        name = source.relative_to(root).as_posix()
        if name in managed:
            continue
        if name.casefold() in replacement_folded:
            raise UpdateError("Un archivo personal coincide con un archivo de la nueva versión. Movelo fuera del programa antes de actualizar.")
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def apply_update(root, archive=None, restore=False, health=smoke):
    root = Path(root).resolve()
    backup, state = locations(root)
    with update_lock(root):
        check_backup_path(backup)
        check_backup_path(root.parent / (root.name + ".older"))
        if recover_interrupted(root):
            return "recovered"
        if not (root / "MediaDownloader.exe").is_file():
            raise UpdateError("No se encontró la instalación portable de MediaDownloader.")
        stage = Path(tempfile.mkdtemp(prefix=root.name + ".stage-", dir=root.parent))
        older = root.parent / (root.name + ".older")
        try:
            if restore:
                if not backup.is_dir():
                    raise UpdateError("Todavía no hay una versión anterior para recuperar.")
                # Preserve the backup until the replacement is completely prepared.
                shutil.copytree(backup, stage, dirs_exist_ok=True)
            else:
                extract_package(archive, stage)
            preserve_user_files(root, stage)
            journal(state, {"phase": "prepared"})
            if older.exists():
                shutil.rmtree(older)
            if backup.exists():
                backup.rename(older)
            # Journal precedes both moves: crash recovery covers either move boundary.
            journal(state, {"phase": "moving"})
            try:
                root.rename(backup)
                journal(state, {"phase": "swapping"})
                stage.rename(root)
                if not health(root):
                    raise UpdateError("La nueva versión no pudo arrancar. Se recuperó la versión anterior.")
            except BaseException:
                if backup.exists():
                    if root.exists():
                        shutil.rmtree(root)
                    backup.rename(root)
                if older.exists():
                    older.rename(backup)
                state.unlink(missing_ok=True)
                raise
            state.unlink(missing_ok=True)
            if older.exists():
                shutil.rmtree(older)
            return "restored" if restore else "updated"
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def wait_parent(pid, timeout=90):
    if not pid:
        return
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:  # already exited
                return
            raise UpdateError("No se pudo esperar el cierre del programa. Cerralo y ejecutá Recuperar versión anterior.cmd.")
        try:
            if kernel.WaitForSingleObject(handle, timeout * 1000) != 0:
                raise UpdateError("Cerrá MediaDownloader antes de actualizar.")
        finally:
            kernel.CloseHandle(handle)
    else:
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.2)
        raise UpdateError("Cerrá MediaDownloader antes de actualizar.")


def helper_main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--parent", type=int, default=0)
    parser.add_argument("--no-relaunch", action="store_true", help="Validación automatizada: no abrir ventanas ni reiniciar al terminar")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    # The recovery launcher also works from .previous if a power cut left the main folder absent.
    if args.restore and root.name.endswith(".previous"):
        original = root.with_name(root.name.removesuffix(".previous"))
        if locations(original)[1].exists():
            root = original
            args.root = original
    # Even a manual restore must relocate the helper before touching its installation.
    if getattr(sys, "frozen", False) and any(p in Path(sys.executable).resolve().parents
                                              for p in (root, locations(root)[0])):
        temp = Path(tempfile.mkdtemp(prefix="MediaDownloader-recovery-"))
        helper = temp / "MediaDownloaderUpdater.exe"
        shutil.copy2(sys.executable, helper)
        forwarded = ["--root", str(root), "--parent", str(os.getpid())]
        if args.zip:
            forwarded += ["--zip", str(args.zip.resolve())]
        if args.restore:
            forwarded += ["--restore"]
        if args.no_relaunch:
            forwarded += ["--no-relaunch"]
        subprocess.Popen([str(helper), *forwarded], cwd=temp)
        return 0
    try:
        wait_parent(args.parent)
        apply_update(root, args.zip, args.restore)
        if not args.no_relaunch:
            subprocess.Popen([str(root / "MediaDownloader.exe")], cwd=root)
        return 0
    except Exception as error:
        log = root.parent / (root.name + ".update-error.txt")
        message = str(error) if isinstance(error, UpdateError) else (
            "No se pudo aplicar la actualización. Revisá los permisos, el espacio libre y que el programa esté cerrado. "
            f"La copia anterior se conserva. Detalle: {type(error).__name__}.")
        try:
            log.write_text(message, encoding="utf-8")
        except OSError:
            pass
        if os.name == "nt" and not args.no_relaunch:
            ctypes.windll.user32.MessageBoxW(None, message, APPLICATION, 0x10)
        if not args.no_relaunch and (root / "MediaDownloader.exe").exists():
            subprocess.Popen([str(root / "MediaDownloader.exe")], cwd=root)
        return 1
