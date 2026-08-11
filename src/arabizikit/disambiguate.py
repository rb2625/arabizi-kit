"""Optional LLM-assisted disambiguation.

The rule engine produces ranked candidates; for genuinely ambiguous input
(dialect-dependent 2-as-qaf vs hamza, proper nouns, code-switching) the
top-k list is handed to an LLM with instructions to pick the intended
Arabic-script rendering and tag the dialect.

Uses only the standard library (urllib) so the core package stays
dependency-free. The default provider is Groq's free tier; see
arabizikit.llm for the supported providers and key env vars. This is only
invoked explicitly via --llm.
"""

from __future__ import annotations

import json

from . import llm


def llm_transliterate(
    text: str,
    api_key: str | None = None,
    model: str | None = None,
    provider: str = "groq",
    timeout: int = 45,
) -> dict:
    """Transliterate ``text`` via the configured LLM provider. Returns the parsed JSON."""
    content = llm.chat_completion(
        provider=provider,
        model=model,
        api_key=api_key,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        max_tokens=1024,
        timeout=timeout,
    )
    return _parse_json(content)


_SYSTEM_PROMPT = (
    "You are an expert in Arabizi (Romanized Arabic) and Arabic dialectology. "
    "Transliterate the user's Arabizi text to natural Arabic script: pick the intended "
    "word given the dialect, attach definite articles (el -> ال), seat hamzas correctly "
    "(أ/إ/ؤ/ئ), and keep the orthography informal-colloquial (no diacritics). "
    "Reply with ONLY a JSON object of the form "
    '{"arabic": "<transliterated text>", "dialect": "gulf|egyptian|levantine|maghrebi|msa|common", "note": "<one short sentence explaining key choices>"}.'
)


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.removeprefix("json")
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        content = content[start : end + 1]
    return json.loads(content)
