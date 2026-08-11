"""Harvest raw posts from Reddit.

The public JSON endpoint blocks anonymous access from many networks. The
reliable path is a free Reddit script app: create one at
reddit.com/prefs/apps, then export REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.
With those set, the harvester uses the OAuth API (higher limits, works
everywhere). Without them it tries the public endpoint and reports a clear
error with setup instructions.
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
    RAW_DIR,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
PUBLIC_BASE = "https://www.reddit.com"

_403_HINT = (
    "Reddit blocked the request (HTTP 403). Create a free script app at "
    "reddit.com/prefs/apps, then export REDDIT_CLIENT_ID and "
    "REDDIT_CLIENT_SECRET to use the OAuth API."
)


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


def iter_raw_rows(raw_dir: str | Path | None = None):
    """Yield every raw row across all JSONL files in raw/."""
    raw_dir = Path(raw_dir or RAW_DIR)
    for path in sorted(raw_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
