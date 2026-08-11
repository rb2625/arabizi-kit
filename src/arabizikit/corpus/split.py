"""Held-out split and external benchmark import.

split_annotated writes train/dev/test in the same shape as data/benchmark.json
so the held-out test set can be scored with:
    arabizikit eval --data corpus_data/splits/test.json

import_parallel converts a parallel Arabizi/Arabic dataset (for example
arbml/Arabizi_Transliteration on Hugging Face, which ships gold references)
into a benchmark file for instant external evaluation.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from . import config
from .harvest import fetch_hf_rows, resolve_split


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


def import_parallel(
    dataset: str,
    arabizi_field: str,
    arabic_field: str,
    config_name: str | None = None,
    split: str | None = None,
    limit: int | None = None,
    out_path: str | Path | None = None,
) -> dict:
    """Convert a parallel Arabizi/Arabic dataset into a benchmark file.

    Rows without usable values in either field are skipped.
    """
    out_path = Path(out_path or config.EXTERNAL_DIR / f"{dataset.split('/')[-1]}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    config_name, split = resolve_split(dataset, config_name, split)

    entries = []
    offset = 0
    while limit is None or len(entries) < limit:
        chunk = fetch_hf_rows(dataset, config_name, split, offset=offset, length=config.HF_BATCH)
        if not chunk:
            break
        for entry in chunk:
            row = entry.get("row") or {}
            arabizi = row.get(arabizi_field)
            arabic = row.get(arabic_field)
            if not arabizi or not arabic or not str(arabizi).strip() or not str(arabic).strip():
                continue
            entries.append(
                {
                    "id": f"ext-{dataset.split('/')[-1]}-{len(entries):05d}",
                    "arabizi": str(arabizi),
                    "reference": str(arabic),
                    "dialect": "",
                    "note": f"external: {dataset}",
                }
            )
            if limit is not None and len(entries) >= limit:
                break
        offset += len(chunk)

    payload = {
        "version": "0.2.0",
        "description": f"external benchmark imported from {dataset}",
        "entries": entries,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"n": len(entries), "out": str(out_path)}
