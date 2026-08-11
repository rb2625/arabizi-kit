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

# A dialect hint picks the regional conventions: 9 is qaf in Morocco,
# sad in Egypt, and the doubled consonants are written once (Darija
# gemination) or kept (Levant).
res = transliterate("bach n9ra lktab", dialect_hint="maghrebi")
print(res.text) # باش نقرا لكتاب
```

CLI:

```bash
arabizikit "shu 3am 3emel el yom" --top-k 5 --dialect
arabizikit "bach n9ra lktab" --hint maghrebi # assume a dialect convention
arabizikit "ya3ne shu" --llm # LLM-assisted (needs an LLM key; Groq free tier by default)
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
arabizikit corpus annotate # needs GROQ_API_KEY (free tier)
arabizikit corpus split
```

Or the whole thing in one command:

```bash
arabizikit corpus run --hf-dataset Mohamedd123321/Arabizi-dataset-v2 --rows 500
```

- filter: keeps Latin-script sentences that score as Arabizi (digit+letter markers, lexicon words), strips URLs, mentions, hashtags, and emoji, and splits posts into sentences
- annotate: the configured LLM renders Arabic script and a dialect tag per sentence; the rule engine top-1 is stored alongside for agreement, and a deterministic 10% sample is annotated twice to report inter-annotator agreement. No paid API needed: Groq's free tier is the default (openai/gpt-oss-120b, no credit card), with Gemini, OpenAI, local Ollama, and Anthropic as fallbacks. Pick one with --provider or ARABIZIKIT_PROVIDER and set the matching key (GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or ARABIZIKIT_API_KEY to override). Batch runs pace themselves under the free tier's per-minute limits, write each batch to disk, and resume where they left off
- split: stratified train/dev/test by dialect, written in benchmark format

External parallel sets with gold references score instantly, no API cost:

```bash
arabizikit corpus import-hf --dataset arbml/Arabizi_Transliteration --arabizi-field Arabize --arabic-field Arabic
arabizikit corpus import-hf --dataset akhanafer/arabic-to-arabizi --arabizi-field arabizi --arabic-field arabic
arabizikit corpus import-hf --dataset elkababi2/Darija-Text-Ar-Arabizi --arabizi-field darija_Latn --arabic-field darija_Arab_new
arabizikit eval --data corpus_data/external/Arabizi_Transliteration.json
```

The pipeline has run end to end on the free tier: 355 sentences from
Mohamedd123321/Arabizi-dataset-v2 were annotated with openai/gpt-oss-120b.
Inter-annotator agreement over the double-annotated 10% sample was 0.171,
the honest measure of how ambiguous Arabizi rendering is (the same model
rarely produces the identical rendering twice, and both are usually valid).
323 usable rows split into train/dev/test; scoring the held-out test set
measures the rules against human-level renderings:

| set | n | exact | hit@3 | CER |
| --- | --- | --- | --- | --- |
| pipeline test set (LLM references) | 49 | 0.000 | 0.000 | 0.299 |

The near-zero exact score is the point, not a bug: the rules emit literal
letter mappings (mettabbal -> متتاببال) while natural renderings differ in
spelling, morphology, and word choice. The v0.4 learned layer (next
section) closes part of that gap by learning from the annotated corpus.

Score a pipeline-split held-out test set with:

```bash
arabizikit eval --data corpus_data/splits/test.json
```

corpus_data/ is gitignored: raw network content, API annotations, and
imported third-party sets are working data, not part of the repository.
The import commands rebuild the external sets in one call.

## Learned layer (v0.4)

A small, dependency-free model trained from the corpus replaces the hand
tuning in three places: dialect detection, word readings, and candidate
ranking. Build it with:

```bash
arabizikit model train
arabizikit model status
python scripts/build_classifier_data.py            # real dialect text (Maghrebi, Egyptian)
python scripts/build_classifier_data.py --synthetic  # LLM-generated Levantine (needs GROQ_API_KEY)
```

Then opt in per call: `arabizikit "bach n9ra" --model` or
`arabizikit eval --data corpus_data/splits/test.json --model`.

Three components, all pure Python:

- dialect classifier: Naive Bayes over word tokens and Arabizi code markers
  (digits, digraphs), trained on a class-balanced sample so large sources do
  not swamp minority dialects. It supplies the dialect hint automatically,
  but only for dialects that change the engine's default readings (Maghrebi
  9 -> qaf and single doubled consonants, Gulf 8 -> ghayn); Egyptian and
  Levantine match the engine defaults, so no hint is emitted there.
- word reading table: arabizi word -> observed Arabic renderings with
  frequencies, learned from parallel pairs with article-aware alignment
  (el etnein -> الاثنين). Known words emit their observed readings instead
  of the letter rules.
- character language model: a smoothed trigram over the corpus references,
  reranking each word's candidates toward readings that look like natural
  Arabic (weight tuned on the dev split).

Training uses the calibration benchmark, the pipeline train/dev splits, and
public dialect text; the held-out test and external sets stay out of
training. Results, all with the same metrics (exact@1 / hit@3 / CER):

| set | rules, no hint | rules, oracle hint | learned layer |
| --- | --- | --- | --- |
| pipeline dev | 0.021 / 0.021 / 0.291 | 0.021 / 0.021 / 0.291 | 0.354 / 0.542 / 0.097 |
| pipeline test | 0.000 / 0.000 / 0.299 | 0.000 / 0.000 / 0.299 | 0.061 / 0.102 / 0.226 |
| Egyptian (external) | 0.376 / 0.526 / 0.236 | 0.376 / 0.526 / 0.236 | 0.348 / 0.502 / 0.248 |
| Levantine (external) | 0.296 / 0.429 / 0.076 | 0.296 / 0.429 / 0.076 | 0.270 / 0.360 / 0.096 |
| Moroccan Darija (external) | 0.035 / 0.057 / 0.235 | 0.088 / 0.115 / 0.180 | 0.053 / 0.080 / 0.207 |

The honest reading: the learned layer is opt-in and learns from the
corpus's human-style renderings, so it wins big where the corpus is
representative (dev exact up 17x, pipeline-test CER down a quarter, Darija
above the no-hint baseline because the classifier auto-selects the Maghrebi
convention) and gives back a couple of points on the external sets whose
gold style differs from the corpus. The rules remain the default for
arbitrary text; `--model` is the data-driven mode.

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
| Egyptian (arbml/Arabizi_Transliteration) | 500 | 0.376 | 0.526 | 0.236 |
| Levantine (akhanafer/arabic-to-arabizi) | 389 | 0.296 | 0.429 | 0.076 |
| Moroccan Darija (elkababi2/Darija-Text-Ar-Arabizi) | 600 | 0.088 | 0.115 | 0.180 |

The evaluation is dialect-conditioned: each row's dialect is passed to the
transliterator as a hint, because the conventions genuinely disagree (9 is
qaf in Morocco and sad in Egypt, doubled consonants are gemination in
Darija and kept as doubles in the Levant). The v0.4 learned layer
supplies the same hint from the text itself (see the Learned layer section).

The v0.3 rule work targets exactly the conventions that previously produced
nothing on Darija: 9 as qaf, ch as shin, doubled consonants written once
(bzzaf -> بزاف), emphatic capitals (T -> ط, S -> ص), the assimilated
definite article (jjaya -> الجاية), and a Maghrebi lexicon block. Darija
exact@1 rose from 0.013 to 0.088, hit@3 from 0.023 to 0.115, and CER fell
from 0.290 to 0.180, while Egyptian and Levantine held or improved.

What remains is honest and documented: short-vowel elision and the ay/ya
distinction are per-word, so a sentence that needs two conventions at once
(n9ra -> نقرا needs qaf plus a written final alif) still lands outside the
top-3. Picking that reading is what the v0.4 learned layer does where the corpus has evidence.

## Roadmap

- [x] **v0.1** - rule engine, seed lexicon, dialect baseline, benchmark, CLI, browser demo, paper outline
- [x] **v0.2** - corpus pipeline built and run end to end: harvest, filter, LLM annotation on the free tier with inter-annotator agreement, stratified split; three external held-out sets plus the pipeline test set evaluated, results in Benchmark
- [x] **v0.3** - Maghrebi rule coverage (9/ch/doubling/case conventions) and dialect hints; results in Benchmark
- [x] **v0.4** - learned layer: dialect classifier, word reading table, language-model reranking; results in Benchmark
- [ ] **v1.0** - arXiv paper + release on PyPI

## Contributing

Corpus contributions are the highest-value contribution: add real Arabizi
sentences (with reference Arabic + dialect tag) to `data/benchmark.json` and
run `arabizikit eval`. See `paper/outline.md` for the research framing.

## License

MIT © 2026 Muhammed Rabeeh Mattath
