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
        self.market_buy_kwargs = None

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

    def market_order_buy(self, **kwargs):
        self.market_buy_kwargs = kwargs
        return {
            "success": True,
            "success_response": {
                "order_id": "market-buy-123",
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

        args = Namespace(
            usd="800.00",
            base=None,
            price="80000",
            post_only=False,
            live=True,
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            coinbase.cmd_limit_buy(args)

        self.assertEqual(fake.limit_buy_kwargs["product_id"], "BTC-USD")
        self.assertEqual(fake.limit_buy_kwargs["base_size"], "0.01000000")
        self.assertEqual(fake.limit_buy_kwargs["limit_price"], "80000")

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["order"]["order_id"], "order-123")
        self.assertEqual(payload["order"]["side"], "BUY")

    def test_limit_buy_defaults_to_dry_run_without_client_call(self):
        fake = FakeClient()
        coinbase._CLIENT = fake

        args = Namespace(usd="800.00", base=None, price="80000", post_only=False)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            coinbase.cmd_limit_buy(args)

        self.assertIsNone(fake.limit_buy_kwargs)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["live"])
        self.assertEqual(payload["action"], "limit_order_gtc_buy")
        self.assertEqual(payload["order"]["product_id"], "BTC-USD")
        self.assertEqual(payload["order"]["side"], "BUY")
        self.assertEqual(payload["order"]["base_size"], "0.01000000")
        self.assertEqual(payload["order"]["limit_price"], "80000")
        self.assertEqual(payload["order"]["status"], "DRY_RUN")

    def test_stop_defaults_to_dry_run_without_client_call(self):
        coinbase._CLIENT = object()

        args = Namespace(base="0.2", stop_price="78000", limit="77610")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            coinbase.cmd_stop(args)

        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["action"], "stop_limit_order_gtc_sell")
        self.assertEqual(payload["order"]["side"], "SELL")
        self.assertEqual(payload["order"]["base_size"], "0.20000000")
        self.assertEqual(payload["order"]["stop_price"], "78000")
        self.assertEqual(payload["order"]["limit_price"], "77610")

    def test_live_market_buy_outputs_normalized_order(self):
        fake = FakeClient()
        coinbase._CLIENT = fake

        args = Namespace(usd="25.00", base=None, live=True)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            coinbase.cmd_buy(args)

        self.assertEqual(fake.market_buy_kwargs["quote_size"], "25.00")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["order"]["order_id"], "market-buy-123")
        self.assertEqual(payload["order"]["side"], "BUY")
        self.assertTrue(payload["order"]["success"])

    def test_other_write_commands_default_to_dry_run(self):
        coinbase._CLIENT = object()
        cases = [
            (coinbase.cmd_buy, Namespace(usd="25.00", base=None), "market_order_buy"),
            (
                coinbase.cmd_sell,
                Namespace(pct=None, base="0.01000000"),
                "market_order_sell",
            ),
            (coinbase.cmd_cancel, Namespace(order_id="order-1"), "cancel_orders"),
            (coinbase.cmd_cancel_all, Namespace(), "cancel_all_open_orders"),
            (
                coinbase.cmd_close,
                Namespace(confirm_sell_all=True),
                "close_all_btc",
            ),
        ]

        for func, args, action in cases:
            with self.subTest(action=action):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    func(args)

                payload = json.loads(stdout.getvalue())
                self.assertTrue(payload["dry_run"])
                self.assertFalse(payload["live"])
                self.assertEqual(payload["action"], action)

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

    def test_normalize_order_response_maps_rejected_create_order(self):
        payload = coinbase.normalize_order_response(
            {
                "success": False,
                "error_response": {
                    "error": "INSUFFICIENT_FUND",
                    "message": "insufficient funds",
                },
            }
        )

        self.assertFalse(payload["order"]["success"])
        self.assertEqual(payload["order"]["reject_reason"], "INSUFFICIENT_FUND")
        self.assertEqual(payload["order"]["reject_message"], "insufficient funds")

    def test_normalize_order_preserves_terminal_statuses(self):
        for status in ("FILLED", "CANCELLED", "PARTIAL_FILL"):
            with self.subTest(status=status):
                order = coinbase.normalize_order(
                    {
                        "order_id": f"order-{status}",
                        "client_order_id": f"client-{status}",
                        "product_id": "BTC-USD",
                        "side": "BUY",
                        "status": status,
                    }
                )

                self.assertEqual(order["status"], status)

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
