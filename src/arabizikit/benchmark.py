"""Reproducible evaluation harness for arabizikit.

Metrics (all computed on orthographically normalised forms):

- **Exact@1** — did the top-ranked candidate match the reference?
- **Hit@k**  — is the reference among the top-k candidates?
- **CER**    — character error rate (Levenshtein / reference length).
- **WER**    — word error rate (Levenshtein over tokens / token count).

Results are aggregated overall and per dialect so regressions are visible
when the corpus grows. ``arabizikit eval`` prints the table and writes the
JSON report to stdout with ``--json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .normalize import normalize, normalized_tokens
from .transliterate import Transliterator

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "benchmark.json"


def levenshtein(a: str, b: str) -> int:
    """Classic DP edit distance (also used for token sequences)."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def word_levenshtein(a: list[str], b: list[str]) -> int:
    return levenshtein(a, b)


def run_benchmark(data_path: str | Path | None = None, top_k: int = 3) -> dict:
    data_path = Path(data_path) if data_path else DEFAULT_DATA
    entries = json.loads(data_path.read_text(encoding="utf-8"))["entries"]
    tr = Transliterator()

    rows: list[dict] = []
    for e in entries:
        res = tr.transliterate(e["arabizi"], top_k=top_k)
        preds = [normalize(ar) for ar, _ in res.candidates]
        ref = normalize(e["reference"])
        ref_tokens = normalized_tokens(e["reference"])
        pred_tokens = normalized_tokens(res.text)
        rows.append(
            {
                "id": e["id"],
                "arabizi": e["arabizi"],
                "reference": e["reference"],
                "predicted": res.text,
                "dialect": e["dialect"],
                "exact": normalize(res.text) == ref,
                "hit": ref in preds,
                "cer": levenshtein(normalize(res.text), ref) / max(len(ref), 1),
                "wer": word_levenshtein(pred_tokens, ref_tokens) / max(len(ref_tokens), 1),
            }
        )

    def aggregate(subset: list[dict]) -> dict:
        n = len(subset)
        if n == 0:
            return {"n": 0, "exact": 0.0, "hit": 0.0, "cer": 0.0, "wer": 0.0}
        return {
            "n": n,
            "exact": sum(r["exact"] for r in subset) / n,
            "hit": sum(r["hit"] for r in subset) / n,
            "cer": sum(r["cer"] for r in subset) / n,
            "wer": sum(r["wer"] for r in subset) / n,
        }

    overall = aggregate(rows)
    by_dialect = {d: aggregate([r for r in rows if r["dialect"] == d]) for d in sorted({r["dialect"] for r in rows})}
    return {"overall": overall, "by_dialect": by_dialect, "rows": rows}


def format_report(report: dict) -> str:
    lines = ["arabizikit benchmark", "=" * 44]
    for section, data in (("overall", report["overall"]),):
        lines.append(
            f"{'metric':<12}{'value':>8}"
        )
        for key in ("n", "exact", "hit", "cer", "wer"):
            val = data[key]
            lines.append(f"{key:<12}{val:>8.3f}" if isinstance(val, float) else f"{key:<12}{val:>8}")
    lines.append("")
    lines.append(f"{'dialect':<12}{'n':>4}{'exact':>8}{'hit':>8}{'cer':>8}{'wer':>8}")
    for dialect, d in report["by_dialect"].items():
        lines.append(f"{dialect:<12}{d['n']:>4}{d['exact']:>8.3f}{d['hit']:>8.3f}{d['cer']:>8.3f}{d['wer']:>8.3f}")
    lines.append("")
    lines.append(f"{'id':<10}{'exact':<6}{'hit':<6}{'arabizi':<32}{'predicted':<28}{'reference'}")
    for r in report["rows"]:
        lines.append(f"{r['id']:<10}{r['exact']!s:<6}{r['hit']!s:<6}{r['arabizi']:<32}{r['predicted']:<28}{r['reference']}")
    return "\n".join(lines)
