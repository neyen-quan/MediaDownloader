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
        if parts < (1, 0, 7) or parts >= tuple(map(int, __version__.split("."))):
            continue
        with tempfile.TemporaryDirectory() as temp:
            gh("release", "download", tag, "--pattern", "*-Windows-x64.zip", "--dir", temp)
            extract_package(next(Path(temp).glob("*-Windows-x64.zip")), folder)
        return
    raise RuntimeError("No compatible baseline release: publish 1.0.7 first.")


def build():
    prepare()
    with tempfile.TemporaryDirectory(prefix='MediaDownloader-delta-build-') as temp:
        temp = Path(temp)
        baseline = temp / 'baseline'
        shutil.copytree(ROOT / 'build/patch-base', baseline)
        base = json.loads((baseline / 'mediadownloader-update.json').read_text(encoding='utf-8'))
        output = ROOT / 'dist' / f"MediaDownloader-{__version__}-from-{base['version']}-patch.zip"
        patch = build_delta(baseline, ROOT / 'dist/MediaDownloader', output, __version__)
        helper = temp / 'updater.exe'
        shutil.copy2(baseline / 'MediaDownloaderUpdater.exe', helper)
        subprocess.run([str(helper), '--root', str(baseline), '--zip', str(output), '--no-relaunch'],
                       check=True, timeout=300)
        for name, digest in patch['target']['files'].items():
            assert sha256(baseline / name) == digest, name
        # Restore using the new helper, after proving the old helper accepts this transition.
        shutil.copy2(baseline / 'MediaDownloaderUpdater.exe', helper)
        subprocess.run([str(helper), '--root', str(baseline), '--restore', '--no-relaunch'],
                       check=True, timeout=300)
        for name, digest in base['files'].items():
            assert sha256(baseline / name) == digest, name
        output.with_suffix('.zip.sha256').write_text(f'{sha256(output)}  {output.name}\n', encoding='ascii')
        write_channel(base['version'], output)
        # Keep direct online updates available to the two preceding releases.
        # Each baseline is downloaded verbatim, never recreated from source.
        releases = json.loads(gh('release', 'list', '--limit', '50', '--json', 'tagName,isDraft,isPrerelease'))
        versions = []
        for release in releases:
            if release['isDraft'] or release['isPrerelease']:
                continue
            try:
                parts = tuple(map(int, release['tagName'].removeprefix('v').split('.')))
            except ValueError:
                continue
            if len(parts) == 3 and (1, 0, 8) <= parts < tuple(map(int, __version__.split('.'))):
                versions.append(parts)
        for parts in sorted(set(versions), reverse=True)[:2]:
            older_version = '.'.join(map(str, parts))
            if older_version == base['version']:
                continue
            with tempfile.TemporaryDirectory() as older_dir:
                gh('release', 'download', 'v' + older_version, '--pattern', '*-Windows-x64.zip', '--dir', older_dir)
                older_root = Path(older_dir) / 'base'
                older_manifest = extract_package(next(Path(older_dir).glob('*-Windows-x64.zip')), older_root)
                extra = ROOT / 'dist' / f'MediaDownloader-{__version__}-from-{older_version}-patch.zip'
                build_delta(older_root, ROOT / 'dist/MediaDownloader', extra, __version__)
                extra_helper = Path(older_dir) / 'updater.exe'
                shutil.copy2(older_root / 'MediaDownloaderUpdater.exe', extra_helper)
                subprocess.run([str(extra_helper), '--root', str(older_root), '--zip', str(extra), '--no-relaunch'], check=True, timeout=300)
                for name, digest in patch['target']['files'].items():
                    assert sha256(older_root / name) == digest, name
                shutil.copy2(older_root / 'MediaDownloaderUpdater.exe', extra_helper)
                subprocess.run([str(extra_helper), '--root', str(older_root), '--restore', '--no-relaunch'], check=True, timeout=300)
                for name, digest in older_manifest['files'].items():
                    assert sha256(older_root / name) == digest, name
                extra.with_suffix('.zip.sha256').write_text(f'{sha256(extra)}  {extra.name}\n', encoding='ascii')
                feed_path = ROOT / 'dist/latest.json'
                feed = json.loads(feed_path.read_text())
                repo = os.environ.get('GITHUB_REPOSITORY', 'neyen-quan/MediaDownloader')
                feed['patches'].append({'from':older_version,'to':__version__, 'url':f'https://github.com/{repo}/releases/download/v{__version__}/{extra.name}', 'sha256':sha256(extra),'size':extra.stat().st_size})
                feed_path.write_text(json.dumps(feed, indent=2), encoding='utf-8')

        # HTTPS transfer is exercised against a controlled server; the same channel
        # client then validates the exact payload used by the Windows updater.
        from tools.test_online_package import verify_online_package
        verify_online_package(output, base['version'], patch['version'], ROOT / 'dist/latest.json')
        message = f"Parche desde {base['version']}: {len(patch['files'])} archivos, {output.stat().st_size / 1024**2:.2f} MiB. Aplicación y recuperación verificadas con el EXE real."
        print(message)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
                f.write(message + '\n')


