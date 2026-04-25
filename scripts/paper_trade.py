#!/usr/bin/env python3
"""Two-week paper trading harness for BTC accumulation cycles.

This script deliberately does not call Coinbase. It simulates the v2 cycle
mechanics against prices supplied by the routine or a human operator.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "memory" / "paper-trading" / "state.json"
SCHEMA_VERSION = 1
DEFAULT_DURATION_DAYS = 14
MAX_CYCLE_FRACTION = Decimal("0.30")
MAX_CYCLES_PER_7D = 2
TIME_CAP_HOURS = 72
VALID_GRADES = {"A", "B"}
VALID_SETUPS = {
    "catalyst_driven_breakdown",
    "sentiment_extreme_greed_fade",
    "funding_flip_divergence",
    "onchain_distribution_top",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def fmt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def dec(value: str | int | float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def dec_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN), "f")


def money_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_DOWN), "f")


def load_state(path: Path = DEFAULT_STATE) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_state(state: dict, path: Path = DEFAULT_STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def seed_state() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "paper",
        "status": "not_started",
        "duration_days": DEFAULT_DURATION_DAYS,
        "started_at_utc": None,
        "ends_at_utc": None,
        "updated_at_utc": None,
        "starting_btc": "0",
        "starting_usd": "0.00",
        "starting_btc_price": "0.00",
        "balances": {
            "btc_available": "0",
            "btc_locked": "0",
            "usd_available": "0.00",
            "usd_locked": "0.00",
        },
        "last_price": {"bid": None, "ask": None, "time_utc": None},
        "active_cycle": None,
        "cycles": [],
        "events": [],
    }


def validate_state(state: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "mode",
        "status",
        "duration_days",
        "started_at_utc",
        "ends_at_utc",
        "updated_at_utc",
        "starting_btc",
        "starting_usd",
        "starting_btc_price",
        "balances",
        "last_price",
        "active_cycle",
        "cycles",
        "events",
    }
    missing = sorted(required - set(state))
    if missing:
        errors.append("missing required keys: " + ", ".join(missing))
        return errors

    if state["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if state["mode"] != "paper":
        errors.append("mode must be paper")
    if state["status"] not in {"not_started", "active", "complete"}:
        errors.append("status must be not_started, active, or complete")
    if state["duration_days"] != DEFAULT_DURATION_DAYS:
        errors.append("duration_days must be 14")
    if not isinstance(state["balances"], dict):
        errors.append("balances must be an object")
    if not isinstance(state["last_price"], dict):
        errors.append("last_price must be an object")
    if not isinstance(state["cycles"], list):
        errors.append("cycles must be a list")
    if not isinstance(state["events"], list):
        errors.append("events must be a list")
    if state["active_cycle"] is not None and not isinstance(state["active_cycle"], dict):
        errors.append("active_cycle must be null or an object")

    for key in ("started_at_utc", "ends_at_utc", "updated_at_utc"):
        if state[key] is not None:
            try:
                parse_utc(state[key])
            except ValueError:
                errors.append(f"{key} must be an ISO UTC timestamp")

    return errors


def require_valid(state: dict) -> None:
    errors = validate_state(state)
    if errors:
        raise ValueError("; ".join(errors))


def append_event(state: dict, event_type: str, at: datetime, details: dict) -> None:
    state["events"].append(
        {
            "type": event_type,
            "time_utc": fmt_utc(at),
            "details": details,
        }
    )


def init_campaign(
    starting_btc: Decimal,
    starting_usd: Decimal,
    starting_btc_price: Decimal,
    start: datetime,
    *,
    force: bool = False,
    existing: dict | None = None,
) -> dict:
    if existing and existing.get("status") == "active" and not force:
        raise ValueError("paper campaign already active; rerun with --force to reset")
    if starting_btc < 0:
        raise ValueError("starting_btc must be non-negative")
    if starting_usd < 0:
        raise ValueError("starting_usd must be non-negative")
    if starting_btc_price <= 0:
        raise ValueError("starting_btc_price must be positive")

    state = seed_state()
    end = start + timedelta(days=DEFAULT_DURATION_DAYS)
    state.update(
        {
            "status": "active",
            "started_at_utc": fmt_utc(start),
            "ends_at_utc": fmt_utc(end),
            "updated_at_utc": fmt_utc(start),
            "starting_btc": dec_str(starting_btc),
            "starting_usd": money_str(starting_usd),
            "starting_btc_price": money_str(starting_btc_price),
            "balances": {
                "btc_available": dec_str(starting_btc),
                "btc_locked": "0E-8",
                "usd_available": money_str(starting_usd),
                "usd_locked": "0.00",
            },
            "last_price": {
                "bid": money_str(starting_btc_price),
                "ask": money_str(starting_btc_price),
                "time_utc": fmt_utc(start),
            },
        }
    )
    append_event(
        state,
        "campaign_started",
        start,
        {
            "duration_days": DEFAULT_DURATION_DAYS,
            "starting_btc": state["starting_btc"],
            "starting_usd": state["starting_usd"],
            "starting_btc_price": state["starting_btc_price"],
        },
    )
    return state


def total_btc_balance(state: dict) -> Decimal:
    balances = state["balances"]
    return dec(balances["btc_available"]) + dec(balances["btc_locked"])


def rolling_cycle_count(state: dict, opened_at: datetime) -> int:
    cutoff = opened_at - timedelta(days=7)
    count = 0
    for cycle in state["cycles"]:
        cycle_opened_at = parse_utc(cycle["opened_at_utc"])
        if cutoff <= cycle_opened_at <= opened_at:
            count += 1
    return count


def open_cycle(
    state: dict,
    *,
    cycle_id: str,
    playbook_setup: str,
    grade: str,
    btc_to_sell: Decimal,
    sell_trigger_price: Decimal,
    rebuy_limit_price: Decimal,
    worst_case_rebuy_price: Decimal,
    current_price: Decimal,
    opened_at: datetime,
) -> dict:
    require_valid(state)
    if state["status"] != "active":
        raise ValueError("paper campaign is not active")
    if state["active_cycle"] is not None:
        raise ValueError("one active paper cycle is already open")
    campaign_end = parse_utc(state["ends_at_utc"])
    if opened_at >= campaign_end:
        raise ValueError("cannot open a cycle after the paper campaign end")
    if opened_at + timedelta(hours=TIME_CAP_HOURS) > campaign_end:
        raise ValueError("cycle time-cap window would exceed the paper campaign end")
    if playbook_setup not in VALID_SETUPS:
        raise ValueError("playbook_setup is not a v2 setup")
    if grade not in VALID_GRADES:
        raise ValueError("grade must be A or B")
    if btc_to_sell <= 0:
        raise ValueError("btc_to_sell must be positive")
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    if not rebuy_limit_price < sell_trigger_price < current_price:
        raise ValueError("requires rebuy_limit_price < sell_trigger_price < current_price")
    if worst_case_rebuy_price <= sell_trigger_price:
        raise ValueError("worst_case_rebuy_price must exceed sell_trigger_price")
    if rolling_cycle_count(state, opened_at) >= MAX_CYCLES_PER_7D:
        raise ValueError("rolling seven-day cycle cap reached")

    stack = total_btc_balance(state)
    if btc_to_sell > stack * MAX_CYCLE_FRACTION:
        raise ValueError("btc_to_sell exceeds 30 percent of paper BTC stack")

    balances = deepcopy(state["balances"])
    available_btc = dec(balances["btc_available"])
    if btc_to_sell > available_btc:
        raise ValueError("btc_to_sell exceeds available paper BTC")
    balances["btc_available"] = dec_str(available_btc - btc_to_sell)
    balances["btc_locked"] = dec_str(dec(balances["btc_locked"]) + btc_to_sell)

    cycle = {
        "cycle_id": cycle_id,
        "phase": "A",
        "playbook_setup": playbook_setup,
        "grade": grade,
        "sell_order_id": f"paper-{cycle_id}-sell",
        "rebuy_order_id": f"paper-{cycle_id}-rebuy",
        "btc_to_sell": dec_str(btc_to_sell),
        "sell_trigger_price": money_str(sell_trigger_price),
        "rebuy_limit_price": money_str(rebuy_limit_price),
        "worst_case_rebuy_price": money_str(worst_case_rebuy_price),
        "opened_at_utc": fmt_utc(opened_at),
        "time_cap_utc": None,
        "sell_filled_at_utc": None,
        "sell_fill_price": None,
        "usd_from_sell": None,
        "closed_at_utc": None,
        "close_reason": None,
        "rebuy_fill_price": None,
        "btc_rebought": None,
        "btc_delta": None,
    }

    state = deepcopy(state)
    state["balances"] = balances
    state["active_cycle"] = cycle
    state["cycles"].append(deepcopy(cycle))
    state["updated_at_utc"] = fmt_utc(opened_at)
    state["last_price"] = {
        "bid": money_str(current_price),
        "ask": money_str(current_price),
        "time_utc": fmt_utc(opened_at),
    }
    append_event(
        state,
        "cycle_opened",
        opened_at,
        {
            "cycle_id": cycle_id,
            "sell_order_id": cycle["sell_order_id"],
            "rebuy_order_id": cycle["rebuy_order_id"],
        },
    )
    return state


def sync_cycle_record(state: dict) -> None:
    active = state["active_cycle"]
    if not active:
        return
    for index, cycle in enumerate(state["cycles"]):
        if cycle["cycle_id"] == active["cycle_id"]:
            state["cycles"][index] = deepcopy(active)
            return


def close_active_cycle(
    state: dict,
    *,
    at: datetime,
    reason: str,
    fill_price: Decimal,
) -> None:
    active = state["active_cycle"]
    if not active:
        raise ValueError("no active cycle to close")
    usd_from_sell = dec(active["usd_from_sell"])
    btc_to_sell = dec(active["btc_to_sell"])
    btc_rebought = usd_from_sell / fill_price
    btc_delta = btc_rebought - btc_to_sell

    balances = state["balances"]
    balances["usd_locked"] = money_str(dec(balances["usd_locked"]) - usd_from_sell)
    balances["btc_available"] = dec_str(dec(balances["btc_available"]) + btc_rebought)

    active["phase"] = "C"
    active["closed_at_utc"] = fmt_utc(at)
    active["close_reason"] = reason
    active["rebuy_fill_price"] = money_str(fill_price)
    active["btc_rebought"] = dec_str(btc_rebought)
    active["btc_delta"] = dec_str(btc_delta)
    sync_cycle_record(state)
    append_event(
        state,
        "cycle_closed",
        at,
        {
            "cycle_id": active["cycle_id"],
            "reason": reason,
            "btc_delta": active["btc_delta"],
        },
    )
    state["active_cycle"] = None


def cancel_untriggered_cycle_at_end(state: dict, *, at: datetime) -> None:
    active = state["active_cycle"]
    if not active:
        raise ValueError("no active cycle to cancel")
    btc_to_sell = dec(active["btc_to_sell"])
    balances = state["balances"]
    balances["btc_locked"] = dec_str(dec(balances["btc_locked"]) - btc_to_sell)
    balances["btc_available"] = dec_str(dec(balances["btc_available"]) + btc_to_sell)
    active["phase"] = "C"
    active["closed_at_utc"] = fmt_utc(at)
    active["close_reason"] = "campaign_end_untriggered"
    active["btc_rebought"] = active["btc_to_sell"]
    active["btc_delta"] = "0.00000000"
    sync_cycle_record(state)
    append_event(
        state,
        "cycle_closed",
        at,
        {
            "cycle_id": active["cycle_id"],
            "reason": "campaign_end_untriggered",
            "btc_delta": active["btc_delta"],
        },
    )
    state["active_cycle"] = None


def tick(state: dict, *, bid: Decimal, ask: Decimal, at: datetime) -> dict:
    require_valid(state)
    if bid <= 0 or ask <= 0:
        raise ValueError("bid and ask must be positive")
    if ask < bid:
        raise ValueError("ask must be greater than or equal to bid")

    state = deepcopy(state)
    state["last_price"] = {
        "bid": money_str(bid),
        "ask": money_str(ask),
        "time_utc": fmt_utc(at),
    }
    state["updated_at_utc"] = fmt_utc(at)

    active = state["active_cycle"]
    if active and active["phase"] == "A" and bid <= dec(active["sell_trigger_price"]):
        btc_to_sell = dec(active["btc_to_sell"])
        sell_fill_price = dec(active["sell_trigger_price"])
        usd_from_sell = btc_to_sell * sell_fill_price
        balances = state["balances"]
        balances["btc_locked"] = dec_str(dec(balances["btc_locked"]) - btc_to_sell)
        balances["usd_locked"] = money_str(dec(balances["usd_locked"]) + usd_from_sell)
        active["phase"] = "B"
        active["sell_filled_at_utc"] = fmt_utc(at)
        active["sell_fill_price"] = money_str(sell_fill_price)
        active["usd_from_sell"] = money_str(usd_from_sell)
        active["time_cap_utc"] = fmt_utc(at + timedelta(hours=TIME_CAP_HOURS))
        sync_cycle_record(state)
        append_event(
            state,
            "sell_trigger_filled",
            at,
            {
                "cycle_id": active["cycle_id"],
                "sell_fill_price": active["sell_fill_price"],
                "usd_from_sell": active["usd_from_sell"],
            },
        )

    active = state["active_cycle"]
    if active and active["phase"] == "B":
        time_cap = parse_utc(active["time_cap_utc"])
        if bid <= dec(active["rebuy_limit_price"]):
            close_active_cycle(
                state,
                at=at,
                reason="rebuy_limit_filled",
                fill_price=dec(active["rebuy_limit_price"]),
            )
        elif at >= time_cap:
            close_active_cycle(
                state,
                at=at,
                reason="time_cap_market_buy",
                fill_price=ask,
            )

    campaign_end = parse_utc(state["ends_at_utc"])
    active = state["active_cycle"]
    if active and at >= campaign_end:
        if active["phase"] == "A":
            cancel_untriggered_cycle_at_end(state, at=at)
        elif active["phase"] == "B":
            close_active_cycle(
                state,
                at=at,
                reason="campaign_end_market_buy",
                fill_price=ask,
            )

    if state["active_cycle"] is None and at >= parse_utc(state["ends_at_utc"]):
        state["status"] = "complete"
        append_event(state, "campaign_completed", at, summary(state))

    return state


def summary(state: dict) -> dict:
    balances = state["balances"]
    btc_available = dec(balances["btc_available"])
    btc_locked = dec(balances["btc_locked"])
    usd_available = dec(balances["usd_available"])
    usd_locked = dec(balances["usd_locked"])
    last_ask = dec(state["last_price"]["ask"])
    starting_price = dec(state["starting_btc_price"])
    starting_btc_equivalent = dec(state["starting_btc"])
    if starting_price > 0:
        starting_btc_equivalent += dec(state["starting_usd"]) / starting_price
    current_btc_equivalent = btc_available + btc_locked
    if last_ask > 0:
        current_btc_equivalent += (usd_available + usd_locked) / last_ask
    closed = [c for c in state["cycles"] if c.get("closed_at_utc")]
    winners = [c for c in closed if dec(c.get("btc_delta")) > 0]
    losers = [c for c in closed if dec(c.get("btc_delta")) < 0]
    flats = [c for c in closed if dec(c.get("btc_delta")) == 0]

    return {
        "status": state["status"],
        "started_at_utc": state["started_at_utc"],
        "ends_at_utc": state["ends_at_utc"],
        "active_cycle": state["active_cycle"]["cycle_id"]
        if state["active_cycle"]
        else None,
        "cycles_opened": len(state["cycles"]),
        "cycles_closed": len(closed),
        "winners": len(winners),
        "losers": len(losers),
        "flats": len(flats),
        "btc_available": dec_str(btc_available),
        "btc_locked": dec_str(btc_locked),
        "usd_available": money_str(usd_available),
        "usd_locked": money_str(usd_locked),
        "starting_btc_equivalent": dec_str(starting_btc_equivalent),
        "current_btc_equivalent": dec_str(current_btc_equivalent),
        "btc_delta_vs_start": dec_str(current_btc_equivalent - starting_btc_equivalent),
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def cmd_init(args) -> None:
    existing = None
    if args.path.exists():
        existing = load_state(args.path)
    state = init_campaign(
        starting_btc=dec(args.starting_btc),
        starting_usd=dec(args.starting_usd),
        starting_btc_price=dec(args.btc_price),
        start=parse_utc(args.start_utc) if args.start_utc else utc_now(),
        force=args.force,
        existing=existing,
    )
    write_state(state, args.path)
    print_json({"ok": True, "state": args.path.as_posix(), "summary": summary(state)})


def cmd_validate(args) -> None:
    state = load_state(args.path)
    errors = validate_state(state)
    if errors:
        print_json({"ok": False, "errors": errors})
        sys.exit(1)
    print_json({"ok": True, "state": args.path.as_posix()})


def cmd_open_cycle(args) -> None:
    state = load_state(args.path)
    state = open_cycle(
        state,
        cycle_id=args.cycle_id,
        playbook_setup=args.playbook_setup,
        grade=args.grade,
        btc_to_sell=dec(args.btc_to_sell),
        sell_trigger_price=dec(args.sell_trigger_price),
        rebuy_limit_price=dec(args.rebuy_limit_price),
        worst_case_rebuy_price=dec(args.worst_case_rebuy_price),
        current_price=dec(args.current_price),
        opened_at=parse_utc(args.opened_at) if args.opened_at else utc_now(),
    )
    write_state(state, args.path)
    print_json({"ok": True, "summary": summary(state), "active_cycle": state["active_cycle"]})


def cmd_tick(args) -> None:
    state = load_state(args.path)
    state = tick(
        state,
        bid=dec(args.bid),
        ask=dec(args.ask),
        at=parse_utc(args.at) if args.at else utc_now(),
    )
    write_state(state, args.path)
    print_json({"ok": True, "summary": summary(state)})


def cmd_summary(args) -> None:
    state = load_state(args.path)
    require_valid(state)
    print_json(summary(state))


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-week BTC paper trading harness")
    parser.add_argument("--path", type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Start or reset a 14-day paper campaign")
    p.add_argument("--starting-btc", required=True)
    p.add_argument("--starting-usd", required=True)
    p.add_argument("--btc-price", required=True)
    p.add_argument("--start-utc")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", help="Validate paper state")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("open-cycle", help="Open a paper sell/rebuy cycle")
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--playbook-setup", required=True)
    p.add_argument("--grade", required=True, choices=sorted(VALID_GRADES))
    p.add_argument("--btc-to-sell", required=True)
    p.add_argument("--sell-trigger-price", required=True)
    p.add_argument("--rebuy-limit-price", required=True)
    p.add_argument("--worst-case-rebuy-price", required=True)
    p.add_argument("--current-price", required=True)
    p.add_argument("--opened-at")
    p.set_defaults(func=cmd_open_cycle)

    p = sub.add_parser("tick", help="Advance the paper broker with bid/ask prices")
    p.add_argument("--bid", required=True)
    p.add_argument("--ask", required=True)
    p.add_argument("--at")
    p.set_defaults(func=cmd_tick)

    p = sub.add_parser("summary", help="Print campaign summary")
    p.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print_json({"ok": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
