"""Optional LLM-assisted disambiguation.

The rule engine produces ranked candidates; for genuinely ambiguous input
(dialect-dependent 2-as-qaf vs hamza, proper nouns, code-switching) the
top-k list is handed to an LLM with instructions to pick the intended
Arabic-script rendering and tag the dialect.

Uses only the standard library (``urllib``) so the core package stays
dependency-free. Requires ``ANTHROPIC_API_KEY`` (or an explicit key) and
is only invoked explicitly via ``--llm``.
"""

from __future__ import annotations

import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = os.environ.get("ARABIZIKIT_MODEL", "claude-sonnet-4-5")

_SYSTEM_PROMPT = (
    "You are an expert in Arabizi (Romanized Arabic) and Arabic dialectology. "
    "Transliterate the user's Arabizi text to natural Arabic script: pick the intended "
    "word given the dialect, attach definite articles (el -> ال), seat hamzas correctly "
    "(أ/إ/ؤ/ئ), and keep the orthography informal-colloquial (no diacritics). "
    "Reply with ONLY a JSON object of the form "
    '{"arabic": "<transliterated text>", "dialect": "gulf|egyptian|levantine|maghrebi|msa|common", "note": "<one short sentence explaining key choices>"}.'
)


def llm_transliterate(text: str, api_key: str | None = None, model: str = DEFAULT_MODEL, timeout: int = 45) -> dict:
    """Transliterate ``text`` via the Anthropic API. Returns the parsed JSON."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("LLM mode requires ANTHROPIC_API_KEY (or pass api_key=...)")

    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": text}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
    return _parse_json(content)


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.removeprefix("json")
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        content = content[start : end + 1]
    return json.loads(content)
