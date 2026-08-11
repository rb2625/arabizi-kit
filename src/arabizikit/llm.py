"""Provider-agnostic LLM client for the optional AI-assisted features.

The core package stays dependency-free: this speaks plain HTTPS via urllib.
Every supported provider is reachable through the OpenAI chat-completions
format except Anthropic, which uses its own messages format; both are handled
here. Groq is the default because its free tier needs no credit card.

Pick a provider with ARABIZIKIT_PROVIDER (default "groq") or --provider.
Keys are read from these env vars, or pass api_key explicitly:

    ARABIZIKIT_API_KEY   overrides the provider-specific key
    GROQ_API_KEY         default provider
    OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY
    Ollama needs no key (http://localhost:11434)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_PROVIDER = "groq"

# Some providers sit behind Cloudflare and reject urllib's default
# Python-urllib user agent with HTTP 403; a browser-style UA avoids that.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

PROVIDERS: dict[str, dict] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": "openai/gpt-oss-120b",  # strong quality, 200k tokens/day on the free tier
        "json_mode": True,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
        "json_mode": True,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.0-flash",
        "json_mode": True,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1/chat/completions",
        "key_env": None,
        "model": "llama3.2",
        "json_mode": False,
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/messages",
        "key_env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-4-5",
        "json_mode": False,
    },

}


def default_model(provider: str) -> str:
    spec = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])
    return spec["model"]


def resolve_key(provider: str, explicit: str | None = None) -> str | None:
    """Return the API key for a provider: explicit arg, then env vars."""
    if explicit:
        return explicit
    override = os.environ.get("ARABIZIKIT_API_KEY")
    if override:
        return override
    spec = PROVIDERS.get(provider, PROVIDERS[DEFAULT_PROVIDER])
    env = spec.get("key_env")
    return os.environ.get(env) if env else None


def _error_message(body: bytes) -> str:
    """Pull a readable message out of a provider error body."""
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)
        if err:
            return str(err)
        if data.get("message"):
            return str(data["message"])
    except (ValueError, AttributeError):
        pass
    return body.decode("utf-8", "replace")[:300]


def chat_completion(
    provider: str,
    model: str | None,
    api_key: str | None,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    timeout: int = 90,
) -> str:
    """One chat request. Returns the assistant's content as a string."""
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"unknown LLM provider {provider!r}; choose from {', '.join(PROVIDERS)}")
    key = resolve_key(provider, api_key)
    if spec.get("key_env") and not key:
        raise RuntimeError(
            f"provider {provider!r} needs a key: set {spec['key_env']} (or ARABIZIKIT_API_KEY, or pass api_key=...)"
        )
    model = model or spec["model"]

    if provider == "anthropic":
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        raw = _post(spec["base_url"], payload, headers, timeout, provider)
        body = json.loads(raw)
        return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")

    # OpenAI-compatible endpoints: system goes in as the first message.
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}] + messages,
    }
    if spec.get("json_mode"):
        payload["response_format"] = {"type": "json_object"}
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    raw = _post(spec["base_url"], payload, headers, timeout, provider)
    body = json.loads(raw)
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"unexpected {provider} response: {_error_message(raw)}") from exc


def _post(url: str, payload: dict, headers: dict, timeout: int, provider: str) -> bytes:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "user-agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = _error_message(exc.read())
        hint = "rate limit; wait and retry" if exc.code == 429 else ("bad or missing key" if exc.code == 401 else "")
        suffix = f" ({hint})" if hint else ""
        raise RuntimeError(f"{provider} returned HTTP {exc.code}: {detail}{suffix}") from exc
