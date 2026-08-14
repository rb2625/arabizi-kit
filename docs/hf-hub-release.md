# Publish the model and corpus to Hugging Face Hub

The paper's future-work section promises "publication of the trained model
and corpus artifacts on the model and data hubs." Doing this turns the
project from "a paper with a GitHub repo" into a complete, citable research
artifact — and it is the single highest-leverage "extreme version" upgrade
left. Estimated time: 20–30 minutes, one-time.

## What gets published

| HF repo | Contents | Source |
|---|---|---|
| `<user>/arabizi-kit-corpus` (dataset) | 355 annotated sentences + train/dev/test splits + cards | `corpus_data/annotated/annotated.jsonl`, `corpus_data/splits/` |
| `<user>/arabizi-kit-model` (model) | trained reading table + trigram LM + classifier data + card | `corpus_data/model/model.json`, `corpus_data/classifier/` |

The three external gold sets are **not** redistributed (they are public HF
datasets with their own terms); the dataset card links them and they are
rebuilt with `arabizikit corpus import-hf`. Both repos are small (~5 MB
total) and MIT-licensed.

## Step 0 — tool and login (the only step only you can do)

The tool is already installed in this repo:

```bash
cd C:\Users\rabee\Documents\arabizi-kit
uv run hf auth login
```

`hf auth login` opens a browser flow or accepts a token paste from
https://huggingface.co/settings/tokens (create a **Write** token if you
don't have one; account creation at https://huggingface.co/join is free).

Verify with `uv run hf auth whoami` — it prints your username, which is the
`<user>` in the repo IDs below (the examples assume `rb2625`; use whatever
whoami prints).

## Step 1 — dataset repo

Files are already staged in `hf_staging/`:

```bash
cd C:\Users\rabee\Documents\arabizi-kit
uv run hf repos create <user>/arabizi-kit-corpus --type dataset
uv run hf upload <user>/arabizi-kit-corpus hf_staging/corpus --repo-type dataset
```

## Step 2 — model repo

```bash
uv run hf repos create <user>/arabizi-kit-model --type model
uv run hf upload <user>/arabizi-kit-model hf_staging/model --repo-type model
```

## Step 3 — verify on the Hub

- Open https://huggingface.co/<user>/arabizi-kit-corpus — the card renders
  from `hf_staging/corpus/README.md`, and the four data files are listed.
- Open https://huggingface.co/<user>/arabizi-kit-model — card plus the four
  JSON artifacts.
- Then update the README (add a "Datasets and models" section with both HF
  links) and `docs/launch.md`.

## Why this matters (the pitch)

- The paper's future-work promise becomes true → a v2 of the paper can cite
  the HF artifacts.
- Recruiters and reviewers can reproduce your exact numbers without running
  the pipeline.
- Hugging Face is where NLP people actually look — it is the strongest
  "this is real research" signal after the arXiv ID itself.
- It is a 20-minute task. Highest ROI of everything left.
