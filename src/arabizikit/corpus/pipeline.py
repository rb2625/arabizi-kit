"""End-to-end corpus pipeline: harvest, filter, annotate, split."""

from __future__ import annotations

from . import config
from .annotate import annotate
from .filter import filter_raw
from .harvest import harvest
from .split import split_annotated


def run(
    subreddits: list[str] | None = None,
    pages: int = config.DEFAULT_PAGES,
    annotate_enabled: bool = True,
    split_enabled: bool = True,
    min_score: int | None = None,
) -> dict:
    """Run the full pipeline and return per-stage stats."""
    report: dict = {"harvest": None, "filter": None, "annotate": None, "split": None}

    report["harvest"] = harvest(subreddits=subreddits, pages=pages)

    report["filter"] = filter_raw(min_score=min_score)

    annotated_path = config.ANNOTATED_DIR / "annotated.jsonl"
    if annotate_enabled:
        report["annotate"] = annotate(candidates_path=config.CORPUS_DIR / "candidates.jsonl", out_path=annotated_path)
    elif not annotated_path.exists():
        report["split"] = {"error": "no annotated data; run annotate first"}

    if split_enabled and annotated_path.exists():
        report["split"] = split_annotated(annotated_path=annotated_path)

    return report
