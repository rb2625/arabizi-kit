"""Build classifier-only training files from public Hugging Face datasets.

The learned dialect classifier needs balanced signal per dialect, but the
annotated corpus is heavily Egyptian. This script pulls plain Arabizi text
from open datasets with known dialects and writes them as benchmark-format
files (dialect tag, no reference) under corpus_data/classifier/. They are
used by `arabizikit model train` for the dialect classifier only; the
reading table and language model never see them, and none of the three
external evaluation sets are used here.

Usage::

    python scripts/build_classifier_data.py                 # real text sources
    python scripts/build_classifier_data.py --synthetic N   # LLM-generated text

Real sources: ilias-brh/english-darija-arabizi-sentence-pairs (Maghrebi)
and Mohamedd123321/Arabizi-dataset-v3 (Egyptian). The --synthetic mode
uses the configured LLM provider (Groq free tier by default) to generate
casual Arabizi for dialects with little public text, such as Levantine.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from arabizikit import llm
from arabizikit.corpus.harvest import fetch_hf_rows

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "corpus_data" / "classifier"

# Dialects with little public Arabizi text get LLM-generated training data.
# Each entry is a short prompt sketch the model expands into natural code.
SYNTHETIC = {
    "levantine": (
        "Levantine Arabizi as a young person in Beirut or Amman texts: use shu, keefak, "
        "keefik, beddi, baddi, ktir, mafi, hal, 3an jad, hay, haida, yalla, shway"
    ),
    "gulf": (
        "Gulf Arabizi as a young person in Riyadh or Dubai texts: use shlonak, shlonik, "
        "wesh, eish, 2ol, wayed, zayn, shway, ala tool, ba3ad, hala"
    ),
}

SOURCES = [
    {
        "dataset": "ilias-brh/english-darija-arabizi-sentence-pairs",
        "field": "darija",
        "dialect": "maghrebi",
        "rows": 2500,
        "name": "maghrebi",
    },
    {
        "dataset": "Mohamedd123321/Arabizi-dataset-v3",
        "field": "text",
        "dialect": "egyptian",
        "rows": 2500,
        "name": "egyptian",
    },
]

_LATIN_SHARE = re.compile(r"[A-Za-z]")


def _parse_array(content: str) -> list[str]:
    """Pull a JSON array of strings out of an LLM reply."""
    content = content.strip()
    start, end = content.find("["), content.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [str(s).strip() for s in data if isinstance(s, str)]


import re
import time


def _synthetic(dialect: str, sketch: str, per_call: int = 25, target: int = 400) -> list[str]:
    """Generate casual Arabizi sentences for a dialect via the LLM."""
    system = (
        "You write authentic casual Arabizi (Romanized Arabic). Reply with ONLY a valid "
        "JSON array of strings, one sentence per string, no quotes or newlines inside "
        "the strings, no explanation."
    )
    sentences: list[str] = []
    seen: set[str] = set()
    calls = 0
    for _ in range(400):  # safety ceiling; exits once enough were generated
        if len(sentences) >= target:
            break
        prompt = (
            f"Write {per_call} short, casual, realistic Arabizi text messages in {dialect} "
            f"dialect. {sketch}. Keep each sentence under 12 words, plain text. Reply ONLY "
            "with a JSON array of strings."
        )
        try:
            content = llm.chat_completion(
                provider=llm.DEFAULT_PROVIDER,
                model=None,
                api_key=None,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                json_mode=False,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            if "429" in str(exc):
                # Free tier per-minute token limits: wait out the window.
                match = re.search(r"in (\d+(?:\.\d+)?)([sm])", str(exc))
                wait = min(float(match.group(1)) * (60 if match.group(2) == "m" else 1) + 5, 120) if match else 45
                print(f"  rate limited; waiting {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  llm call failed: {exc}", file=sys.stderr)
            break
        for s in _parse_array(content):
            if _usable(s) and s.lower() not in seen:
                seen.add(s.lower())
                sentences.append(s)
        calls += 1
        time.sleep(12)  # stay under the free tier's per-minute token cap
    return sentences[:target]


def _usable(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    words = text.split()
    if not 2 <= len(words) <= 40:
        return False
    letters = sum(1 for ch in text if ch.isalpha())
    latin = len(_LATIN_SHARE.findall(text))
    return latin > 0 and latin / max(letters, 1) > 0.5


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", help="generate LLM text for under-represented dialects")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.synthetic:
        for dialect, sketch in SYNTHETIC.items():
            sentences = _synthetic(dialect, sketch)
            entries = [
                {"id": f"clf-syn-{dialect}-{i:06d}", "arabizi": s, "reference": "", "dialect": dialect}
                for i, s in enumerate(sentences)
            ]
            path = OUT_DIR / f"{dialect}.json"
            payload = {
                "version": "1.0.0",
                "description": f"classifier-only synthetic {dialect} text (LLM-generated)",
                "entries": entries,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{dialect} (synthetic): {len(entries)} sentences -> {path}")
        return 0

    for spec in SOURCES:
        entries = []
        offset = 0
        while len(entries) < spec["rows"]:
            chunk = fetch_hf_rows(spec["dataset"], "default", "train", offset=offset, length=100)
            if not chunk:
                break
            for item in chunk:
                row = item.get("row") or {}
                text = str(row.get(spec["field"]) or "")
                if _usable(text):
                    entries.append(
                        {
                            "id": f"clf-{spec['name']}-{len(entries):06d}",
                            "arabizi": text,
                            "reference": "",
                            "dialect": spec["dialect"],
                        }
                    )
                    if len(entries) >= spec["rows"]:
                        break
            offset += len(chunk)
        path = OUT_DIR / f"{spec['name']}.json"
        payload = {"version": "1.0.0", "description": f"classifier-only {spec['dialect']} text from {spec['dataset']}", "entries": entries}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{spec['name']}: {len(entries)} sentences -> {path}")

    total = sum(1 for f in OUT_DIR.glob("*.json"))
    print(f"done: {total} classifier files under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
