# ArabiziKit - Project Status

Snapshot taken August 11, 2026; updated August 15, 2026. All numbers are
verified against the released code and are reproducible with
`arabizikit eval`.

## What it is

ArabiziKit turns Arabizi (Arabic written in Latin letters plus digits, like
`ezayak ya 7abiby`) into proper Arabic script (`إزيك يا حبيبي`). One library,
four faces:

- Python library plus CLI (`pip install arabizikit`, v1.0.0 on PyPI)
- Browser demo at https://arabizi-kit.vercel.app
- npm package (`arabizikit` v1.0.0 on the npm registry, with TypeScript
  declarations)
- Paper submitted to arXiv (submission `submit/7944082`, cs.CL)

MIT licensed, open source at github.com/rb2625/arabizi-kit, zero runtime
dependencies, 113 passing tests.

## Device setup

| Thing | Version / location |
|---|---|
| Project | `C:\Users\rabee\Documents\arabizi-kit` |
| Python | 3.14.4 |
| uv | 0.11.14 (package manager, build, publish) |
| Node / npm | v24.15.0 / 11.12.1 |
| Git | 2.54.0 |
| Code size | about 4,300 lines across the Python package, corpus pipeline, and JS engine |

Repo layout: `src/arabizikit/` (the library), `corpus_data/` (collected data,
gitignored), `data/` (benchmark), `web/` (demo and npm package), `scripts/`,
`tests/` (13 test files), `paper/`, `docs/` (launch material and the HF hub
guide), plus `pyproject.toml`, `README.md`, `RELEASE.md`,
`PROJECT_STATUS.md`.

## Milestones (11 commits, 7 milestones)

| # | Milestone | Commit | Result |
|---|---|---|---|
| 1 | v0.1 rule engine, lexicon, benchmark, CLI, demo | `9d1ee0b` | Phoneme rules, 180+ word lexicon, ranked candidates, 33-sentence calibration set |
| 2 | v0.2 corpus pipeline | `d0e38db`, `2aae1a0` | Harvest from public Hugging Face datasets (Reddit was blocked), filter, split; three external gold sets imported (Egyptian 500, Levantine 389, Darija 600) |
| 3 | Darija gap closed | `bb40e26` | Maghrebi conventions: 9 to qaf, ch to shin, doubled consonants, dialect hints. Darija exact 0.013 to 0.088, CER 0.290 to 0.180 |
| 4 | Annotate plus split on the free tier | `2c8a81d` | Provider-agnostic LLM client (Groq free by default). 355 sentences annotated, inter-annotator agreement 0.171, held-out test set of 49 |
| 5 | v0.3 learned layer | `a890c3e` | Dialect classifier (94% on Darija), word reading table (1,155 words), trigram LM reranker. Dev split exact 17x, pipeline test 0.000 to 0.061 |
| 6 | v0.4 LLM API plus npm | `a28a5ae` | `llm_transliterate()` first class, `arabizikit` npm package, demo redeployed |
| 7 | v1.0 paper plus release prep | `f6d4047` | Near-final paper draft, versions at 1.0.0, RELEASE.md runbook, GitHub Actions publish workflow |

Cleanup commits in between: em-dash sweep (`5b8ea7b`) and Vercel config
ignores (`a9ac301`, `315b317`). arXiv finalization: bundled Amiri fonts,
corrected stale numbers, `%&xelatex` directive, `xurl` fix (`ec14d3e`).

## Live status

| Property | Status |
|---|---|
| PyPI (pypi.org/project/arabizikit) | Published, v1.0.0, HTTP 200 |
| Demo (arabizi-kit.vercel.app) | Live, HTTP 200 |
| npm (registry.npmjs.org/arabizikit) | Published, v1.0.0, HTTP 200 |
| arXiv | Submitted (`submit/7944082`, cs.CL), in moderation |
| GitHub | All commits pushed, tree clean |

## Data owned (corpus_data, ~5.8 MB, gitignored)

- 355 annotated sentences of real social-media Arabizi to Arabic
- Stratified split: train 226 / dev 48 / test 49
- 35 double-annotated samples producing the IAA 0.171 number
- Three external gold sets: Egyptian, Levantine, Moroccan Darija (1,489 sentences)
- Trained model (~4 MB): 1,155 learned words, 70-char LM vocabulary
- Classifier data: about 280k Maghrebi and 263k Egyptian sentences, classifier only

## Benchmark numbers

| Set | rules exact | learned layer exact | CER |
|---|---|---|---|
| Calibration (33) | 1.000 | - | 0.000 |
| Egyptian (500) | 0.376 | 0.348 | 0.236 |
| Levantine (389) | 0.296 | 0.270 | 0.076 |
| Darija (600) | 0.088 (oracle) | 0.053 | 0.180 |
| Pipeline test (49) | 0.000 | 0.061 | 0.226 |

## Current state (Aug 15, 2026)

- arXiv: **submitted**, compiled clean with XeLaTeX + bundled Amiri fonts;
  in moderation, announcement pending (check https://arxiv.org/user/).
- PyPI and npm both published at v1.0.0; demo live; GitHub clean and pushed;
  113 tests passing.
- Launch material drafted in `docs/launch.md` (LinkedIn post, CV bullets,
  repo polish) - the agreed last step, ready to post on announcement day.

## What is left

1. Announcement: confirm the arXiv ID lands (1-2 business days), then add the
   ID to the README and `docs/launch.md`, and post the LinkedIn announcement.
2. (Optional, high ROI) Hugging Face hub release of the model + corpus -
   step-by-step guide in `docs/hf-hub-release.md`; makes the paper's
   future-work promise true and is the strongest research signal after arXiv.
3. (Optional) v2 of the paper with the author's email added to the author
   block - only if desired, after the announcement.

## Verify any time

```powershell
cd Documents/arabizi-kit
uv run pytest          # 113 tests
arabizikit eval        # reproduces every benchmark number
arabizikit eval --model
```
