#!/usr/bin/env python3
"""Coinbase Advanced Trade wrapper. All trading API calls go through here.

Usage:
    python scripts/coinbase.py <subcommand> [args...]

Subcommands:
    account, position, quote, product, orders, order, fills, buy, limit-buy,
    sell, stop, cancel, cancel-all, close

Mutating subcommands default to dry-run. Add --live only after the relevant
policy or kill-switch gate has passed and the caller is intentionally placing
or cancelling orders.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # cloud runner may not need it
    load_dotenv = None

# Prevent this file (coinbase.py) from shadowing the coinbase-advanced-py package
sys.path = [p for p in sys.path if os.path.abspath(p) != os.path.dirname(os.path.abspath(__file__))]

import base64
import secrets as _secrets

import jwt as _jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from coinbase import jwt_generator as _jg
from coinbase.rest import RESTClient  # coinbase-advanced-py


def _build_jwt_compat(key_var: str, secret_var: str, uri: str | None = None) -> str:
    """SDK v1.8.2 only signs ES256+PEM; Coinbase now issues Ed25519 CDP keys.
    Detect Ed25519 base64 secrets and sign EdDSA; fall through to PEM/ES256."""
    if "BEGIN" in secret_var:
        private_key = serialization.load_pem_private_key(
            secret_var.encode("utf-8"), password=None
        )
        algorithm = "ES256"
    else:
        raw = base64.b64decode(secret_var)
        if len(raw) not in (32, 64):
            raise ValueError(
                f"Ed25519 secret must decode to 32 or 64 bytes, got {len(raw)}"
            )
        private_key = Ed25519PrivateKey.from_private_bytes(raw[:32])
        algorithm = "EdDSA"

    payload = {
        "sub": key_var,
        "iss": "cdp",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 120,
    }
    if uri:
        payload["uri"] = uri
    return _jwt.encode(
        payload,
        private_key,
        algorithm=algorithm,
        headers={"kid": key_var, "nonce": _secrets.token_hex()},
    )


_jg.build_jwt = _build_jwt_compat

PRODUCT = "BTC-USD"
ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

if load_dotenv and ENV_FILE.exists():
    load_dotenv(ENV_FILE)

_CLIENT: RESTClient | None = None


def _client() -> RESTClient:
    """Create the Coinbase client lazily so tests can import this module."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = os.getenv("COINBASE_API_KEY")
    api_secret = os.getenv("COINBASE_API_SECRET")

    if not api_key:
        print("COINBASE_API_KEY not set in environment", file=sys.stderr)
        sys.exit(3)
    if not api_secret:
        print("COINBASE_API_SECRET not set in environment", file=sys.stderr)
        sys.exit(3)

    _CLIENT = RESTClient(api_key=api_key, api_secret=api_secret)
    return _CLIENT


def _as_dict(obj):
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()
    return obj


def _dump(obj) -> None:
    """Dump any SDK response as pretty JSON for the agent to parse."""
    obj = _as_dict(obj)
    print(json.dumps(obj, indent=2, default=str))


def _q(n: Decimal, places: int) -> str:
    """Quantize down to `places` decimal places, return string."""
    quant = Decimal(10) ** -places
    return str(n.quantize(quant, rounding=ROUND_DOWN))


def _is_live(args) -> bool:
    return bool(getattr(args, "live", False))


def _dry_run_payload(action: str, **fields) -> dict:
    return {
        "dry_run": True,
        "live": False,
        "action": action,
        **fields,
    }


def _dry_run_order(action: str, order: dict, **fields) -> None:
    order = {
        "order_id": None,
        "status": "DRY_RUN",
        "success": True,
        **order,
    }
    _dump(_dry_run_payload(action, order=normalize_order(order), **fields))


def _dry_run_notice(action: str, **fields) -> None:
    _dump(_dry_run_payload(action, **fields))


def _order_config(order: dict) -> tuple[str | None, dict]:
    cfg = order.get("order_configuration") or order.get("order_config") or {}
    if not isinstance(cfg, dict):
        return None, {}
    for name, value in cfg.items():
        if isinstance(value, dict):
            return name, value
    return None, {}


def _pick(order: dict, cfg: dict, *keys: str):
    for key in keys:
        if key in order and order[key] not in ("", None):
            return order[key]
        if key in cfg and cfg[key] not in ("", None):
            return cfg[key]
    return None


