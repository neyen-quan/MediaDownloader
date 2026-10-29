"""Story URL/session handling and the real pinned extractor against offline API data."""
import copy
import io
import json
import threading
from types import SimpleNamespace

import pytest
import requests
from gallery_dl.extractor.instagram import InstagramStoriesExtractor
from gallery_dl.job import DataJob

from mediadownloader.core import UserError, public_url
from mediadownloader import engines


STORIES = "https://www.instagram.com/stories/example.name/"


@pytest.mark.parametrize("url,expected", [
    (STORIES, STORIES),
    (STORIES + "22/?igsh=tracking#fragment", STORIES + "22/"),
    ("https://m.instagram.com/stories/example.name/22", STORIES + "22"),
    ("https://instagram.com/stories/example.name/", STORIES),
])
def test_story_links_are_canonical_and_keep_the_exact_media_id(url, expected):
    assert public_url(url) == ("instagram", expected)
    assert InstagramStoriesExtractor.from_url(expected) is not None


@pytest.mark.parametrize("suffix", ["", "me/", "highlights/", "highlights/22/",
    "example.name/not-an-id/", "example.name/22/extra", "example%2Fname/22/",
    "example.name/../22/", "a" * 31 + "/22/"])
def test_invalid_or_special_story_links_are_rejected(suffix):
    with pytest.raises(UserError):
        public_url("https://www.instagram.com/stories/" + suffix)


def session_file(tmp_path, domain=".instagram.com", expires=0, name="sessionid"):
    path = tmp_path / "session-fixture.txt"
    path.write_text("# Netscape HTTP Cookie File\n"
                    f"{domain}\tTRUE\t/\tTRUE\t{expires}\t{name}\tfixture-value\n", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("kind", ["missing", "expired", "other-site", "no-sessionid"])
def test_stories_explain_missing_or_expired_instagram_session_before_network(tmp_path, monkeypatch, kind):
    if kind == "expired": path = session_file(tmp_path, expires=1)
    elif kind == "other-site": path = session_file(tmp_path, domain=".example.test")
    elif kind == "no-sessionid": path = session_file(tmp_path, name="csrftoken")
    else: path = ""
    def network(*args, **kwargs):
        raise AssertionError("No network request should be made without an Instagram session")
    monkeypatch.setattr(engines, "run_engine", network)
    with pytest.raises(UserError, match="Sesión local"):
        engines.analyze(STORIES, path, threading.Event(), lambda *_: None)


def story_api_payload():
    def item(pk, video=False):
        result = {"pk": str(pk), "taken_at": 100,
                  "image_versions2": {"candidates": [{"url": f"https://cdn.test/{pk}.jpg",
                                                       "width": 1080, "height": 1920}]}}
        if video:
            result["video_versions"] = [{"url": f"https://cdn.test/{pk}.mp4", "width": 1080, "height": 1920}]
            result["video_dash_manifest"] = "<MPD/>"
        return result
    return [{"id": "123", "seen": 100, "user": {"pk": "123", "username": "example.name"},
             "items": [item(11), item(22, video=True), item(33)]}]


def extractor_output(source):
    extractor = InstagramStoriesExtractor.from_url(source)
    extractor.session = requests.Session()
    extractor.initialize()
    extractor.config = lambda key, default=None: {
        "videos": True, "audio": True, "previews": False, "order-files": "asc"
    }.get(key, default)
    extractor.login = lambda: None
    extractor.api = SimpleNamespace(user=lambda name: {"id": "123"},
        reels_media=lambda ids: copy.deepcopy(story_api_payload()))
    output = io.StringIO()
    # Real DataJob also captures NotFoundError as [-1, {error, message}].
    job = DataJob(extractor, file=output)
    job.filter = dict.copy  # Equivalent to output.private=true in production.
    job.run()
    extractor.session.close()
    return output.getvalue()


@pytest.mark.parametrize("expiry", [0, "", 4102444800])
@pytest.mark.parametrize("suffix,kinds", [("", ["foto", "video", "foto"]),
    ("11/", ["foto"]), ("22/", ["video"])])
def test_analyze_uses_pinned_story_extractor_for_exact_story_or_active_set(tmp_path, monkeypatch, suffix, kinds, expiry):
    calls = []
    def run(engine, args, cancel):
        calls.append((engine, args))
        return extractor_output(args[-1])
    monkeypatch.setattr(engines, "run_engine", run)
    cookies = session_file(tmp_path, expires=expiry)
    items = engines.analyze(STORIES + suffix + "?igsh=tracking", cookies, threading.Event(), lambda *_: None)
    assert [item.kind for item in items] == kinds
    assert [item.index for item in items] == list(range(1, len(items) + 1))
    assert all(item.source == STORIES + suffix for item in items)
    video = next((item for item in items if item.kind == "video"), None)
    if video:
        assert video.engine == "instagram-dash" and video.manifest == "<MPD/>"
        assert video.thumbnail == "https://cdn.test/22.jpg"
    assert calls[0][0] == "gallery-dl"
    args = calls[0][1]
    assert args[args.index("--cookies") + 1] == cookies
    assert "--ignore-config" in args and "output.private=true" in args


def test_expired_or_missing_exact_story_is_not_replaced_with_other_active_stories():
    raw = extractor_output(STORIES + "999/")
    with pytest.raises(UserError, match="historia ya no está disponible"):
        engines.gallery_items(raw, STORIES + "999/")


def test_empty_story_result_has_actionable_message():
    with pytest.raises(UserError, match="No hay historias disponibles"):
        engines.gallery_items("[]", STORIES)


def test_revoked_session_error_is_recognized_without_exposing_details():
    raw = json.dumps([[-1, {"error": "AuthenticationError", "message": "fixture-private-value"}]])
    with pytest.raises(UserError, match="Renová las cookies") as error:
        engines.gallery_items(raw, STORIES)
    assert "fixture-private-value" not in str(error.value)
