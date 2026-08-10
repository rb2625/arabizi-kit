"""Core Arabizi -> Arabic transliteration engine.

Design (v0.1, hybrid):

1. **Lexicon first** — exact matches against a curated bilingual lexicon win
   outright (they carry dialect evidence and no ambiguity).
2. **Rule-based fallback** — an ordered phoneme scan (longest-match digraphs,
   digit codes, single letters) produces a ranked set of candidate spellings.
   Ambiguous positions (2 -> hamza/qaf, t -> ta/taa, a -> alif/taa-marbuta,
   ay -> alif+ya / ya, short vowels elided or written) are expanded into
   candidates and ranked with small orthographic-plausibility penalties.
3. **Post-processing** — hamza seating (ء -> أ/إ/ؤ/ئ), taa-marbuta
   alternates, and Arabic clitic attachment (el -> ال, w -> و, 3al -> على ال).

The candidate list (top-k) is what the optional LLM disambiguator and the
benchmark's hit@k metric consume.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .dialect import guess_dialect, pattern_hints

DATA_DIR = Path(__file__).resolve().parent / "data"

_TOKEN_RE = re.compile(r"[A-Za-z0-9'’]+|[^\sA-Za-z0-9'’]+")


@dataclass
class Result:
    """Outcome of transliterating one string."""

    text: str  # top-1 rendering, preserving original spacing/punctuation
    candidates: list[tuple[str, float]]  # top-k full-sentence candidates, ascending score
    words: list[dict] = field(default_factory=list)  # per-word detail (arabizi, candidates, evidence)
    dialect: dict | None = None
    evidence: list[dict] = field(default_factory=list)


def _tokenize(text: str):
    """Yield (kind, token) tuples; kind in {"space", "latin", "other"}."""
    for chunk in re.split(r"(\s+)", text):
        if not chunk:
            continue
        if chunk.isspace():
            yield ("space", chunk)
            continue
        for piece in _TOKEN_RE.findall(chunk):
            if re.fullmatch(r"[A-Za-z0-9'’]+", piece):
                yield ("latin", piece)
            else:
                yield ("other", piece)


class Transliterator:
    def __init__(self, data_dir: str | Path = DATA_DIR):
        data_dir = Path(data_dir)
        self._phonemes = json.loads((data_dir / "phonemes.json").read_text(encoding="utf-8"))
        raw_lexicon = json.loads((data_dir / "lexicon.json").read_text(encoding="utf-8"))
        self.lexicon = {k.lower(): v for k, v in raw_lexicon["entries"].items()}
        self.digraphs = sorted(self._phonemes["digraphs"], key=len, reverse=True)
        self.digits = self._phonemes["digits"]
        self.letters = self._phonemes["letters"]
        self.bad_sequences = self._phonemes.get("bad_sequences", [])
        self._context = {r["id"]: r for r in self._phonemes.get("context_rules", [])}
        self._articles = {"el", "al", "il", "l"}
        self._contractions = {"3al": {"prefix": "على ال", "fallback": "على"}}
        self._conj = {"w": "و"}

    # ------------------------------------------------------------------ API
    def transliterate(self, text: str, top_k: int = 1, with_dialect: bool = False) -> Result:
        tokens = list(_tokenize(text))
        words: list[dict] = []
        for kind, tok in tokens:
            if kind == "latin":
                words.append(self._process_word(tok.lower()))
            else:
                words.append({"kind": kind, "raw": tok})
        words = self._attach_pass(words)

        parts: list[str] = []
        evidence: list[dict] = []
        for w in words:
            kind = w["kind"]
            if kind == "space" or kind == "other":
                parts.append(w["raw"])
                continue
            cands = w["candidates"]
            if cands:
                parts.append(cands[0][0])
                evidence.extend(w.get("evidence", []))
        text_out = "".join(parts)

        candidates = self._sentence_candidates(words, top_k=max(top_k, 1))
        word_tokens = [w for w in words if w["kind"] == "word"]

        dialect = None
        if with_dialect:
            dialect = guess_dialect(evidence)
            extra = pattern_hints(text)
            if extra and (dialect["dialect"] == "unknown" or dialect["confidence"] < 0.5):
                dialect = {"dialect": extra[0], "confidence": 0.0, "evidence": []}
        return Result(text=text_out, candidates=candidates, words=word_tokens, dialect=dialect, evidence=evidence)

    # ------------------------------------------------------- sentence level
    @staticmethod
    def _sentence_candidates(words: list[dict], top_k: int) -> list[tuple[str, float]]:
        """Best full-sentence strings from the per-word candidate lists."""
        word_tokens = [w for w in words if w["kind"] == "word"]
        combos: list[tuple[list[str], float]] = [([], 0.0)]
        for w in word_tokens:
            cands = w["candidates"][:top_k]
            combos = [(parts + [ar], score + s) for parts, score in combos for ar, s in cands]
            if len(combos) > top_k * 6:
                combos = sorted(combos, key=lambda c: c[1])[: top_k * 6]
        if not word_tokens:
            return []
        seen: set[str] = set()
        out: list[tuple[str, float]] = []
        for parts, score in sorted(combos, key=lambda c: c[1]):  # stable: product order breaks ties
            sentence = " ".join(parts)
            if sentence in seen:
                continue
            seen.add(sentence)
            out.append((sentence, round(score, 6)))
            if len(out) >= top_k:
                break
        return out

    # ------------------------------------------------------------ word level
    def _process_word(self, word: str) -> dict:
        if word in self._conj:
            return {"kind": "conj", "raw": word, "attach": self._conj[word]}
        if word in self._articles:
            return {"kind": "article", "raw": word}
        if word in self._contractions:
            return {"kind": "contraction", "raw": word, **self._contractions[word]}
        if word in self.lexicon:
            entry = self.lexicon[word]
            return {
                "kind": "word",
                "raw": word,
                "candidates": [(entry["ar"], 0.0)],
                "evidence": [{"arabizi": word, "ar": entry["ar"], "dialect": entry["dialect"]}],
            }
        return {"kind": "word", "raw": word, "candidates": self._rule_candidates(word), "evidence": []}

    def _attach_pass(self, words: list[dict]) -> list[dict]:
        out: list[dict] = []
        i, n = 0, len(words)
        while i < n:
            w = words[i]
            kind = w["kind"]
            if kind in ("article", "conj", "contraction"):
                if kind == "article":
                    prefix, fallback = "ال", None
                elif kind == "conj":
                    prefix, fallback = w["attach"], "و"
                else:
                    prefix, fallback = w["prefix"], w["fallback"]
                j = i + 1
                while j < n and words[j]["kind"] == "space":
                    j += 1
                if j < n and words[j]["kind"] == "word":
                    words[j]["candidates"] = [(prefix + ar, score) for ar, score in words[j]["candidates"]]
                    i = j
                    continue
                out.append({"kind": "word", "raw": w["raw"], "candidates": [(fallback or prefix, 0.0)], "evidence": []})
                i += 1
                continue
            out.append(w)
            i += 1
        return out

    # -------------------------------------------------------------- rules
    def _rule_candidates(self, word: str, max_candidates: int = 8) -> list[tuple[str, float]]:
        segments = self._scan(word)
        results = [""]
        for seg in segments:
            opts = seg["options"]
            if len(results) * len(opts) > max_candidates * 4:
                opts = opts[:1]
            results = [r + o for r in results for o in opts]

        finals: list[tuple[str, float]] = []
        for r in results:
            finals.append((self._seat_hamza(r), 0.0))

        scored: list[tuple[float, str]] = []
        seen: set[str] = set()
        for idx, (ar, extra) in enumerate(finals):
            if ar in seen:
                continue
            seen.add(ar)
            penalty = sum(2 for seq in self.bad_sequences if seq in ar)
            scored.append((penalty + extra + idx * 1e-6, ar))
        scored.sort()
        return [(ar, round(score, 6)) for score, ar in scored[: max(max_candidates, 1)]]

    def _scan(self, word: str) -> list[dict]:
        """Phoneme scan producing per-position option lists (primary first)."""
        segments: list[dict] = []
        i, n = 0, len(word)
        while i < n:
            # ay/ey: split alif+ya is primary (dayman -> دايما), digraph ya is
            # the alternative (3alayk -> عليك). Handled before the digraph table.
            if word[i] in "ae" and i + 1 < n and word[i + 1] == "y" and (i + 2 >= n or word[i + 2] != "y"):
                segments.append({"options": ["اي", "ي"], "final_a": False})
                i += 2
                continue

            digraph = next((d for d in self.digraphs if word.startswith(d, i)), None)
            if digraph:
                segments.append({"options": [self._phonemes["digraphs"][digraph]], "final_a": False})
                i += len(digraph)
                continue

            ch = word[i]
            if ch in self.digits:
                spec = self.digits[ch]
                primary = spec["primary"]
                alts = list(spec.get("alternatives", []))
                if ch == "2":
                    prev_out = segments[-1]["options"][0] if segments else ""
                    if i == n - 1 and prev_out in ("ا", "و", "ي", ""):
                        primary, alts = "ق", [a for a in alts if a != "ق"]
                    elif i == 0 and n > 1 and word[1] not in "aeiou":
                        primary, alts = "ق", ["ا"]
                segments.append({"options": [primary] + [a for a in alts if a != primary], "final_a": False})
                i += 1
                continue

            if ch in self.letters:
                spec = self.letters[ch]
                primary = spec["primary"]
                alts = list(spec.get("alternatives", []))
                if ch == "a" and i == n - 1:
                    rule = self._context.get("final_a_taa_marbuta")
                    if rule:
                        primary, alts = rule["primary"], list(rule.get("alternatives", []))
                if ch == "i" and i == n - 1:
                    primary, alts = "ي", [a for a in alts if a != "ي"]
                segments.append({"options": [primary] + [a for a in alts if a != primary]})
                i += 1
                continue

            segments.append({"options": [ch], "final_a": False})
            i += 1
        return segments

    def _seat_hamza(self, s: str) -> str:
        """Convert a bare hamza (ء) to its orthographic seat, merging where Arabic orthography collapses the carrier with the hamza (و+ء -> ؤ, ي+ء -> ئ, ا+ء+ا -> أ)."""
        rule = self._phonemes.get("hamza_seating", {})
        chars = list(s)
        out: list[str] = []
        i, n = 0, len(chars)
        while i < n:
            ch = chars[i]
            if ch != "ء":
                out.append(ch)
                i += 1
                continue
            prev = out[-1] if out else None
            nxt = chars[i + 1] if i + 1 < n else None
            if prev is None:
                out.append(rule["word_initial"]["before_ya"] if nxt == "ي" else rule["word_initial"]["default"])
                i += 1
            elif prev == "و":
                out[-1] = rule["after_waaw"]  # و + ء -> ؤ (su2al -> سؤال)
                i += 1
            elif prev == "ي":
                out[-1] = rule["after_ya"]  # ي + ء -> ئ (shay2 -> شيء)
                i += 1
            elif prev == "ا":
                out[-1] = rule["after_alif"]  # ا + ء (+ ا) -> أ (sa2al -> سأل)
                i += 2 if nxt == "ا" else 1
            elif nxt == "ا":
                out.append(rule["after_alif"])  # C + ء + ا -> C + أ (mas2ala -> مسألة)
                i += 2
            else:
                out.append(rule["else"])
                i += 1
        return "".join(out)


_transliterator: Transliterator | None = None


def transliterate(text: str, top_k: int = 1, with_dialect: bool = False) -> Result:
    """Transliterate an Arabizi string to Arabic script (convenience API)."""
    global _transliterator
    if _transliterator is None:
        _transliterator = Transliterator()
    return _transliterator.transliterate(text, top_k=top_k, with_dialect=with_dialect)
