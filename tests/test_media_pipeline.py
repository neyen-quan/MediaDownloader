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
from mediadownloader.engines import fetch, analyze, engine_command


def test_instagram_extraction_keeps_dash_metadata(monkeypatch):
    seen = []
    def run(engine, args, cancel):
        seen.extend(args)
        return json.dumps([[3, "ytdl:synthetic.mp4", {"extension": "mp4", "count": 1,
                             "_ytdl_manifest_data": "<MPD/>"}]])
    monkeypatch.setattr("mediadownloader.engines.run_engine", run)
    items = analyze("https://www.instagram.com/reel/abc/", "", threading.Event(), lambda *_: None)
    assert "output.private=true" in seen
    assert "extractor.instagram.audio=true" in seen
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


def test_youtube_video_and_audio_with_packaged_runtime_and_ejs(tmp_path, monkeypatch):
    """Exercise actual yt-dlp, JS dependency detection and muxing offline.

    Only platform metadata is supplied locally; downloads, format selection,
    FFmpeg and the optional frozen worker are real. Live YouTube is checked
    separately and is not a deterministic release prerequisite.
    """
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("FFmpeg no está disponible; obligatorio en la compilación Windows")
    served = tmp_path / "served"; served.mkdir()
    for name, size in [("low.mp4", "80x46"), ("high.mp4", "160x90")]:
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s={size}:r=10",
                        "-t", "1", "-an", "-c:v", "libx264", str(served / name)], check=True, timeout=30)
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "1", "-vn", "-c:a", "aac", str(served / "audio.m4a")], check=True, timeout=30)
    seen = []
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            seen.append(self.path)
            super().do_GET()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(served)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    source = "https://www.youtube.com/watch?v=xHEMkbyXFxs"
    base = f"http://127.0.0.1:{server.server_port}/"
    metadata = tmp_path / "fixture.info.json"
    metadata.write_text(json.dumps({"id": "xHEMkbyXFxs", "title": "YouTube fixture", "extractor": "youtube",
        "extractor_key": "Youtube", "webpage_url": source, "duration": 1, "formats": [
            {"format_id": "low", "url": base + "low.mp4", "ext": "mp4", "width": 80, "height": 46, "vcodec": "h264", "acodec": "none"},
            {"format_id": "high", "url": base + "high.mp4", "ext": "mp4", "width": 160, "height": 90, "vcodec": "h264", "acodec": "none"},
            {"format_id": "audio", "url": base + "audio.m4a", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
        ]}), encoding="utf-8")
    executable = os.environ.get("MEDIADOWNLOADER_TEST_EXE")
    def command(engine, args):
        assert engine == "yt-dlp" and args[-1] == source and "--no-playlist" in args
        args = [*args[:-1], "--verbose", "--load-info-json", str(metadata)]
        if executable:
            # Exercise the runtime from the built bundle, not the build machine's Python.
            runtime_index = args.index("--js-runtimes") + 1
            args[runtime_index] = "deno:" + str(Path(executable).parent / "_internal/deno/deno.exe")
            return [str(Path(executable).with_name("MediaDownloaderEngine.exe")), "--engine", engine, *args]
        return engine_command(engine, args)
    monkeypatch.setattr("mediadownloader.engines.engine_command", command)
    try:
        items = analyze(source, "", threading.Event(), lambda *_: None)
        assert len(items) == 1 and items[0].selector == "xHEMkbyXFxs"
        path = fetch(items[0], tmp_path / "result", threading.Event(), lambda *_: None)
        log = (path.parent / "engine.log").read_text(encoding="utf-8", errors="replace")
        assert "JS runtimes: deno-2.9.8" in log, log
        assert "yt_dlp_ejs-0.8.0" in log, log
        streams = json.loads(subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
                                            capture_output=True, text=True, check=True, timeout=20).stdout)["streams"]
        assert {s["codec_type"] for s in streams} == {"video", "audio"}
        assert next(s for s in streams if s["codec_type"] == "video")["width"] == 160
        assert "/high.mp4" in seen and "/audio.m4a" in seen and "/low.mp4" not in seen
        for original, selector, options in [(served / "high.mp4", "0:v:0", ["-bsf:v", "h264_mp4toannexb", "-f", "h264"]),
                                             (served / "audio.m4a", "0:a:0", ["-f", "adts"])]:
            def encoded_bytes(media):
                return subprocess.run([ffmpeg, "-v", "error", "-i", str(media), "-map", selector,
                                       "-c", "copy", *options, "-"], capture_output=True, check=True, timeout=20).stdout
            assert hashlib.sha256(encoded_bytes(original)).digest() == hashlib.sha256(encoded_bytes(path)).digest()
    finally:
        server.shutdown(); server.server_close(); thread.join()

