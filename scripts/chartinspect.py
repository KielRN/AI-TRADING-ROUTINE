#!/usr/bin/env python3
"""ChartInspect Pro API wrapper. Read-only. All ChartInspect calls go through here.

Usage:
    python scripts/chartinspect.py <subcommand> [args...]

Subcommands:
    funding-rates   Aggregate BTC perp funding rate (latest row)
    open-interest   BTC perp OI — aggregate + per venue (latest row)
    whale-flows     Balance distribution flows for 1k+ BTC cohorts (latest row)

All subcommands print a single JSON object to stdout and exit 0 on success.
Exit codes: 0 ok | 1 usage error | 2 API error | 3 config error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
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

API_KEY = os.getenv("CHARTINSPECT_API_KEY")
if not API_KEY:
    print("CHARTINSPECT_API_KEY not set in environment", file=sys.stderr)
    sys.exit(3)

BASE_URL = "https://chartinspect.com/api/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}


def _get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"request failed: {e}", file=sys.stderr)
        sys.exit(2)
    if r.status_code != 200:
        print(f"HTTP {r.status_code} from {url}: {r.text[:300]}", file=sys.stderr)
        sys.exit(2)
    try:
        return r.json()
    except ValueError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        sys.exit(2)


def _dump(obj: dict) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _latest(data: list) -> dict:
    if not data:
        print("no data rows returned", file=sys.stderr)
        sys.exit(2)
    return data[-1]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_funding_rates(args) -> None:
    """Latest aggregate BTC perp funding rate across all venues."""
    d = _get("/derivatives/futures_funding_rates")
    row = _latest(d["data"])
    _dump({
        "source": "chartinspect/futures_funding_rates",
        "date": row["date"],
        "btc_price": row["price"],
        "funding_rate_pct": round(row["Funding_Rate_ve"] * 100, 6),
        "adj_funding_rate_pct": round(row["AdjFR_ve"] * 100, 6),
        "premium_longs_pay_usd": row["Premium_LongsPay"],
        "premium_shorts_pay_usd": row["Premium_ShortsPay"],
    })


def cmd_open_interest(args) -> None:
    """Latest BTC perp open interest — aggregate and per venue."""
    d = _get("/derivatives/futures_open_interest")
    row = _latest(d["data"])

    venues = {k: v for k, v in row.items() if k not in ("date", "price")}
    aggregate = venues.pop("Aggregate_Total", None)

    _dump({
        "source": "chartinspect/futures_open_interest",
        "date": row["date"],
        "btc_price": row["price"],
        "aggregate_total_usd": aggregate,
        "venues": {k: v for k, v in sorted(venues.items(), key=lambda x: x[1], reverse=True)},
    })


def cmd_whale_flows(args) -> None:
    """Latest BTC balance distribution flows for 1k+ BTC cohorts (whale proxy)."""
    d = _get("/onchain/balance-distribution-flows")
    row = _latest(d["data"])

    flow_1k_10k = row.get("flow_1kto10kbtc", 0)
    flow_above_10k = row.get("flow_above10kbtc", 0)
    total_whale_flow = flow_1k_10k + flow_above_10k

    _dump({
        "source": "chartinspect/balance-distribution-flows",
        "date": row.get("date"),
        "btc_price": row.get("btc_price"),
        "whale_flow_total_btc": round(total_whale_flow, 4),
        "flow_1k_to_10k_btc": round(flow_1k_10k, 4),
        "flow_above_10k_btc": round(flow_above_10k, 4),
        "balance_1k_to_10k_btc": row.get("btc_in_1kto10kbtc"),
        "balance_above_10k_btc": row.get("btc_in_above10kbtc"),
    })


# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="ChartInspect Pro read-only wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("funding-rates", help="Aggregate BTC perp funding rate")
    sub.add_parser("open-interest", help="BTC perp OI aggregate + per venue")
    sub.add_parser("whale-flows", help="1k+ BTC cohort balance flows")

    args = p.parse_args()

    handlers = {
        "funding-rates": cmd_funding_rates,
        "open-interest": cmd_open_interest,
        "whale-flows": cmd_whale_flows,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
