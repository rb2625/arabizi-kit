from arabizikit.corpus import annotate


def test_chunk():
    chunks = list(annotate._chunk([1, 2, 3, 4, 5], 2))
    assert chunks == [[1, 2], [3, 4], [5]]


def test_parse_array_plain():
    content = '[{"id": "a", "arabic": "أنا", "dialect": "msa", "note": ""}]'
    parsed = annotate._parse_array(content)
    assert parsed and parsed[0]["id"] == "a"


def test_parse_array_fenced():
    content = '```json\n[{"id": "b", "arabic": "شكرا", "dialect": "common", "note": ""}]\n```'
    parsed = annotate._parse_array(content)
    assert parsed and parsed[0]["arabic"] == "شكرا"


def test_parse_array_ignores_invalid_rows():
    content = '[{"id": "c", "arabic": "لا", "dialect": "msa", "note": ""}, {"junk": true}]'
    parsed = annotate._parse_array(content)
    assert len(parsed) == 1


def test_parse_array_garbage_returns_none():
    assert annotate._parse_array("sorry, no json here") is None


def test_annotate_batch_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_call(items, api_key, model, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("bad json")
        return [{"id": "a", "arabic": "أنا", "dialect": "msa", "note": ""}]

    monkeypatch.setattr(annotate, "_call_api", fake_call)
    result = annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key="test-key", retries=3)
    assert result[0]["arabic"] == "أنا"
    assert calls["n"] == 3


def test_annotate_batch_gives_up(monkeypatch):
    def fake_call(items, api_key, model, timeout):
        raise OSError("network down")

    monkeypatch.setattr(annotate, "_call_api", fake_call)
    try:
        annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key="test-key", retries=2)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "network down" in str(exc)


def test_annotate_requires_key():
    try:
        annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key=None)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
