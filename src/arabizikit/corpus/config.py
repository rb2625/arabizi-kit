"""Defaults for the corpus pipeline. Everything is overridable on the CLI."""

from __future__ import annotations

import os
from pathlib import Path

# Working data lives at the repo root, outside the package, and is gitignored.
# Point ARABIZIKIT_CORPUS_DIR elsewhere if you want the data somewhere else.
CORPUS_DIR = Path(os.environ.get("ARABIZIKIT_CORPUS_DIR", Path(__file__).resolve().parents[3] / "corpus_data"))
RAW_DIR = CORPUS_DIR / "raw"
ANNOTATED_DIR = CORPUS_DIR / "annotated"
SPLITS_DIR = CORPUS_DIR / "splits"
EXTERNAL_DIR = CORPUS_DIR / "external"

DEFAULT_SUBREDDITS = ["Egypt", "arabs", "saudiarabia", "jordan", "Morocco", "Tunisia", "algeria", "lebanon"]
DEFAULT_PAGES = 2
REDDIT_USER_AGENT = "arabizikit-corpus/0.2 (+https://github.com/rb2625/arabizi-kit)"

# Reddit OAuth. Create a free script app at reddit.com/prefs/apps, then export
# these two values. Without them the harvester falls back to the public JSON
# endpoint, which many networks block.
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")

# Hugging Face datasets-server: no account needed for public datasets.
HF_TEXT_FIELDS = ("arabize", "arabizi", "arabizi_text", "text", "tweet", "comment", "sentence", "content")
HF_BATCH = 100

MIN_ARABIZI_SCORE = 2
MIN_WORDS = 2
MAX_WORDS = 40

# LLM annotation. Provider defaults to Groq (free tier, no credit card);
# see arabizikit.llm for the others (openai, gemini, ollama, anthropic).
# Switch with ARABIZIKIT_PROVIDER or --provider. Keys: GROQ_API_KEY,
# OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, or ARABIZIKIT_API_KEY
# as a blanket override. Ollama needs no key.
ANNOTATION_PROVIDER = os.environ.get("ARABIZIKIT_PROVIDER", "groq")
ANNOTATION_MODEL = os.environ.get("ARABIZIKIT_MODEL") or None  # None = provider default

# Learned layer (v0.3): the trained model lives in the working data dir and
# is built with `arabizikit model train` from the calibration benchmark plus
# the pipeline train/dev splits (never the held-out sets).
MODEL_DIR = CORPUS_DIR / "model"
MODEL_PATH = MODEL_DIR / "model.json"
MODEL_SOURCES = [
    Path(__file__).resolve().parents[3] / "data" / "benchmark.json",
    SPLITS_DIR / "train.json",
    SPLITS_DIR / "dev.json",
    CORPUS_DIR / "classifier" / "maghrebi.json",
    CORPUS_DIR / "classifier" / "egyptian.json",
    CORPUS_DIR / "classifier" / "levantine.json",
]
ANNOTATION_BATCH = 5  # keep requests small so free-tier per-minute token limits don't bite
ANNOTATION_RETRIES = 4
ANNOTATION_TIMEOUT = 90
IAA_SAMPLE = 0.1  # share of sentences double-annotated for inter-annotator agreement

RANDOM_SEED = 42

# Approximate pricing in USD per million tokens, used only for a cost estimate.
# Verify current rates before relying on the number.
PRICE_INPUT_PER_MT = 3.0
PRICE_OUTPUT_PER_MT = 15.0
