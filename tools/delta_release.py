"""Build/test incremental ZIPs against immutable GitHub release packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mediadownloader import __version__
from mediadownloader.updater import build_delta, extract_package, sha256


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def prepare():
    if __version__ == "1.0.7":
        # Bootstrap from our already verified 1.0.6 artifact. Its FFmpeg files
        # need no upgrade for this updater-only transition, even if upstream is down.
        folder = ROOT / "build/patch-base"
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as temp:
                gh('run', 'download', '39534612183', '--name', 'MediaDownloader-Windows-x64', '--dir', temp)
                extract_package(next(Path(temp).glob('*-Windows-x64.zip')), folder)
        return
    folder = ROOT / "build/patch-base"
    if folder.exists():
        return
    folder.parent.mkdir(parents=True, exist_ok=True)
    releases = json.loads(gh("release", "list", "--limit", "50", "--json", "tagName,isDraft,isPrerelease"))
    for release in releases:
        tag = release["tagName"]
        if release["isDraft"] or release["isPrerelease"] or tag == "v" + __version__:
            continue
        try:
            parts = tuple(map(int, tag.removeprefix("v").split(".")))
        except ValueError:
            continue
        if parts < (1, 0, 7):
            continue
        with tempfile.TemporaryDirectory() as temp:
            gh("release", "download", tag, "--pattern", "*-Windows-x64.zip", "--dir", temp)
            extract_package(next(Path(temp).glob("*-Windows-x64.zip")), folder)
        return
    raise RuntimeError("No compatible baseline release: publish 1.0.7 first.")


def build():
    if __version__ == '1.0.7':
        print('Transition release: full package installs incremental updater.')
        return
    prepare()
    with tempfile.TemporaryDirectory(prefix='MediaDownloader-delta-build-') as temp:
        temp = Path(temp)
        baseline = temp / 'baseline'
        shutil.copytree(ROOT / 'build/patch-base', baseline)
        base = json.loads((baseline / 'mediadownloader-update.json').read_text(encoding='utf-8'))
        output = ROOT / 'dist' / f"MediaDownloader-{__version__}-from-{base['version']}-patch.zip"
        patch = build_delta(baseline, ROOT / 'dist/MediaDownloader', output, __version__)
        helper = temp / 'updater.exe'
        shutil.copy2(ROOT / 'dist/MediaDownloader/MediaDownloaderUpdater.exe', helper)
        subprocess.run([str(helper), '--root', str(baseline), '--zip', str(output), '--no-relaunch'],
                       check=True, timeout=300)
        for name, digest in patch['target']['files'].items():
            assert sha256(baseline / name) == digest, name
        subprocess.run([str(helper), '--root', str(baseline), '--restore', '--no-relaunch'],
                       check=True, timeout=300)
        for name, digest in base['files'].items():
            assert sha256(baseline / name) == digest, name
        output.with_suffix('.zip.sha256').write_text(f'{sha256(output)}  {output.name}\n', encoding='ascii')
        message = f"Parche desde {base['version']}: {len(patch['files'])} archivos, {output.stat().st_size / 1024**2:.2f} MiB. Aplicación y recuperación verificadas con el EXE real."
        print(message)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(message + '\n')


def publish():
    tag = 'v' + __version__
    # Never replace a published baseline: subsequent patches depend on its exact bytes.
    existing = subprocess.run(['gh', 'release', 'view', tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if existing.returncode == 0:
        raise RuntimeError('Version already published. Bump the application version; never overwrite a patch baseline.')
    assets = sorted((ROOT / 'dist').glob('MediaDownloader-*-Windows-x64.zip*'))
    assets += sorted((ROOT / 'dist').glob('MediaDownloader-*-patch.zip*'))
    notes = ('Transición: instalar el ZIP completo una vez desde Actualizar programa. Las próximas versiones permiten parches incrementales.'
             if __version__ == '1.0.7' else
             'Para actualizar, descargar el archivo patch correspondiente a la versión instalada. El ZIP Windows-x64 completo es para instalaciones nuevas o reparación.')
    gh('release', 'create', tag, *map(str, assets), '--target', os.environ['GITHUB_SHA'],
       '--title', 'MediaDownloader ' + __version__, '--notes', notes)


if __name__ == '__main__':
    if '--prepare' in sys.argv:
        prepare()
        if (ROOT / 'build/patch-base').exists() and os.environ.get('GITHUB_ENV'):
            with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as f:
                f.write('MEDIADOWNLOADER_FFMPEG_BASELINE=' + str(ROOT / 'build/patch-base') + '\n')
    elif '--publish' in sys.argv:
        publish()
    else:
        build()
