"""LLM-assisted annotation of candidate Arabizi sentences.

Each batch of sentences is sent to the configured LLM provider (Groq's free
tier by default) with instructions to return the Arabic-script rendering, a
dialect tag, and a short note. Results are written as JSONL and include the
rule engine's top-1 prediction for agreement reporting. A deterministic
sample is annotated twice so the run reports inter-annotator agreement
(exact match on normalized Arabic).
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from arabizikit import llm
from arabizikit.normalize import normalize

from . import config

SYSTEM_PROMPT = (
    "You are an expert in Arabizi (Romanized Arabic) and Arabic dialectology. "
    "For each sentence, produce the natural Arabic-script rendering: informal "
    "orthography, no diacritics, definite articles attached (el -> ال), hamzas "
    "seated correctly. Reply with ONLY a JSON array, one object per sentence, "
    'with keys "id", "arabic", "dialect", "note". "dialect" must be one of '
    "gulf, egyptian, levantine, maghrebi, msa, other. Keep each \"id\" value "
    "exactly as given."
)


def _chunk(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _parse_array(content: str):
    """Parse a JSON array out of an LLM reply. Returns None on failure."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.removeprefix("json")
    start, end = content.find("["), content.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [d for d in data if isinstance(d, dict) and "id" in d and "arabic" in d]


def _call_api(
    prompt_items: list[dict],
    model: str | None,
    provider: str,
    api_key: str | None,
    timeout: int,
) -> list[dict]:
    content = llm.chat_completion(
        provider=provider,
        model=model,
        api_key=api_key,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)}],
        max_tokens=2048,
        timeout=timeout,
    )
    parsed = _parse_array(content)
    if parsed is None:
        raise ValueError("could not parse annotation reply as JSON array")
    return parsed


def annotate_batch(
    prompt_items: list[dict],
    api_key: str | None = None,
    model: str | None = None,
    provider: str = config.ANNOTATION_PROVIDER,
    retries: int = config.ANNOTATION_RETRIES,
    timeout: int = config.ANNOTATION_TIMEOUT,
) -> list[dict]:
    """Annotate one batch with retries and backoff."""
    spec = llm.PROVIDERS.get(provider)
    if spec is None:
        raise RuntimeError(f"unknown LLM provider {provider!r}; choose from {', '.join(llm.PROVIDERS)}")
    key = llm.resolve_key(provider, api_key)
    if spec.get("key_env") and not key:
        env = spec["key_env"]
        raise RuntimeError(f"annotation needs a key for provider {provider!r}: set {env} (or ARABIZIKIT_API_KEY)")
    last_error: Exception | None = None
    for attempt in range(max(retries, 1)):
        try:
            return _call_api(prompt_items, model, provider, key, timeout)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries - 1:
                if "429" in str(exc):
                    _wait_after_rate_limit(exc)
                else:
                    time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"annotation failed after {retries} attempts: {last_error}")


def _estimate_cost(requests_made: int, batch_size: int, prompt_len: int) -> str:
    input_chars = requests_made * batch_size * prompt_len
    input_tokens = input_chars / 4
    output_tokens = requests_made * batch_size * 40
    cost = (
        input_tokens / 1_000_000 * config.PRICE_INPUT_PER_MT
        + output_tokens / 1_000_000 * config.PRICE_OUTPUT_PER_MT
    )
    return f"${cost:.2f} (estimate, {input_tokens:.0f} in / {output_tokens:.0f} out tokens)"


# Seconds to pause between API requests: keeps batch runs under the free
# tier rate limits instead of burning retries on 429s.
PACING_SECONDS = 4

# Ceiling for how long we sleep after a rate-limit error, even if the
# provider suggests waiting longer (the caller can just resume the run).
MAX_RATE_LIMIT_WAIT = 120


def _wait_after_rate_limit(exc: RuntimeError) -> None:
    """Sleep through a 429 using the provider's own hint when available."""
    text = str(exc)
    wait = 45.0  # default: roughly one TPM window
    # Providers say things like "try again in 5.7s" or "in 29m0.96s".
    for match in re.finditer(r"in (\d+(?:\.\d+)?)([sm])", text):
        value = float(match.group(1))
        unit = match.group(2)
        seconds = value * 60 if unit == "m" else value
        if 0 < seconds <= MAX_RATE_LIMIT_WAIT:
            wait = seconds + 2
            break
    time.sleep(wait)


