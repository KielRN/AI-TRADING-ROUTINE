#!/usr/bin/env python3
"""Code-owned paired cycle order transaction.

This is the only order-writing helper for opening a v2 accumulation cycle:
policy gate first, then sell-trigger plus paired re-entry as one transaction.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != SCRIPT_DIR]

try:
    from scripts import coinbase
    from scripts.policy import (
        DEFAULT_MAX_RESEARCH_AGE_HOURS,
        PRODUCT,
        fmt_utc,
        parse_utc,
        utc_now,
        validate_cycle_open,
    )
    from scripts.state import DEFAULT_STATE, load_state
    from scripts.state import open_cycle as state_open_cycle
    from scripts.state import write_state_atomic
except ImportError:  # pragma: no cover - direct script execution from scripts/
    import coinbase
    from policy import (
        DEFAULT_MAX_RESEARCH_AGE_HOURS,
        PRODUCT,
        fmt_utc,
        parse_utc,
        utc_now,
        validate_cycle_open,
    )
    from state import DEFAULT_STATE, load_state
    from state import open_cycle as state_open_cycle
    from state import write_state_atomic

STOP_LIMIT_BUFFER = Decimal("0.995")
TIME_CAP = timedelta(hours=72)
DEFAULT_LOCK = ROOT / "memory" / ".locks" / "cycle-orders.lock"


def dec(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def q_base(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN), "f")


def q_money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_DOWN), "f")


def stable_client_order_id(cycle_id: str, role: str) -> str:
    safe = "".join(c if c.isalnum() or c in {"-", "_"} else "-" for c in cycle_id)
    safe = safe.strip("-_")
    if not safe:
        raise ValueError("cycle_id must contain at least one alphanumeric character")
    client_order_id = f"{safe}-{role}"
    if len(client_order_id) > 96:
        raise ValueError("cycle_id is too long for stable client_order_id")
    return client_order_id


def planned_orders(
    *,
    cycle_id: str,
    product_id: str,
    btc_to_sell: Decimal,
    sell_trigger_price: Decimal,
    rebuy_limit_price: Decimal,
    stop_limit_price: Decimal | None = None,
    expected_usd: Decimal | None = None,
    post_only: bool = False,
) -> dict:
    if stop_limit_price is None:
        stop_limit_price = sell_trigger_price * STOP_LIMIT_BUFFER
    if expected_usd is None:
        expected_usd = btc_to_sell * sell_trigger_price
    if stop_limit_price <= 0:
        raise ValueError("stop_limit_price must be positive")
    if expected_usd <= 0:
        raise ValueError("expected_usd must be positive")

    quote_size = q_money(expected_usd)
    rebuy_base = dec(quote_size, "expected_usd") / rebuy_limit_price

    sell = coinbase.normalize_order(
        {
            "order_id": None,
            "client_order_id": stable_client_order_id(cycle_id, "sell-trigger"),
            "product_id": product_id,
            "side": "SELL",
            "order_type": "stop_limit_stop_limit_gtc",
            "status": "PLANNED",
            "base_size": q_base(btc_to_sell),
            "limit_price": q_money(stop_limit_price),
            "stop_price": q_money(sell_trigger_price),
            "stop_direction": "STOP_DIRECTION_STOP_DOWN",
            "success": True,
        }
    )
    rebuy = coinbase.normalize_order(
        {
            "order_id": None,
            "client_order_id": stable_client_order_id(cycle_id, "rebuy-limit"),
            "product_id": product_id,
            "side": "BUY",
            "order_type": "limit_limit_gtc",
            "status": "PLANNED",
            "base_size": q_base(rebuy_base),
            "quote_size": quote_size,
            "limit_price": q_money(rebuy_limit_price),
            "post_only": post_only,
            "success": True,
        }
    )
    return {
        "sell_trigger": sell,
        "rebuy_limit": rebuy,
        "expected_usd": quote_size,
        "stop_limit_price": sell["limit_price"],
    }


def _normalized_order(resp) -> dict:
    normalized = coinbase.normalize_order_response(resp)
    if isinstance(normalized, dict) and isinstance(normalized.get("order"), dict):
        return normalized["order"]
    return coinbase.normalize_order(resp)


def _order_error(order: dict) -> str | None:
    if not isinstance(order, dict):
        return "order response was not an object"
    if order.get("success") is False:
        return order.get("reject_message") or order.get("reject_reason") or "order rejected"
    if order.get("reject_message") or order.get("reject_reason"):
        return order.get("reject_message") or order.get("reject_reason")
    if not order.get("order_id"):
        return "order response did not include order_id"
    return None


def _rollback_plan(sell_order_id: str | None, sell_client_order_id: str) -> dict:
    return {
        "dry_run": True,
        "live": False,
        "action": "cancel_orders",
        "order_ids": [sell_order_id or "<sell_order_id>"],
        "sell_client_order_id": sell_client_order_id,
    }


def _cancel_sell(client, sell_order: dict, *, dry_run: bool) -> dict:
    order_id = sell_order.get("order_id")
    if dry_run:
        return _rollback_plan(order_id, sell_order["client_order_id"])
    if not order_id:
        return {"ok": False, "error": "cannot cancel sell order without order_id"}
    resp = client.cancel_orders(order_ids=[order_id])
    return {
        "ok": True,
        "action": "cancel_orders",
        "order_ids": [order_id],
        "response": coinbase._as_dict(resp),
    }


def _reload_matching_orders(client, product_id: str, client_order_ids: list[str]) -> dict:
    """Reload open live orders by stable client_order_id after an uncertain write."""
    try:
        resp = client.list_orders(order_status=["OPEN"], product_ids=[product_id])
        normalized = coinbase.normalize_order_response(resp)
        orders = normalized.get("orders", []) if isinstance(normalized, dict) else []
        matches = [
            order
            for order in orders
            if isinstance(order, dict)
            and order.get("client_order_id") in set(client_order_ids)
        ]
        return {"ok": True, "orders": matches}
    except Exception as exc:  # pragma: no cover - defensive around SDK/network
        return {"ok": False, "error": str(exc)}


def _match_by_client_id(reload: dict, client_order_id: str) -> dict | None:
    if not reload.get("ok"):
        return None
    for order in reload.get("orders", []):
        if order.get("client_order_id") == client_order_id:
            return order
    return None


@contextmanager
def routine_lock(path: Path, *, run_id: str, now) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "pid": os.getpid(),
        "started_at_utc": fmt_utc(now),
    }
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = "<unreadable>"
        raise RuntimeError(f"routine lock is held at {path}: {existing}") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def open_cycle_orders(
    *,
    state: dict,
    cycle_id: str,
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
    research_fetched_at,
    now,
    max_research_age_hours: Decimal = DEFAULT_MAX_RESEARCH_AGE_HOURS,
    expected_usd: Decimal | None = None,
    stop_limit_price: Decimal | None = None,
    post_only: bool = False,
    live: bool = False,
    simulate_rebuy_failure: bool = False,
    idempotency_key: str | None = None,
    client=None,
) -> dict:
    policy = validate_cycle_open(
        state=state,
        product_id=product_id,
        playbook_setup=playbook_setup,
        btc_stack=btc_stack,
        btc_equivalent_stack=btc_equivalent_stack,
        btc_to_sell=btc_to_sell,
        sell_trigger_price=sell_trigger_price,
        rebuy_limit_price=rebuy_limit_price,
        worst_case_rebuy_price=worst_case_rebuy_price,
        current_price=current_price,
        usd_reserve_pct=usd_reserve_pct,
        research_fetched_at=research_fetched_at,
        now=now,
        max_research_age_hours=max_research_age_hours,
    )
    base = {
        "dry_run": not live,
        "live": live,
        "cycle_id": cycle_id,
        "idempotency_key": idempotency_key or f"open-cycle:{cycle_id}",
        "product_id": product_id,
        "policy": policy,
        "opened_at_utc": fmt_utc(now),
        "time_cap_utc": fmt_utc(now + TIME_CAP),
    }
    if not policy["ok"]:
        return {"ok": False, "status": "blocked", "reason": "policy", **base}

    plan = planned_orders(
        cycle_id=cycle_id,
        product_id=product_id,
        btc_to_sell=btc_to_sell,
        sell_trigger_price=sell_trigger_price,
        rebuy_limit_price=rebuy_limit_price,
        stop_limit_price=stop_limit_price,
        expected_usd=expected_usd,
        post_only=post_only,
    )
    base["plan"] = plan

    if not live:
        if simulate_rebuy_failure:
            return {
                "ok": True,
                "status": "rolled_back",
                "reason": "simulated_rebuy_failure",
                "sell_order": plan["sell_trigger"],
                "rebuy_error": "simulated re-entry placement failure",
                "rollback": _rollback_plan(None, plan["sell_trigger"]["client_order_id"]),
                **base,
            }
        return {"ok": True, "status": "planned", **base}

    if simulate_rebuy_failure:
        raise ValueError("--simulate-rebuy-failure is only allowed with dry-run")

    client = client or coinbase._client()
    sell_client_order_id = plan["sell_trigger"]["client_order_id"]
    rebuy_client_order_id = plan["rebuy_limit"]["client_order_id"]
    try:
        sell_resp = client.stop_limit_order_gtc_sell(
            client_order_id=sell_client_order_id,
            product_id=product_id,
            base_size=plan["sell_trigger"]["base_size"],
            limit_price=plan["sell_trigger"]["limit_price"],
            stop_price=plan["sell_trigger"]["stop_price"],
            stop_direction="STOP_DIRECTION_STOP_DOWN",
        )
        sell_order = _normalized_order(sell_resp)
    except Exception as exc:  # pragma: no cover - exercised by CLI/integration only
        reload = _reload_matching_orders(
            client, product_id, [sell_client_order_id, rebuy_client_order_id]
        )
        recovered = _match_by_client_id(reload, sell_client_order_id)
        if recovered:
            sell_order = recovered
            base["sell_recovered_after_exception"] = True
            base["live_order_reload"] = reload
        else:
            return {
                "ok": False,
                "status": "blocked",
                "reason": "sell_trigger_exception",
                "error": str(exc),
                "live_order_reload": reload,
                **base,
            }
    sell_error = _order_error(sell_order)
    if sell_error:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "sell_trigger_rejected",
            "error": sell_error,
            "sell_order": sell_order,
            **base,
        }

    try:
        rebuy_resp = client.limit_order_gtc_buy(
            client_order_id=rebuy_client_order_id,
            product_id=product_id,
            base_size=plan["rebuy_limit"]["base_size"],
            limit_price=plan["rebuy_limit"]["limit_price"],
            post_only=post_only,
        )
        rebuy_order = _normalized_order(rebuy_resp)
        rebuy_error = _order_error(rebuy_order)
    except Exception as exc:
        reload = _reload_matching_orders(
            client, product_id, [sell_client_order_id, rebuy_client_order_id]
        )
        recovered = _match_by_client_id(reload, rebuy_client_order_id)
        if recovered:
            rebuy_order = recovered
            rebuy_error = _order_error(rebuy_order)
            base["rebuy_recovered_after_exception"] = True
            base["live_order_reload"] = reload
        else:
            rebuy_order = None
            rebuy_error = str(exc)
            base["live_order_reload"] = reload

    if rebuy_error:
        try:
            rollback = _cancel_sell(client, sell_order, dry_run=False)
        except Exception as exc:  # pragma: no cover - exercised by CLI/integration only
            rollback = {"ok": False, "error": str(exc)}
        return {
            "ok": bool(rollback.get("ok")),
            "status": "rolled_back",
            "reason": "rebuy_rejected",
            "sell_order": sell_order,
            "rebuy_order": rebuy_order,
            "rebuy_error": rebuy_error,
            "rollback": rollback,
            **base,
        }

    return {
        "ok": True,
        "status": "opened",
        "sell_order": sell_order,
        "rebuy_order": rebuy_order,
        **base,
    }


def _persist_opened_state(state_doc: dict, args, result: dict) -> dict:
    next_state = state_open_cycle(
        state_doc,
        cycle_id=args.cycle_id,
        sell_order_id=result["sell_order"]["order_id"],
        rebuy_order_id=result["rebuy_order"]["order_id"],
        sell_client_order_id=result["sell_order"].get("client_order_id"),
        rebuy_client_order_id=result["rebuy_order"].get("client_order_id"),
        btc_to_sell=args.btc_to_sell,
        sell_trigger_price=args.sell_trigger_price,
        rebuy_limit_price=args.rebuy_limit_price,
        worst_case_rebuy_price=args.worst_case_rebuy_price,
        expected_usd=result["plan"].get("expected_usd"),
        stop_limit_price=result["plan"].get("stop_limit_price"),
        cycle_opened_at_utc=result["opened_at_utc"],
        time_cap_utc=result["time_cap_utc"],
        playbook_setup=args.playbook_setup,
    )
    write_state_atomic(next_state, args.state)
    return next_state


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _decimal_arg(value: str, field: str) -> Decimal:
    return dec(value, field)


def _cmd_open_cycle_unlocked(args, *, now, run_id: str) -> int:
    btc_stack = _decimal_arg(args.btc_stack, "btc_stack")
    state_doc = load_state(args.state)
    result = open_cycle_orders(
        state=state_doc,
        cycle_id=args.cycle_id,
        product_id=args.product,
        playbook_setup=args.playbook_setup,
        btc_stack=btc_stack,
        btc_equivalent_stack=_decimal_arg(args.btc_equivalent_stack, "btc_equivalent_stack")
        if args.btc_equivalent_stack
        else btc_stack,
        btc_to_sell=_decimal_arg(args.btc_to_sell, "btc_to_sell"),
        sell_trigger_price=_decimal_arg(args.sell_trigger_price, "sell_trigger_price"),
        rebuy_limit_price=_decimal_arg(args.rebuy_limit_price, "rebuy_limit_price"),
        worst_case_rebuy_price=_decimal_arg(
            args.worst_case_rebuy_price, "worst_case_rebuy_price"
        ),
        current_price=_decimal_arg(args.current_price, "current_price")
        if args.current_price
        else None,
        usd_reserve_pct=_decimal_arg(args.usd_reserve_pct, "usd_reserve_pct"),
        research_fetched_at=parse_utc(args.research_fetched_at),
        now=now,
        max_research_age_hours=_decimal_arg(
            args.max_research_age_hours, "max_research_age_hours"
        ),
        expected_usd=_decimal_arg(args.expected_usd, "expected_usd")
        if args.expected_usd
        else None,
        stop_limit_price=_decimal_arg(args.stop_limit_price, "stop_limit_price")
        if args.stop_limit_price
        else None,
        post_only=args.post_only,
        live=args.live,
        simulate_rebuy_failure=args.simulate_rebuy_failure,
        idempotency_key=run_id,
    )
    if args.live and result["status"] == "opened":
        try:
            _persist_opened_state(state_doc, args, result)
            result["state_updated"] = True
            result["state_path"] = str(args.state)
        except Exception as exc:
            result["state_updated"] = False
            result["state_error"] = str(exc)
            print_json(result)
            return 1
    print_json(result)
    if result["status"] == "blocked":
        return 1
    if result["status"] == "rolled_back" and args.live:
        return 1
    if result["status"] == "rolled_back" and not result.get("ok"):
        return 1
    return 0


def cmd_open_cycle(args) -> int:
    now = parse_utc(args.now) if args.now else utc_now()
    run_id = args.run_id or f"open-cycle:{args.cycle_id}"
    if args.live and not args.no_lock:
        try:
            with routine_lock(args.lock_file, run_id=run_id, now=now):
                return _cmd_open_cycle_unlocked(args, now=now, run_id=run_id)
        except RuntimeError as exc:
            print_json(
                {
                    "ok": False,
                    "status": "blocked",
                    "reason": "routine_lock",
                    "error": str(exc),
                    "idempotency_key": run_id,
                    "lock_file": str(args.lock_file),
                }
            )
            return 1
    return _cmd_open_cycle_unlocked(args, now=now, run_id=run_id)


def add_execution_flags(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="plan only (default)")
    mode.add_argument("--live", action="store_true", help="place real Coinbase orders")


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a v2 BTC cycle transaction")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open-cycle", help="Policy-gate and place a paired cycle")
    p.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p.add_argument("--cycle-id", required=True)
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
    p.add_argument("--expected-usd")
    p.add_argument("--stop-limit-price")
    p.add_argument("--post-only", action="store_true")
    p.add_argument("--simulate-rebuy-failure", action="store_true")
    p.add_argument("--now")
    p.add_argument("--run-id", help="stable idempotency key for the scheduled run")
    p.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    p.add_argument("--no-lock", action="store_true", help="skip the local routine lock")
    add_execution_flags(p)
    p.set_defaults(func=cmd_open_cycle)

    args = parser.parse_args()
    try:
        code = args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print_json({"ok": False, "status": "blocked", "error": str(exc)})
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
