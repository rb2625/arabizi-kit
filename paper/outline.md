# Paper outline - "ArabiziKit: an open, hybrid, benchmarked Arabizi -> Arabic-script transliteration system"

> Status: draft outline for an arXiv submission (target: late 2026). The
> benchmark numbers below are placeholders; the held-out corpus (milestone
> v0.2) provides the real evaluation. Verify all bibliographic details before
> submission.

## Working title options
- *ArabiziKit: an open, hybrid, benchmarked Arabizi -> Arabic-script transliteration system*
- *From 2 to ء: ranking the ambiguity of Romanized Arabic*
- *Every Arabizi letter has a secret second life: a modern toolkit for Romanized Arabic*

## Abstract (draft)
Arabizi - Arabic written in Latin script with digit-substituted letters
(`2` for hamza/qaf, `3` for ʿayn, `5` for khāʾ) - is the default writing
system for millions of Arabic speakers on WhatsApp, TikTok, and X, yet
existing transliteration tooling is either a decade-old academic demo or a
subroutine inside a monolithic toolkit. We present ArabiziKit, a modern,
dependency-light, open-source library that (i) combines a curated bilingual
lexicon with an interpretable rule engine that produces *ranked candidate
readings* rather than a single guess, (ii) attaches Arabic clitics
(`el` -> ال, `w` -> و), seats hamzas orthographically (ء -> أ/إ/ؤ/ئ), and tags
the input dialect (Gulf, Egyptian, Levantine, Maghrebi, MSA), and
(iii) ships a reproducible evaluation suite with CER/WER, exact-match, and
hit@k metrics. We release the seed corpus and benchmark, and outline an
LLM-assisted disambiguation mode that consumes the ranked candidates. On our
32-sentence calibration set the hybrid pipeline reaches 1.0 exact-match; the
open questions - short-vowel elision, the dialect-dependent 2/qaf split, and
taa-marbuta vs alef - are exactly the ambiguities the candidate ranking is
designed to surface.

## Sections

### 1. Introduction
- Arabizi is pervasive (Darwish 2014 definition), under-served, and growing
 with social media + LLM-era NLP.
- Why transliteration matters downstream: sentiment, dialect ID, machine
 translation, and LLM prompt hygiene (Arabic-script inputs beat Romanized
 ones for Arabic-capable models).
- Contributions:
 1. A dependency-free, MIT-licensed Python library + CLI + browser demo
 (no infrastructure, instant reproducibility).
 2. Ranked-candidate design that treats ambiguity as first-class output
 instead of hiding it.
 3. A reproducible benchmark + seed corpus with dialect labels, and an
 explicit corpus-collection pipeline for scale.

### 2. Background & related work
- Arabizi orthography: letter/digit conventions by dialect
 (2 = hamza in Egypt/Levant vs qaf in Gulf/Iraq; 8 = qaf in Egypt; g/j
 alternation; short-vowel elision).
- Prior systems: Habash et al. (2012) hybrid Arabizi->Arabic transliteration;
 COLABA (Al-Badrashiny et al. 2014) corpus; Jordanian Arabizi-Transliteration
 Corpus; NYUAD Arabizi transliteration demo; CAMeL Tools (Obeid et al. 2020)
 toolkit; MADAR dialect-ID (Bouamor et al. 2018).
- Gap: no maintained, open, modern (LLM-era) implementation with candidate
 output and a living benchmark. *TODO: verify exact titles/venues/citations.*

### 3. Method
- **Lexicon layer**: curated seed lexicon (~120 words) with dialect tags;
 exact matches win and carry dialect evidence.
- **Rule engine**: longest-match phoneme scan (digraphs > digit codes >
 letters), context rules:
 - word-final `2` after a vowel -> qaf (`tare2` -> طريق),
 - word-initial `2` before a consonant -> {qaf, alef} (`2alb` -> قلب vs
 `2ktob` -> اكتب),
 - word-final `a` -> {taa-marbuta, alef} (`7elwa` -> حلوة vs `hada` -> هذا),
 - `ay`/`ey` -> {alif+ya, ya-diphthong} (`3ayza` -> عايزة vs `3alayk` -> عليك),
 - short vowels e/o/u elided by default (`3emel` -> عمل).
- **Candidate generation & ranking**: cartesian product of per-position
 options (bounded), orthographic-plausibility penalties (bad bigrams),
 stable tie-breaking. Output is the ranked top-k.
- **Post-processing**: hamza seating with carrier merging (و+ء -> ؤ,
 ي+ء -> ئ, ا+ء(+ا) -> أ); clitic attachment (el/al/il/l -> ال, w -> و,
 3al -> على ال).
- **Dialect baseline**: lexicon-tag voting + hand-written pattern rules.
 Planned replacement: fine-tuned dialect classifier on the collected corpus.
- **LLM-assisted mode**: top-k candidates + an LLM (Anthropic API, stdlib
 HTTP) picks the intended reading and dialect. Ablation vs rules-only is a
 headline experiment.

### 4. Data & benchmark
- **Seed calibration set**: 33 hand-curated sentences across 5 dialect
 groups; shares distribution with the lexicon -> upper-bound numbers.
- **Corpus collection pipeline (v0.2)**: harvest Arabizi from Reddit
 (r/Egypt, r/arabs, r/saudiarabia), TikTok/X hashtags, and YouTube comments;
 filter to Latin-script Arabic content; LLM-assisted annotation
 (Arabizi -> Arabic + dialect tag) with inter-annotator agreement sampling.
- **Benchmark protocol**: per-sentence CER (normalized orthography), WER,
 exact@1, hit@k; aggregated overall and per dialect; `arabizikit eval`
 reproduces every number. Versioned data file = versioned results.

### 5. Experiments (planned)
- Hybrid (lexicon + rules) on held-out split: exact@1, hit@3/5, CER, WER.
- Ablations: rules-only vs lexicon-only vs hybrid; with/without attachment;
 with/without hamza seating (shows the orthography value).
- LLM-assisted vs rules-only on the *miss* set (where top-k contains the
 reference but top-1 does not): measures the headroom.
- Dialect-specific breakdown (Gulf vs Egyptian vs Maghrebi - expected
 hardest: most orthographic drift).
- Error taxonomy: short-vowel elision, 2/qaf split, taa-marbuta/alef,
 proper nouns, code-switching with English.

### 6. Limitations & ethics
- Seed set is a calibration set; real generalization numbers require the
 held-out corpus (v0.2).
- Rule engine is not learned; dialect coverage is asymmetric (Maghrebi is
 thin). Arabic script is written without diacritics here by design.
- Ethical note: transliteration is a rendering task; we do not claim
 sentiment or intent. Corpus collection will respect platform ToS and
 anonymize personal data.

### 7. Conclusion & future work
- v0.2 corpus + fine-tuned reranker; v0.3 JS/npm distribution; v0.4 dialect
 classifier; PyPI release at v1.0.

## Roadmap ↔ paper mapping
| Repo milestone | Paper artifact |
|---|---|
| v0.1 (this commit) | System description, seed benchmark, error taxonomy |
| v0.2 corpus | Section 4 + real Experiments (Section 5) |
| v0.3 reranker / dialect model | Section 3.5/3.6 + ablations |
| v1.0 release | arXiv submission + PyPI + demo link |
