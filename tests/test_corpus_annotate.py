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

    def fake_call(prompt_items, model, provider, api_key, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("bad json")
        return [{"id": "a", "arabic": "أنا", "dialect": "msa", "note": ""}]

    monkeypatch.setattr(annotate, "_call_api", fake_call)
    result = annotate.annotate_batch(
        [{"id": "a", "arabizi": "ana"}],
        api_key="test-key",
        provider="groq",
        retries=3,
    )
    assert result[0]["arabic"] == "أنا"
    assert calls["n"] == 3


def test_annotate_batch_gives_up(monkeypatch):
    def fake_call(prompt_items, model, provider, api_key, timeout):
        raise OSError("network down")

    monkeypatch.setattr(annotate, "_call_api", fake_call)
    try:
        annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key="test-key", provider="groq", retries=2)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "network down" in str(exc)


def test_annotate_batch_requires_key(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not call the API without a key")

    monkeypatch.setattr(annotate, "_call_api", fail)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ARABIZIKIT_API_KEY", raising=False)
    try:
        annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key=None, provider="groq")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)


def test_annotate_batch_ollama_needs_no_key(monkeypatch):
    def fake_call(prompt_items, model, provider, api_key, timeout):
        assert api_key is None
        return [{"id": "a", "arabic": "أنا", "dialect": "msa", "note": ""}]

    monkeypatch.setattr(annotate, "_call_api", fake_call)
    result = annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key=None, provider="ollama")
    assert result[0]["id"] == "a"


def test_unknown_provider_rejected():
    try:
        annotate.annotate_batch([{"id": "a", "arabizi": "ana"}], api_key="k", provider="nope")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "unknown LLM provider" in str(exc)


def test_wait_after_rate_limit_uses_provider_hint(monkeypatch):
    slept = []
    monkeypatch.setattr(annotate.time, "sleep", lambda s: slept.append(s))
    annotate._wait_after_rate_limit(RuntimeError("groq returned HTTP 429: ... try again in 5.7s ..."))
    assert slept and abs(slept[0] - 7.7) < 0.001


def test_wait_after_rate_limit_minutes_hint(monkeypatch):
    slept = []
    monkeypatch.setattr(annotate.time, "sleep", lambda s: slept.append(s))
    annotate._wait_after_rate_limit(RuntimeError("groq returned HTTP 429: ... try again in 29m0.96s ..."))
    # 29m exceeds the ceiling, so the default 45s window applies
    assert slept and slept[0] == 45.0


def test_wait_after_rate_limit_default(monkeypatch):
    slept = []
    monkeypatch.setattr(annotate.time, "sleep", lambda s: slept.append(s))
    annotate._wait_after_rate_limit(RuntimeError("groq returned HTTP 429: rate limited"))
    assert slept and slept[0] == 45.0


import json


def _fake_annotations(prompt_items, model, provider, api_key, timeout):
    return [
        {"id": p["id"], "arabic": "أنا عايز", "dialect": "egyptian", "note": ""}
        for p in prompt_items
    ]


def test_annotate_end_to_end_with_iaa(tmp_path, monkeypatch):
    cands = tmp_path / "candidates.jsonl"
    out = tmp_path / "annotated.jsonl"
    rows = [{"id": f"s{i}", "arabizi": "ana 3ayz"} for i in range(12)]
    cands.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(annotate, "_call_api", _fake_annotations)
    monkeypatch.setattr(annotate.time, "sleep", lambda s: None)

    report = annotate.annotate(
        candidates_path=cands, out_path=out, batch_size=4, iaa_sample=0.5,
        api_key="k", provider="groq",
    )
    assert report["n"] == 12
    # Half the rows were double-annotated: the IAA sample must actually run.
    assert report["iaa_samples"] == 6
    assert report["iaa"] == 1.0


def test_annotate_resume_dedupes(tmp_path, monkeypatch):
    cands = tmp_path / "candidates.jsonl"
    out = tmp_path / "annotated.jsonl"
    rows = [{"id": f"s{i}", "arabizi": "ana"} for i in range(6)]
    cands.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    # Simulate an interrupted append: 5 lines but only 4 unique ids.
    dup = [
        {"id": f"s{i}", "arabizi": "ana", "arabic": "أنا", "dialect": "egyptian",
         "note": "", "rule_top1": "x", "rule_match": False}
        for i in range(4)
    ]
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dup + [dup[0]]) + "\n", encoding="utf-8")
    monkeypatch.setattr(annotate, "_call_api", _fake_annotations)
    monkeypatch.setattr(annotate.time, "sleep", lambda s: None)

    report = annotate.annotate(
        candidates_path=cands, out_path=out, batch_size=4, iaa_sample=0.1,
        api_key="k", provider="groq",
    )
    assert report["n"] == 6
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 6
    assert len({r["id"] for r in lines}) == 6
