from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from scripts.policy import parse_utc, validate_cycle_open


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


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = parse_utc("2026-04-25T12:00:00Z")

    def validate(self, **overrides):
        params = {
            "state": base_state(),
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
        return validate_cycle_open(**params)

    def test_valid_cycle_passes_policy(self):
        report = self.validate()

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(Decimal(report["metrics"]["btc_r_r"]), Decimal("2"))

    def test_rejects_wrong_product_and_setup(self):
        report = self.validate(product_id="ETH-USD", playbook_setup="old_v1_setup")

        self.assertFalse(report["ok"])
        self.assertIn("product_id must be BTC-USD spot", report["errors"])
        self.assertIn("playbook_setup is not a v2 setup", report["errors"])

    def test_rejects_active_cycle_drawdown_and_cooldown(self):
        state = base_state()
        state["active_cycle"] = True
        state["active_cycle_detail"] = {
            "cycle_id": "cycle-1",
            "sell_order_id": "sell-1",
            "rebuy_order_id": "rebuy-1",
            "btc_to_sell": "0.2",
            "sell_trigger_price": "78000",
            "rebuy_limit_price": "74000",
            "worst_case_rebuy_price": "81000",
            "cycle_opened_at_utc": "2026-04-25T10:00:00Z",
            "time_cap_utc": "2026-04-28T10:00:00Z",
            "playbook_setup": "catalyst_driven_breakdown",
        }
        state["drawdown_halt"] = True
        state["last_losing_cycle_utc"] = "2026-04-25T00:00:00Z"
        state["consecutive_losing_cycles"] = 1

        report = self.validate(state=state, btc_equivalent_stack=Decimal("0.80"))

        self.assertFalse(report["ok"])
        self.assertIn("one active cycle is already open", report["errors"])
        self.assertIn("drawdown_halt is active", report["errors"])
        self.assertIn("BTC drawdown halt threshold breached", report["errors"])
        self.assertTrue(any(error.startswith("cooldown active") for error in report["errors"]))

    def test_rejects_cycle_size_and_rolling_cap(self):
        state = base_state()
        state["cycles_opened"] = [
            {"cycle_opened_at_utc": "2026-04-23T12:00:00Z"},
            {"cycle_opened_at_utc": "2026-04-24T12:00:00Z"},
        ]

        report = self.validate(state=state, btc_to_sell=Decimal("0.31000000"))

        self.assertFalse(report["ok"])
        self.assertIn("btc_to_sell exceeds 30 percent of BTC stack", report["errors"])
        self.assertIn("rolling seven-day cycle cap reached", report["errors"])

    def test_rejects_price_rr_reserve_and_stale_data(self):
        report = self.validate(
            sell_trigger_price=Decimal("79000"),
            rebuy_limit_price=Decimal("79500"),
            worst_case_rebuy_price=Decimal("80000"),
            current_price=Decimal("78500"),
            usd_reserve_pct=Decimal("5"),
            research_fetched_at=self.now - timedelta(hours=4),
        )

        self.assertFalse(report["ok"])
        self.assertIn("USD reserve must be inside the 10-20 percent band", report["errors"])
        self.assertIn("sell_trigger_price must be below current spot price", report["errors"])
        self.assertIn("rebuy_limit_price must be below sell_trigger_price", report["errors"])
        self.assertIn("research data is stale", report["errors"])


if __name__ == "__main__":
    unittest.main()
