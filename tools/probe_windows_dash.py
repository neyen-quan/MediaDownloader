import functools
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mediadownloader.core import Media
from mediadownloader.engines import fetch
from mediadownloader import engines

if executable := os.environ.get("MEDIADOWNLOADER_TEST_EXE"):
    engines.engine_command = lambda engine, args: [executable, "--engine", engine, *args]

os.environ["NO_PROXY"] = "127.0.0.1"
with tempfile.TemporaryDirectory(prefix="MediaDownloader-DASH-probe-") as temp:
    for relative in (False, True):
        served = Path(temp) / ("relative" if relative else "absolute")
        served.mkdir()
        output = "manifest.mpd" if relative else str(served / "manifest.mpd")
        subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "color=c=blue:s=160x90:r=10", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "1", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
            "-f", "dash", output], cwd=served, check=True)
        print("SCENARIO", "relative" if relative else "absolute", flush=True)
        print("FILES", [p.name for p in served.iterdir()], flush=True)
        manifest = (served / "manifest.mpd").read_text()
        print(manifest, flush=True)
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                print("HTTP", format % args, flush=True)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(served)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            root = ET.fromstring(manifest)
            base = ET.Element("{urn:mpeg:dash:schema:mpd:2011}BaseURL")
            base.text = f"http://127.0.0.1:{server.server_port}/"; root.insert(0, base)
            item = Media(1, "video", "ytdl:fixture.mp4", "mkv", "instagram-dash", "https://instagram.com/reel/test/",
                         manifest=ET.tostring(root, encoding="unicode"))
            result = served / "result"
            try:
                path = fetch(item, result, threading.Event(), lambda *_: None)
                print("RESULT PASS", path.stat().st_size, flush=True)
            except Exception as error:
                print("RESULT FAIL", type(error).__name__, str(error), flush=True)
            print((result / "engine.log").read_text(encoding="utf-8", errors="replace"), flush=True)
        finally:
            server.shutdown(); server.server_close(); thread.join()
