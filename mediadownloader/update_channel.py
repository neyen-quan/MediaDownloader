"""Bounded HTTPS GitHub channel; never send platform cookies to update hosts."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, urljoin

import requests
from .core import UserError, check_cancel

DEFAULT_CHANNEL = 'https://github.com/neyen-quan/MediaDownloader/releases/latest/download/latest.json'
HOSTS = {'github.com', 'raw.githubusercontent.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
MAX_DOWNLOAD = 512 * 1024**2


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise UserError('Versión de actualización inválida.')
    return tuple(map(int, value.split('.')))


def valid_url(value, channel=False):
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and u.hostname in HOSTS and not u.username and not u.password
                and u.port in (None, 443) and not u.fragment and len(value) < 4096
                and (not channel or (u.path.endswith('/latest.json') and not u.query)))
    except (ValueError, TypeError):
        return False


def response(url, cancel):
    for _ in range(6):
        check_cancel(cancel)
        if not valid_url(url):
            raise UserError('Dirección de actualización no permitida. Usá HTTPS de GitHub.')
        try:
            result = requests.get(url, stream=True, allow_redirects=False, timeout=(15, 30),
                                  headers={'User-Agent': 'MediaDownloader-Updater', 'Accept': 'application/octet-stream'})
            if result.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, result.headers.get('Location', ''))
                result.close()
                continue
            result.raise_for_status()
            return result
        except requests.RequestException:
            raise UserError('No se pudo consultar GitHub. Revisá la conexión o intentá más tarde.') from None
    raise UserError('Demasiadas redirecciones en el canal de actualización.')


def check(channel, installed, cancel):
    if not valid_url(channel, channel=True):
        raise UserError('El canal debe ser una URL HTTPS de GitHub que termine en /latest.json.')
    version(installed)
    with response(channel, cancel) as r:
        raw = bytearray()
        for chunk in r.iter_content(16384):
            check_cancel(cancel)
            raw.extend(chunk)
            if len(raw) > 256 * 1024:
                raise UserError('El canal supera el tamaño permitido.')
    try:
        feed = json.loads(raw.decode('utf-8-sig'))
        if feed['product'] != 'MediaDownloader' or feed['schema'] != 1:
            raise ValueError()
        available = feed['version']; version(available)
        patches = feed['patches']
        if not isinstance(patches, list) or len(patches) > 100:
            raise ValueError()
        seen = set()
        for p in patches:
            version(p['from'])
            if p['from'] in seen or p['to'] != available or version(p['from']) >= version(available):
                raise ValueError()
            seen.add(p['from'])
            if not valid_url(p['url']) or not re.fullmatch(r'[a-f0-9]{64}', p['sha256']):
                raise ValueError()
            if type(p['size']) is not int or not 0 < p['size'] <= MAX_DOWNLOAD:
                raise ValueError()
        patch = next((p for p in patches if p['from'] == installed), None)
        return {'installed': installed, 'available': available,
                'up_to_date': version(available) <= version(installed), 'patch': patch, 'channel': channel}
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        raise UserError('El canal de MediaDownloader es inválido o incompatible.') from None


def download(info, folder, cancel, progress):
    p = info.get('patch')
    if not p or p['from'] != info['installed'] or p['to'] != info['available'] or version(p['to']) <= version(p['from']):
        raise UserError('No hay parche compatible con la versión instalada.')
    if not valid_url(p['url']) or not re.fullmatch(r'[a-f0-9]{64}', p['sha256']) or not 0 < p['size'] <= MAX_DOWNLOAD:
        raise UserError('Datos de descarga inválidos.')
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='patch-', suffix='.zip.part', dir=folder)
    import os
    path = Path(name)
    try:
        received = 0; digest = hashlib.sha256()
        with os.fdopen(fd, 'wb') as output, response(p['url'], cancel) as r:
            for chunk in r.iter_content(256 * 1024):
                check_cancel(cancel)
                received += len(chunk)
                if received > p['size']:
                    raise UserError('El parche supera el tamaño anunciado.')
                output.write(chunk); digest.update(chunk)
                progress(int(received * 100 / p['size']), 'Descargando actualización…')
            output.flush(); os.fsync(output.fileno())
        if received != p['size'] or digest.hexdigest() != p['sha256']:
            raise UserError('No coincide el SHA-256 o el tamaño del parche. No se instalará.')
        target = path.with_suffix(''); path.replace(target)
        return target
    except BaseException:
        path.unlink(missing_ok=True)
        raise
