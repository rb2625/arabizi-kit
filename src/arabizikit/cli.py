"""Command-line interface for arabizikit.

Examples::

    arabizikit "ana 3ayz 2akol"
    arabizikit "shlonak ya 5al" --dialect
    arabizikit "shu 3am 3emel" --top-k 5
    arabizikit "ya3ne shu" --llm          # needs an LLM key (Groq free tier by default)
    arabizikit eval
    arabizikit eval --json
    arabizikit eval --data corpus_data/splits/test.json
    arabizikit eval --data corpus_data/splits/test.json --model   # learned layer
    arabizikit model train                                        # build the learned layer
    arabizikit normalize "مرحباً 3alam"

Corpus pipeline (v0.2)::

    # no-account path: harvest from a public Hugging Face dataset
    arabizikit corpus harvest-hf --dataset Mohamedd123321/Arabizi-dataset-v2 --rows 500
    arabizikit corpus filter
    arabizikit corpus annotate            # needs GROQ_API_KEY (free tier) by default
    arabizikit corpus split
    arabizikit corpus run --hf-dataset Mohamedd123321/Arabizi-dataset-v2 --rows 500

    # external parallel set with gold references (instant eval, no API cost)
    arabizikit corpus import-hf --dataset arbml/Arabizi_Transliteration \
        --arabizi-field Arabize --arabic-field Arabic
    arabizikit eval --data corpus_data/external/Arabizi_Transliteration.json

    # optional Reddit path (needs a script app + the two env vars)
    arabizikit corpus harvest --subreddits Egypt arabs --pages 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import benchmark as bench
from .corpus import annotate as corpus_annotate
from .corpus import config as corpus_config
from .corpus import pipeline as corpus_pipeline
from .corpus.filter import filter_raw
from .corpus.harvest import harvest, harvest_hf
from .corpus.split import import_parallel, split_annotated
from .disambiguate import llm_transliterate
from .model import Model
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
    parser.add_argument("--hint", metavar="DIALECT", default=None, help="assume a dialect convention (egyptian, levantine, gulf, maghrebi) for the ambiguous readings")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--llm", action="store_true", help="LLM-assisted disambiguation (needs an LLM key; Groq free tier by default)")
    parser.add_argument("--eval", nargs="?", const="default", metavar="DATA", help="run the benchmark suite")
    parser.add_argument("--data", metavar="FILE", help="evaluate against a benchmark file (alias for --eval FILE)")
    parser.add_argument("--model", action="store_true", help="use the trained learned layer (dialect prediction, learned readings, reranking)")
    parser.add_argument("--normalize", nargs="+", metavar="TEXT", help="normalise Arabic text")
    return parser


def corpus_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="arabizikit corpus", description="Arabizi corpus pipeline (v0.2)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="harvest, filter, then annotate and split when possible")
    p_run.add_argument("--subreddits", nargs="*", default=None)
    p_run.add_argument("--pages", type=int, default=corpus_config.DEFAULT_PAGES)
    p_run.add_argument("--hf-dataset", default=None, help="harvest from Hugging Face instead of Reddit")
    p_run.add_argument("--rows", type=int, default=500)
    p_run.add_argument("--min-score", type=int, default=None)
    p_run.add_argument("--provider", default=corpus_config.ANNOTATION_PROVIDER, help="LLM provider for annotation (default groq)")
    p_run.add_argument("--no-annotate", action="store_true", help="skip LLM annotation")
    p_run.add_argument("--no-split", action="store_true", help="skip the split")

    p_harvest = sub.add_parser("harvest", help="fetch public Reddit posts into corpus_data/raw/")
    p_harvest.add_argument("--subreddits", nargs="*", default=None)
    p_harvest.add_argument("--pages", type=int, default=corpus_config.DEFAULT_PAGES)

    p_hf = sub.add_parser("harvest-hf", help="harvest text from a public Hugging Face dataset (no account needed)")
    p_hf.add_argument("--dataset", required=True)
    p_hf.add_argument("--rows", type=int, default=500)
    p_hf.add_argument("--text-field", default=None, help="column holding the text (auto-detected otherwise)")
    p_hf.add_argument("--config", default=None)
    p_hf.add_argument("--split", default=None)

    p_import = sub.add_parser("import-hf", help="import a parallel Arabizi/Arabic dataset as a benchmark file")
    p_import.add_argument("--dataset", required=True)
    p_import.add_argument("--arabizi-field", required=True)
    p_import.add_argument("--arabic-field", required=True)
    p_import.add_argument("--config", default=None)
    p_import.add_argument("--split", default=None)
    p_import.add_argument("--limit", type=int, default=None)
    p_import.add_argument("--dialect", default=None, help="override the dialect tag (known datasets are tagged automatically)")

    p_filter = sub.add_parser("filter", help="extract Arabizi sentences from raw posts")
    p_filter.add_argument("--min-score", type=int, default=None)

    p_annotate = sub.add_parser("annotate", help="LLM-annotate candidates (needs GROQ_API_KEY by default; free tier)")
    p_annotate.add_argument("--batch", type=int, default=corpus_config.ANNOTATION_BATCH)
    p_annotate.add_argument("--iaa", type=float, default=corpus_config.IAA_SAMPLE, help="share annotated twice for agreement")
    p_annotate.add_argument("--provider", default=corpus_config.ANNOTATION_PROVIDER, help="LLM provider: groq (default), openai, gemini, ollama, anthropic")
    p_annotate.add_argument("--model", default=corpus_config.ANNOTATION_MODEL, help="model name (defaults to the provider default)")

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
            hf_dataset=args.hf_dataset,
            hf_rows=args.rows,
            annotate_enabled=not args.no_annotate,
            split_enabled=not args.no_split,
            min_score=args.min_score,
            provider=args.provider,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "harvest":
        stats = harvest(subreddits=args.subreddits, pages=args.pages)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "harvest-hf":
        try:
            stats = harvest_hf(
                dataset=args.dataset,
                rows=args.rows,
                text_field=args.text_field,
                config=args.config,
                split=args.split,
            )
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"harvest failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "import-hf":
        try:
            report = import_parallel(
                dataset=args.dataset,
                arabizi_field=args.arabizi_field,
                arabic_field=args.arabic_field,
                config_name=args.config,
                split=args.split,
                limit=args.limit,
                dialect=args.dialect,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"import failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "filter":
        stats = filter_raw(min_score=args.min_score)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "annotate":
        try:
            report = corpus_annotate.annotate(
                batch_size=args.batch,
                iaa_sample=args.iaa,
                provider=args.provider,
                model=args.model,
            )
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


def model_main(argv: list[str]) -> int:
    """Subcommands for the trained learned layer."""
    parser = argparse.ArgumentParser(prog="arabizikit model", description="learned layer (v0.3)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_train = sub.add_parser("train", help="train the dialect classifier, reading table, and reranker")
    p_train.add_argument("--extra", nargs="*", default=None, help="extra benchmark files to train on")
    p_train.add_argument("--lambda-weight", type=float, default=8.0, dest="lambda_weight", help="language-model weight in the rerank (tuned on the dev split)")
    p_train.add_argument("--out", default=None, help="where to save the model (default corpus_data/model/model.json)")

    sub.add_parser("status", help="show whether a trained model exists")

    args = parser.parse_args(argv)

    if args.cmd == "train":
        sources = list(corpus_config.MODEL_SOURCES)
        if args.extra:
            sources += [Path(s) for s in args.extra]
        existing = [s for s in sources if s.exists()]
        if not existing:
            print("no training sources found; run the corpus pipeline first", file=sys.stderr)
            return 1
        model = Model.train(existing, rerank_lambda=args.lambda_weight)
        out = Path(args.out) if args.out else corpus_config.MODEL_PATH
        model.save(out)
        report = {
            "sources": [str(s) for s in existing],
            "out": str(out),
            "dialect_classes": len(model.dialect.classes),
            "learned_words": len(model.words.words),
            "lm_vocab": len(model.lm.vocab),
            "rerank_lambda": model.rerank_lambda,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "status":
        path = corpus_config.MODEL_PATH
        if not path.exists():
            print(json.dumps({"trained": False, "path": str(path)}, indent=2))
            return 0
        model = Model.load(path)
        print(
            json.dumps(
                {
                    "trained": True,
                    "path": str(path),
                    "dialect_classes": len(model.dialect.classes),
                    "learned_words": len(model.words.words),
                    "lm_vocab": len(model.lm.vocab),
                    "rerank_lambda": model.rerank_lambda,
                },
                indent=2,
            )
        )
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
    if argv and argv[0] == "model":
        return model_main(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.normalize:
        for text in args.normalize:
            print(normalize(text))
        return 0

    if args.eval or args.data:
        data_path = args.data if args.data else (None if args.eval == "default" else args.eval)
        report = bench.run_benchmark(data_path=data_path, top_k=max(args.top_k, 1), use_model=args.model)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(bench.format_report(report))
        return 0

    # `arabizikit eval` (bare word, no dashes) is friendlier than --eval
    if args.text == ["eval"]:
        report = bench.run_benchmark(data_path=None, top_k=max(args.top_k, 1), use_model=args.model)
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

    model = None
    if args.model:
        if not corpus_config.MODEL_PATH.exists():
            print(f"no trained model at {corpus_config.MODEL_PATH}; run `arabizikit model train` first", file=sys.stderr)
            return 1
        model = Model.load(corpus_config.MODEL_PATH)
    tr = Transliterator(model=model)
    res = tr.transliterate(text, top_k=max(args.top_k, 1), with_dialect=args.dialect, dialect_hint=args.hint)

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
