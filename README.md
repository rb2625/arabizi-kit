# ArabiziKit — open-source Arabizi → Arabic-script NLP toolkit

Transliterate **Arabizi** (Arabic written in Latin letters and digits — `2` for hamza/qaf, `3` for ʿayn, `7` for ḥāʾ, `5` for khāʾ…) into proper Arabic script, tag the dialect, and evaluate it all reproducibly.

```bash
$ arabizikit "ana 3ayz 2akol"
أنا عايز آكل

$ arabizikit "shlonak ya 5al" --dialect
شلونك يا خال
dialect: gulf  confidence: 1.0
```

## Why this project exists

Arabizi is everywhere — WhatsApp, TikTok, X, Reddit — but the existing
solutions are academic demos from a decade ago (NYU Abu Dhabi's transliteration
demo, the Jordanian Arabizi-Transliteration Corpus, COLABA) or subroutines
buried inside monolithic toolkits (CAMeL Tools). There is **no modern,
maintained, open-source Arabizi library** with:

- a clean Python API and CLI,
- dialect tagging (Gulf / Egyptian / Levantine / Maghrebi / MSA),
- ranked candidate output with an optional **LLM disambiguation** mode,
- and a **reproducible benchmark** you can run with one command.

That gap is this project. It is designed from day one as research infrastructure:
the corpus, benchmark, and paper plan live in-repo.

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │                 arabizikit                    │
                    └──────────────────────────────────────────────┘
   Arabizi text ──► Lexicon lookup ──► Rule engine ──► Candidates ──► Ranking
                     (exact match)    (phoneme scan)  (top-k list)   (bad-sequence
                          │               │               │             penalties)
                          │               │               │
                          ▼               ▼               ▼
                     dialect tag    context rules    hamza seating
                     (per word)     (2→ق/ء, ay→اي/ي,   (ء→أ/إ/ؤ/ئ)
                                     final a→ا/ة)
                          │                              │
                          ▼                              ▼
                    dialect guesser ───────────► final text + evidence
                          ▲
                          │  (optional, needs API key)
                    LLM disambiguation ─────► picks from top-k candidates
```

Key design decisions:

- **Lexicon first, rules second.** Exact lexicon matches win (they carry
  dialect evidence). Rules cover everything else and produce *ranked
  candidates* instead of a single guess — ambiguity is surfaced, not hidden.
- **Context rules resolve the easy cases.** Word-final `2` after a vowel is
  almost always qaf (`tare2 → طريق`); word-initial `2` before a consonant
  is either qaf or elided-alef (`2alb → قلب` vs `2ktob → اكتب`), so both are
  produced and ranked.
- **Short vowels are elided by default** (`3emel → عمل`, `nemshi → نمشي`),
  matching how Arabs actually write Arabizi, with the full vowel as a
  candidate alternative.
- **Arabic clitics are handled**: `el` attaches as `ال`, `w` as `و`,
  `3al` as `على ال`.
- **Zero core dependencies** — pure standard library. The optional LLM mode
  uses `urllib` (Anthropic API) so the package stays lightweight.

## Install

```bash
uv sync            # dev environment (or: pip install -e .[dev])
```

## Usage

```python
from arabizikit import transliterate

res = transliterate("ana 3ayz 2akol", top_k=3, with_dialect=True)
print(res.text)          # أنا عايز آكل
print(res.candidates)    # [('أنا عايز آكل', 0.0), ...]
print(res.dialect)       # {'dialect': 'egyptian', 'confidence': 1.0, 'evidence': [...]}
```

CLI:

```bash
arabizikit "shu 3am 3emel el yom" --top-k 5 --dialect
arabizikit "ya3ne shu" --llm                # LLM-assisted (needs ANTHROPIC_API_KEY)
arabizikit eval                             # run the benchmark
arabizikit eval --json                      # machine-readable report
arabizikit normalize "مُحَمَّد ـ"             # orthographic normalisation
```

## Web demo

The demo runs entirely in the browser — zero backend, zero dependencies:

```bash
python scripts/build_web.py    # embeds the phoneme/lexicon tables into the JS engine
# then open web/index.html
```

The tables are the single source of truth: `build_web.py` embeds them verbatim
into the JS engine, and `tests/test_web.py` fails if the bundle drifts from
the data (plus a Node syntax check). Python and browser engines produce
byte-identical candidate rankings on the golden set.

## Benchmark

```bash
arabizikit eval
```

Reports top-1 exact match, **hit@k** (is the reference among the ranked
candidates — the metric the LLM mode builds on), CER, and WER, overall and
per dialect.

> ⚠️ The current 33-sentence seed set is a **calibration set**: it shares
> distribution with the seed lexicon, so scores are an upper bound on the
> hybrid pipeline. The real held-out corpus (social-media Arabizi collected
> via the pipeline described in `paper/outline.md`) is the next milestone —
> see Roadmap.

## Roadmap

- [x] **v0.1** — rule engine, seed lexicon (~120 words), dialect baseline, benchmark, CLI, browser demo, paper outline
- [ ] **v0.2** — corpus collection pipeline (Reddit/TikTok/X/Youtube → LLM-assisted annotation) + first held-out split
- [ ] **v0.3** — dialect classification beyond lexicon tags; fine-tuned reranker over top-k candidates
- [ ] **v0.4** — LLM mode as a first-class API, npm/JS distribution
- [ ] **v1.0** — arXiv paper + release on PyPI

## Contributing

Corpus contributions are the highest-value contribution: add real Arabizi
sentences (with reference Arabic + dialect tag) to `data/benchmark.json` and
run `arabizikit eval`. See `paper/outline.md` for the research framing.

## License

MIT © 2026 Muhammed Rabeeh Mattath
