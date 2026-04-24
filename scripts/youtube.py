#!/usr/bin/env python3
"""YouTube Data API v3 wrapper for research sentiment signals.

Usage:
    python scripts/youtube.py <subcommand> [args...]

Subcommands:
    titles      Last N video titles per research channel (default N=5)
    velocity    Videos posted per channel in the last 48 hours

All subcommands print a single JSON object to stdout and exit 0 on success.
Exit codes: 0 ok | 1 usage error | 2 API error | 3 config error
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    print("requests not installed — run: pip install requests", file=sys.stderr)
    sys.exit(3)

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

if load_dotenv and ENV_FILE.exists():
    load_dotenv(ENV_FILE)

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    print("YOUTUBE_API_KEY not set in environment", file=sys.stderr)
    sys.exit(3)

BASE_URL = "https://www.googleapis.com/youtube/v3/search"

# Research channels — confirmed channel IDs
CHANNELS: dict[str, str] = {
    "Benjamin Cowen": "UCRvqjQPSeaWn-uEx-w0XOIg",
    "Coin Bureau":     "UCqK_GSMbpiV8spgD3ZGloSw",
    "InvestAnswers":   "UClgJyzwGs-GyaNxUHcLZrkg",
    "Crypto Banter":   "UCN9Nj4tjXbVTLYWN0EKly_Q",
    "Plan B":          "UCyTSwVh66Y2Ww_CIIHhuxbw",
    "Raoul Pal":       "UCVFSzL3VuZKP3cN9IXdLOtw",
}


def _search(channel_id: str, max_results: int, published_after: str | None = None) -> list[dict]:
    params: dict = {
        "key": API_KEY,
        "channelId": channel_id,
        "part": "snippet",
        "order": "date",
        "maxResults": max_results,
        "type": "video",
    }
    if published_after:
        params["publishedAfter"] = published_after

    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"request failed: {e}", file=sys.stderr)
        sys.exit(2)

    if r.status_code == 403:
        body = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
        reason = body.get("error", {}).get("message", r.text[:200])
        print(f"YouTube API 403 — quota exceeded or key invalid: {reason}", file=sys.stderr)
        sys.exit(2)

    if r.status_code != 200:
        print(f"HTTP {r.status_code} from YouTube API: {r.text[:300]}", file=sys.stderr)
        sys.exit(2)

    try:
        return r.json().get("items", [])
    except ValueError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        sys.exit(2)


def _dump(obj: dict) -> None:
    sys.stdout.buffer.write(json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_titles(args) -> None:
    """Last N video titles per research channel."""
    n = args.count
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    channels_out = []

    for name, cid in CHANNELS.items():
        items = _search(cid, max_results=n)
        titles = [html.unescape(item["snippet"]["title"]) for item in items]
        channels_out.append({"channel": name, "titles": titles})

    _dump({
        "source": "youtube/titles",
        "fetched_at": fetched_at,
        "titles_per_channel": n,
        "channels": channels_out,
    })


def cmd_velocity(args) -> None:
    """Video count per research channel in the last 48 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    channels_out = []
    total = 0

    for name, cid in CHANNELS.items():
        # maxResults=50 to count accurately; API caps at 50 per request
        items = _search(cid, max_results=50, published_after=published_after)
        count = len(items)
        total += count
        channels_out.append({"channel": name, "videos_last_48h": count})

    _dump({
        "source": "youtube/velocity",
        "fetched_at": fetched_at,
        "window_hours": 48,
        "published_after": published_after,
        "total_videos": total,
        "channels": channels_out,
    })


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube Data API v3 — research sentiment signals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="subcommand")

    p_titles = sub.add_parser("titles", help="last N video titles per channel")
    p_titles.add_argument("-n", "--count", type=int, default=5, metavar="N",
                          help="titles to fetch per channel (default 5)")
    p_titles.set_defaults(func=cmd_titles)

    p_vel = sub.add_parser("velocity", help="videos posted in last 48h per channel")
    p_vel.set_defaults(func=cmd_velocity)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