def annotate(
    candidates_path: str | Path | None = None,
    out_path: str | Path | None = None,
    batch_size: int = config.ANNOTATION_BATCH,
    iaa_sample: float = config.IAA_SAMPLE,
    api_key: str | None = None,
    provider: str = config.ANNOTATION_PROVIDER,
    model: str | None = None,
) -> dict:
    """Annotate the candidate sentences file end to end.

    Writes each batch to disk as it completes, so an interrupted run can be
    resumed by calling annotate again: rows already in the output file are
    skipped, and the inter-annotator sample is re-annotated.
    """
    from . import config as cfg

    candidates_path = Path(candidates_path or cfg.CORPUS_DIR / "candidates.jsonl")
    out_path = Path(out_path or cfg.ANNOTATED_DIR / "annotated.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {"n": 0, "error": "no candidates"}

    from arabizikit.transliterate import Transliterator

    rng = random.Random(cfg.RANDOM_SEED)
    order = list(range(len(rows)))
    rng.shuffle(order)
    iaa_count = max(1, int(len(rows) * iaa_sample))
    iaa_ids = {rows[i]["id"] for i in order[:iaa_count]}

    # Resume: rows already written keep their annotations. Duplicates can
    # appear if a previous run was interrupted mid-append, so rebuild the
    # file from the deduped view when that happens.
    done: dict[str, dict] = {}
    raw_lines: list[str] = []
    if out_path.exists():
        raw_lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in raw_lines:
            row = json.loads(line)
            done[row["id"]] = row
    if len(raw_lines) != len(done):
        with out_path.open("w", encoding="utf-8") as fh:
            for row in done.values():
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    pending = [r for r in rows if r["id"] not in done]
    results = list(done.values())

    tr = Transliterator()
    key = api_key  # resolved and checked per batch by annotate_batch

    requests = 0
    prompt_len = 80  # rough chars per sentence in the prompt
    with out_path.open("a", encoding="utf-8") as fh:
        for batch in _chunk(pending, batch_size):
            items = [{"id": r["id"], "arabizi": r["arabizi"]} for r in batch]
            parsed = annotate_batch(items, api_key=key, model=model, provider=provider)
            requests += 1
            by_id = {p["id"]: p for p in parsed}
            for r in batch:
                ann = by_id.get(r["id"], {})
                arabic = ann.get("arabic", "")
                rule = tr.transliterate(r["arabizi"]).text
                row = {
                    "id": r["id"],
                    "arabizi": r["arabizi"],
                    "arabic": arabic,
                    "dialect": ann.get("dialect", "other"),
                    "note": ann.get("note", ""),
                    "rule_top1": rule,
                    "rule_match": bool(arabic) and normalize(arabic) == normalize(rule),
                }
                results.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            time.sleep(PACING_SECONDS)

    # Inter-annotator agreement: re-annotate the sampled ids and compare.
    iaa_results: list[tuple[str, str]] = []
    for batch in _chunk([r for r in results if r["id"] in iaa_ids], batch_size):
        items = [{"id": r["id"], "arabizi": r["arabizi"]} for r in batch]
        parsed = annotate_batch(items, api_key=key, model=model, provider=provider)
        requests += 1
        by_id = {p["id"]: p for p in parsed}
        for r in batch:
            second = by_id.get(r["id"], {}).get("arabic", "")
            iaa_results.append((normalize(r["arabic"]), normalize(second)))
        time.sleep(PACING_SECONDS)

    agreement = 1.0 if not iaa_results else sum(a == b for a, b in iaa_results) / len(iaa_results)
    rule_agree = sum(r["rule_match"] for r in results) / len(results) if results else 0.0

    return {
        "n": len(results),
        "provider": provider,
        "model": model or llm.default_model(provider),
        "rule_agreement": round(rule_agree, 3),
        "iaa": round(agreement, 3),
        "iaa_samples": len(iaa_results),
        "calls": requests,
        "cost_estimate": _estimate_cost(requests, batch_size, prompt_len),
        "out": str(out_path),
    }
