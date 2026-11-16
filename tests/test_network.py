"""Functional download test using a real local HTTPS server and verified certificate."""
import functools
import gzip
import http.server
import ssl
import threading
import zipfile

import pytest
import trustme
from mediadownloader.core import Cancelled, Media, UserError, save_selection
from mediadownloader.engines import direct_download, fetch


@pytest.fixture
def https_media(tmp_path, monkeypatch):
    served = tmp_path / "served"; served.mkdir()
    payload = b"original-image-payload\x00\xff" * 20000
    (served / "original.jpg").write_bytes(payload)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            if self.path in {"/compressed.jpg", "/truncated.jpg"}:
                body = gzip.compress(payload) if self.path == "/compressed.jpg" else payload
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(body) + (1 if self.path == "/truncated.jpg" else 0)))
                if self.path == "/compressed.jpg":
                    self.send_header("Content-Encoding", "gzip")
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(served)))
    ca = trustme.CA(); cert = ca.issue_cert("127.0.0.1")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); cert.configure_cert(context)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    ca.cert_pem.write_to_path(tmp_path / "ca.pem")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "ca.pem"))
    # Keep this fixture local even on machines with mandatory remote HTTP proxies.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}", payload
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_verified_https_download_and_zip_preserve_original_bytes(tmp_path, https_media):
    base, payload = https_media
    item = Media(2, "foto", base + "/original.jpg", "jpg", "gallery-dl", "https://instagram.com/p/test/")
    progress = []
    files = save_selection([item], tmp_path / "downloads", True, fetch, threading.Event(), lambda p, _: progress.append(p))
    with zipfile.ZipFile(files[0]) as archive:
        assert archive.read("002_foto.jpg") == payload
    assert progress[-1] == 100
    assert progress == sorted(progress)


def test_http_content_encoding_keeps_original_bytes_without_false_length_error(tmp_path, https_media):
    base, payload = https_media
    path = tmp_path / "original.jpg"
    direct_download(base + "/compressed.jpg", path, threading.Event(), lambda *_: None)
    assert path.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("cancelled", [False, True])
def test_incomplete_or_cancelled_download_never_replaces_complete_file(tmp_path, https_media, cancelled):
    base, _ = https_media
    path = tmp_path / "original.jpg"
    path.write_bytes(b"previous-complete-download")
    cancel = threading.Event()
    def progress(*_):
        if cancelled:
            cancel.set()
    expected = Cancelled if cancelled else UserError
    url = base + ("/original.jpg" if cancelled else "/truncated.jpg")
    with pytest.raises(expected):
        direct_download(url, path, cancel, progress)
    assert path.read_bytes() == b"previous-complete-download"
    assert not list(tmp_path.glob("*.part"))


def test_already_cancelled_download_does_not_open_network(monkeypatch, tmp_path):
    cancel = threading.Event()
    cancel.set()
    def no_session(*_):
        pytest.fail("A cancelled download must not open a connection")
    monkeypatch.setattr("mediadownloader.engines.session", no_session)
    with pytest.raises(Cancelled):
        direct_download("https://cdn.test/original.jpg", tmp_path / "original.jpg", cancel, lambda *_: None)
    assert not list(tmp_path.iterdir())

