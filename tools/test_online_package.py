"""Exercise production channel/download validation over a real local HTTPS transfer."""
import functools
import http.server
import json
from pathlib import Path
import ssl
import tempfile
import threading
from unittest.mock import patch

import requests
import trustme
from mediadownloader import update_channel
from mediadownloader.updater import validate_package


def verify_online_package(archive, installed, target, feed_path):
    archive = Path(archive)
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        ca = trustme.CA(); cert = ca.issue_cert('localhost')
        ca.cert_pem.write_to_path(temp / 'ca.pem')
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                path = Path(feed_path) if self.path == '/latest.json' else archive
                self.send_response(200); self.send_header('Content-Length', str(path.stat().st_size)); self.end_headers()
                with path.open('rb') as f:
                    import shutil
                    shutil.copyfileobj(f, self.wfile)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); cert.configure_cert(context)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        def local_response(url, cancel):
            suffix = '/latest.json' if url.endswith('/latest.json') else '/patch.zip'
            session = requests.Session(); session.trust_env = False
            return session.get(f'https://localhost:{server.server_port}' + suffix, stream=True,
                               verify=str(temp / 'ca.pem'), timeout=20)
        try:
            with patch.object(update_channel, 'response', side_effect=local_response):
                info = update_channel.check(update_channel.DEFAULT_CHANNEL, installed, threading.Event())
                if not info['patch'] or info['available'] != target:
                    raise AssertionError('Channel does not offer the expected update')
                path = update_channel.download(info, temp / 'downloads', threading.Event(), lambda *_: None)
                manifest = validate_package(path)
                assert manifest['schema'] == 2 and manifest['base']['version'] == installed and manifest['version'] == target
                current = update_channel.check(update_channel.DEFAULT_CHANNEL, target, threading.Event())
                assert current['up_to_date']
            print('PASS: HTTPS channel → streamed ZIP → SHA-256 → internal validation → latest-version check')
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=5)
