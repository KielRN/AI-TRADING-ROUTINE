from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from scripts.cycle_orders import DEFAULT_LOCK, open_cycle_orders, routine_lock, cmd_open_cycle
from scripts.policy import parse_utc
from scripts.state import write_state_atomic


def base_state() -> dict:
    return {
        "schema_version": 1,
        "updated_at_utc": None,
        "quarterly_start_btc": "1.00000000",
        "drawdown_halt": False,
        "active_cycle": False,
        "active_cycle_detail": None,
        "last_losing_cycle_utc": None,
        "consecutive_losing_cycles": 0,
        "cycles_opened": [],
    }


class FakeClient:
    def __init__(self, *, fail_rebuy: bool = False):
        self.fail_rebuy = fail_rebuy
        self.sell_kwargs = None
        self.rebuy_kwargs = None
        self.cancelled_ids = []

    def stop_limit_order_gtc_sell(self, **kwargs):
        self.sell_kwargs = kwargs
        return {
            "success": True,
            "success_response": {
                "order_id": "sell-123",
                "client_order_id": kwargs["client_order_id"],
                "product_id": kwargs["product_id"],
                "side": "SELL",
            },
        }

    def limit_order_gtc_buy(self, **kwargs):
        self.rebuy_kwargs = kwargs
        if self.fail_rebuy:
            raise RuntimeError("rebuy rejected")
        return {
            "success": True,
            "success_response": {
                "order_id": "rebuy-123",
                "client_order_id": kwargs["client_order_id"],
                "product_id": kwargs["product_id"],
                "side": "BUY",
            },
        }

    def cancel_orders(self, **kwargs):
        self.cancelled_ids.extend(kwargs["order_ids"])
        return {"cancelled": len(kwargs["order_ids"]), "order_ids": kwargs["order_ids"]}


class RecoveringClient(FakeClient):
    def __init__(self):
        super().__init__(fail_rebuy=True)

    def list_orders(self, **kwargs):
        return {
            "orders": [
                {
                    "order_id": "sell-123",
                    "client_order_id": self.sell_kwargs["client_order_id"],
                    "product_id": self.sell_kwargs["product_id"],
                    "side": "SELL",
                    "status": "OPEN",
                },
                {
                    "order_id": "rebuy-123",
                    "client_order_id": self.rebuy_kwargs["client_order_id"],
                    "product_id": self.rebuy_kwargs["product_id"],
                    "side": "BUY",
                    "status": "OPEN",
                },
            ]
        }


class CycleOrdersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = parse_utc("2026-04-25T12:00:00Z")

    def open(self, **overrides):
        params = {
            "state": base_state(),
            "cycle_id": "cycle-test-1",
            "product_id": "BTC-USD",
            "playbook_setup": "catalyst_driven_breakdown",
            "btc_stack": Decimal("1.00000000"),
            "btc_equivalent_stack": Decimal("1.00000000"),
            "btc_to_sell": Decimal("0.20000000"),
            "sell_trigger_price": Decimal("78000"),
            "rebuy_limit_price": Decimal("74000"),
            "worst_case_rebuy_price": Decimal("79500"),
            "current_price": Decimal("80000"),
            "usd_reserve_pct": Decimal("15"),
            "research_fetched_at": self.now - timedelta(minutes=30),
            "now": self.now,
        }
        params.update(overrides)
        return open_cycle_orders(**params)

    def test_dry_run_plans_paired_orders_after_policy_passes(self):
        result = self.open()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "planned")
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["policy"]["ok"])
        self.assertEqual(result["plan"]["expected_usd"], "15600.00")
        self.assertEqual(result["plan"]["stop_limit_price"], "77610.00")
        self.assertEqual(result["plan"]["sell_trigger"]["client_order_id"], "cycle-test-1-sell-trigger")
        self.assertEqual(result["plan"]["sell_trigger"]["base_size"], "0.20000000")
        self.assertEqual(result["plan"]["rebuy_limit"]["client_order_id"], "cycle-test-1-rebuy-limit")
        self.assertEqual(result["plan"]["rebuy_limit"]["base_size"], "0.21081081")

    def test_policy_rejection_blocks_before_live_client_use(self):
        state = base_state()
        state["drawdown_halt"] = True
        fake = FakeClient()

        result = self.open(state=state, live=True, client=fake)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("drawdown_halt is active", result["policy"]["errors"])
        self.assertIsNone(fake.sell_kwargs)

    def test_dry_run_can_exercise_rebuy_failure_rollback_path(self):
        result = self.open(simulate_rebuy_failure=True)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(result["reason"], "simulated_rebuy_failure")
        self.assertEqual(result["rollback"]["action"], "cancel_orders")
        self.assertEqual(result["rollback"]["order_ids"], ["<sell_order_id>"])
        self.assertEqual(result["rollback"]["sell_client_order_id"], "cycle-test-1-sell-trigger")

    def test_live_open_places_sell_then_rebuy(self):
        fake = FakeClient()

        result = self.open(live=True, client=fake)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "opened")
        self.assertEqual(result["sell_order"]["order_id"], "sell-123")
        self.assertEqual(result["rebuy_order"]["order_id"], "rebuy-123")
        self.assertEqual(fake.sell_kwargs["client_order_id"], "cycle-test-1-sell-trigger")
        self.assertEqual(fake.rebuy_kwargs["client_order_id"], "cycle-test-1-rebuy-limit")
        self.assertEqual(fake.rebuy_kwargs["base_size"], "0.21081081")
        self.assertEqual(fake.cancelled_ids, [])
        self.assertEqual(result["idempotency_key"], "open-cycle:cycle-test-1")

    def test_live_rebuy_failure_rolls_back_sell_order(self):
        fake = FakeClient(fail_rebuy=True)

        result = self.open(live=True, client=fake)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(result["reason"], "rebuy_rejected")
        self.assertEqual(result["sell_order"]["order_id"], "sell-123")
        self.assertEqual(result["rebuy_error"], "rebuy rejected")
        self.assertEqual(fake.cancelled_ids, ["sell-123"])
        self.assertEqual(result["rollback"]["ok"], True)

    def test_live_rebuy_exception_recovers_existing_rebuy_order(self):
        fake = RecoveringClient()

        result = self.open(live=True, client=fake)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "opened")
        self.assertTrue(result["rebuy_recovered_after_exception"])
        self.assertEqual(result["rebuy_order"]["order_id"], "rebuy-123")
        self.assertEqual(fake.cancelled_ids, [])

    def test_cli_live_open_persists_state_atomically(self):
        fake = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            write_state_atomic(base_state(), state_path)
            args = Namespace(
                state=state_path,
                cycle_id="cycle-test-1",
                product="BTC-USD",
                playbook_setup="catalyst_driven_breakdown",
                btc_stack="1.00000000",
                btc_equivalent_stack="1.00000000",
                btc_to_sell="0.20000000",
                sell_trigger_price="78000",
                rebuy_limit_price="74000",
                worst_case_rebuy_price="79500",
                current_price="80000",
                usd_reserve_pct="15",
                research_fetched_at="2026-04-25T11:30:00Z",
                max_research_age_hours="3",
                expected_usd=None,
                stop_limit_price=None,
                post_only=False,
                live=True,
                simulate_rebuy_failure=False,
                now="2026-04-25T12:00:00Z",
                run_id="scheduled-run-1",
                lock_file=Path(tmp) / "cycle-orders.lock",
                no_lock=True,
            )

            stdout = io.StringIO()
            with patch("scripts.cycle_orders.coinbase._client", return_value=fake):
                with contextlib.redirect_stdout(stdout):
                    code = cmd_open_cycle(args)

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["state_updated"])
            self.assertEqual(payload["idempotency_key"], "scheduled-run-1")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state["active_cycle"])
            self.assertEqual(state["active_cycle_detail"]["phase"], "A")
            self.assertEqual(state["active_cycle_detail"]["sell_order_id"], "sell-123")
            self.assertEqual(
                state["active_cycle_detail"]["sell_client_order_id"],
                "cycle-test-1-sell-trigger",
            )

    def test_routine_lock_blocks_second_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / DEFAULT_LOCK.name
            with routine_lock(lock_path, run_id="run-1", now=self.now):
                with self.assertRaises(RuntimeError):
                    with routine_lock(lock_path, run_id="run-2", now=self.now):
                        pass


if __name__ == "__main__":
    unittest.main()
