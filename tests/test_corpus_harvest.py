
import arabizikit.corpus.harvest as harvest_mod
from arabizikit.corpus.harvest import _403_HINT, _listings, harvest, post_text


def test_post_text_combines_title_and_selftext():
    post = {"title": "ana 3ayz 2akol", "selftext": "khalas"}
    assert post_text(post) == "ana 3ayz 2akol\nkhalas"
    assert post_text({"title": "only"}) == "only"


def test_listings_empty_payload():
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data": {"children": [], "after": null}}'

    import urllib.request

    original = urllib.request.urlopen
    try:
        urllib.request.urlopen = lambda req, timeout: FakeResp()
        rows = list(_listings("Egypt", pages=2, limit=10, url_builder=lambda s, l, a: "http://example.com/new.json", headers={}))
    finally:
        urllib.request.urlopen = original
    assert rows == []


def test_harvest_writes_one_file_per_subreddit(tmp_path, monkeypatch):
    def fake_fetch(sub, pages=1, limit=100):
        yield {"id": "a1", "title": "ana 3ayz 2akol", "selftext": ""}
        yield {"id": "b2", "title": "shlonak ya 5al", "selftext": "3afwan"}

    monkeypatch.setattr(harvest_mod, "fetch_posts", fake_fetch)
    stats = harvest(subreddits=["Egypt", "arabs"], pages=1, out_dir=tmp_path)
    assert stats == {"Egypt": 2, "arabs": 2}
    lines = (tmp_path / "Egypt.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "shlonak ya 5al" in lines[1]


def test_403_error_includes_setup_hint(tmp_path, monkeypatch):
    import urllib.error

    def fail(sub, pages=1, limit=100):
        raise urllib.error.HTTPError("url", 403, "Blocked", {}, None)

    monkeypatch.setattr(harvest_mod, "fetch_posts", fail)
    stats = harvest(subreddits=["Egypt"], pages=1, out_dir=tmp_path)
    assert "REDDIT_CLIENT_ID" in str(stats["Egypt"])
    assert _403_HINT in str(stats["Egypt"])
