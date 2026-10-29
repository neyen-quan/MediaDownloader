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
import traceback
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

APPLICATION = "MediaDownloader"
MANIFEST = "mediadownloader-update.json"
MAX_SIZE = 4 * 1024**3
MAX_FILES = 20000
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
TOP_FILES = {"MediaDownloader.exe", "MediaDownloaderEngine.exe", "MediaDownloaderUpdater.exe",
             "MediaDownloader.ico", "ffmpeg.exe", "ffprobe.exe", "LEEME.txt", "THIRD_PARTY.md",
             "LICENSE", "Recuperar version anterior.cmd"}


def allowed_file(name):
    return name in TOP_FILES or name.startswith(("_internal/", "licenses/", "resources/"))


class UpdateError(Exception):
    pass


def emit_progress(progress, value, message, cancel=None):
    if cancel is not None and cancel.is_set():
        raise UpdateError('Operación cancelada.')
    if progress:
        progress(value, message)


def retry_filesystem(action, progress=None, message='Esperando que Windows libere los archivos…', timeout=3):
    """Retry temporary sharing/access violations without hiding persistent failures."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return action()
        except OSError as error:
            if not (isinstance(error, PermissionError) or getattr(error, 'winerror', None) in (5, 32, 33)):
                raise
            if time.monotonic() >= deadline:
                raise
            emit_progress(progress, -1, message)
            time.sleep(0.1)


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
        if manifest["application"] != APPLICATION or manifest["schema"] not in (1, 2):
            raise ValueError()
        if not isinstance(manifest["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", manifest["version"]):
            raise ValueError()
        files = manifest["files"]
        if not isinstance(files, dict) or (not files and manifest["schema"] == 1) or len(files) > MAX_FILES:
            raise ValueError()
        names = set()
        for name, digest in files.items():
            safe_name(name)
            if not allowed_file(name):
                raise ValueError()
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError()
            if name.casefold() in names or name.casefold() == MANIFEST:
                raise ValueError()
            names.add(name.casefold())
        if manifest["schema"] == 2:
            base, target = manifest["base"], manifest["target"]
            if base.get("schema") != 1 or target.get("schema") != 1:
                raise ValueError()
            read_manifest(json.dumps(base)); read_manifest(json.dumps(target))
            if target["version"] != manifest["version"] or base["version"] == target["version"]:
                raise ValueError()
            if all(re.fullmatch(r"\d+\.\d+\.\d+", x["version"]) for x in (base, target)):
                if tuple(map(int, target["version"].split('.'))) <= tuple(map(int, base["version"].split('.'))):
                    raise ValueError()
            changed = {n: h for n, h in target["files"].items() if base["files"].get(n) != h}
            if files != changed:
                raise ValueError()
        elif not {"MediaDownloader.exe", "MediaDownloaderUpdater.exe"} <= files.keys():
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


def extract_package(archive, stage, progress=None, cancel=None):
    """Only extract into a new, empty directory; never call ZipFile.extractall."""
    stage = Path(stage)
    if stage.exists() and any(stage.iterdir()):
        raise UpdateError("La carpeta temporal de actualización no está vacía.")
    stage.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as z:
            manifest = inspect_archive(z)
            total = sum(z.getinfo(n).file_size for n in manifest['files']) or 1
            received = 0
            emit_progress(progress, 0, 'Verificando y extrayendo el paquete…', cancel)
            for name, expected in manifest["files"].items():
                target = stage.joinpath(*safe_name(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                with z.open(name) as source, target.open("xb") as dest:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        h.update(block)
                        dest.write(block)
                        received += len(block)
                        emit_progress(progress, int(received * 100 / total), 'Verificando y extrayendo el paquete…', cancel)
                if h.hexdigest() != expected:
                    raise UpdateError(f"El paquete está dañado: no coincide la verificación de {name}.")
            (stage / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
            return manifest
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        raise UpdateError("No se pudo leer o extraer el ZIP. Comprobá el espacio libre y los permisos.") from e


def validate_package(archive, installed=None, progress=None, cancel=None):
    with tempfile.TemporaryDirectory(prefix="MediaDownloader-check-") as stage:
        manifest = extract_package(archive, Path(stage), progress, cancel)
        if installed is not None and manifest["schema"] == 2:
            materialize_delta(Path(installed), Path(stage), manifest, progress, cancel)
        elif installed is not None:
            check_target_version(Path(installed), manifest)
        return manifest


def check_target_version(root, manifest):
    path = root / MANIFEST
    if path.exists():
        installed = read_manifest(path.read_bytes())['version']
        target = manifest['version']
        if all(re.fullmatch(r'\d+\.\d+\.\d+', x) for x in (installed, target)):
            if tuple(map(int, target.split('.'))) < tuple(map(int, installed.split('.'))):
                raise UpdateError('El ZIP contiene una versión anterior. Usá Recuperar versión anterior para volver atrás.')


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


def build_delta(base, target, output, version):
    """Create a changed-files-only ZIP against an exact, installed full manifest."""
    base, target, output = Path(base).resolve(), Path(target).resolve(), Path(output).resolve()
    if base in output.parents or target in output.parents:
        raise UpdateError("Guardá el parche fuera de las carpetas de origen.")
    baseline = read_manifest((base / MANIFEST).read_bytes())
    if baseline["schema"] != 1:
        raise UpdateError("La base debe ser una instalación completa.")
    for name, digest in baseline["files"].items():
        if sha256(base / name) != digest:
            raise UpdateError("La instalación de referencia fue modificada.")
    files = {}
    for path in sorted(target.rglob("*")):
        if path.is_symlink():
            raise UpdateError("No se pueden empaquetar enlaces simbólicos.")
        if path.is_file() and path.name != MANIFEST:
            name = path.relative_to(target).as_posix()
            safe_name(name)
            files[name] = sha256(path)
    complete = {"application": APPLICATION, "schema": 1, "version": version, "files": files}
    manifest = {"application": APPLICATION, "schema": 2, "version": version,
                "base": baseline, "target": complete,
                "files": {n: h for n, h in files.items() if baseline["files"].get(n) != h}}
    read_manifest(json.dumps(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".part")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
            for name in manifest["files"]:
                z.write(target / name, name)
            z.writestr(MANIFEST, json.dumps(manifest, indent=2))
        validate_package(temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def materialize_delta(root, stage, manifest, progress=None, cancel=None):
    """Reconstruct in staging; never modify the live installation in place."""
    base, target = manifest["base"], manifest["target"]
    try:
        installed = read_manifest((root / MANIFEST).read_bytes())
    except OSError:
        raise UpdateError("Falta la versión base del parche. Instalá primero la actualización de transición.") from None
    if installed != base:
        raise UpdateError(f"Este parche requiere MediaDownloader {base['version']}. No corresponde a la instalación actual.")
    # Check all managed files, including ones removed/replaced in the target.
    for i, (name, digest) in enumerate(base['files'].items(), 1):
        emit_progress(progress, int(i * 100 / len(base['files'])), f"Validando instalación actual: archivo {i}/{len(base['files'])}", cancel)
        path = root / name
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise UpdateError("La instalación base está incompleta o modificada. Usá el paquete completo para repararla.")
    for i, (name, digest) in enumerate(target['files'].items(), 1):
        emit_progress(progress, int(i * 100 / len(target['files'])), f"Preparando nueva versión: archivo {i}/{len(target['files'])}", cancel)
        path = stage / name
        if name not in manifest["files"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, path)
        if sha256(path) != digest:
            raise UpdateError("No se pudo reconstruir y verificar la nueva versión.")
    (stage / MANIFEST).write_text(json.dumps(target), encoding="utf-8")


def check_backup_path(path, partial=False):
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise UpdateError(f"La carpeta reservada {path.name} contiene datos ajenos al programa. Movela antes de actualizar.")
        identified = False
        if (path / MANIFEST).exists():
            identified = read_manifest((path / MANIFEST).read_bytes())['schema'] == 1
        if not (partial and (identified or not any(path.iterdir()))) and not all(
                (path / name).is_file() for name in ("MediaDownloader.exe", "MediaDownloaderUpdater.exe")):
            raise UpdateError(f"La carpeta reservada {path.name} contiene datos ajenos al programa. Movela antes de actualizar.")


def remove_old_backup(path):
    """Keep the product manifest until last so an interrupted cleanup is identifiable."""
    if not path.exists():
        return
    check_backup_path(path, partial=True)
    for entry in path.iterdir():
        if entry.name == MANIFEST:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    (path / MANIFEST).unlink(missing_ok=True)
    path.rmdir()


def finish_committed_update(root, progress=None):
    """Optional cleanup can never turn an already healthy installation into failure."""
    _, state = locations(root)
    older = root.parent / (root.name + '.older')
    try:
        emit_progress(progress, -1, 'Finalizando la actualización y limpiando el respaldo antiguo…')
        retry_filesystem(lambda: remove_old_backup(older), progress)
        retry_filesystem(lambda: state.unlink(missing_ok=True), progress)
        return True
    except (OSError, UpdateError):
        # Keep the committed journal. A later update retries cleanup and MUST NOT
        # interpret this as an interrupted swap or revert the healthy version.
        emit_progress(progress, 100, 'Actualización instalada. La limpieza del respaldo antiguo queda pendiente.')
        return False


def journal(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    retry_filesystem(lambda: os.replace(temporary, path))


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
                try:
                    f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass  # Closing the descriptor releases the lock regardless.


def recover_interrupted(root, progress=None):
    """Only our own deterministic sibling paths are accepted, never paths from JSON."""
    backup, state = locations(root)
    older = root.parent / (root.name + ".older")
    if not state.exists():
        return False
    try:
        phase = json.loads(state.read_text(encoding="utf-8"))["phase"]
    except (OSError, ValueError, KeyError):
        raise UpdateError("El registro de actualización está dañado; conservá las carpetas actual y .previous.") from None
    if phase == 'committed' and root.exists():
        check_backup_path(root)
        finish_committed_update(root, progress)
        return False
    if phase in {"prepared", "moving"} and root.exists():
        if older.exists() and not backup.exists():
            retry_filesystem(lambda: older.rename(backup), progress)
        retry_filesystem(state.unlink, progress)
        return False
    if backup.exists():
        failed = root.parent / (root.name + ".failed")
        check_backup_path(backup)
        check_backup_path(failed)
        if root.exists():
            if failed.exists():
                retry_filesystem(lambda: shutil.rmtree(failed), progress)
            retry_filesystem(lambda: root.rename(failed), progress)
        retry_filesystem(lambda: backup.rename(root), progress)
        if older.exists():
            retry_filesystem(lambda: older.rename(backup), progress)
        retry_filesystem(state.unlink, progress)
        return True
    raise UpdateError("La actualización quedó interrumpida y no se encontró la copia anterior.")


def smoke(root, progress=None):
    try:
        args = [str(root / 'MediaDownloader.exe'), '--smoke-test']
        manifest = read_manifest((root / MANIFEST).read_bytes())
        if re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']):
            args += ['--expected-version', manifest['version']]
        process = retry_filesystem(lambda: subprocess.Popen(args, cwd=root,
            creationflags=0x08000000 if os.name == 'nt' else 0), progress,
            'Esperando que Windows permita comprobar el arranque…')
        started = time.monotonic()
        while process.poll() is None:
            emit_progress(progress, -1, 'Comprobando el arranque de la nueva versión…')
            if time.monotonic() - started > 60:
                process.kill(); process.wait()
                return False
            time.sleep(0.1)
        return process.returncode == 0
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


def apply_update(root, archive=None, restore=False, health=smoke, progress=None):
    root = Path(root).resolve()
    backup, state = locations(root)
    emit_progress(progress, -1, 'Preparando actualización y recuperación…')
    with update_lock(root):
        check_backup_path(backup)
        check_backup_path(root.parent / (root.name + ".older"), partial=True)
        if recover_interrupted(root, progress):
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
                emit_progress(progress, -1, 'Preparando la versión anterior…')
                shutil.copytree(backup, stage, dirs_exist_ok=True)
            else:
                manifest = extract_package(archive, stage, progress)
                check_target_version(root, manifest)
                if manifest["schema"] == 2:
                    materialize_delta(root, stage, manifest, progress)
            emit_progress(progress, -1, 'Conservando archivos personales y preparando respaldo…')
            preserve_user_files(root, stage)
            journal(state, {"phase": "prepared"})
            if older.exists():
                retry_filesystem(lambda: remove_old_backup(older), progress)
            if backup.exists():
                retry_filesystem(lambda: backup.rename(older), progress)
            # Journal precedes both moves: crash recovery covers either move boundary.
            journal(state, {"phase": "moving"})
            try:
                emit_progress(progress, -1, 'Respaldando la versión actual…')
                retry_filesystem(lambda: root.rename(backup), progress)
                journal(state, {"phase": "swapping"})
                emit_progress(progress, -1, 'Instalando la nueva versión…')
                retry_filesystem(lambda: stage.rename(root), progress)
                emit_progress(progress, -1, 'Comprobando el arranque de la nueva versión…')
                healthy = smoke(root, progress) if health is smoke else health(root)
                if not healthy:
                    raise UpdateError("La nueva versión no pudo arrancar. Se recuperó la versión anterior.")
                emit_progress(progress, -1, 'Confirmando la instalación verificada…')
                journal(state, {"phase": "committed"})
            except BaseException:
                emit_progress(progress, -1, 'Recuperando la copia anterior…')
                if backup.exists():
                    if root.exists():
                        retry_filesystem(lambda: shutil.rmtree(root), progress)
                    retry_filesystem(lambda: backup.rename(root), progress)
                if older.exists():
                    retry_filesystem(lambda: older.rename(backup), progress)
                retry_filesystem(lambda: state.unlink(missing_ok=True), progress)
                raise
            finish_committed_update(root, progress)
            emit_progress(progress, 100, 'Actualización completada. Reiniciando MediaDownloader…')
            return "restored" if restore else "updated"
        finally:
            if stage.exists():
                try:
                    shutil.rmtree(stage)
                except OSError:
                    pass  # A temporary-directory cleanup must not mask the result.


def wait_parent(pid, timeout=90, progress=None):
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
            started = time.monotonic()
            while True:
                result = kernel.WaitForSingleObject(handle, 100)
                if result == 0: break
                if result != 0x102: raise UpdateError('No se pudo esperar el cierre de MediaDownloader.')
                emit_progress(progress, -1, 'Esperando el cierre de MediaDownloader…')
                if time.monotonic() - started > timeout:
                    raise UpdateError('Cerrá MediaDownloader antes de actualizar.')
        finally:
            kernel.CloseHandle(handle)
    else:
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            emit_progress(progress, -1, 'Esperando el cierre de MediaDownloader…')
            time.sleep(0.2)
        raise UpdateError("Cerrá MediaDownloader antes de actualizar.")


def helper_main(argv=None):
    if os.name == 'nt' and not (sys.argv[1:] if argv is None else argv):
        # One-time repair for releases whose nested confirmation loop lost the
        # pending installation. It invokes this SAME transactional updater.
        from .install_progress import choose_file
        ctypes.windll.user32.MessageBoxW(None,
            'Cerrá MediaDownloader. Luego elegí su MediaDownloader.exe y el ZIP del parche. Tus datos se conservan.',
            APPLICATION, 0x40)
        executable = choose_file('Elegí el MediaDownloader.exe que usás', 'MediaDownloader.exe\0MediaDownloader.exe\0\0')
        if executable is None: return 0
        if executable.name.lower() != 'mediadownloader.exe': return 1
        archive = choose_file('Elegí el ZIP de actualización sin descomprimir', 'Actualización ZIP\0*.zip\0\0')
        if archive is None: return 0
        if ctypes.windll.user32.MessageBoxW(None, '¿Aplicar el parche elegido y reiniciar MediaDownloader?', APPLICATION, 0x24) != 6:
            return 0
        argv = ['--root', str(executable.parent), '--zip', str(archive)]
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--parent", type=int, default=0)
    parser.add_argument("--progress-report", type=Path)
    parser.add_argument("--no-relaunch", action="store_true", help="Validación automatizada: no abrir ventanas ni reiniciar al terminar")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    from .install_progress import ProgressWindow
    if args.progress_report:
        window = ProgressWindow(root)
        try:
            states = []
            for value, text in [(-1,'Preparando actualización…'),(45,'Verificando archivos…'),(100,'Listo')]:
                window(value, text); states.append(window.snapshot())
            args.progress_report.write_text(json.dumps(states), encoding='utf-8')
        finally:
            window.close()
        return 0
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
    window = ProgressWindow(root) if os.name == 'nt' and not args.no_relaunch else None
    phase = 'Preparando actualización'
    def progress(value, message):
        nonlocal phase
        phase = message
        if window:
            window(value, message)
    outcome = None
    try:
        wait_parent(args.parent, progress=progress)
        outcome = apply_update(root, args.zip, args.restore, progress=progress)
        if not args.no_relaunch:
            progress(-1, 'Abriendo MediaDownloader actualizado…')
            retry_filesystem(lambda: subprocess.Popen([str(root / "MediaDownloader.exe")], cwd=root), progress)
        return 0
    except Exception as error:
        log = root.parent / (root.name + ".update-error.txt")
        if outcome is not None:
            message = ("La instalación terminó, pero Windows no permitió abrir MediaDownloader automáticamente. "
                       "Abrí MediaDownloader.exe desde su carpeta. "
                       f"Detalle: {type(error).__name__}.")
        else:
            message = str(error) if isinstance(error, UpdateError) else (
                "No se pudo completar la actualización. Revisá los permisos, el espacio libre y que el programa esté cerrado. "
                f"Conservá las carpetas actual y .previous. Detalle: {type(error).__name__}.")
        try:
            log.write_text(message + f'\n\nEtapa: {phase}\nResultado: {outcome or "sin confirmar"}\n'
                           + traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        if os.name == "nt" and not args.no_relaunch:
            ctypes.windll.user32.MessageBoxW(None, message, APPLICATION, 0x10)
        if not args.no_relaunch and outcome is None and (root / "MediaDownloader.exe").exists():
            try:
                retry_filesystem(lambda: subprocess.Popen([str(root / "MediaDownloader.exe")], cwd=root), progress)
            except OSError:
                pass
        return 1
    finally:
        if window:
            window.close()
