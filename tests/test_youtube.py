"""Single-video links preserve identity and use the complete video/audio engine."""
import json
import threading

import pytest
from yt_dlp.extractor.youtube import YoutubeIE

from mediadownloader import engines
from mediadownloader.core import UserError, public_url


SOURCE = "https://www.youtube.com/watch?v=xHEMkbyXFxs"


@pytest.mark.parametrize("url", [
    SOURCE,
    SOURCE + "&list=PLexample&index=2&t=90#fragment",
    "https://youtube.com/watch?si=tracking&v=xHEMkbyXFxs",
    "https://m.youtube.com/watch?v=xHEMkbyXFxs",
    "https://music.youtube.com/watch?v=xHEMkbyXFxs",
    "https://youtu.be/xHEMkbyXFxs?si=tracking&t=5",
    "https://www.youtu.be/xHEMkbyXFxs/",
    "https://www.youtube.com/shorts/xHEMkbyXFxs?feature=share",
    "https://www.youtube.com/live/xHEMkbyXFxs?si=tracking",
    "https://www.youtube.com/embed/xHEMkbyXFxs",
])
def test_shared_video_links_preserve_video_identity_and_remove_playlist_and_tracking(url):
    assert public_url(url) == ("youtube", SOURCE)
    assert YoutubeIE.suitable(public_url(url)[1])


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/",
    "https://www.youtube.com/playlist?list=PLexample",
    "https://www.youtube.com/@example",
    "https://www.youtube.com/watch?list=PLexample",
    SOURCE + "&v=abcdefghijk",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/watch?v=xHEMkbyXFxs/extra",
    "https://youtu.be/xHEMkbyXFxs/extra",
    "https://www.youtube.com/shorts/xHEMkbyXFxs/extra",
    "https://www.youtube.com.evil.test/watch?v=xHEMkbyXFxs",
    "https://www.youtube.com@evil.test/watch?v=xHEMkbyXFxs",
    "https://user:password@www.youtube.com/watch?v=xHEMkbyXFxs",
    "https://www.youtube.com:444/watch?v=xHEMkbyXFxs",
    "http://www.youtube.com/watch?v=xHEMkbyXFxs",
])
def test_non_video_and_malformed_youtube_links_are_rejected(url):
    with pytest.raises(UserError):
        public_url(url)


def test_analysis_uses_one_video_with_explicit_bundled_runtime(monkeypatch):
    calls = []
    def run(engine, args, cancel):
        calls.append((engine, args))
        return json.dumps({"id": "xHEMkbyXFxs", "title": "Video de prueba", "thumbnail": "https://cdn.test/thumb.jpg"})
    monkeypatch.setattr(engines, "run_engine", run)
    items = engines.analyze(SOURCE + "&list=PLexample", "", threading.Event(), lambda *_: None)
    assert len(items) == 1
    assert (items[0].source, items[0].selector, items[0].engine, items[0].ext) == (SOURCE, "xHEMkbyXFxs", "yt-dlp", "mkv")
    engine, args = calls[0]
    assert engine == "yt-dlp" and args[-1] == SOURCE
    assert "--no-playlist" in args and "--no-js-runtimes" in args
    assert args[args.index("--js-runtimes") + 1].startswith("deno:")
    assert "--remote-components" not in args


@pytest.mark.parametrize("status", ["is_live", "is_upcoming"])
def test_analysis_does_not_start_an_unbounded_livestream(status):
    with pytest.raises(UserError, match="finalizado"):
        engines.ytdlp_items(json.dumps({"id": "xHEMkbyXFxs", "live_status": status}), SOURCE)


def test_completed_livestream_is_a_normal_download():
    assert len(engines.ytdlp_items(json.dumps({"id": "xHEMkbyXFxs", "live_status": "was_live"}), SOURCE)) == 1
