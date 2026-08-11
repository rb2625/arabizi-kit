"""LLM-assisted annotation of candidate Arabizi sentences.

Each batch of sentences is sent to the Anthropic API with instructions to
return the Arabic-script rendering, a dialect tag, and a short note. Results
are written as JSONL and include the rule engine's top-1 prediction for
agreement reporting. A deterministic sample is annotated twice so the run
reports inter-annotator agreement (exact match on normalized Arabic).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

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


def _call_api(prompt_items: list[dict], api_key: str, model: str, timeout: int) -> list[dict]:
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
    parsed = _parse_array(content)
    if parsed is None:
        raise ValueError("could not parse annotation reply as JSON array")
    return parsed


def annotate_batch(
    prompt_items: list[dict],
    api_key: str | None = None,
    model: str = config.ANNOTATION_MODEL,
    retries: int = config.ANNOTATION_RETRIES,
    timeout: int = config.ANNOTATION_TIMEOUT,
) -> list[dict]:
    """Annotate one batch with retries and backoff."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("annotation requires ANTHROPIC_API_KEY (or pass api_key=...)")
    last_error: Exception | None = None
    for attempt in range(max(retries, 1)):
        try:
            return _call_api(prompt_items, key, model, timeout)
        except (OSError, ValueError, KeyError) as exc:
            last_error = exc
            if attempt < retries - 1:
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


def annotate(
    candidates_path: str | Path | None = None,
    out_path: str | Path | None = None,
    batch_size: int = config.ANNOTATION_BATCH,
    iaa_sample: float = config.IAA_SAMPLE,
    api_key: str | None = None,
) -> dict:
    """Annotate the candidate sentences file end to end."""
    from . import config as cfg

    candidates_path = Path(candidates_path or cfg.CORPUS_DIR / "candidates.jsonl")
    out_path = Path(out_path or cfg.ANNOTATED_DIR / "annotated.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {"n": 0, "error": "no candidates"}

    import random

    from arabizikit.transliterate import Transliterator

    rng = random.Random(cfg.RANDOM_SEED)
    order = list(range(len(rows)))
    rng.shuffle(order)
    iaa_count = max(1, int(len(rows) * iaa_sample))
    iaa_indexes = set(order[:iaa_count])

    tr = Transliterator()
    results: list[dict] = []
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("annotation requires ANTHROPIC_API_KEY (or pass api_key=...)")

    requests = 0
    prompt_len = 80  # rough chars per sentence in the prompt
    for batch in _chunk(rows, batch_size):
        items = [{"id": r["id"], "arabizi": r["arabizi"]} for r in batch]
        parsed = annotate_batch(items, api_key=key)
        requests += 1
        by_id = {p["id"]: p for p in parsed}
        for r in batch:
            ann = by_id.get(r["id"], {})
            arabic = ann.get("arabic", "")
            rule = tr.transliterate(r["arabizi"]).text
            results.append(
                {
                    "id": r["id"],
                    "arabizi": r["arabizi"],
                    "arabic": arabic,
                    "dialect": ann.get("dialect", "other"),
                    "note": ann.get("note", ""),
                    "rule_top1": rule,
                    "rule_match": bool(arabic) and normalize(arabic) == normalize(rule),
                }
            )

    # Inter-annotator agreement: re-annotate the sampled ids and compare.
    iaa_results: list[tuple[str, str]] = []
    for batch in _chunk([r for r in results if r["id"] in iaa_indexes], batch_size):
        items = [{"id": r["id"], "arabizi": r["arabizi"]} for r in batch]
        parsed = annotate_batch(items, api_key=key)
        requests += 1
        by_id = {p["id"]: p for p in parsed}
        for r in batch:
            second = by_id.get(r["id"], {}).get("arabic", "")
            iaa_results.append((normalize(r["arabic"]), normalize(second)))

    agreement = 1.0 if not iaa_results else sum(a == b for a, b in iaa_results) / len(iaa_results)
    rule_agree = sum(r["rule_match"] for r in results) / len(results) if results else 0.0

    with out_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {
        "n": len(results),
        "rule_agreement": round(rule_agree, 3),
        "iaa": round(agreement, 3),
        "iaa_samples": len(iaa_results),
        "calls": requests,
        "cost_estimate": _estimate_cost(requests, batch_size, prompt_len),
        "out": str(out_path),
    }