def normalize_order(order_obj: dict) -> dict:
    """Normalize Coinbase order-ish objects to stable fields for routines."""
    order = _as_dict(order_obj)
    if not isinstance(order, dict):
        return {"raw": order}

    error_response = order.get("error_response")
    if not isinstance(error_response, dict):
        error_response = {}

    # CreateOrderResponse nests the useful fields under success_response.
    if "success_response" in order and isinstance(order["success_response"], dict):
        base = dict(order["success_response"])
        base["success"] = order.get("success")
        if order.get("error_response"):
            base["error_response"] = order.get("error_response")
        order = base
        error_response = order.get("error_response")
        if not isinstance(error_response, dict):
            error_response = {}

    cfg_name, cfg = _order_config(order)
    order_type = order.get("order_type") or cfg_name

    return {
        "order_id": order.get("order_id"),
        "client_order_id": order.get("client_order_id"),
        "product_id": order.get("product_id"),
        "side": order.get("side"),
        "type": order_type,
        "status": order.get("status"),
        "time_in_force": order.get("time_in_force"),
        "base_size": _pick(order, cfg, "base_size"),
        "quote_size": _pick(order, cfg, "quote_size"),
        "limit_price": _pick(order, cfg, "limit_price"),
        "stop_price": _pick(order, cfg, "stop_price"),
        "stop_direction": _pick(order, cfg, "stop_direction"),
        "post_only": _pick(order, cfg, "post_only"),
        "filled_size": order.get("filled_size"),
        "filled_value": order.get("filled_value"),
        "average_fill_price": order.get("average_filled_price")
        or order.get("average_fill_price"),
        "total_fees": order.get("total_fees") or order.get("commission"),
        "number_of_fills": order.get("number_of_fills"),
        "created_time": order.get("created_time"),
        "last_fill_time": order.get("last_fill_time"),
        "success": order.get("success"),
        "reject_reason": order.get("reject_reason")
        or error_response.get("reject_reason")
        or error_response.get("error"),
        "reject_message": order.get("reject_message")
        or error_response.get("message")
        or error_response.get("error_details"),
    }


def normalize_order_response(resp) -> dict:
    data = _as_dict(resp)
    if isinstance(data, dict) and isinstance(data.get("orders"), list):
        return {
            "orders": [normalize_order(o) for o in data["orders"]],
            "cursor": data.get("cursor"),
            "has_next": data.get("has_next"),
        }
    if isinstance(data, dict) and isinstance(data.get("order"), dict):
        return {"order": normalize_order(data["order"])}
    if isinstance(data, dict) and (
        "success_response" in data or "error_response" in data
    ):
        return {"order": normalize_order(data)}
    return data


def summarize_fills(resp) -> dict:
    data = _as_dict(resp)
    fills = data.get("fills", []) if isinstance(data, dict) else []
    total_size = Decimal("0")
    total_value = Decimal("0")
    total_fees = Decimal("0")
    normalized = []
    for fill in fills:
        fill = _as_dict(fill)
        if not isinstance(fill, dict):
            continue
        price = Decimal(str(fill.get("price", "0") or "0"))
        size = Decimal(str(fill.get("size", "0") or "0"))
        commission = Decimal(str(fill.get("commission", "0") or "0"))
        total_size += size
        total_value += price * size
        total_fees += commission
        normalized.append(fill)
    average_fill_price = total_value / total_size if total_size else None
    return {
        "fills": normalized,
        "summary": {
            "fill_count": len(normalized),
            "total_size": str(total_size),
            "total_value": str(total_value),
            "average_fill_price": str(average_fill_price) if average_fill_price else None,
            "total_fees": str(total_fees),
        },
        "cursor": data.get("cursor") if isinstance(data, dict) else None,
    }


def cmd_account(args) -> None:
    client = _client()
    accounts = client.get_accounts()
    usd_bal = Decimal("0")
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        cur = a["currency"]
        avail = Decimal(a["available_balance"]["value"])
        if cur == "USD":
            usd_bal += avail
        elif cur == "BTC":
            btc_bal += avail
    bid_ask = client.get_best_bid_ask(product_ids=[PRODUCT])
    price = Decimal(bid_ask["pricebooks"][0]["bids"][0]["price"])
    equity = usd_bal + btc_bal * price
    _dump({
        "usd_balance": str(usd_bal),
        "btc_balance": str(btc_bal),
        "btc_price": str(price),
        "equity_usd": str(equity),
    })


def cmd_position(args) -> None:
    client = _client()
    accounts = client.get_accounts()
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        if a["currency"] == "BTC":
            btc_bal += Decimal(a["available_balance"]["value"])
    bid_ask = client.get_best_bid_ask(product_ids=[PRODUCT])
    price = Decimal(bid_ask["pricebooks"][0]["bids"][0]["price"])
    _dump({
        "product_id": PRODUCT,
        "size_btc": str(btc_bal),
        "current_price": str(price),
        "notional_usd": str(btc_bal * price),
        "has_position": btc_bal > Decimal("0.00001"),
    })


