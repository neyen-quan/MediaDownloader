import hashlib
import json
import threading

import pytest
from mediadownloader import update_channel as channel
from mediadownloader.core import UserError, Cancelled, Settings

URL = channel.DEFAULT_CHANNEL
DATA = b'fixture package'


def feed():
    return {'schema': 1, 'product': 'MediaDownloader', 'version': '1.0.9', 'patches': [
        {'from': '1.0.8', 'to': '1.0.9', 'url': 'https://github.com/test/app/releases/download/v1.0.9/patch.zip',
         'sha256': hashlib.sha256(DATA).hexdigest(), 'size': len(DATA)}]}


class Response:
    def __init__(self, data, code=200, location=''):
        self.data = data; self.status_code = code; self.headers = {'Location': location}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, *args): yield self.data
    def close(self): pass
    def raise_for_status(self):
        if self.status_code != 200: raise channel.requests.HTTPError()


def install_response(monkeypatch, data):
    monkeypatch.setattr(channel, 'response', lambda *_: Response(data))


@pytest.mark.parametrize('url', ['http://github.com/a/latest.json', 'https://github.com.evil.test/a/latest.json',
    'https://user:pass@github.com/a/latest.json', 'https://github.com:123/a/latest.json', 'file:///tmp/latest.json',
    'https://github.com/a/latest.json?token=fixture', 'https://127.0.0.1/latest.json'])
def test_channel_url_rejected(url):
    assert not channel.valid_url(url, channel=True)


def test_redirect_to_other_host_rejected_before_following(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        assert kwargs['allow_redirects'] is False
        return Response(b'', 302, 'https://other.test/patch.zip')
    monkeypatch.setattr(channel.requests, 'get', get)
    with pytest.raises(UserError, match='permitida'):
        channel.response(URL, threading.Event())
    assert len(calls) == 1


@pytest.mark.parametrize('change', [
    lambda f: f.update(product='PhotoBatch'), lambda f: f.update(version='invalid'),
    lambda f: f['patches'][0].update(to='1.0.10'), lambda f: f['patches'][0].update(sha256='bad'),
    lambda f: f['patches'][0].update(size=-1), lambda f: f['patches'][0].update(url='https://other.test/x'),
    lambda f: f['patches'][0].update(**{'from': '1.0.10'}), lambda f: f['patches'].append(f['patches'][0].copy()),
])
def test_bad_feed_never_offers_install(monkeypatch, change):
    value = feed(); change(value); install_response(monkeypatch, json.dumps(value).encode())
    with pytest.raises(UserError): channel.check(URL, '1.0.8', threading.Event())


def test_available_up_to_date_and_unsupported(monkeypatch):
    install_response(monkeypatch, json.dumps(feed()).encode())
    assert channel.check(URL, '1.0.8', threading.Event())['patch']
    assert channel.check(URL, '1.0.9', threading.Event())['up_to_date']
    older = channel.check(URL, '1.0.7', threading.Event())
    assert not older['patch'] and not older['up_to_date']


@pytest.mark.parametrize('data', [b'corrupt package', DATA[:-1], DATA + b'extra'])
def test_bad_download_removed_before_install(tmp_path, monkeypatch, data):
    install_response(monkeypatch, data)
    info = {'patch': feed()['patches'][0], 'installed': '1.0.8', 'available': '1.0.9'}
    with pytest.raises(UserError): channel.download(info, tmp_path, threading.Event(), lambda *_: None)
    assert not list(tmp_path.iterdir())


def test_valid_download_and_cancel_cleanup(tmp_path, monkeypatch):
    install_response(monkeypatch, DATA)
    info = {'patch': feed()['patches'][0], 'installed': '1.0.8', 'available': '1.0.9'}
    result = channel.download(info, tmp_path, threading.Event(), lambda *_: None)
    assert result.read_bytes() == DATA and result.suffix == '.zip'
    result.unlink()
    cancel = threading.Event(); cancel.set()
    with pytest.raises(Cancelled): channel.download(info, tmp_path, cancel, lambda *_: None)
    assert not list(tmp_path.iterdir())


def test_legacy_settings_preserved_with_configurable_channel(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'destination': 'fixture-downloads', 'cookies': 'fixture-session.txt'}))
    s = Settings.load(path)
    assert s.update_channel == URL
    s.update_channel = 'https://github.com/example/channel/releases/latest/download/latest.json'; s.save(path)
    assert Settings.load(path) == s and s.destination == 'fixture-downloads' and s.cookies == 'fixture-session.txt'
