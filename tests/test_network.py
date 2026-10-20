"""Functional download test using a real local HTTPS server and verified certificate."""
import functools
import http.server
import ssl
import threading
import zipfile

import pytest
import trustme
from mediadownloader.core import Media, save_selection
from mediadownloader.engines import fetch


def test_verified_https_download_and_zip_preserve_original_bytes(tmp_path, monkeypatch):
    served = tmp_path / "served"; served.mkdir()
    payload = b"original-image-payload\x00\xff" * 20000
    (served / "original.jpg").write_bytes(payload)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
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
        item = Media(2, "foto", f"https://127.0.0.1:{server.server_port}/original.jpg", "jpg", "gallery-dl", "https://instagram.com/p/test/")
        progress = []
        files = save_selection([item], tmp_path / "downloads", True, fetch, threading.Event(), lambda p, _: progress.append(p))
        with zipfile.ZipFile(files[0]) as z:
            assert z.read("002_foto.jpg") == payload
        assert progress[-1] == 100
    finally:
        server.shutdown(); server.server_close(); thread.join()
