"""Command-line interface for arabizikit.

Examples::

    arabizikit "ana 3ayz 2akol"
    arabizikit "shlonak ya 5al" --dialect
    arabizikit "shu 3am 3emel" --top-k 5
    arabizikit "ya3ne shu" --llm          # requires ANTHROPIC_API_KEY
    arabizikit eval
    arabizikit eval --json
    arabizikit eval --data corpus_data/splits/test.json
    arabizikit normalize "مرحباً 3alam"

Corpus pipeline (v0.2)::

    arabizikit corpus harvest --subreddits Egypt arabs --pages 2
    arabizikit corpus filter
    arabizikit corpus annotate            # requires ANTHROPIC_API_KEY
    arabizikit corpus split
    arabizikit corpus run --subreddits Egypt arabs --pages 1
"""

from __future__ import annotations

import argparse
import json
import sys

from . import benchmark as bench
from .corpus import annotate as corpus_annotate
from .corpus import config as corpus_config
from .corpus import pipeline as corpus_pipeline
from .corpus.filter import filter_raw
from .corpus.harvest import harvest
from .corpus.split import split_annotated
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


def corpus_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="arabizikit corpus", description="Arabizi corpus pipeline (v0.2)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="harvest, filter, then annotate and split when possible")
    p_run.add_argument("--subreddits", nargs="*", default=None)
    p_run.add_argument("--pages", type=int, default=corpus_config.DEFAULT_PAGES)
    p_run.add_argument("--min-score", type=int, default=None)
    p_run.add_argument("--no-annotate", action="store_true", help="skip LLM annotation")
    p_run.add_argument("--no-split", action="store_true", help="skip the split")

    p_harvest = sub.add_parser("harvest", help="fetch public Reddit posts into corpus_data/raw/")
    p_harvest.add_argument("--subreddits", nargs="*", default=None)
    p_harvest.add_argument("--pages", type=int, default=corpus_config.DEFAULT_PAGES)

    p_filter = sub.add_parser("filter", help="extract Arabizi sentences from raw posts")
    p_filter.add_argument("--min-score", type=int, default=None)

    p_annotate = sub.add_parser("annotate", help="LLM-annotate candidates (needs ANTHROPIC_API_KEY)")
    p_annotate.add_argument("--batch", type=int, default=corpus_config.ANNOTATION_BATCH)
    p_annotate.add_argument("--iaa", type=float, default=corpus_config.IAA_SAMPLE, help="share annotated twice for agreement")
    p_annotate.add_argument("--model", default=corpus_config.ANNOTATION_MODEL)

    p_split = sub.add_parser("split", help="stratified train/dev/test split in benchmark format")
    p_split.add_argument("--train", type=float, default=0.70)
    p_split.add_argument("--dev", type=float, default=0.15)
    p_split.add_argument("--test", type=float, default=0.15)
    p_split.add_argument("--seed", type=int, default=corpus_config.RANDOM_SEED)

    args = parser.parse_args(argv)

    if args.cmd == "run":
        report = corpus_pipeline.run(
            subreddits=args.subreddits,
            pages=args.pages,
            annotate_enabled=not args.no_annotate,
            split_enabled=not args.no_split,
            min_score=args.min_score,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "harvest":
        stats = harvest(subreddits=args.subreddits, pages=args.pages)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "filter":
        stats = filter_raw(min_score=args.min_score)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "annotate":
        try:
            report = corpus_annotate.annotate(batch_size=args.batch, iaa_sample=args.iaa)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"annotation failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "split":
        report = split_annotated(train=args.train, dev=args.dev, test=args.test, seed=args.seed)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    return 1


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 and cannot print Arabic; force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "corpus":
        return corpus_main(argv[1:])

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
