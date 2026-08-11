"""Harvest raw posts from public sources.

Reddit is the classic source, but Reddit now gates app creation behind an
API approval queue (Responsible Builder Policy), so the pipeline also ships
a Hugging Face datasets adapter that needs no account at all. Both write the
same JSONL shape into raw/ so the rest of the pipeline is source-agnostic.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DEFAULT_PAGES,
    DEFAULT_SUBREDDITS,
    HF_BATCH,
    HF_TEXT_FIELDS,
    RAW_DIR,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
PUBLIC_BASE = "https://www.reddit.com"
HF_SPLITS_URL = "https://datasets-server.huggingface.co/splits"
HF_FIRST_ROWS_URL = "https://datasets-server.huggingface.co/first-rows"
HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"

_403_HINT = (
    "Reddit blocked the request (HTTP 403). Create a free script app at "
    "reddit.com/prefs/apps, then export REDDIT_CLIENT_ID and "
    "REDDIT_CLIENT_SECRET to use the OAuth API."
)


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------
def get_access_token(client_id: str, client_secret: str) -> str:
    """Exchange client credentials for an OAuth token."""
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
    payload = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "User-Agent": REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Reddit token request failed: {body.get('error', 'unknown error')}")
    return token


def _listings(subreddit: str, pages: int, limit: int, url_builder, headers: dict):
    """Page through a listing, yielding post dicts, one request per 0.6s."""
    after = None
    for _ in range(max(pages, 1)):
        url = url_builder(subreddit, limit, after)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        children = payload.get("data", {}).get("children", [])
        if not children:
            break
        for child in children:
            yield child.get("data", {})
        after = payload.get("data", {}).get("after")
        if not after:
            break
        time.sleep(0.6)


def fetch_posts(subreddit: str, pages: int = 1, limit: int = 100):
    """Yield post dicts from a subreddit's new listing (OAuth when configured)."""
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        token = get_access_token(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)

        def builder(sub, lim, after):
            url = f"{API_BASE}/r/{sub}/new?limit={lim}"
            if after:
                url += f"&after={urllib.parse.quote(after)}"
            return url

        headers = {"Authorization": f"Bearer {token}", "User-Agent": REDDIT_USER_AGENT}
        yield from _listings(subreddit, pages, limit, builder, headers)
        return

    def builder(sub, lim, after):
        url = f"{PUBLIC_BASE}/r/{sub}/new.json?limit={lim}"
        if after:
            url += f"&after={urllib.parse.quote(after)}"
        return url

    headers = {"User-Agent": REDDIT_USER_AGENT}
    yield from _listings(subreddit, pages, limit, builder, headers)


def post_text(post: dict) -> str:
    """Best-effort plain text for a post: title plus selftext."""
    parts = []
    if post.get("title"):
        parts.append(post["title"])
    if post.get("selftext"):
        parts.append(post["selftext"])
    return "\n".join(parts)