def write_channel(base_version, patch):
    repo = os.environ.get('GITHUB_REPOSITORY', 'neyen-quan/MediaDownloader')
    url = f'https://github.com/{repo}/releases/download/v{__version__}/'
    full = ROOT / 'dist' / f'MediaDownloader-{__version__}-Windows-x64.zip'
    feed = {'schema': 1, 'product': 'MediaDownloader', 'version': __version__,
            'patches': [{'from': base_version, 'to': __version__, 'url': url + patch.name,
                         'sha256': sha256(patch), 'size': patch.stat().st_size}],
            'full': {'url': url + full.name, 'sha256': sha256(full), 'size': full.stat().st_size}}
    repair = ROOT / 'dist/MediaDownloader-Repararactualizador.exe'
    if repair.exists():
        feed['recovery'] = {'url': url + repair.name, 'sha256': sha256(repair), 'size': repair.stat().st_size}
    (ROOT / 'dist/latest.json').write_text(json.dumps(feed, indent=2), encoding='utf-8')


def verify_release(tag):
    from mediadownloader.update_channel import check
    import threading
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        gh('release', 'download', tag, '--pattern', 'latest.json', '--dir', temp)
        feed = json.loads((folder / 'latest.json').read_text(encoding='utf-8-sig'))
        if feed['version'] != tag.removeprefix('v') or feed['product'] != 'MediaDownloader':
            raise RuntimeError('Published channel identity/version mismatch')
        for asset in [feed['full'], *feed['patches'], *([feed['recovery']] if 'recovery' in feed else [])]:
            name = asset['url'].rsplit('/', 1)[-1]
            expected_prefix = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/download/{tag}/"
            if asset['url'] != expected_prefix + name or '/' in name or '..' in name:
                raise RuntimeError('Unexpected asset URL')
            gh('release', 'download', tag, '--pattern', name, '--dir', temp)
            path = folder / name
            if path.stat().st_size != asset['size'] or sha256(path) != asset['sha256']:
                raise RuntimeError('Published SHA-256 mismatch: ' + name)
        # Parse every patch through the application's own schema/version checks.
        from unittest.mock import patch
        from mediadownloader import update_channel
        class LocalResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_content(self, *args): yield (folder / 'latest.json').read_bytes()
        with patch.object(update_channel, 'response', return_value=LocalResponse()):
            check(update_channel.DEFAULT_CHANNEL, feed['version'], threading.Event())
    print('PASS: published assets, byte counts, SHA-256 and channel schema')


def publish():
    tag = 'v' + __version__
    source = os.environ.get('MEDIADOWNLOADER_SOURCE_SHA', os.environ.get('GITHUB_SHA'))
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets,isDraft'], capture_output=True, text=True)
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        if any(a['name'] == 'latest.json' for a in release['assets']) and not release['isDraft']:
            verify_release(tag)
            print('Existing complete release verified; immutable assets preserved.')
            return
        gh('release', 'edit', tag, '--draft=true')
    else:
        gh('release', 'create', tag, '--target', source, '--draft', '--title', 'MediaDownloader ' + __version__,
           '--notes', 'Instalación nueva: paquete Windows-x64. Actualización: Actualizar programa → Buscar actualizaciones → Descargar e instalar. ZIP local disponible como alternativa.')
    assets = sorted((ROOT / 'dist').glob('MediaDownloader-*.zip*'))
    assets += sorted((ROOT / 'dist').glob('MediaDownloader-Repararactualizador.exe*'))
    gh('release', 'upload', tag, *map(str, assets), '--clobber')
    gh('release', 'upload', tag, str(ROOT / 'dist/latest.json'), '--clobber')
    verify_release(tag)  # Verify downloaded bytes before making the release public/latest.
    gh('release', 'edit', tag, '--draft=false', '--latest')
    # Check the real public stable channel; allow the CDN a short propagation delay.
    import time, threading
    from mediadownloader.update_channel import check, DEFAULT_CHANNEL
    for attempt in range(8):
        try:
            info = check(DEFAULT_CHANNEL, __version__, threading.Event())
            if info['available'] == __version__ and info['up_to_date']:
                print('PASS: public latest.json is ready')
                return
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError('Assets verified, but public latest.json is not ready yet; recover this tag using workflow_dispatch.')


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

