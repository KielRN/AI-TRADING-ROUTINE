#!/usr/bin/env python3
"""Auditable paper-shadow routine runner.

This script stitches together the deterministic paper steps. It does not do
market analysis; new paper cycles still require a fresh research report from
the research-and-plan agent.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != SCRIPT_DIR]

try:
    from scripts import coinbase
    from scripts.paper_trade import (
        DEFAULT_STATE,
        dec as paper_dec,
        fmt_utc,
        load_state,
        open_cycle,
        parse_utc,
        summary,
        tick,
        utc_now,
        validate_state,
        write_state,
    )
    from scripts.research_gate import (
        DEFAULT_REPORT_DIR,
        latest_report_path,
        validate_research_report,
    )
except ImportError:  # pragma: no cover - direct script execution from scripts/
    import coinbase
    from paper_trade import (
        DEFAULT_STATE,
        dec as paper_dec,
        fmt_utc,
        load_state,
        open_cycle,
        parse_utc,
        summary,
        tick,
        utc_now,
        validate_state,
        write_state,
    )
    from research_gate import (
        DEFAULT_REPORT_DIR,
        latest_report_path,
        validate_research_report,
    )


def dec(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def fetch_quote(product: str) -> dict:
    resp = coinbase._client().get_best_bid_ask(product_ids=[product])
    pb = resp["pricebooks"][0]
    return {
        "product_id": product,
        "bid": pb["bids"][0]["price"] if pb["bids"] else None,
        "ask": pb["asks"][0]["price"] if pb["asks"] else None,
        "time": pb.get("time"),
    }


def _resolve_report(args) -> tuple[Path | None, dict]:
    try:
        path = args.research_report or latest_report_path(args.report_dir)
        gate = validate_research_report(
            path,
            now=parse_utc(args.at) if args.at else utc_now(),
            max_age_minutes=dec(args.max_age_minutes, "max_age_minutes"),
            require_trade_idea=False,
        )
        return path, gate
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {
            "ok": False,
            "path": str(args.research_report or args.report_dir),
            "errors": [str(exc)],
            "warnings": [],
            "require_trade_idea": False,
        }


def _open_requested(args) -> bool:
    return bool(args.cycle_id)


def _validate_open_args(args) -> list[str]:
    if not _open_requested(args):
        return []
    required = [
        "playbook_setup",
        "grade",
        "btc_to_sell",
        "sell_trigger_price",
        "rebuy_limit_price",
        "worst_case_rebuy_price",
    ]
    return [name for name in required if not getattr(args, name)]


def run_shadow(args) -> tuple[int, dict]:
    at = parse_utc(args.at) if args.at else utc_now()
    state = load_state(args.path)
    state_errors = validate_state(state)
    if state_errors:
        return (
            1,
            {
                "ok": False,
                "reason": "paper_state_invalid",
                "state": args.path.as_posix(),
                "errors": state_errors,
            },
        )
    if state.get("status") == "not_started":
        return (
            1,
            {
                "ok": False,
                "reason": "paper_campaign_not_started",
                "state": args.path.as_posix(),
                "error": "initialize with scripts/paper_trade.py init before paper shadow runs",
            },
        )

    report_path, research = _resolve_report(args)

    if args.bid and args.ask:
        quote = {
            "product_id": args.product,
            "bid": str(dec(args.bid, "bid")),
            "ask": str(dec(args.ask, "ask")),
            "time": fmt_utc(at),
            "source": "args",
        }
    else:
        quote = fetch_quote(args.product)

    if not quote.get("bid") or not quote.get("ask"):
        return 1, {"ok": False, "reason": "quote_missing_bid_ask", "quote": quote}

    state = tick(
        state,
        bid=paper_dec(quote["bid"]),
        ask=paper_dec(quote["ask"]),
        at=at,
    )
    write_state(state, args.path)

    result = {
        "ok": True,
        "state": args.path.as_posix(),
        "at_utc": fmt_utc(at),
        "quote": quote,
        "research": research,
        "tick": {"summary": summary(state)},
        "open_requested": _open_requested(args),
        "open_result": None,
    }

    missing_open_args = _validate_open_args(args)
    if missing_open_args:
        result["ok"] = False
        result["open_result"] = {
            "ok": False,
            "reason": "missing_open_args",
            "missing": missing_open_args,
        }
        return 1, result

    if not _open_requested(args):
        return 0, result

    if not report_path:
        result["ok"] = False
        result["open_result"] = {"ok": False, "reason": "research_report_missing"}
        return 1, result

    actionable = validate_research_report(
        report_path,
        now=at,
        max_age_minutes=dec(args.max_age_minutes, "max_age_minutes"),
        require_trade_idea=True,
    )
    result["research"] = actionable
    if not actionable["ok"]:
        result["ok"] = False
        result["open_result"] = {"ok": False, "reason": "research_gate"}
        return 1, result

    state = open_cycle(
        state,
        cycle_id=args.cycle_id,
        playbook_setup=args.playbook_setup,
        grade=args.grade,
        btc_to_sell=paper_dec(args.btc_to_sell),
        sell_trigger_price=paper_dec(args.sell_trigger_price),
        rebuy_limit_price=paper_dec(args.rebuy_limit_price),
        worst_case_rebuy_price=paper_dec(args.worst_case_rebuy_price),
        current_price=paper_dec(quote["bid"]),
        opened_at=at,
    )
    write_state(state, args.path)
    result["open_result"] = {
        "ok": True,
        "active_cycle": state["active_cycle"],
        "summary": summary(state),
    }
    return 0, result


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper shadow workflow")
    parser.add_argument("--path", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--research-report", type=Path)
    parser.add_argument("--max-age-minutes", default="45")
    parser.add_argument("--product", default=coinbase.PRODUCT)
    parser.add_argument("--bid")
    parser.add_argument("--ask")
    parser.add_argument("--at")
    parser.add_argument("--cycle-id")
    parser.add_argument("--playbook-setup")
    parser.add_argument("--grade", choices=["A", "B"])
    parser.add_argument("--btc-to-sell")
    parser.add_argument("--sell-trigger-price")
    parser.add_argument("--rebuy-limit-price")
    parser.add_argument("--worst-case-rebuy-price")

    args = parser.parse_args()
    try:
        code, payload = run_shadow(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        code = 1
        payload = {"ok": False, "error": str(exc)}
    print_json(payload)
    sys.exit(code)


if __name__ == "__main__":
    main()
