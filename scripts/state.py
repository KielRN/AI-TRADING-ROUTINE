#!/usr/bin/env python3
"""Validate and update the bot's machine-readable state file."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "memory" / "state.json"
SCHEMA_VERSION = 1

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
    "phase",
    "sell_order_id",
    "rebuy_order_id",
    "btc_to_sell",
    "sell_trigger_price",
    "rebuy_limit_price",
    "worst_case_rebuy_price",
    "cycle_opened_at_utc",
    "time_cap_utc",
    "playbook_setup",
    "sell_filled_at_utc",
    "sell_fill_price",
    "rebuy_fill_price",
}

ACTIVE_PHASES = {"A", "B", "D"}


def load_state(path: Path = DEFAULT_STATE) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def fmt_utc(value: datetime | str) -> str:
    if isinstance(value, str):
        value = parse_utc(value)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _dec(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def _dec_str(value) -> str:
    return format(_dec(value, "decimal"), "f")


def _optional_dec_str(value):
    return None if value is None else _dec_str(value)


def _validate_timestamp(errors: list[str], value, field: str, *, nullable: bool) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be an ISO UTC timestamp")
        return
    try:
        parse_utc(value)
    except ValueError:
        errors.append(f"{field} must be an ISO UTC timestamp")


def require_valid(state: dict) -> None:
    errors = validate_state(state)
    if errors:
        raise ValueError("; ".join(errors))


def validate_state(state: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_KEYS - set(state))
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")

    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(state.get("drawdown_halt"), bool):
        errors.append("drawdown_halt must be boolean")
    if not isinstance(state.get("active_cycle"), bool):
        errors.append("active_cycle must be boolean")
    if not isinstance(state.get("consecutive_losing_cycles"), int):
        errors.append("consecutive_losing_cycles must be integer")
    if not isinstance(state.get("cycles_opened"), list):
        errors.append("cycles_opened must be a list")
    _validate_timestamp(
        errors, state.get("updated_at_utc"), "updated_at_utc", nullable=True
    )
    _validate_timestamp(
        errors,
        state.get("last_losing_cycle_utc"),
        "last_losing_cycle_utc",
        nullable=True,
    )
    if "quarterly_start_btc" in state:
        try:
            if _dec(state["quarterly_start_btc"], "quarterly_start_btc") <= 0:
                errors.append("quarterly_start_btc must be positive")
        except ValueError as exc:
            errors.append(str(exc))

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
        phase = detail.get("phase")
        if phase not in ACTIVE_PHASES:
            errors.append("active_cycle_detail phase must be A, B, or D")
        for field in (
            "btc_to_sell",
            "sell_trigger_price",
            "rebuy_limit_price",
            "worst_case_rebuy_price",
        ):
            if field in detail:
                try:
                    if _dec(detail[field], field) <= 0:
                        errors.append(f"active_cycle_detail {field} must be positive")
                except ValueError as exc:
                    errors.append(f"active_cycle_detail {exc}")
        for field in ("cycle_opened_at_utc", "time_cap_utc"):
            if field in detail:
                _validate_timestamp(
                    errors, detail.get(field), f"active_cycle_detail {field}", nullable=False
                )
        for field in ("sell_filled_at_utc", "rebuy_filled_at_utc", "closed_at_utc"):
            if field in detail:
                _validate_timestamp(
                    errors, detail.get(field), f"active_cycle_detail {field}", nullable=True
                )

    return errors


def write_state_atomic(state: dict, path: Path = DEFAULT_STATE) -> None:
    """Validate and atomically replace the state file."""
    require_valid(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        Path(tmp_name).replace(path)
    except Exception:
        try:
            Path(tmp_name).unlink()
        except OSError:
            pass
        raise


def _copy_valid_state(state: dict) -> dict:
    require_valid(state)
    return copy.deepcopy(state)


def _find_cycle_index(state: dict, cycle_id: str) -> int | None:
    for index, cycle in enumerate(state.get("cycles_opened", [])):
        if isinstance(cycle, dict) and cycle.get("cycle_id") == cycle_id:
            return index
    return None


def _sync_cycle_record(state: dict, cycle: dict) -> None:
    index = _find_cycle_index(state, cycle["cycle_id"])
    if index is None:
        state["cycles_opened"].append(copy.deepcopy(cycle))
    else:
        state["cycles_opened"][index] = copy.deepcopy(cycle)


def open_cycle(
    state: dict,
    *,
    cycle_id: str,
    sell_order_id: str,
    rebuy_order_id: str,
    btc_to_sell,
    sell_trigger_price,
    rebuy_limit_price,
    worst_case_rebuy_price,
    cycle_opened_at_utc: datetime | str,
    time_cap_utc: datetime | str,
    playbook_setup: str,
    sell_client_order_id: str | None = None,
    rebuy_client_order_id: str | None = None,
    expected_usd=None,
    stop_limit_price=None,
) -> dict:
    """Return a new state with a Phase-A active cycle recorded."""
    next_state = _copy_valid_state(state)
    if next_state["active_cycle"]:
        raise ValueError("cannot open a cycle while active_cycle=true")
    if _find_cycle_index(next_state, cycle_id) is not None:
        raise ValueError(f"cycle_id already exists in cycles_opened: {cycle_id}")

    opened_at = fmt_utc(cycle_opened_at_utc)
    cycle = {
        "cycle_id": cycle_id,
        "phase": "A",
        "sell_order_id": sell_order_id,
        "rebuy_order_id": rebuy_order_id,
        "sell_client_order_id": sell_client_order_id,
        "rebuy_client_order_id": rebuy_client_order_id,
        "btc_to_sell": _dec_str(btc_to_sell),
        "sell_trigger_price": _dec_str(sell_trigger_price),
        "rebuy_limit_price": _dec_str(rebuy_limit_price),
        "worst_case_rebuy_price": _dec_str(worst_case_rebuy_price),
        "expected_usd": _optional_dec_str(expected_usd),
        "stop_limit_price": _optional_dec_str(stop_limit_price),
        "cycle_opened_at_utc": opened_at,
        "time_cap_utc": fmt_utc(time_cap_utc),
        "playbook_setup": playbook_setup,
        "sell_filled_at_utc": None,
        "sell_fill_price": None,
        "usd_from_sell": None,
        "rebuy_filled_at_utc": None,
        "rebuy_fill_price": None,
        "rebuy_filled_size": None,
        "closed_at_utc": None,
        "close_reason": None,
        "btc_delta": None,
    }
    next_state["active_cycle"] = True
    next_state["active_cycle_detail"] = copy.deepcopy(cycle)
    next_state["updated_at_utc"] = opened_at
    _sync_cycle_record(next_state, cycle)
    require_valid(next_state)
    return next_state


def mark_sell_filled(
    state: dict,
    *,
    sell_filled_at_utc: datetime | str,
    sell_fill_price,
    usd_from_sell=None,
) -> dict:
    """Return a new state with the active cycle moved to Phase B."""
    next_state = _copy_valid_state(state)
    cycle = next_state.get("active_cycle_detail")
    if not next_state["active_cycle"] or not isinstance(cycle, dict):
        raise ValueError("no active cycle to mark sell-filled")
    if cycle.get("phase") not in {"A", "B"}:
        raise ValueError("sell fill can only be recorded from Phase A or B")

    at = fmt_utc(sell_filled_at_utc)
    cycle["phase"] = "B"
    cycle["sell_filled_at_utc"] = at
    cycle["sell_fill_price"] = _dec_str(sell_fill_price)
    cycle["usd_from_sell"] = _optional_dec_str(usd_from_sell)
    next_state["updated_at_utc"] = at
    _sync_cycle_record(next_state, cycle)
    require_valid(next_state)
    return next_state


def update_cooldown_from_result(
    state: dict,
    *,
    closed_at_utc: datetime | str,
    btc_delta,
) -> dict:
    """Return a new state with loss-cooldown counters updated from BTC delta."""
    next_state = copy.deepcopy(state)
    delta = _dec(btc_delta, "btc_delta")
    if delta < 0:
        next_state["last_losing_cycle_utc"] = fmt_utc(closed_at_utc)
        next_state["consecutive_losing_cycles"] = int(
            next_state.get("consecutive_losing_cycles") or 0
        ) + 1
    else:
        next_state["consecutive_losing_cycles"] = 0
    require_valid(next_state)
    return next_state


def close_cycle(
    state: dict,
    *,
    closed_at_utc: datetime | str,
    rebuy_fill_price,
    rebuy_filled_size,
    close_reason: str = "clean_close",
) -> dict:
    """Return a new state with the active cycle closed and cooldown updated."""
    next_state = _copy_valid_state(state)
    cycle = next_state.get("active_cycle_detail")
    if not next_state["active_cycle"] or not isinstance(cycle, dict):
        raise ValueError("no active cycle to close")
    if cycle.get("phase") not in {"A", "B", "D"}:
        raise ValueError("active cycle phase is not closeable")

    at = fmt_utc(closed_at_utc)
    btc_delta = _dec(rebuy_filled_size, "rebuy_filled_size") - _dec(
        cycle["btc_to_sell"], "btc_to_sell"
    )
    cycle["phase"] = "C"
    cycle["rebuy_filled_at_utc"] = at
    cycle["rebuy_fill_price"] = _dec_str(rebuy_fill_price)
    cycle["rebuy_filled_size"] = _dec_str(rebuy_filled_size)
    cycle["closed_at_utc"] = at
    cycle["close_reason"] = close_reason
    cycle["btc_delta"] = _dec_str(btc_delta)
    _sync_cycle_record(next_state, cycle)

    next_state["active_cycle"] = False
    next_state["active_cycle_detail"] = None
    next_state["updated_at_utc"] = at
    next_state = update_cooldown_from_result(
        next_state, closed_at_utc=at, btc_delta=btc_delta
    )
    require_valid(next_state)
    return next_state


def force_close_cycle(
    state: dict,
    *,
    closed_at_utc: datetime | str,
    market_buy_fill_price,
    rebuy_filled_size,
    close_reason: str = "forced_close",
) -> dict:
    return close_cycle(
        state,
        closed_at_utc=closed_at_utc,
        rebuy_fill_price=market_buy_fill_price,
        rebuy_filled_size=rebuy_filled_size,
        close_reason=close_reason,
    )


def set_drawdown_halt(
    state: dict,
    *,
    active: bool,
    updated_at_utc: datetime | str,
    reason: str | None = None,
) -> dict:
    next_state = _copy_valid_state(state)
    next_state["drawdown_halt"] = bool(active)
    next_state["updated_at_utc"] = fmt_utc(updated_at_utc)
    if reason:
        next_state["drawdown_halt_reason"] = reason
    elif not active:
        next_state.pop("drawdown_halt_reason", None)
    require_valid(next_state)
    return next_state


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
