"""Instagram account-prefixed links must reach the full carousel extractor."""
import json
import threading

import pytest
from gallery_dl.extractor.instagram import InstagramPostExtractor

from mediadownloader import engines
from mediadownloader.core import UserError, public_url


@pytest.mark.parametrize('url,expected', [
    ('https://www.instagram.com/mackennn_/p/DX_8HDHjNtX/?img_index=1',
     'https://www.instagram.com/p/DX_8HDHjNtX/'),
    ('https://www.instagram.com/example.name/p/AbC_12-3?img_index=4&igsh=tracking#fragment',
     'https://www.instagram.com/p/AbC_12-3/'),
    ('https://m.instagram.com/example_name/reel/AbC_12-3/',
     'https://www.instagram.com/reel/AbC_12-3/'),
    ('https://instagram.com/example.name/reels/AbC_12-3/',
     'https://www.instagram.com/reel/AbC_12-3/'),
    ('https://www.instagram.com/example.name/tv/AbC_12-3/',
     'https://www.instagram.com/tv/AbC_12-3/'),
    ('https://instagram.com/p/AbC_12-3/?img_index=2',
     'https://www.instagram.com/p/AbC_12-3/'),
])
def test_post_links_are_canonical_and_accepted_by_the_pinned_extractor(url, expected):
    assert public_url(url) == ('instagram', expected)
    assert InstagramPostExtractor.from_url(expected) is not None


@pytest.mark.parametrize('url', [
    'https://www.instagram.com/example.name/',
    'https://www.instagram.com/example.name/p/',
    'https://www.instagram.com/example/name/p/AbC123/',
    'https://www.instagram.com/example.name/p/AbC123/extra/',
    'https://www.instagram.com/' + 'a' * 31 + '/p/AbC123/',
    'https://www.instagram.com/example%2fname/p/AbC123/',
    'https://www.instagram.com.evil.test/example.name/p/AbC123/',
    'https://www.instagram.com@evil.test/example.name/p/AbC123/',
])
def test_malformed_account_prefixed_links_remain_rejected(url):
    with pytest.raises(UserError):
        public_url(url)


def test_account_prefixed_carousel_enumerates_every_entry_in_order(tmp_path, monkeypatch):
    calls = []
    def run(engine, args, cancel):
        calls.append((engine, args))
        return json.dumps([[2, '', {'count': 3}],
            [3, 'https://cdn.test/first.jpg', {'extension': 'jpg', 'count': 3}],
            [3, 'https://cdn.test/second.mp4', {'extension': 'mp4', 'count': 3}],
            [3, 'https://cdn.test/third.jpg', {'extension': 'jpg', 'count': 3}]])
    monkeypatch.setattr(engines, 'run_engine', run)
    items = engines.analyze('https://www.instagram.com/example.name/p/AbC_12-3/?img_index=2',
                            '', threading.Event(), lambda *_: None)
    canonical = 'https://www.instagram.com/p/AbC_12-3/'
    assert len(calls) == 1 and calls[0][0] == 'gallery-dl'
    assert calls[0][1][-1] == canonical
    assert [item.source for item in items] == [canonical] * 3
    assert [item.index for item in items] == [1, 2, 3]
    assert [item.kind for item in items] == ['foto', 'video', 'foto']
