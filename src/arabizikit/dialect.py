"""Lightweight dialect identification for Arabizi text.

The recogniser is intentionally simple for v0.1: it counts dialect tags of
lexicon matches and applies a few hand-written pattern rules. It is a
baseline that the paper plans to replace with a fine-tuned classifier
(trained on the collected corpus).
"""

from __future__ import annotations

import re

DIALECTS = ("common", "msa", "gulf", "egyptian", "levantine", "maghrebi")

# Order matters: more specific patterns first so "shu" (Levantine) wins over
# generic heuristics when several fire.
_PATTERN_RULES: list[tuple[str, re.Pattern]] = [
    ("maghrebi", re.compile(r"\b(wesh|wacha|kifash|3afak|bzzaf|daba|sh7al|bghit|mzyan)\b", re.IGNORECASE)),
    ("gulf", re.compile(r"\b(shlonak|shlonik|shakhbarak|2ol|2ool|wayed|zayn|walaw|shway)\b", re.IGNORECASE)),
    ("levantine", re.compile(r"\b(shu|keefak|keefik|beddi|biddi|mafi|kolshi|mneeh|mnih|kteer|keteer)\b", re.IGNORECASE)),
    ("egyptian", re.compile(r"\b(ezayak|ezayek|3ayz|3ayza|ayz|awi|mesh|mish|kwayes|kwayis|eih|aywa|keda|3ashan)\b", re.IGNORECASE)),
]


def guess_dialect(evidence: list[dict]) -> dict:
    """Guess the dialect from per-word evidence.

    ``evidence`` is a list of ``{"arabizi", "ar", "dialect"}`` dicts collected
    while transliterating. Returns a dict with ``dialect``, ``confidence``
    (0..1) and the contributing ``evidence``.
    """
    counts: dict[str, int] = {}
    matched: list[dict] = []
    for item in evidence:
        d = item.get("dialect")
        if d not in DIALECTS or d in ("common", "msa"):
            continue
        counts[d] = counts.get(d, 0) + 1
        matched.append(item)
    if not counts:
        return {"dialect": "unknown", "confidence": 0.0, "evidence": []}

    top = max(counts, key=lambda d: (counts[d], _order(d)))
    total = sum(counts.values())
    return {
        "dialect": top,
        "confidence": round(counts[top] / total, 2),
        "evidence": matched,
    }


def _order(dialect: str) -> int:
    return {"gulf": 0, "egyptian": 1, "levantine": 2, "maghrebi": 3}.get(dialect, 99)


def pattern_hints(text: str) -> list[str]:
    """Dialect patterns that fired on the raw text (used as extra evidence)."""
    hits = []
    for dialect, pattern in _PATTERN_RULES:
        if pattern.search(text):
            hits.append(dialect)
    return hits
