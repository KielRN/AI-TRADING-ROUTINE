#!/usr/bin/env python3
"""Coinbase Advanced Trade wrapper. All trading API calls go through here.

Usage:
    python scripts/coinbase.py <subcommand> [args...]

Subcommands:
    account, position, quote, orders, buy, sell, stop, cancel, cancel-all, close
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

API_KEY = os.getenv("COINBASE_API_KEY")
API_SECRET = os.getenv("COINBASE_API_SECRET")

if not API_KEY:
    print("COINBASE_API_KEY not set in environment", file=sys.stderr)
    sys.exit(3)
if not API_SECRET:
    print("COINBASE_API_SECRET not set in environment", file=sys.stderr)
    sys.exit(3)

client = RESTClient(api_key=API_KEY, api_secret=API_SECRET)


def _dump(obj) -> None:
    """Dump any SDK response as pretty JSON for the agent to parse."""
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()
    print(json.dumps(obj, indent=2, default=str))


def _q(n: Decimal, places: int) -> str:
    """Quantize down to `places` decimal places, return string."""
    quant = Decimal(10) ** -places
    return str(n.quantize(quant, rounding=ROUND_DOWN))


def cmd_account(args) -> None:
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
    status = args.status.upper() if args.status else "OPEN"
    resp = client.list_orders(order_status=[status], product_ids=[PRODUCT])
    _dump(resp)


def cmd_buy(args) -> None:
    coid = str(uuid.uuid4())
    if args.usd:
        usd = Decimal(args.usd).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            quote_size=str(usd),
        )
    elif args.base:
        btc = Decimal(args.base)
        resp = client.market_order_buy(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(btc, 8),
        )
    else:
        print("usage: buy --usd <amt> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(resp)


def cmd_sell(args) -> None:
    coid = str(uuid.uuid4())
    if args.pct is not None:
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
        resp = client.market_order_sell(
            client_order_id=coid,
            product_id=PRODUCT,
            base_size=_q(Decimal(args.base), 8),
        )
    else:
        print("usage: sell --pct <n> OR --base <btc>", file=sys.stderr)
        sys.exit(1)
    _dump(resp)


def cmd_stop(args) -> None:
    coid = str(uuid.uuid4())
    resp = client.stop_limit_order_gtc_sell(
        client_order_id=coid,
        product_id=PRODUCT,
        base_size=_q(Decimal(args.base), 8),
        limit_price=str(Decimal(args.limit)),
        stop_price=str(Decimal(args.stop_price)),
        stop_direction="STOP_DIRECTION_STOP_DOWN",
    )
    _dump(resp)


def cmd_cancel(args) -> None:
    resp = client.cancel_orders(order_ids=[args.order_id])
    _dump(resp)


def cmd_cancel_all(args) -> None:
    open_orders = client.list_orders(order_status=["OPEN"], product_ids=[PRODUCT])
    ids = [o["order_id"] for o in open_orders.get("orders", [])]
    if not ids:
        _dump({"cancelled": 0, "order_ids": []})
        return
    resp = client.cancel_orders(order_ids=ids)
    _dump(resp)


def cmd_close(args) -> None:
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
    _dump(resp)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("account")
    sub.add_parser("position")

    sp = sub.add_parser("quote")
    sp.add_argument("product", nargs="?", default=PRODUCT)

    sp = sub.add_parser("orders")
    sp.add_argument("status", nargs="?", default="OPEN")

    sp = sub.add_parser("buy")
    sp.add_argument("--usd")
    sp.add_argument("--base")

    sp = sub.add_parser("sell")
    sp.add_argument("--pct", type=Decimal)
    sp.add_argument("--base")

    sp = sub.add_parser("stop")
    sp.add_argument("--base", required=True)
    sp.add_argument("--stop-price", required=True)
    sp.add_argument("--limit", required=True)

    sp = sub.add_parser("cancel")
    sp.add_argument("order_id")

    sub.add_parser("cancel-all")
    sub.add_parser("close")

    args = p.parse_args()

    handlers = {
        "account": cmd_account,
        "position": cmd_position,
        "quote": cmd_quote,
        "orders": cmd_orders,
        "buy": cmd_buy,
        "sell": cmd_sell,
        "stop": cmd_stop,
        "cancel": cmd_cancel,
        "cancel-all": cmd_cancel_all,
        "close": cmd_close,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
