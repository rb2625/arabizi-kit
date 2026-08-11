"""Stratified train/dev/test split of the annotated corpus.

Output files use the same shape as data/benchmark.json so the held-out test
set can be scored directly with: arabizikit eval --data corpus_data/splits/test.json
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from . import config


def load_annotated(path: str | Path) -> list[dict]:
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_annotated(
    annotated_path: str | Path | None = None,
    train: float = 0.70,
    dev: float = 0.15,
    test: float = 0.15,
    out_dir: str | Path | None = None,
    seed: int = config.RANDOM_SEED,
) -> dict:
    """Stratify by dialect, split per dialect, write benchmark-format files."""
    annotated_path = Path(annotated_path or config.ANNOTATED_DIR / "annotated.jsonl")
    out_dir = Path(out_dir or config.SPLITS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_annotated(annotated_path)
    if not rows:
        return {"error": "no annotated rows", "n": 0}

    by_dialect: dict[str, list[dict]] = {}
    for r in rows:
        by_dialect.setdefault(r.get("dialect", "other"), []).append(r)

    rng = random.Random(seed)
    buckets = {"train": [], "dev": [], "test": []}
    for group in by_dialect.values():
        rng.shuffle(group)
        n = len(group)
        n_train = round(n * train)
        n_dev = round(n * dev)
        buckets["train"] += group[:n_train]
        buckets["dev"] += group[n_train : n_train + n_dev]
        buckets["test"] += group[n_train + n_dev :]

    written = {}
    counter = 0
    for name, bucket in buckets.items():
        entries = []
        for r in bucket:
            counter += 1
            entries.append(
                {
                    "id": f"corp-{counter:05d}",
                    "arabizi": r["arabizi"],
                    "reference": r.get("arabic", ""),
                    "dialect": r.get("dialect", "other"),
                    "note": r.get("note", ""),
                }
            )
        path = out_dir / f"{name}.json"
        payload = {
            "version": "0.2.0",
            "description": f"arabizikit held-out corpus, {name} split",
            "entries": entries,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written[name] = len(entries)

    dialect_counts = {d: len(g) for d, g in by_dialect.items()}
    return {"n": len(rows), "splits": written, "dialects": dialect_counts, "out": str(out_dir)}