def cmd_quote(args) -> None:
    client = _client()
    product = args.product or PRODUCT
    bid_ask = client.get_best_bid_ask(product_ids=[product])
    pb = bid_ask["pricebooks"][0]
    _dump({
        "product_id": product,
        "bid": pb["bids"][0]["price"] if pb["bids"] else None,
        "ask": pb["asks"][0]["price"] if pb["asks"] else None,
        "time": pb["time"],
    })


def cmd_orders(args) -> None:
    client = _client()
    status = args.status.upper() if args.status else "OPEN"
    resp = client.list_orders(order_status=[status], product_ids=[PRODUCT])
    _dump(normalize_order_response(resp))


def cmd_order(args) -> None:
    resp = _client().get_order(args.order_id)
    _dump(normalize_order_response(resp))


def cmd_fills(args) -> None:
    resp = _client().get_fills(order_ids=[args.order_id], product_ids=[PRODUCT])
    _dump(summarize_fills(resp))


def cmd_product(args) -> None:
    product = args.product or PRODUCT
    _dump(_client().get_product(product_id=product))


def cmd_buy(args) -> None:
    coid = str(uuid.uuid4())
    if args.usd:
        usd = Decimal(args.usd).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if not _is_live(args):
            _dry_run_order(
                "market_order_buy",
                {
                    "client_order_id": coid,
                    "product_id": PRODUCT,
                    "side": "BUY",
                    "order_type": "market_market_ioc",
                    "quote_size": str(usd),
                },
            )
            return
        client = _client()
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            quote_size=str(usd),
        )
    elif args.base:
        btc = Decimal(args.base)
        if not _is_live(args):
            _dry_run_order(
                "market_order_buy",
                {
                    "client_order_id": coid,
                    "product_id": PRODUCT,
                    "side": "BUY",
                    "order_type": "market_market_ioc",
                    "base_size": _q(btc, 8),
                },
            )
            return
        client = _client()
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(btc, 8),
        )
    else:
        print("usage: buy --usd <amt> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(normalize_order_response(resp))


def cmd_limit_buy(args) -> None:
    coid = str(uuid.uuid4())
    limit_price = Decimal(args.price)
    if args.usd:
        usd = Decimal(args.usd).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        btc = usd / limit_price
    elif args.base:
        btc = Decimal(args.base)
    else:
        print("usage: limit-buy --usd <amt> OR --base <btc>", file=sys.stderr)
        sys.exit(1)

    if not _is_live(args):
        _dry_run_order(
            "limit_order_gtc_buy",
            {
                "client_order_id": coid,
                "product_id": PRODUCT,
                "side": "BUY",
                "order_type": "limit_limit_gtc",
                "base_size": _q(btc, 8),
                "quote_size": str(usd) if args.usd else None,
                "limit_price": str(limit_price),
                "post_only": args.post_only,
            },
        )
        return

    client = _client()
    resp = client.limit_order_gtc_buy(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(btc, 8),
        limit_price=str(limit_price),
        post_only=args.post_only,
    )
    _dump(normalize_order_response(resp))


def cmd_sell(args) -> None:
    coid = str(uuid.uuid4())
    if args.pct is not None:
        if not _is_live(args):
            _dry_run_order(
                "market_order_sell",
                {
                    "client_order_id": coid,
                    "product_id": PRODUCT,
                    "side": "SELL",
                    "order_type": "market_market_ioc",
                },
                percent=str(args.pct),
                requires_live_balance_lookup=True,
            )
            return
        client = _client()
        accounts = client.get_accounts()
        btc_bal = Decimal("0")
        for a in accounts["accounts"]:
            if a["currency"] == "BTC":
                btc_bal = Decimal(a["available_balance"]["value"])
                break
        if btc_bal <= 0:
            print("no BTC balance to sell", file=sys.stderr)
            sys.exit(2)
        size = (btc_bal * Decimal(args.pct) / Decimal(100))
        resp = client.market_order_sell(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(size, 8),
        )
    elif args.base:
        if not _is_live(args):
            _dry_run_order(
                "market_order_sell",
                {
                    "client_order_id": coid,
                    "product_id": PRODUCT,
                    "side": "SELL",
                    "order_type": "market_market_ioc",
                    "base_size": _q(Decimal(args.base), 8),
                },
            )
            return
        client = _client()
        resp = client.market_order_sell(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(Decimal(args.base), 8),
        )
    else:
        print("usage: sell --pct <n> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(normalize_order_response(resp))


def cmd_stop(args) -> None:
    coid = str(uuid.uuid4())
    if not _is_live(args):
        _dry_run_order(
            "stop_limit_order_gtc_sell",
            {
                "client_order_id": coid,
                "product_id": PRODUCT,
                "side": "SELL",
                "order_type": "stop_limit_stop_limit_gtc",
                "base_size": _q(Decimal(args.base), 8),
                "limit_price": str(Decimal(args.limit)),
                "stop_price": str(Decimal(args.stop_price)),
                "stop_direction": "STOP_DIRECTION_STOP_DOWN",
            },
        )
        return
    client = _client()
    resp = client.stop_limit_order_gtc_sell(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(Decimal(args.base), 8),
        limit_price=str(Decimal(args.limit)),
        stop_price=str(Decimal(args.stop_price)),
        stop_direction="STOP_DIRECTION_STOP_DOWN",
    )
    _dump(normalize_order_response(resp))


def cmd_cancel(args) -> None:
    if not _is_live(args):
        _dry_run_notice("cancel_orders", order_ids=[args.order_id])
        return
    resp = _client().cancel_orders(order_ids=[args.order_id])
    _dump(normalize_order_response(resp))


def cmd_cancel_all(args) -> None:
    if not _is_live(args):
        _dry_run_notice(
            "cancel_all_open_orders",
            product_id=PRODUCT,
            order_status=["OPEN"],
        )
        return
    client = _client()
    open_orders = _as_dict(client.list_orders(order_status=["OPEN"], product_ids=[PRODUCT]))
    ids = [o["order_id"] for o in open_orders.get("orders", [])]
    if not ids:
        _dump({"cancelled": 0, "order_ids": []})
        return
    resp = client.cancel_orders(order_ids=ids)
    _dump(normalize_order_response(resp))


def cmd_close(args) -> None:
    if not args.confirm_sell_all:
        print(
            "close sells the entire available BTC balance; rerun with "
            "--confirm-sell-all to proceed",
            file=sys.stderr,
        )
        sys.exit(1)
    if not _is_live(args):
        _dry_run_notice(
            "close_all_btc",
            product_id=PRODUCT,
            side="SELL",
            requires_live_balance_lookup=True,
        )
        return
    client = _client()
    accounts = client.get_accounts()
    btc_bal = Decimal("0")
    for a in accounts["accounts"]:
        if a["currency"] == "BTC":
            btc_bal += Decimal(a["available_balance"]["value"])
    if btc_bal <= Decimal("0.00001"):
        _dump({"closed": False, "reason": "no BTC position"})
        return
    coid = str(uuid.uuid4())
    resp = client.market_order_sell(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(btc_bal, 8),
    )
    _dump(normalize_order_response(resp))


def add_execution_flags(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the intended write without placing/cancelling orders (default)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="place or cancel real Coinbase orders; use only after relevant gates pass",
    )


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("account")
    sub.add_parser("position")

    sp = sub.add_parser("quote")
    sp.add_argument("product", nargs="?", default=PRODUCT)

    sp = sub.add_parser("product")
    sp.add_argument("product", nargs="?", default=PRODUCT)

    sp = sub.add_parser("orders")
    sp.add_argument("status", nargs="?", default="OPEN")

    sp = sub.add_parser("order")
    sp.add_argument("order_id")

    sp = sub.add_parser("fills")
    sp.add_argument("order_id")

    sp = sub.add_parser("buy")
    sp.add_argument("--usd")
    sp.add_argument("--base")
    add_execution_flags(sp)

    sp = sub.add_parser("limit-buy")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--usd")
    g.add_argument("--base")
    sp.add_argument("--price", required=True)
    sp.add_argument("--post-only", action="store_true")
    add_execution_flags(sp)

    sp = sub.add_parser("sell")
    sp.add_argument("--pct", type=Decimal)
    sp.add_argument("--base")
    add_execution_flags(sp)

    sp = sub.add_parser("stop")
    sp.add_argument("--base", required=True)
    sp.add_argument("--stop-price", required=True)
    sp.add_argument("--limit", required=True)
    add_execution_flags(sp)

    sp = sub.add_parser("cancel")
    sp.add_argument("order_id")
    add_execution_flags(sp)

    sp = sub.add_parser("cancel-all")
    add_execution_flags(sp)
    sp = sub.add_parser("close")
    sp.add_argument("--confirm-sell-all", action="store_true")
    add_execution_flags(sp)

    args = p.parse_args()

    handlers = {
        "account": cmd_account,
        "position": cmd_position,
        "quote": cmd_quote,
        "product": cmd_product,
        "orders": cmd_orders,
        "order": cmd_order,
        "fills": cmd_fills,
        "buy": cmd_buy,
        "limit-buy": cmd_limit_buy,
        "sell": cmd_sell,
        "stop": cmd_stop,
        "cancel": cmd_cancel,
        "cancel-all": cmd_cancel_all,
        "close": cmd_close,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
