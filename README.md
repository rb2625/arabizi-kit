# ArabiziKit - open-source Arabizi -> Arabic-script NLP toolkit

Transliterate **Arabizi** (Arabic written in Latin letters and digits - `2` for hamza/qaf, `3` for ʿayn, `7` for ḥāʾ, `5` for khāʾ...) into proper Arabic script, tag the dialect, and evaluate it all reproducibly.

```bash
$ arabizikit "ana 3ayz 2akol"
أنا عايز آكل

$ arabizikit "shlonak ya 5al" --dialect
شلونك يا خال
dialect: gulf confidence: 1.0
```

## Why this project exists

Arabizi is everywhere - WhatsApp, TikTok, X, Reddit - but the existing
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
Arabizi text
 -> Lexicon lookup (exact match): dialect tag per word
 -> Rule engine (phoneme scan): context rules (2 as qaf or hamza,
 short-vowel elision, final a as taa marbuta or alef)
 -> Candidates (top-k list): ranked with bad-sequence penalties
 -> Hamza seating, clitic attachment
 -> Final text and evidence
 -> LLM disambiguation (optional): picks from the top-k candidates
```

Key design decisions:

- **Lexicon first, rules second.** Exact lexicon matches win (they carry
 dialect evidence). Rules cover everything else and produce *ranked
 candidates* instead of a single guess - ambiguity is surfaced, not hidden.
- **Context rules resolve the easy cases.** Word-final `2` after a vowel is
 almost always qaf (`tare2 -> طريق`); word-initial `2` before a consonant
 is either qaf or elided-alef (`2alb -> قلب` vs `2ktob -> اكتب`), so both are
 produced and ranked.
- **Short vowels are elided by default** (`3emel -> عمل`, `nemshi -> نمشي`),
 matching how Arabs actually write Arabizi, with the full vowel as a
 candidate alternative.
- **Arabic clitics are handled**: `el` attaches as `ال`, `w` as `و`,
 `3al` as `على ال`.
- **Zero core dependencies** - pure standard library. The optional LLM mode
 uses `urllib` (Anthropic API) so the package stays lightweight.

## Install

```bash
uv sync # dev environment (or: pip install -e .[dev])
```

## Usage

```python
from arabizikit import transliterate

res = transliterate("ana 3ayz 2akol", top_k=3, with_dialect=True)
print(res.text) # أنا عايز آكل
print(res.candidates) # [('أنا عايز آكل', 0.0), ...]
print(res.dialect) # {'dialect': 'egyptian', 'confidence': 1.0, 'evidence': [...]}
```

CLI:

```bash
arabizikit "shu 3am 3emel el yom" --top-k 5 --dialect
arabizikit "ya3ne shu" --llm # LLM-assisted (needs ANTHROPIC_API_KEY)
arabizikit eval # run the benchmark
arabizikit eval --json # machine-readable report
arabizikit normalize "مُحَمَّد ـ" # orthographic normalisation
```

## Web demo

The demo runs entirely in the browser - zero backend, zero dependencies:

```bash
python scripts/build_web.py # embeds the phoneme/lexicon tables into the JS engine
# then open web/index.html
```

The tables are the single source of truth: `build_web.py` embeds them verbatim
into the JS engine, and `tests/test_web.py` fails if the bundle drifts from
the data (plus a Node syntax check). Python and browser engines produce
byte-identical candidate rankings on the golden set.

## Corpus pipeline (v0.2)

Build a held-out evaluation set from real social-media Arabizi. Four stages,
no new dependencies. Harvesting works two ways:

- Hugging Face (no account, works today): harvest-hf pulls text from a
  public dataset; the text column is auto-detected
- Reddit (optional, needs a free script app): harvest pulls posts via OAuth
  with REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET set, one JSONL per
  subreddit into corpus_data/raw/

```bash
arabizikit corpus harvest-hf --dataset Mohamedd123321/Arabizi-dataset-v2 --rows 500
arabizikit corpus filter
arabizikit corpus annotate # needs ANTHROPIC_API_KEY
arabizikit corpus split
```

Or the whole thing in one command:

```bash
arabizikit corpus run --hf-dataset Mohamedd123321/Arabizi-dataset-v2 --rows 500
```

- filter: keeps Latin-script sentences that score as Arabizi (digit+letter markers, lexicon words), strips URLs, mentions, hashtags, and emoji, and splits posts into sentences
- annotate: Claude renders Arabic script and a dialect tag per sentence; the rule engine top-1 is stored alongside for agreement, and a deterministic 10% sample is annotated twice to report inter-annotator agreement
- split: stratified train/dev/test by dialect, written in benchmark format

External parallel sets with gold references score instantly, no API cost:

```bash
arabizikit corpus import-hf --dataset arbml/Arabizi_Transliteration --arabizi-field Arabize --arabic-field Arabic
arabizikit corpus import-hf --dataset akhanafer/arabic-to-arabizi --arabizi-field arabizi --arabic-field arabic
arabizikit corpus import-hf --dataset elkababi2/Darija-Text-Ar-Arabizi --arabizi-field darija_Latn --arabic-field darija_Arab_new
arabizikit eval --data corpus_data/external/Arabizi_Transliteration.json
```

Score a pipeline-split held-out test set with:

```bash
arabizikit eval --data corpus_data/splits/test.json
```

corpus_data/ is gitignored: raw network content, API annotations, and
imported third-party sets are working data, not part of the repository.
The import commands rebuild the external sets in one call.

## Benchmark

```bash
arabizikit eval
```

Reports top-1 exact match, **hit@k** (is the reference among the ranked
candidates - the metric the LLM mode builds on), CER, and WER, overall and
per dialect.

Two evaluation sets exist. The 33-sentence seed set in `data/benchmark.json`
is a **calibration set**: it shares distribution with the seed lexicon, so
scores are an upper bound on the hybrid pipeline.

Real held-out numbers come from three external parallel sets (imported via
`corpus import-hf`, gold references, no annotation cost):

| set | n | exact | hit@3 | CER |
| --- | --- | --- | --- | --- |
| Egyptian (arbml/Arabizi_Transliteration) | 500 | 0.366 | 0.510 | 0.243 |
| Levantine (akhanafer/arabic-to-arabizi) | 389 | 0.296 | 0.427 | 0.076 |
| Moroccan Darija (elkababi2/Darija-Text-Ar-Arabizi) | 600 | 0.013 | 0.023 | 0.290 |

The honest read: the rule engine generalizes to Egyptian and Levantine
without training (about a third exact, most errors within one or two
letters), and fails on Moroccan Darija, whose French-influenced conventions
(9 for qaf, ch/gh digraphs, doubled consonants) are outside the current
rules. That failure is the point of the corpus: it is the roadmap.

## Roadmap

- [x] **v0.1** - rule engine, seed lexicon (~120 words), dialect baseline, benchmark, CLI, browser demo, paper outline
- [x] **v0.2** - corpus pipeline built (harvest, filter, LLM annotation, stratified split); three external held-out sets evaluated, results in Benchmark
- [ ] **v0.3** - dialect classification beyond lexicon tags; fine-tuned reranker over top-k candidates
- [ ] **v0.4** - LLM mode as a first-class API, npm/JS distribution
- [ ] **v1.0** - arXiv paper + release on PyPI

## Contributing

Corpus contributions are the highest-value contribution: add real Arabizi
sentences (with reference Arabic + dialect tag) to `data/benchmark.json` and
run `arabizikit eval`. See `paper/outline.md` for the research framing.

## License

MIT © 2026 Muhammed Rabeeh Mattath
