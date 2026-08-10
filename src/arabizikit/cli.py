"""Command-line interface for arabizikit.

Examples::

    arabizikit "ana 3ayz 2akol"
    arabizikit "shlonak ya 5al" --dialect
    arabizikit "shu 3am 3emel" --top-k 5
    arabizikit "ya3ne shu" --llm          # requires ANTHROPIC_API_KEY
    arabizikit eval
    arabizikit eval --json
    arabizikit normalize "مرحباً 3alam"
"""

from __future__ import annotations

import argparse
import json
import sys

from . import benchmark as bench
from .disambiguate import llm_transliterate
from .normalize import normalize
from .transliterate import Transliterator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arabizikit",
        description="Transliterate Arabizi (Romanized Arabic) to Arabic script.",
    )
    parser.add_argument("text", nargs="*", help="Arabizi text to transliterate")
    parser.add_argument("--top-k", type=int, default=3, help="number of ranked candidates (default 3)")
    parser.add_argument("--dialect", action="store_true", help="show the detected dialect")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--llm", action="store_true", help="LLM-assisted disambiguation (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--eval", nargs="?", const="default", metavar="DATA", help="run the benchmark suite")
    parser.add_argument("--normalize", nargs="+", metavar="TEXT", help="normalise Arabic text")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 and cannot print Arabic; force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.normalize:
        for text in args.normalize:
            print(normalize(text))
        return 0

    if args.eval:
        data_path = None if args.eval == "default" else args.eval
        report = bench.run_benchmark(data_path=data_path, top_k=max(args.top_k, 1))
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(bench.format_report(report))
        return 0

    # `arabizikit eval` (bare word, no dashes) is friendlier than --eval
    if args.text == ["eval"]:
        report = bench.run_benchmark(data_path=None, top_k=max(args.top_k, 1))
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else bench.format_report(report))
        return 0

    text = " ".join(args.text)
    if not text:
        parser.print_help()
        return 0

    if args.llm:
        try:
            result = llm_transliterate(text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RuntimeError) as exc:  # network / key / parse errors
            print(f"LLM mode failed: {exc}", file=sys.stderr)
            return 1
        return 0

    tr = Transliterator()
    res = tr.transliterate(text, top_k=max(args.top_k, 1), with_dialect=args.dialect)

    if args.json:
        payload = {"text": res.text, "candidates": [{"arabic": ar, "score": s} for ar, s in res.candidates]}
        if res.dialect:
            payload["dialect"] = res.dialect
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(res.text)
    if args.top_k > 1:
        for rank, (ar, score) in enumerate(res.candidates[1:], start=2):
            print(f"  [{rank}] {ar}  (score {score:+.3f})")
    if args.dialect:
        d = res.dialect or {}
        print(f"dialect: {d.get('dialect', 'unknown')}  confidence: {d.get('confidence', 0.0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
