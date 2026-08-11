"""Learned layer for the transliterator (v0.3, data-driven).

Three small, dependency-free components trained from the corpus:

- Dialect classifier: Naive Bayes over Arabizi word tokens and code markers
  (digits and digraphs). It replaces the hand-written heuristics and supplies
  the dialect hint automatically, so the benchmark no longer needs the
  oracle tag.
- Word reading table: arabizi word -> observed Arabic renderings with
  frequencies, learned from parallel pairs. Known words skip the letter
  rules and emit their observed readings.
- Character language model: a Laplace-smoothed trigram model over the corpus
  references, used to rerank sentence candidates toward readings that look
  like natural Arabic.

Everything serializes to one JSON file. Training data is the calibration
benchmark plus the pipeline train/dev splits; the held-out test and
external sets are deliberately excluded so the eval stays honest.
"""

from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path

from .normalize import normalize

HINT_DIALECTS = ("gulf", "egyptian", "levantine", "maghrebi")

# Dialects whose conventions change the rule engine's default readings. The
# engine defaults to the Egyptian convention, so a predicted Egyptian or
# Levantine label adds nothing; only these classes actually flip readings
# (9 -> qaf and single doubled consonants in Maghrebi, 8 -> ghayn in Gulf).
EFFECTIVE_HINTS = ("maghrebi", "gulf")

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class DialectNB:
    """Naive Bayes over word tokens and digit/digraph markers."""

    def __init__(self) -> None:
        self.classes: list[str] = []
        self.priors: dict[str, float] = {}
        self.feature_probs: dict[str, dict[str, float]] = {}
        self.vocab: list[str] = []

    @staticmethod
    def _features(text: str) -> set[str]:
        toks = _tokens(text)
        feats = set(toks)
        joined = "".join(toks)
        for digit in "2345798":
            if digit in joined:
                feats.add("D:" + digit)
        for digraph in ("kh", "ch", "gh", "sh", "dh", "th", "ts", "dj"):
            if digraph in joined:
                feats.add("G:" + digraph)
        return feats

    def train(self, pairs: list[tuple[str, str]]) -> None:
        counts: dict[str, dict[str, int]] = {}
        class_counts: dict[str, int] = {}
        vocab: set[str] = set()
        for text, cls in pairs:
            cls = (cls or "other").strip().lower()
            class_counts[cls] = class_counts.get(cls, 0) + 1
            bucket = counts.setdefault(cls, {})
            for f in self._features(text):
                bucket[f] = bucket.get(f, 0) + 1
                vocab.add(f)
        self.classes = sorted(class_counts)
        total = sum(class_counts.values())
        v = len(vocab)
        self.priors = {c: class_counts[c] / total for c in self.classes}
        self.feature_probs = {}
        for c in self.classes:
            n = sum(counts[c].values())
            self.feature_probs[c] = {f: math.log((counts[c].get(f, 0) + 1) / (n + v)) for f in vocab}
        self.vocab = sorted(vocab)

    def predict(self, text: str) -> tuple[str, float]:
        """Return (dialect, confidence) for an Arabizi string."""
        if not self.classes:
            return "unknown", 0.0
        feats = self._features(text)
        scores = {}
        for c in self.classes:
            s = math.log(self.priors[c])
            for f in feats:
                s += self.feature_probs[c].get(f, 0.0)
            scores[c] = s
        best = max(scores, key=scores.get)
        peak = scores[best]
        exps = {c: math.exp(s - peak) for c, s in scores.items()}
        total = sum(exps.values())
        return best, exps[best] / total

    def to_dict(self) -> dict:
        return {"classes": self.classes, "priors": self.priors, "feature_probs": self.feature_probs, "vocab": self.vocab}

    @classmethod
    def from_dict(cls, data: dict) -> DialectNB:
        nb = cls()
        nb.classes = data["classes"]
        nb.priors = data["priors"]
        nb.feature_probs = data["feature_probs"]
        nb.vocab = data["vocab"]
        return nb


class WordTable:
    """Learned arabizi -> Arabic reading frequencies from parallel pairs."""

    def __init__(self) -> None:
        self.words: dict[str, dict[str, dict]] = {}

    ARTICLES = ("el", "al", "il", "l")

    def add_pair(self, arabizi: str, arabic: str) -> None:
        toks = _tokens(arabizi)
        refs = arabic.split()
        if not toks or not refs:
            return
        if len(toks) == len(refs):
            for tok, ref in zip(toks, refs):
                self._learn(tok, ref)
            return
        # Monotone alignment for the common case where the reference merges
        # the definite article into the noun (el etnein -> الاثنين). The bare
        # noun is learned; the article is re-attached at inference time.
        i = j = 0
        while i < len(toks) and j < len(refs):
            tok, ref = toks[i], refs[j]
            if tok in self.ARTICLES and i + 1 < len(toks) and ref.startswith("ال") and len(ref) > 2:
                self._learn(toks[i + 1], ref[2:])
                i += 2
                j += 1
                continue
            self._learn(tok, ref)
            i += 1
            j += 1

    def _learn(self, tok: str, ref: str) -> None:
        norm = normalize(ref)
        if len(tok) < 2 or not norm:
            return
        bucket = self.words.setdefault(tok, {})
        entry = bucket.get(norm)
        if entry is None:
            bucket[norm] = {"raw": ref, "count": 1}
        else:
            entry["count"] += 1

    def readings(self, word: str) -> list[tuple[str, float]] | None:
        """Top observed readings as (arabic, score); None if the word is unseen.

        Scores are small non-negative penalties (0 for the most frequent
        reading), the same scale the rule engine uses, so the two sources
        combine in one ranking.
        """
        bucket = self.words.get(word.lower())
        if not bucket:
            return None
        items = sorted(bucket.values(), key=lambda v: -v["count"])
        return [(it["raw"], 2.0 * i) for i, it in enumerate(items[:5])]

    def to_dict(self) -> dict:
        return self.words

    @classmethod
    def from_dict(cls, data: dict) -> WordTable:
        wt = cls()
        wt.words = data
        return wt


