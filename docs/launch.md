# ArabiziKit — launch material

Everything here is grounded in the released code and the arXiv paper
(submission `submit/7944082`, cs.CL). Swap in the final arXiv ID
(`arXiv:2508.xxxxx`) after the announcement lands.

---

## LinkedIn post (the agreed last step)

Post this on the day the arXiv announcement lands. Draft below — two versions
of the opener so you can pick the tone.

**Version A — technical hook:**

> I published my first research paper to arXiv this week — about the way
> hundreds of millions of Arabic speakers actually type.
>
> Not Arabic script. Arabizi: Latin letters and digits — "ezayak ya 7abiby"
> instead of إزيك يا حبيبي. 2 for hamza or qaf, 3 for ayn, 7 for ha, 5 for kha.
>
> The tools to convert Arabizi back into proper Arabic script were either
> academic demos from a decade ago or subroutines buried inside monolithic
> toolkits. So I built my own, end to end:
>
> - a zero-dependency Python library + CLI + browser demo + npm package
> - a rule engine that returns **ranked candidate readings**, not a single
>   guess — because "2" is hamza in Egypt and qaf in the Gulf
> - a learned layer: Naive Bayes dialect classifier (94% accuracy on Moroccan
>   Darija), a 1,155-word reading table, and a character trigram reranker
> - a fully reproducible benchmark: 0.376 exact@1 on Egyptian, 0.296 on
>   Levantine, 0.088 on Darija with the Maghrebi conventions — 113 tests,
>   every number regenerated with one command
>
> The paper is on arXiv (cs.CL), the code is MIT-licensed on GitHub, and the
> demo runs entirely in the browser — no backend, no API keys.
>
> Built as a student at the American University of Ras Al Khaimah, with zero
> ML-framework dependencies and a lot of coffee.
>
> If you've ever typed "7abiby" and wished your phone understood you — this
> one's for you. 💚
>
> 📄 arXiv: <insert link after announcement>
> 💻 Code: https://github.com/rb2625/arabizi-kit
> 🌐 Demo: https://arabizi-kit.vercel.app
> 📦 PyPI: https://pypi.org/project/arabizikit
> 📦 npm: https://www.npmjs.com/package/arabizikit

**Version B — story hook (same body, different opener):**

> Last year I kept running into a small frustration: friends typing "ana 3ayz
> 2akol" and my phone getting it wrong. This year I turned that into a
> research paper on arXiv.
> ...

**Posting tips:**
- Post at ~9–11 am your local time on a Tuesday–Thursday; engagement peaks
  midday.
- Pin the demo link in a first comment too — LinkedIn shows comments to
  non-connections more than the body sometimes.
- Add 2–3 images: a demo screenshot, a benchmark table screenshot, and a
  before/after Arabizi→Arabic example. Text-only posts underperform.
- Tag the university page (American University of Ras Al Khaimah) and your
  professor — a small audience boost and it signals mentorship.
- Reply to every comment for the first 48 hours; that is what the algorithm
  actually rewards.

---

## CV / resume bullets

### One-liner (for your summary/skills section)

> First-author research paper on arXiv (cs.CL) for ArabiziKit, an open-source,
> benchmark-driven Arabizi→Arabic-script transliteration system shipped as a
> Python library, CLI, npm package, and browser demo.

### Three bullets (projects section, compact)

> **ArabiziKit — Arabizi → Arabic Script Transliteration (arXiv, cs.CL)**
> - Designed and shipped a zero-dependency Python library + CLI + npm package
>   + browser demo converting Romanized Arabic into Arabic script, with ranked
>   candidate output, dialect tagging, and an optional LLM disambiguation mode.
> - Built a hybrid pipeline: 204-entry dialect-tagged lexicon, context-aware
>   rule engine, Naive Bayes dialect classifier (94% accuracy on Darija), and a
>   trigram language-model reranker.
> - Published a first-author paper on arXiv with a reproducible benchmark —
>   113 tests, 1,489 gold-reference sentences (Egyptian/Levantine/Darija),
>   exact@1 up to 0.376 — and a corpus pipeline with measured inter-annotator
>   agreement (0.171).

### Five bullets (full detail, for a "research" or "selected projects" page)

> **ArabiziKit — Open-Source Arabizi Transliteration System** (arXiv cs.CL;
> MIT; PyPI + npm; live demo) — github.com/rb2625/arabizi-kit
> - Built a transliteration system for Arabizi (Arabic in Latin letters +
>   digits) using a dialect-tagged lexicon, a context-aware rule engine
>   producing ranked candidate readings, and a learned layer (Naive Bayes
>   dialect classifier, word reading table, trigram LM reranker) — zero
>   runtime dependencies.
> - Achieved 0.376 exact@1 / 0.236 CER on Egyptian (500), 0.296 exact@1 on
>   Levantine (389), and 0.088 exact@1 on Moroccan Darija (600) with Maghrebi
>   conventions; learned layer raised held-out test exact@1 from 0.000 to
>   0.061 and cut CER from 0.299 to 0.226.
> - Built a free-tier corpus pipeline: harvested 355 real social-media
>   sentences, LLM-annotated them (inter-annotator agreement 0.171 over a
>   double-annotated 10% sample), and produced stratified train/dev/test
>   splits — every benchmark number reproducible with one command.
> - Shipped the full stack: PyPI package, npm package with TypeScript
>   declarations, browser demo on Vercel, GitHub Actions release workflow,
>   113 passing tests.
> - Published the work as a first-author paper on arXiv (cs.CL) and presented
>   results with a fully reproducible evaluation suite (CER, WER, exact@1,
>   hit@k).

---

## GitHub repo polish (5 minutes)

- **Repo description:** `Arabizi (Romanized Arabic) → Arabic script. Rule
  engine + learned layer + optional LLM disambiguation. Zero dependencies,
  113 tests, fully reproducible benchmark.`
- **Topics (add on the repo page):** `arabizi`, `arabic-nlp`,
  `transliteration`, `arabic-language`, `nlp`, `dialect`,
  `natural-language-processing`, `benchmark`, `arabic-dialects`
- **Website field (already set):** https://arabizi-kit.vercel.app
