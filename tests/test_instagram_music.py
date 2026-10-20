"""Regressions for gallery-dl's count including a separate music track."""
import json
from types import SimpleNamespace

import pytest
from gallery_dl.extractor.instagram import InstagramExtractor
from mediadownloader.core import UserError
from mediadownloader.engines import gallery_items


SOURCE = "https://www.instagram.com/p/test/"


def extractor_messages(*, audio=True, reel=False):
    """Run the installed extractor's enumeration, including its real count logic."""
    visual = [dict(num=1, media_id="1", display_url="https://cdn.test/1.jpg",
                   video_url="https://cdn.test/1.mp4" if reel else None)]
    if not reel:
        visual.append(dict(num=2, media_id="2", display_url="https://cdn.test/2.jpg"))
    music = dict(num=len(visual) + 1, media_id="music",
                 audio_url="https://cdn.test/music.m4a", display_url="https://cdn.test/cover.jpg")
    config = {"videos": True, "audio": audio, "previews": False, "order-files": "asc"}
    extractor = SimpleNamespace(
        login=lambda: None, metadata=lambda: {}, _user=None,
        config=lambda key, default=None: config.get(key, default),
        posts=lambda: iter([{"post_url": SOURCE, "_files": visual + [music]}]),
        _parse_post=lambda post: post)
    messages = []
    for kind, url, meta in InstagramExtractor.items(extractor):
        messages.append([int(kind), meta] if int(kind) == 2 else [int(kind), url, meta])
    return json.dumps(messages)


@pytest.mark.parametrize("reel", [False, True])
def test_music_is_counted_but_never_shown_as_photo_or_video(reel):
    raw = extractor_messages(reel=reel)
    items = gallery_items(raw, SOURCE)
    assert len(items) == (1 if reel else 2)
    assert [item.index for item in items] == list(range(1, len(items) + 1))
    assert items[0].kind == ("video" if reel else "foto")
    assert all("music" not in item.url and "cover" not in item.url for item in items)


def test_old_audio_false_configuration_reproduces_false_incomplete_error():
    with pytest.raises(UserError, match="incompleto"):
        gallery_items(extractor_messages(audio=False), SOURCE)


def test_music_does_not_hide_missing_carousel_image():
    messages = json.loads(extractor_messages())
    del messages[2]  # Remove the second photo, keeping count=3 and the music URL.
    with pytest.raises(UserError, match="2 de 3"):
        gallery_items(json.dumps(messages), SOURCE)


@pytest.mark.parametrize("message,expected", [
    ("HTTP redirect to login page", "rechazó la sesión"),
    ("HTTP 429 Too Many Requests", "limitó temporalmente"),
    ("ProxyError: tunnel failed", "proxy"),
])
def test_extractor_errors_explain_the_cause_without_echoing_raw_details(message, expected):
    secret = " private-session-value"
    with pytest.raises(UserError, match=expected) as exc:
        gallery_items(json.dumps([[-1, {"error": "AbortExtraction", "message": message + secret}]]), SOURCE)
    assert secret not in str(exc.value)
