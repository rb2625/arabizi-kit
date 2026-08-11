"""Arabizi detection and sentence cleaning.

A sentence counts as Arabizi when it is Latin script and scores high enough
on markers: digit+letter blends (3ayz, 7elwa) and known Arabizi words drawn
from the project lexicon plus a small set of common particles. English and
pure Arabic-script text score zero.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import MAX_WORDS, MIN_ARABIZI_SCORE, MIN_WORDS, RAW_DIR

_LEXICON_WORDS: set[str] | None = None


def _markers() -> set[str]:
    global _LEXICON_WORDS
    if _LEXICON_WORDS is None:
        from arabizikit.transliterate import Transliterator

        words = set(Transliterator().lexicon.keys())
        words |= {
            # particles and fillers not in the lexicon but very Arabizi
            "el", "al", "il", "w", "b", "fi", "fe", "ma3", "men", "min", "kaman",
            "kman", "bardo", "ardo", "bas", "bess", "aw", "la2", "aywa", "eih",
            "mashi", "kollo", "kol", "awal", "awel", "tab3an", "teb3an", "2a",
            "3ashan", "3ashaan", "ya3ni", "ya3ne", "inshallah", "mashallah",
        }
        _LEXICON_WORDS = words
    return _LEXICON_WORDS


DIGIT_BLEND_RE = re.compile(r"[a-z][2356789]|[2356789][a-z]")
LATIN_RE = re.compile(r"[a-zA-Z]")
ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"[@#][\w-]+")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF]")
SENT_SPLIT_RE = re.compile(r"[.!?؟\n]+")


def arabizi_score(text: str) -> int:
    """Score how strongly a text looks like Arabizi (0 for English/Arabic)."""
    words = re.findall(r"[a-z0-9'’]+", text.lower())
    if not words:
        return 0
    score = 0
    for w in words:
        if DIGIT_BLEND_RE.search(w):
            score += 2
        if w in _markers():
            score += 1
    return score


def is_arabizi(text: str, min_score: int | None = None) -> bool:
    """True when the text is Latin script with enough Arabizi markers."""
    min_score = MIN_ARABIZI_SCORE if min_score is None else min_score
    if not LATIN_RE.search(text):
        return False
    if len(re.findall(r"[a-z]+", text.lower())) < MIN_WORDS:
        return False
    return arabizi_score(text) >= min_score


def clean_sentence(text: str) -> str:
    """Strip URLs, mentions/hashtags, emoji, and collapse whitespace."""
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sentences(text: str, min_score: int | None = None) -> list[str]:
    """Split into cleaned sentences that qualify as Arabizi."""
    out: list[str] = []
    for chunk in SENT_SPLIT_RE.split(text):
        chunk = clean_sentence(chunk)
        if not chunk:
            continue
        word_count = len(chunk.split())
        if word_count < MIN_WORDS or word_count > MAX_WORDS:
            continue
        if is_arabizi(chunk, min_score):
            out.append(chunk)
    return out


def filter_raw(
    raw_dir: str | Path | None = None,
    out_path: str | Path | None = None,
    min_score: int | None = None,
) -> dict:
    """Walk raw rows, keep qualifying sentences, dedupe, write JSONL."""
    from .harvest import iter_raw_rows

    out_path = Path(out_path or RAW_DIR.parent / "candidates.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    kept = 0
    rows_written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for row in iter_raw_rows(raw_dir):
            for sent in sentences(row.get("text", ""), min_score):
                kept += 1
                key = sent.lower()
                if key in seen:
                    continue
                seen.add(key)
                record = {
                    "id": f"{row.get('subreddit', 'raw')}-{row.get('id', '')}-{kept}",
                    "arabizi": sent,
                    "source": row.get("source", ""),
                    "subreddit": row.get("subreddit", ""),
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                rows_written += 1
    return {"candidate_sentences": kept, "unique_written": rows_written, "out": str(out_path)}
