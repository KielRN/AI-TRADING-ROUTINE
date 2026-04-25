#!/usr/bin/env python3
"""Validate and summarize the bot's machine-readable state file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "memory" / "state.json"

REQUIRED_KEYS = {
    "schema_version",
    "updated_at_utc",
    "quarterly_start_btc",
    "drawdown_halt",
    "active_cycle",
    "active_cycle_detail",
    "last_losing_cycle_utc",
    "consecutive_losing_cycles",
    "cycles_opened",
}

ACTIVE_CYCLE_KEYS = {
    "cycle_id",
    "sell_order_id",
    "rebuy_order_id",
    "btc_to_sell",
    "sell_trigger_price",
    "rebuy_limit_price",
    "worst_case_rebuy_price",
    "cycle_opened_at_utc",
    "time_cap_utc",
    "playbook_setup",
}


def load_state(path: Path = DEFAULT_STATE) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_state(state: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_KEYS - set(state))
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")

    if state.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(state.get("drawdown_halt"), bool):
        errors.append("drawdown_halt must be boolean")
    if not isinstance(state.get("active_cycle"), bool):
        errors.append("active_cycle must be boolean")
    if not isinstance(state.get("consecutive_losing_cycles"), int):
        errors.append("consecutive_losing_cycles must be integer")
    if not isinstance(state.get("cycles_opened"), list):
        errors.append("cycles_opened must be a list")

    active_cycle = state.get("active_cycle")
    detail = state.get("active_cycle_detail")
    if active_cycle and not isinstance(detail, dict):
        errors.append("active_cycle_detail must be an object when active_cycle=true")
    if not active_cycle and detail is not None:
        errors.append("active_cycle_detail must be null when active_cycle=false")
    if isinstance(detail, dict):
        detail_missing = sorted(ACTIVE_CYCLE_KEYS - set(detail))
        if detail_missing:
            errors.append(
                "active_cycle_detail missing keys: " + ", ".join(detail_missing)
            )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate memory/state.json")
    parser.add_argument("path", nargs="?", default=str(DEFAULT_STATE))
    args = parser.parse_args()

    path = Path(args.path)
    try:
        state = load_state(path)
    except OSError as e:
        print(f"state read failed: {e}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"state JSON invalid: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate_state(state)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        sys.exit(1)
    print(json.dumps({"ok": True, "path": str(path)}, indent=2))


if __name__ == "__main__":
    main()

