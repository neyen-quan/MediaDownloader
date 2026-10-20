import json
import threading
import zipfile
from pathlib import Path

import pytest
from mediadownloader.core import (Media, Settings, UserError, Cancelled, public_url,
                                  save_selection)
from mediadownloader.engines import gallery_items, ytdlp_items, validate_cookies


@pytest.mark.parametrize("url,platform", [
    ("https://www.instagram.com/p/abc123/?igsh=x", "instagram"),
    ("https://instagram.com/reel/abc_123/", "instagram"),
    ("https://vm.tiktok.com/ABC/", "tiktok"),
    ("https://www.tiktok.com/@user/video/123", "tiktok"),
])
def test_public_urls(url, platform):
    found, clean = public_url(url)
    assert found == platform and "?" not in clean


@pytest.mark.parametrize("url", ["http://instagram.com/p/a/", "https://evil.com/p/a/",
    "https://instagram.com.evil.com/p/a/", "https://x:y@instagram.com/p/a/",
    "https://instagram.com:99/p/a/", "https://instagram.com/user/", "file:///tmp/a"])
def test_reject_urls(url):
    with pytest.raises(UserError):
        public_url(url)


def test_settings_atomic(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(str(tmp_path / "Descargas"), "")
    settings.save(path)
    assert Settings.load(path) == settings
    path.write_text("{broken", encoding="utf-8")
    assert Settings.load(path) == Settings()
    path.write_text("[]", encoding="utf-8")
    assert Settings.load(path) == Settings()


def sample_items():
    return [Media(i, "video" if i == 2 else "foto", "https://cdn.test/x", "mp4" if i == 2 else "jpg",
                  "gallery-dl", "https://instagram.com/p/test/") for i in (1, 2, 3)]


def fixture_fetch(item, folder, cancel, progress):
    folder.mkdir(parents=True)
    result = folder / item.filename
    result.write_bytes(f"original-{item.index}".encode())
    progress(100, "Listo")
    return result


def test_mixed_selection_zip_order_and_exact_bytes(tmp_path):
    items = sample_items()
    result = save_selection([items[2], items[1]], tmp_path, True, fixture_fetch,
                            threading.Event(), lambda *_: None)
    with zipfile.ZipFile(result[0]) as z:
        assert z.namelist() == ["002_video.mp4", "003_foto.jpg"]
        assert z.read("002_video.mp4") == b"original-2"
    assert list(tmp_path.iterdir()) == result


def test_does_not_overwrite_and_saves_one_or_all(tmp_path):
    items = sample_items()
    old = tmp_path / items[0].filename
    old.write_bytes(b"previous")
    results = save_selection(items, tmp_path, False, fixture_fetch,
                             threading.Event(), lambda *_: None)
    assert len(results) == 3 and old.read_bytes() == b"previous"
    assert results[0].name == "001_foto (1).jpg"


def test_cancel_zip_leaves_no_partial_output(tmp_path):
    cancel = threading.Event()
    def fetch(*args):
        result = fixture_fetch(*args)
        cancel.set()
        return result
    with pytest.raises(Cancelled):
        save_selection(sample_items(), tmp_path, True, fetch, cancel, lambda *_: None)
    assert not list(tmp_path.iterdir())


def test_empty_selection(tmp_path):
    with pytest.raises(UserError):
        save_selection([], tmp_path, True, fixture_fetch, threading.Event(), lambda *_: None)


def test_gallery_mixed_carousel_and_dash():
    raw = json.dumps([[2, "", {"count": 3}],
        [3, "https://cdn.test/1.jpg", {"extension": "jpg", "count": 3}],
        [3, "ytdl:instagram2.mp4", {"extension": "mp4", "count": 3, "_ytdl_manifest_data": "<MPD/>"}],
        [3, "https://cdn.test/3.jpg", {"extension": "jpg", "count": 3}]])
    items = gallery_items(raw, "https://instagram.com/p/abc/")
    assert [x.kind for x in items] == ["foto", "video", "foto"]
    assert [x.index for x in items] == [1, 2, 3]
    assert items[1].engine == "instagram-dash" and items[1].manifest == "<MPD/>"


def test_partial_carousel_is_not_silently_accepted():
    with pytest.raises(UserError, match="incompleto"):
        gallery_items(json.dumps([[3, "https://cdn.test/1.jpg", {"extension": "jpg", "count": 3}]]), "source")


def test_tiktok_metadata():
    items = ytdlp_items(json.dumps({"id": "123", "title": "Video de prueba", "thumbnail": "https://x/y"}),
                        "https://www.tiktok.com/@x/video/123")
    assert len(items) == 1 and items[0].selector == "123" and items[0].engine == "yt-dlp"


def test_invalid_cookies(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text("not cookies", encoding="utf-8")
    with pytest.raises(UserError, match="Netscape"):
        validate_cookies(str(path))