class CharacterLM:
    """Laplace-smoothed character trigram model over Arabic references."""

    def __init__(self) -> None:
        self.contexts: dict[str, int] = {}
        self.counts: dict[str, int] = {}
        self.vocab: list[str] = []

    def train_texts(self, texts: list[str]) -> None:
        vocab: set[str] = set()
        for text in texts:
            chars = [" ", " "] + list(text) + [" "]
            for i in range(2, len(chars)):
                ctx = chars[i - 2] + chars[i - 1]
                ch = chars[i]
                self.contexts[ctx] = self.contexts.get(ctx, 0) + 1
                key = ctx + ch
                self.counts[key] = self.counts.get(key, 0) + 1
                vocab.add(ch)
        self.vocab = sorted(vocab)

    def penalty(self, text: str) -> float:
        """Total negative log10 probability, Laplace-smoothed.

        Natural Arabic scores lower; longer and weirder strings score
        higher. Used to rerank the rule engine's candidates.
        """
        v = len(self.vocab)
        if not v:
            return 0.0
        chars = [" ", " "] + list(text) + [" "]
        total = 0.0
        for i in range(2, len(chars)):
            ctx = chars[i - 2] + chars[i - 1]
            ch = chars[i]
            c = self.contexts.get(ctx, 0)
            p = (self.counts.get(ctx + ch, 0) + 1) / (c + v)
            total += -math.log10(p)
        return total

    def to_dict(self) -> dict:
        return {"contexts": self.contexts, "counts": self.counts, "vocab": self.vocab}

    @classmethod
    def from_dict(cls, data: dict) -> CharacterLM:
        lm = cls()
        lm.contexts = data["contexts"]
        lm.counts = data["counts"]
        lm.vocab = data["vocab"]
        return lm


class Model:
    """The complete learned layer: classifier + reading table + language model."""

    def __init__(self) -> None:
        self.dialect = DialectNB()
        self.words = WordTable()
        self.lm = CharacterLM()
        self.rerank_lambda = 8.0  # weight of the LM penalty vs word scores (tuned on the dev split)

    # ------------------------------------------------------------- training
    @classmethod
    def train(
        cls,
        sources: list[Path],
        rerank_lambda: float = 8.0,
        per_class: int = 2000,
        seed: int = 42,
    ) -> Model:
        """Train on benchmark-format files: entries with arabizi/reference/dialect.

        The classifier is trained on a class-balanced sample (capped at
        per_class sentences per dialect) so large sources do not swamp the
        minority dialects. Entries without a reference contribute dialect
        signal only; the reading table and language model use only parallel
        pairs.
        """
        pairs: list[tuple[str, str]] = []
        parallel: list[tuple[str, str]] = []
        model = cls()
        for src in sources:
            data = json.loads(Path(src).read_text(encoding="utf-8"))
            for e in data.get("entries", []):
                pairs.append((e["arabizi"], e.get("dialect") or "other"))
                if e.get("reference"):
                    parallel.append((e["arabizi"], e["reference"]))
        by_class: dict[str, list[tuple[str, str]]] = {}
        for p in pairs:
            by_class.setdefault(p[1], []).append(p)
        rng = random.Random(seed)
        balanced: list[tuple[str, str]] = []
        for items in by_class.values():
            rng.shuffle(items)
            balanced.extend(items[:per_class])
        model.dialect.train(balanced)
        for arabizi, arabic in parallel:
            model.words.add_pair(arabizi, arabic)
        model.lm.train_texts([ar for _, ar in parallel])
        model.rerank_lambda = rerank_lambda
        return model

    # ------------------------------------------------------------- predict
    def hint_for(self, text: str) -> str | None:
        """Predicted dialect hint, or None when the call is not confident.

        Requires at least one feature seen in training: unseen text gets no
        hint rather than a confident guess on smoothed priors alone.
        """
        dialect, confidence = self.dialect.predict(text)
        seen = any(f in self.dialect.vocab for f in DialectNB._features(text))
        if dialect in EFFECTIVE_HINTS and confidence >= 0.4 and seen:
            return dialect
        return None

    # ----------------------------------------------------------- serialise
    def to_dict(self) -> dict:
        return {
            "version": "0.4.0",
            "rerank_lambda": self.rerank_lambda,
            "dialect": self.dialect.to_dict(),
            "words": self.words.to_dict(),
            "lm": self.lm.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Model:
        model = cls()
        model.rerank_lambda = data.get("rerank_lambda", 2.0)
        model.dialect = DialectNB.from_dict(data["dialect"])
        model.words = WordTable.from_dict(data["words"])
        model.lm = CharacterLM.from_dict(data["lm"])
        return model

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Model:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)