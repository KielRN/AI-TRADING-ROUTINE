#!/usr/bin/env python3
"""BTC-denominated risk math helpers for the accumulation bot."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal


def cycle_unrealized_r(
    btc_to_sell: Decimal,
    sell_fill_price: Decimal,
    current_ask: Decimal,
    worst_case_rebuy_price: Decimal,
) -> dict[str, str]:
    """Return current Phase-B loss in R units.

    Positive R means the cycle is losing BTC versus the original sell amount.
    Negative R means the cycle is favorable because BTC can be bought back
    below the sell fill price.
    """
    if btc_to_sell <= 0:
        raise ValueError("btc_to_sell must be positive")
    if sell_fill_price <= 0:
        raise ValueError("sell_fill_price must be positive")
    if current_ask <= 0:
        raise ValueError("current_ask must be positive")
    if worst_case_rebuy_price <= sell_fill_price:
        raise ValueError("worst_case_rebuy_price must exceed sell_fill_price")

    usd_from_sell = btc_to_sell * sell_fill_price
    btc_at_market_now = usd_from_sell / current_ask
    btc_at_worst_case = usd_from_sell / worst_case_rebuy_price
    btc_at_risk_1r = btc_to_sell - btc_at_worst_case
    if btc_at_risk_1r <= 0:
        raise ValueError("btc_at_risk_1r must be positive")

    unrealized_btc_loss = btc_to_sell - btc_at_market_now
    unrealized_r = unrealized_btc_loss / btc_at_risk_1r

    return {
        "usd_from_sell": str(usd_from_sell),
        "btc_at_market_now": str(btc_at_market_now),
        "btc_at_worst_case": str(btc_at_worst_case),
        "btc_at_risk_1r": str(btc_at_risk_1r),
        "unrealized_btc_loss": str(unrealized_btc_loss),
        "unrealized_r": str(unrealized_r),
        "force_close": str(unrealized_r >= Decimal("1.5")).lower(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC accumulation risk math")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("cycle-r", help="Compute Phase-B unrealized R")
    p.add_argument("--btc-to-sell", required=True)
    p.add_argument("--sell-fill-price", required=True)
    p.add_argument("--current-ask", required=True)
    p.add_argument("--worst-case-rebuy-price", required=True)

    args = parser.parse_args()
    if args.cmd == "cycle-r":
        result = cycle_unrealized_r(
            btc_to_sell=Decimal(args.btc_to_sell),
            sell_fill_price=Decimal(args.sell_fill_price),
            current_ask=Decimal(args.current_ask),
            worst_case_rebuy_price=Decimal(args.worst_case_rebuy_price),
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

