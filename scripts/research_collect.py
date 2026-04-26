#!/usr/bin/env python3
"""Collect the currently validated research inputs.

This is intentionally bounded. It uses data sources already validated or
already paid for, then leaves missing/unvalidated rubric slots for the
research agent's WebSearch analysis.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WEBSEARCH_QUERIES = [
    "US economic calendar next 5 days FOMC CPI NFP",
    "Spot BTC ETF aggregate net flow last 24 hours USD",
    "BTC-specific news last 24h regulation SEC ETF exchange failure",
    "DXY trend last week, 10Y real yield DFII10 latest",
    "Crypto Fear Greed Index latest",
    "BTC dominance, stablecoin supply (USDT+USDC), total crypto market cap latest",
    "Exchange BTC net inflow outflow whale cohort last 7 days",
]

COMMANDS = {
    "chartinspect_funding": [
        sys.executable,
        str(ROOT / "scripts" / "chartinspect.py"),
        "funding-rates",
    ],
    "chartinspect_open_interest": [
        sys.executable,
        str(ROOT / "scripts" / "chartinspect.py"),
        "open-interest",
    ],
    "chartinspect_whale_flows": [
        sys.executable,
        str(ROOT / "scripts" / "chartinspect.py"),
        "whale-flows",
    ],
    "youtube_titles": [
        sys.executable,
        str(ROOT / "scripts" / "youtube.py"),
        "titles",
    ],
    "youtube_velocity": [
        sys.executable,
        str(ROOT / "scripts" / "youtube.py"),
        "velocity",
    ],
    "coinbase_quote": [
        sys.executable,
        str(ROOT / "scripts" / "coinbase.py"),
        "quote",
        "BTC-USD",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def run_source(name: str, command: list[str], *, timeout: int = 45) -> dict:
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "source": name,
            "error": f"timed out after {timeout}s",
            "stderr": str(exc),
        }
    except OSError as exc:
        return {"ok": False, "source": name, "error": str(exc), "stderr": ""}

    if proc.returncode != 0:
        return {
            "ok": False,
            "source": name,
            "exit_code": proc.returncode,
            "error": "source command failed",
            "stderr": proc.stderr.strip(),
            "stdout": proc.stdout.strip(),
        }

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "source": name,
            "error": f"invalid JSON: {exc}",
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    return {"ok": True, "source": name, "data": data}


def collect(commands: dict[str, list[str]] = COMMANDS) -> dict:
    fetched_at = utc_now()
    sources = {name: run_source(name, command) for name, command in commands.items()}
    missing_slots = sorted(name for name, result in sources.items() if not result["ok"])
    ok_sources = sorted(name for name, result in sources.items() if result["ok"])
    return {
        "ok": bool(ok_sources),
        "mode": "validated_sources_plus_websearch",
        "fetched_at": fetched_at,
        "scope": {
            "policy": (
                "Use currently validated or already-paid data sources only; "
                "research agent covers gaps with WebSearch."
            ),
            "paid_sources": ["ChartInspect Pro"],
            "validated_sources": [
                "chartinspect_funding",
                "chartinspect_open_interest",
                "chartinspect_whale_flows",
                "youtube_titles",
                "youtube_velocity",
                "coinbase_quote",
            ],
        },
        "sources": sources,
        "missing_slots": missing_slots,
        "websearch_required": WEBSEARCH_QUERIES,
        "stale_warnings": [],
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect validated research inputs")
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="print configured sources without calling APIs",
    )
    args = parser.parse_args()

    if args.list_sources:
        print_json(
            {
                "ok": True,
                "mode": "validated_sources_plus_websearch",
                "sources": sorted(COMMANDS),
                "websearch_required": WEBSEARCH_QUERIES,
            }
        )
        return

    payload = collect()
    print_json(payload)
    sys.exit(0 if payload["ok"] else 2)


if __name__ == "__main__":
    main()
