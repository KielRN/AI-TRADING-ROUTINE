from __future__ import annotations

import contextlib
import io
import json
import unittest
from argparse import Namespace

import scripts.coinbase as coinbase


class FakeClient:
    def __init__(self):
        self.limit_buy_kwargs = None

    def limit_order_gtc_buy(self, **kwargs):
        self.limit_buy_kwargs = kwargs
        return {
            "success": True,
            "success_response": {
                "order_id": "order-123",
                "client_order_id": kwargs["client_order_id"],
                "product_id": kwargs["product_id"],
                "side": "BUY",
            },
        }


class CoinbaseWrapperTests(unittest.TestCase):
    def tearDown(self) -> None:
        coinbase._CLIENT = None

    def test_limit_buy_with_usd_converts_to_base_size(self):
        fake = FakeClient()
        coinbase._CLIENT = fake

        args = Namespace(usd="800.00", base=None, price="80000", post_only=False)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            coinbase.cmd_limit_buy(args)

        self.assertEqual(fake.limit_buy_kwargs["product_id"], "BTC-USD")
        self.assertEqual(fake.limit_buy_kwargs["base_size"], "0.01000000")
        self.assertEqual(fake.limit_buy_kwargs["limit_price"], "80000")

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["order"]["order_id"], "order-123")
        self.assertEqual(payload["order"]["side"], "BUY")

    def test_normalize_order_extracts_nested_limit_config(self):
        order = {
            "order_id": "order-456",
            "client_order_id": "client-456",
            "product_id": "BTC-USD",
            "side": "BUY",
            "status": "OPEN",
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": "0.01000000",
                    "limit_price": "80000",
                    "post_only": False,
                }
            },
            "filled_size": "0",
            "average_filled_price": "",
        }

        normalized = coinbase.normalize_order(order)

        self.assertEqual(normalized["type"], "limit_limit_gtc")
        self.assertEqual(normalized["base_size"], "0.01000000")
        self.assertEqual(normalized["limit_price"], "80000")
        self.assertEqual(normalized["status"], "OPEN")

    def test_summarize_fills_computes_weighted_average(self):
        summary = coinbase.summarize_fills(
            {
                "fills": [
                    {"price": "80000", "size": "0.01000000", "commission": "1.00"},
                    {"price": "82000", "size": "0.01000000", "commission": "1.00"},
                ]
            }
        )

        self.assertEqual(summary["summary"]["fill_count"], 2)
        self.assertEqual(summary["summary"]["total_size"], "0.02000000")
        self.assertEqual(summary["summary"]["total_value"], "1620.00000000")
        self.assertEqual(summary["summary"]["average_fill_price"], "81000")
        self.assertEqual(summary["summary"]["total_fees"], "2.00")

    def test_close_requires_explicit_confirmation(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
            coinbase.cmd_close(Namespace(confirm_sell_all=False))

        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
