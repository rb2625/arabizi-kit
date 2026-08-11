"""Orthographic normalisation for Arabic comparison and downstream pipelines.

``normalize`` collapses the orthographic variants that Arabizi transliteration
naturally blurs (alef forms, taa marbuta vs ha, alef maqsura vs ya, hamza
seats) so that the benchmark can measure whether the *word* was recovered
rather than whether the exact glyph was chosen.
"""

from __future__ import annotations

import re
import unicodedata

# Hamza-bearing alef forms -> plain alef (أ إ آ ٱ -> ا)
_ALEF_VARIANTS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})

_DIACRITIC_RANGES = ((0x064B, 0x065F),)  # Arabic combining marks (fatha..sukun)
_TATWEEL = "\u0640"  # ـ
_ALEF_SUPERSCRIPT = "\u0670"  # ٰ


def normalize(text: str) -> str:
    """Normalise Arabic orthographic variants for comparison.

    Removes diacritics and tatweel, unifies alef forms, taa marbuta -> ha,
    alef maqsura -> ya, and hamza seats -> their plain carriers.
    """
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ch in text:
        if ch in (_TATWEEL, _ALEF_SUPERSCRIPT):
            continue
        if any(lo <= ord(ch) <= hi for lo, hi in _DIACRITIC_RANGES):
            continue
        out.append(ch)
    text = "".join(out)
    text = text.translate(_ALEF_VARIANTS)
    text = (
        text.replace("ة", "ه")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ء", "ا")
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalized_tokens(text: str) -> list[str]:
    """Normalise and split into whitespace-separated tokens."""
    return [t for t in normalize(text).split(" ") if t]


_PUNCT_RE = re.compile(r"[.,!?;:،؛؟()\"'‘’“”]")


def normalize_eval(text: str) -> str:
    """Normalise and strip punctuation for benchmark comparisons.

    Real corpora attach trailing punctuation and whitespace to references;
    the engine's sentence candidates do not. Measuring word recovery, not
    punctuation fidelity, is the point of the eval metrics.
    """
    text = normalize(text)
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
