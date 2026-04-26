#!/usr/bin/env python3
"""Executable policy gates for BTC accumulation cycle opening."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from scripts.state import DEFAULT_STATE, load_state, validate_state
except ImportError:  # pragma: no cover - direct script execution from scripts/
    from state import DEFAULT_STATE, load_state, validate_state

PRODUCT = "BTC-USD"
VALID_SETUPS = {
    "catalyst_driven_breakdown",
    "sentiment_extreme_greed_fade",
    "funding_flip_divergence",
    "onchain_distribution_top",
}
MAX_CYCLE_FRACTION = Decimal("0.30")
MAX_CYCLES_PER_7D = 2
MIN_BTC_RR = Decimal("2.0")
MIN_USD_RESERVE_PCT = Decimal("10")
MAX_USD_RESERVE_PCT = Decimal("20")
DRAWDOWN_HALT_FRACTION = Decimal("0.15")
ONE_LOSS_COOLDOWN = timedelta(hours=48)
TWO_LOSS_COOLDOWN = timedelta(days=7)
DEFAULT_MAX_RESEARCH_AGE_HOURS = Decimal("3")


def parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def fmt_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def dec(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def btc_rr(
    sell_trigger_price: Decimal,
    rebuy_limit_price: Decimal,
    worst_case_rebuy_price: Decimal,
) -> Decimal:
    if sell_trigger_price <= 0:
        raise ValueError("sell_trigger_price must be positive")
    if rebuy_limit_price <= 0:
        raise ValueError("rebuy_limit_price must be positive")
    if worst_case_rebuy_price <= 0:
        raise ValueError("worst_case_rebuy_price must be positive")
    if rebuy_limit_price >= sell_trigger_price:
        raise ValueError("rebuy_limit_price must be below sell_trigger_price")
    if worst_case_rebuy_price <= sell_trigger_price:
        raise ValueError("worst_case_rebuy_price must exceed sell_trigger_price")

    gain_if_right = (sell_trigger_price / rebuy_limit_price) - Decimal("1")
    loss_if_wrong = Decimal("1") - (sell_trigger_price / worst_case_rebuy_price)
    if loss_if_wrong <= 0:
        raise ValueError("loss_if_wrong must be positive")
    return gain_if_right / loss_if_wrong


def _cycle_opened_at(cycle) -> datetime | None:
    if isinstance(cycle, str):
        value = cycle
    elif isinstance(cycle, dict):
        value = (
            cycle.get("cycle_opened_at_utc")
            or cycle.get("opened_at_utc")
            or cycle.get("opened_at")
        )
    else:
        return None
    if not value:
        return None
    return parse_utc(str(value))


def rolling_cycle_count(state: dict, now: datetime) -> int:
    cutoff = now - timedelta(days=7)
    count = 0
    for cycle in state.get("cycles_opened", []):
        opened_at = _cycle_opened_at(cycle)
        if opened_at and cutoff <= opened_at <= now:
            count += 1
    return count


def cooldown_until(state: dict, now: datetime) -> datetime | None:
    last_losing = state.get("last_losing_cycle_utc")
    if not last_losing:
        return None
    losing_at = parse_utc(str(last_losing))
    losses = int(state.get("consecutive_losing_cycles") or 0)
    if losses >= 2:
        until = losing_at + TWO_LOSS_COOLDOWN
    elif losses >= 1:
        until = losing_at + ONE_LOSS_COOLDOWN
    else:
        return None
    return until if now < until else None


def validate_cycle_open(
    *,
    state: dict,
    product_id: str,
    playbook_setup: str,
    btc_stack: Decimal,
    btc_equivalent_stack: Decimal,
    btc_to_sell: Decimal,
    sell_trigger_price: Decimal,
    rebuy_limit_price: Decimal,
    worst_case_rebuy_price: Decimal,
    current_price: Decimal | None,
    usd_reserve_pct: Decimal,
    research_fetched_at: datetime,
    now: datetime,
    max_research_age_hours: Decimal = DEFAULT_MAX_RESEARCH_AGE_HOURS,
) -> dict:
    errors: list[str] = []
    metrics: dict[str, str | int] = {}

    for error in validate_state(state):
        errors.append(f"state invalid: {error}")

    if product_id != PRODUCT:
        errors.append("product_id must be BTC-USD spot")
    if playbook_setup not in VALID_SETUPS:
        errors.append("playbook_setup is not a v2 setup")
    if state.get("active_cycle"):
        errors.append("one active cycle is already open")
    if state.get("drawdown_halt"):
        errors.append("drawdown_halt is active")

    quarterly_start = dec(state.get("quarterly_start_btc", "0"), "quarterly_start_btc")
    if quarterly_start <= 0:
        errors.append("quarterly_start_btc must be positive")
    else:
        drawdown_floor = quarterly_start * (Decimal("1") - DRAWDOWN_HALT_FRACTION)
        metrics["drawdown_floor_btc"] = str(drawdown_floor)
        if btc_equivalent_stack <= drawdown_floor:
            errors.append("BTC drawdown halt threshold breached")

    if btc_stack <= 0:
        errors.append("btc_stack must be positive")
    if btc_equivalent_stack <= 0:
        errors.append("btc_equivalent_stack must be positive")
    if btc_to_sell <= 0:
        errors.append("btc_to_sell must be positive")
    elif btc_stack > 0:
        max_btc_to_sell = btc_stack * MAX_CYCLE_FRACTION
        metrics["max_btc_to_sell"] = str(max_btc_to_sell)
        if btc_to_sell > max_btc_to_sell:
            errors.append("btc_to_sell exceeds 30 percent of BTC stack")

    if not (MIN_USD_RESERVE_PCT <= usd_reserve_pct <= MAX_USD_RESERVE_PCT):
        errors.append("USD reserve must be inside the 10-20 percent band")

    if current_price is not None and sell_trigger_price >= current_price:
        errors.append("sell_trigger_price must be below current spot price")

    try:
        ratio = btc_rr(sell_trigger_price, rebuy_limit_price, worst_case_rebuy_price)
        metrics["btc_r_r"] = str(ratio)
        if ratio < MIN_BTC_RR:
            errors.append("BTC R:R must be at least 2.0")
    except ValueError as exc:
        errors.append(str(exc))

    cycle_count = rolling_cycle_count(state, now)
    metrics["rolling_7d_cycle_count"] = cycle_count
    if cycle_count >= MAX_CYCLES_PER_7D:
        errors.append("rolling seven-day cycle cap reached")

    until = cooldown_until(state, now)
    if until:
        errors.append(f"cooldown active until {fmt_utc(until)}")

    max_age = timedelta(hours=float(max_research_age_hours))
    age = now - research_fetched_at
    metrics["research_age_seconds"] = str(int(age.total_seconds()))
    if research_fetched_at > now + timedelta(minutes=5):
        errors.append("research_fetched_at is in the future")
    elif age > max_age:
        errors.append("research data is stale")

    return {"ok": not errors, "errors": errors, "metrics": metrics}


def _decimal_arg(value: str) -> Decimal:
    return dec(value, "argument")


def cmd_validate_cycle(args) -> int:
    state = load_state(args.state)
    now = parse_utc(args.now) if args.now else utc_now()
    btc_stack = _decimal_arg(args.btc_stack)
    btc_equivalent_stack = (
        _decimal_arg(args.btc_equivalent_stack)
        if args.btc_equivalent_stack
        else btc_stack
    )
    report = validate_cycle_open(
        state=state,
        product_id=args.product,
        playbook_setup=args.playbook_setup,
        btc_stack=btc_stack,
        btc_equivalent_stack=btc_equivalent_stack,
        btc_to_sell=_decimal_arg(args.btc_to_sell),
        sell_trigger_price=_decimal_arg(args.sell_trigger_price),
        rebuy_limit_price=_decimal_arg(args.rebuy_limit_price),
        worst_case_rebuy_price=_decimal_arg(args.worst_case_rebuy_price),
        current_price=_decimal_arg(args.current_price) if args.current_price else None,
        usd_reserve_pct=_decimal_arg(args.usd_reserve_pct),
        research_fetched_at=parse_utc(args.research_fetched_at),
        now=now,
        max_research_age_hours=_decimal_arg(args.max_research_age_hours),
    )
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate BTC bot policy gates")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate-cycle", help="Validate a proposed live cycle")
    p.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p.add_argument("--product", default=PRODUCT)
    p.add_argument("--playbook-setup", required=True)
    p.add_argument("--btc-stack", required=True)
    p.add_argument("--btc-equivalent-stack")
    p.add_argument("--btc-to-sell", required=True)
    p.add_argument("--sell-trigger-price", required=True)
    p.add_argument("--rebuy-limit-price", required=True)
    p.add_argument("--worst-case-rebuy-price", required=True)
    p.add_argument("--current-price")
    p.add_argument("--usd-reserve-pct", required=True)
    p.add_argument("--research-fetched-at", required=True)
    p.add_argument("--max-research-age-hours", default=str(DEFAULT_MAX_RESEARCH_AGE_HOURS))
    p.add_argument("--now")
    p.set_defaults(func=cmd_validate_cycle)

    args = parser.parse_args()
    try:
        code = args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
