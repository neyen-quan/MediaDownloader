"""Exercise yt-dlp + real FFmpeg muxing against a local DASH fixture, without platform access."""
import functools
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from mediadownloader.core import Media
from mediadownloader.engines import fetch, analyze


def test_instagram_extraction_keeps_dash_metadata(monkeypatch):
    seen = []
    def run(engine, args, cancel):
        seen.extend(args)
        return json.dumps([[3, "ytdl:synthetic.mp4", {"extension": "mp4", "count": 1,
                             "_ytdl_manifest_data": "<MPD/>"}]])
    monkeypatch.setattr("mediadownloader.engines.run_engine", run)
    items = analyze("https://www.instagram.com/reel/abc/", "", threading.Event(), lambda *_: None)
    assert "output.private=true" in seen
    assert items[0].engine == "instagram-dash"


def test_dash_best_video_and_audio_are_muxed_without_reencoding(tmp_path, monkeypatch):
    executable = os.environ.get("MEDIADOWNLOADER_TEST_EXE")
    if executable:
        monkeypatch.setattr("mediadownloader.engines.engine_command",
                            lambda engine, args: [str(Path(executable).with_name("MediaDownloaderEngine.exe")), "--engine", engine, *args])
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("FFmpeg no está disponible; la compilación Windows debe ejecutar esta prueba tras instalarlo")
    served = tmp_path / "served"; served.mkdir()
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=160x90:r=10", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "1", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
        # Windows FFmpeg resolves fragment templates from cwd, even with an absolute MPD path.
        "-f", "dash", "manifest.mpd"], cwd=served, check=True, timeout=30)
    # Compare against the encoded files themselves. Reading the MPD through FFmpeg can
    # trim/reorder packets at the presentation boundary, depending on FFmpeg's version.
    references = []
    for representation in (0, 1):
        reference = tmp_path / f"original-{representation}.mp4"
        fragments = sorted(served.glob(f"chunk-stream{representation}-*.m4s"))
        assert fragments, "FFmpeg did not generate the source fragments"
        with reference.open("wb") as output:
            for part in [served / f"init-stream{representation}.m4s", *fragments]:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output)
        references.append(reference)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            requests_seen.append(self.path)
            super().do_GET()
    requests_seen = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(served)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    try:
        # Instagram's inline MPD carries absolute media locations; make the fixture equivalent.
        root = ET.fromstring((served / "manifest.mpd").read_text())
        ns = "{urn:mpeg:dash:schema:mpd:2011}"
        base = ET.Element(ns + "BaseURL"); base.text = f"http://127.0.0.1:{server.server_port}/"
        root.insert(0, base)
        item = Media(1, "video", "ytdl:fixture.mp4", "mkv", "instagram-dash",
                     "https://instagram.com/reel/test/", manifest=ET.tostring(root, encoding="unicode"))
        try:
            path = fetch(item, tmp_path / "result", threading.Event(), lambda *_: None)
        except Exception as error:
            error.add_note("HTTP requests: " + repr(requests_seen))
            error.add_note("Served files: " + repr([p.name for p in served.iterdir()]))
            log = tmp_path / "result" / "engine.log"
            if log.exists():
                error.add_note(log.read_text(encoding="utf-8", errors="replace"))
            raise
        probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, text=True, check=True, timeout=20)
        streams = json.loads(probe.stdout)["streams"]
        assert {s["codec_type"] for s in streams} == {"video", "audio"}
        assert {s["codec_name"] for s in streams} == {"h264", "aac"}
        assert next(s for s in streams if s["codec_type"] == "video")["width"] == 160
        # Canonical elementary streams avoid hashing MP4/MKV packet framing as video data.
        # Both exports use stream copy: no decoder or encoder participates in the comparison.
        def stream_hash(path, selector):
            options = ["-bsf:v", "h264_mp4toannexb", "-f", "h264"] if ":v:" in selector else ["-f", "adts"]
            result = subprocess.run([ffmpeg, "-v", "error", "-i", path.name, "-map", selector,
                "-c", "copy", *options, "-"], cwd=path.parent,
                check=True, capture_output=True, timeout=20)
            return hashlib.sha256(result.stdout).hexdigest()
        assert stream_hash(references[0], "0:v:0") == stream_hash(path, "0:v:0")
        assert stream_hash(references[1], "0:a:0") == stream_hash(path, "0:a:0")
    finally:
        server.shutdown(); server.server_close(); thread.join()
