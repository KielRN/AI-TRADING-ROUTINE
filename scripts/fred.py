#!/usr/bin/env python3
"""FRED (St. Louis Fed) macro data wrapper. Read-only.

Usage:
    python scripts/fred.py rates

Subcommands:
    rates   Fetch DGS10, DFII10, M2SL, T10Y2Y — latest observation each

Prints a single JSON object to stdout and exits 0 on success.
Exit codes: 0 ok | 1 usage error | 2 API error | 3 config error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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

API_KEY = os.getenv("FRED_API_KEY")
if not API_KEY:
    print("FRED_API_KEY not set in environment", file=sys.stderr)
    sys.exit(3)

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "DGS10":  "10y_nominal_yield_pct",
    "DFII10": "10y_real_yield_pct",
    "M2SL":   "m2_supply_bn_usd",
    "T10Y2Y": "yield_curve_10y2y_pct",
}


def _fetch(series_id: str) -> dict:
    params = {
        "series_id": series_id,
        "api_key": API_KEY,
        "limit": 1,
        "sort_order": "desc",
        "file_type": "json",
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=20)
    except requests.RequestException as e:
        print(f"request failed for {series_id}: {e}", file=sys.stderr)
        sys.exit(2)
    if r.status_code != 200:
        print(f"HTTP {r.status_code} for {series_id}: {r.text[:300]}", file=sys.stderr)
        sys.exit(2)
    try:
        data = r.json()
    except ValueError as e:
        print(f"JSON parse error for {series_id}: {e}", file=sys.stderr)
        sys.exit(2)

    obs = data.get("observations", [])
    if not obs:
        print(f"no observations returned for {series_id}", file=sys.stderr)
        sys.exit(2)

    row = obs[0]
    raw = row["value"]
    # FRED uses "." for missing values
    value = float(raw) if raw != "." else None
    return {"date": row["date"], "value": value}


def cmd_rates(_args) -> None:
    results = {}
    for series_id, field in SERIES.items():
        obs = _fetch(series_id)
        results[field] = obs["value"]
        results[f"{field}_date"] = obs["date"]

    # Derived: breakeven inflation = nominal - real (10y)
    nom = results.get("10y_nominal_yield_pct")
    real = results.get("10y_real_yield_pct")
    breakeven = round(nom - real, 4) if nom is not None and real is not None else None

    print(json.dumps({
        "source": "fred",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "10y_nominal_yield_pct":      results["10y_nominal_yield_pct"],
        "10y_nominal_yield_pct_date": results["10y_nominal_yield_pct_date"],
        "10y_real_yield_pct":         results["10y_real_yield_pct"],
        "10y_real_yield_pct_date":    results["10y_real_yield_pct_date"],
        "breakeven_inflation_pct":    breakeven,
        "m2_supply_bn_usd":           results["m2_supply_bn_usd"],
        "m2_supply_bn_usd_date":      results["m2_supply_bn_usd_date"],
        "yield_curve_10y2y_pct":      results["yield_curve_10y2y_pct"],
        "yield_curve_10y2y_pct_date": results["yield_curve_10y2y_pct_date"],
    }, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(
        description="FRED macro data wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rates", help="Fetch DGS10, DFII10, M2SL, T10Y2Y")

    args = p.parse_args()
    if args.cmd == "rates":
        cmd_rates(args)


if __name__ == "__main__":
    main()
