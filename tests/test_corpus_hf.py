import json

from arabizikit.corpus import harvest, split


def test_pick_text_field():
    features = [{"name": "text"}, {"name": "label"}]
    assert harvest.pick_text_field(features) == "text"
    assert harvest.pick_text_field([{"name": "arabize"}]) == "arabize"
    assert harvest.pick_text_field(features, preferred="text") == "text"


def test_pick_text_field_missing():
    try:
        harvest.pick_text_field([{"name": "label"}], preferred="nope")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "not in" in str(exc)
    try:
        harvest.pick_text_field([{"name": "label"}])
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass


def test_resolve_split_prefers_train(monkeypatch):
    monkeypatch.setattr(harvest, "discover_splits", lambda ds: [("default", "test"), ("default", "train")])
    assert harvest.resolve_split("x", None, None) == ("default", "train")
    assert harvest.resolve_split("x", "default", "test") == ("default", "test")
    assert harvest.resolve_split("x", "default", None) == ("default", "train")


def test_harvest_hf_pagination(monkeypatch, tmp_path):
    schema = {"features": [{"name": "text"}], "rows": []}

    def fake_hf_get(url):
        if "first-rows" in url:
            return schema
        raise AssertionError(f"unexpected url {url}")

    pages = {
        0: [{"row_idx": i, "row": {"text": f"ana 3ayz {i}"}} for i in range(3)],
        3: [{"row_idx": i, "row": {"text": f"ana 3ayz {i}"}} for i in range(3, 5)],
    }

    def fake_fetch(dataset, config, split, offset=0, length=100):
        return pages.get(offset, [])

    monkeypatch.setattr(harvest, "_hf_get", fake_hf_get)
    monkeypatch.setattr(harvest, "fetch_hf_rows", fake_fetch)
    monkeypatch.setattr(harvest, "resolve_split", lambda ds, c, s: ("default", "train"))

    stats = harvest.harvest_hf(dataset="demo/ds", rows=5, out_dir=tmp_path)
    assert stats["rows_written"] == 5
    lines = (tmp_path / "demo__ds.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    first = json.loads(lines[0])
    assert first["source"] == "huggingface"
    assert "ana 3ayz 0" in first["text"]


def test_import_parallel_writes_benchmark(monkeypatch, tmp_path):
    def fake_fetch(dataset, config, split, offset=0, length=100):
        if offset == 0:
            return [
                {"row_idx": 0, "row": {"Arabize": "so2al", "Arabic": "سؤال"}},
                {"row_idx": 1, "row": {"Arabize": "junk", "Arabic": ""}},
                {"row_idx": 2, "row": {"Arabize": "2ktob", "Arabic": "اكتب"}},
            ]
        return []

    monkeypatch.setattr(split, "fetch_hf_rows", fake_fetch)
    monkeypatch.setattr(split, "resolve_split", lambda ds, c, s: ("default", "train"))

    out = tmp_path / "bench.json"
    report = split.import_parallel(
        dataset="arbml/Arabizi_Transliteration",
        arabizi_field="Arabize",
        arabic_field="Arabic",
        out_path=out,
    )
    assert report["n"] == 2  # the row with an empty Arabic value is skipped
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 2
    entry = payload["entries"][0]
    assert entry["arabizi"] == "so2al"
    assert entry["reference"] == "سؤال"
    assert entry["id"].startswith("ext-")