def harvest(
    subreddits: list[str] | None = None,
    pages: int = DEFAULT_PAGES,
    out_dir: str | Path | None = None,
) -> dict:
    """Fetch posts per subreddit and write one JSONL file each into raw/."""
    subreddits = subreddits or DEFAULT_SUBREDDITS
    out_dir = Path(out_dir or RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats: dict[str, object] = {}
    for sub in subreddits:
        rows: list[dict] = []
        try:
            for post in fetch_posts(sub, pages=pages):
                text = post_text(post)
                if text.strip():
                    rows.append(
                        {
                            "source": "reddit",
                            "subreddit": sub,
                            "id": post.get("id", ""),
                            "url": post.get("url", ""),
                            "text": text,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
        except urllib.error.HTTPError as exc:
            stats[sub] = f"error: {exc}. {_403_HINT}" if exc.code == 403 else f"error: {exc}"
            continue
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            stats[sub] = f"error: {exc}"
            continue
        path = out_dir / f"{sub}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        stats[sub] = len(rows)
    return stats


# ---------------------------------------------------------------------------
# Hugging Face datasets
# ---------------------------------------------------------------------------
def _hf_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": REDDIT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_splits(dataset: str) -> list[tuple[str, str]]:
    """Return (config, split) pairs for a dataset, train first when present."""
    payload = _hf_get(f"{HF_SPLITS_URL}?dataset={urllib.parse.quote(dataset)}")
    splits = [(s["config"], s["split"]) for s in payload.get("splits", [])]
    return sorted(splits, key=lambda pair: (pair[1] != "train", pair))


def resolve_split(dataset: str, config: str | None, split: str | None) -> tuple[str, str]:
    """Pick config/split, preferring the train split."""
    splits = discover_splits(dataset)
    if not splits:
        raise RuntimeError(f"no splits found for dataset {dataset}")
    if config and split:
        return config, split
    if config:
        candidates = [pair for pair in splits if pair[0] == config]
        if not candidates:
            raise RuntimeError(f"config {config} not found in {splits}")
        for pair in candidates:
            if pair[1] == "train":
                return pair
        return candidates[0]
    for pair in splits:
        if pair[1] == "train":
            return pair
    return splits[0]


def fetch_hf_rows(dataset: str, config: str, split: str, offset: int = 0, length: int = 100) -> list[dict]:
    """Fetch {row_idx, row} entries from the datasets-server rows endpoint."""
    params = urllib.parse.urlencode(
        {"dataset": dataset, "config": config, "split": split, "offset": offset, "length": length}
    )
    payload = _hf_get(f"{HF_ROWS_URL}?{params}")
    if "rows" not in payload:
        raise RuntimeError(f"HF rows request failed: {payload.get('error', 'unknown error')}")
    return payload["rows"]


def pick_text_field(features: list[dict], preferred: str | None = None) -> str:
    """Find the Arabizi/text column in a dataset's schema."""
    names = [f["name"] for f in features]
    if preferred:
        if preferred in names:
            return preferred
        raise RuntimeError(f"field {preferred} not in {names}")
    for candidate in HF_TEXT_FIELDS:
        if candidate in names:
            return candidate
    raise RuntimeError(f"no usable text field in {names}; pass --text-field")


def harvest_hf(
    dataset: str,
    rows: int = 500,
    text_field: str | None = None,
    config: str | None = None,
    split: str | None = None,
    out_dir: str | Path | None = None,
) -> dict:
    """Harvest text rows from a public Hugging Face dataset into raw/."""
    out_dir = Path(out_dir or RAW_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    config, split = resolve_split(dataset, config, split)

    params = urllib.parse.urlencode({"dataset": dataset, "config": config, "split": split})
    schema = _hf_get(f"{HF_FIRST_ROWS_URL}?{params}")
    if "features" not in schema:
        raise RuntimeError(f"HF schema request failed: {schema.get('error', 'unknown error')}")
    field = pick_text_field(schema["features"], text_field)

    written = 0
    offset = 0
    seen_ids: set[int] = set()
    path = out_dir / f"{dataset.replace('/', '__')}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        while written < rows:
            chunk = fetch_hf_rows(dataset, config, split, offset=offset, length=HF_BATCH)
            if not chunk:
                break
            for entry in chunk:
                row_idx = entry.get("row_idx", offset)
                if row_idx in seen_ids:
                    continue
                seen_ids.add(row_idx)
                text = (entry.get("row") or {}).get(field)
                if not text or not str(text).strip():
                    continue
                fh.write(
                    json.dumps(
                        {
                            "source": "huggingface",
                            "dataset": dataset,
                            "config": config,
                            "split": split,
                            "id": f"{dataset}-{row_idx}",
                            "text": str(text),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1
                if written >= rows:
                    break
            offset += len(chunk)
    return {"dataset": dataset, "field": field, "rows_written": written, "out": str(path)}


def iter_raw_rows(raw_dir: str | Path | None = None):
    """Yield every raw row across all JSONL files in raw/."""
    raw_dir = Path(raw_dir or RAW_DIR)
    for path in sorted(raw_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
