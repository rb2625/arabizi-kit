import json

from arabizikit import llm


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    def __init__(self, payload: dict):
        self.payload = payload
        self.request = None

    def __call__(self, req, timeout=90):
        self.request = req
        body = json.dumps(self.payload).encode("utf-8")
        return FakeResponse(body)


def test_groq_payload_and_response(monkeypatch):
    fake = FakeUrlopen(
        {
            "choices": [
                {
                    "message": {
                        "content": '[{"id": "a", "arabic": "أنا", "dialect": "msa", "note": ""}]'
                    }
                }
            ]
        }
    )
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    content = llm.chat_completion(
        provider="groq",
        model=None,
        api_key="gsk-test",
        system="sys",
        messages=[{"role": "user", "content": "[{\"id\": \"a\", \"arabizi\": \"ana\"}]"}],
    )
    assert '"arabic": "أنا"' in content
    # Groq speaks the OpenAI format: system as first message, bearer auth, json mode.
    sent = json.loads(fake.request.data)
    assert sent["messages"][0]["role"] == "system"
    assert sent["response_format"] == {"type": "json_object"}
    assert fake.request.headers["Authorization"] == "Bearer gsk-test"
    assert fake.request.full_url == llm.PROVIDERS["groq"]["base_url"]


def test_anthropic_response_format(monkeypatch):
    fake = FakeUrlopen({"content": [{"type": "text", "text": "{\"ok\": true}"}]})
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    content = llm.chat_completion(
        provider="anthropic",
        model="claude-sonnet-4-5",
        api_key="sk-ant-test",
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert content == '{"ok": true}'
    sent = json.loads(fake.request.data)
    assert sent["system"] == "sys"
    header_keys = {k.lower(): v for k, v in fake.request.headers.items()}
    assert header_keys["x-api-key"] == "sk-ant-test"


def test_ollama_needs_no_key(monkeypatch):
    fake = FakeUrlopen({"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    content = llm.chat_completion(
        provider="ollama",
        model=None,
        api_key=None,
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert content == "ok"
    assert "Authorization" not in fake.request.headers


def test_missing_key_raises(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not call the API without a key")

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
    monkeypatch.delenv("ARABIZIKIT_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    try:
        llm.chat_completion(provider="groq", model=None, api_key=None, system="s", messages=[])
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)


def test_unknown_provider():
    try:
        llm.chat_completion(provider="nope", model=None, api_key="k", system="s", messages=[])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "unknown LLM provider" in str(exc)
