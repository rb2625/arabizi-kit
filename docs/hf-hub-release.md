# Publish the model and corpus to Hugging Face Hub

The paper's future-work section promises "publication of the trained model
and corpus artifacts on the model and data hubs." Doing this turns the
project from "a paper with a GitHub repo" into a complete, citable research
artifact — and it is the single highest-leverage "extreme version" upgrade
left. Estimated time: 20–30 minutes, one-time.

## What gets published

| HF repo | Contents | Source |
|---|---|---|
| `rb2625/arabizi-kit-corpus` (dataset) | 355 annotated sentences, train/dev/test splits, 3 external gold sets | `corpus_data/annotated/`, `corpus_data/splits/`, `corpus_data/external/` |
| `rb2625/arabizi-kit-model` (model) | trained reading table + trigram LM + classifier data | `corpus_data/model/model.json`, `corpus_data/classifier/` |

Both are small (~6 MB total) and MIT-licensed, so this is quick and free.

## Step 0 — install the hub CLI and log in

```bash
uv add --dev huggingface_hub   # or: pip install huggingface_hub
huggingface-cli login          # paste a write token from https://huggingface.co/settings/tokens
```

## Step 1 — dataset repo

```bash
cd C:\Users\rabee\Documents\arabizi-kit
mkdir -p hf_staging/corpus hf_staging/model

# annotated corpus + splits, in the benchmark format already on disk
cp corpus_data/annotated/annotated.jsonl  hf_staging/corpus/
cp corpus_data/splits/train.json          hf_staging/corpus/
cp corpus_data/splits/dev.json            hf_staging/corpus/
cp corpus_data/splits/test.json           hf_staging/corpus/
cp corpus_data/external/*.json            hf_staging/corpus/

huggingface-cli repo create arabizi-kit-corpus --type dataset
huggingface-cli upload rb2625/arabizi-kit-corpus hf_staging/corpus --repo-type dataset
```

## Step 2 — model repo

```bash
cp corpus_data/model/model.json hf_staging/model/
cp corpus_data/classifier/*.json hf_staging/model/

huggingface-cli repo create arabizi-kit-model --type model
huggingface-cli upload rb2625/arabizi-kit-model hf_staging/model --repo-type model
```

## Step 3 — write the cards

Put a `README.md` in each staging folder before uploading (the upload command
above copies it too). Templates:

### Dataset card (`hf_staging/corpus/README.md`)

```markdown
---
license: mit
language:
- ar
- arz
- ary
- apc
- afb
task_categories:
- text2text-generation
tags:
- arabizi
- transliteration
- arabic-nlp
pretty_name: ArabiziKit Corpus
---

# ArabiziKit Corpus

355 LLM-annotated sentences of real social-media Arabizi (Latin-script
Arabic) with Arabic-script references and dialect tags, stratified into
train / dev / test, plus three external gold-reference sets (Egyptian 500,
Levantine 389, Moroccan Darija 600). Inter-annotator agreement over a
double-annotated 10% sample: 0.171 exact on normalized Arabic.

Produced by the ArabiziKit corpus pipeline (https://github.com/rb2625/arabizi-kit).
See the paper (arXiv cs.CL) for the full protocol.
```

### Model card (`hf_staging/model/README.md`)

```markdown
---
license: mit
base_model: none
tags:
- arabizi
- transliteration
- arabic-nlp
pretty_name: ArabiziKit trained layer
---

# ArabiziKit model

Trained layer of the ArabiziKit hybrid transliteration system: a word
reading table (1,155 entries), a Laplace-smoothed character trigram
language model, and Naive Bayes dialect-classifier data. Trained only on
the calibration set plus pipeline train/dev splits (held-out and external
sets excluded).

Load it with `arabizikit model train` (rebuilds from the corpus) or use the
`--model` flag of `arabizikit eval` to reproduce the paper's learned-layer
numbers.
```

Then re-run the `huggingface-cli upload` commands so the READMEs land.

## Step 4 — update the repo and paper links

1. README: add a "Datasets and models" section with the two HF links.
2. Optionally add `corpus_data` metadata — keep the data itself gitignored;
   the HF repos are the canonical copy.

## Why this matters (the pitch)

- The paper's future-work promise becomes true → a v2 of the paper can cite
  the HF artifacts.
- Recruiters and reviewers can reproduce your exact numbers without running
  the pipeline.
- Hugging Face is where NLP people actually look — it is the strongest
  "this is real research" signal after the arXiv ID itself.
- It is a 20-minute task. Highest ROI of everything left.
