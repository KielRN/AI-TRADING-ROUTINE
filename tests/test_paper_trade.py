from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from scripts.paper_trade import (
    init_campaign,
    open_cycle,
    parse_utc,
    summary,
    tick,
    validate_state,
)


class PaperTradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = parse_utc("2026-04-25T12:00:00Z")

    def _active_state(self):
        return init_campaign(
            starting_btc=Decimal("0.10000000"),
            starting_usd=Decimal("100.00"),
            starting_btc_price=Decimal("80000"),
            start=self.start,
        )

    def _open_cycle(self, state, btc_to_sell="0.02000000"):
        return open_cycle(
            state,
            cycle_id="paper-test-1",
            playbook_setup="catalyst_driven_breakdown",
            grade="B",
            btc_to_sell=Decimal(btc_to_sell),
            sell_trigger_price=Decimal("78000"),
            rebuy_limit_price=Decimal("74000"),
            worst_case_rebuy_price=Decimal("82000"),
            current_price=Decimal("80000"),
            opened_at=self.start,
        )

    def test_init_campaign_sets_fourteen_day_window(self):
        state = self._active_state()

        self.assertEqual(validate_state(state), [])
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["started_at_utc"], "2026-04-25T12:00:00Z")
        self.assertEqual(state["ends_at_utc"], "2026-05-09T12:00:00Z")

    def test_open_cycle_enforces_thirty_percent_cap(self):
        state = self._active_state()

        with self.assertRaisesRegex(ValueError, "30 percent"):
            self._open_cycle(state, btc_to_sell="0.04000000")

    def test_cycle_fills_sell_then_rebuy_and_gains_btc(self):
        state = self._open_cycle(self._active_state())

        self.assertEqual(state["active_cycle"]["phase"], "A")
        self.assertEqual(state["balances"]["btc_available"], "0.08000000")
        self.assertEqual(state["balances"]["btc_locked"], "0.02000000")

        state = tick(
            state,
            bid=Decimal("77900"),
            ask=Decimal("77950"),
            at=self.start + timedelta(hours=1),
        )
        self.assertEqual(state["active_cycle"]["phase"], "B")
        self.assertEqual(state["balances"]["btc_locked"], "0.00000000")
        self.assertEqual(state["balances"]["usd_locked"], "1560.00")

        state = tick(
            state,
            bid=Decimal("73900"),
            ask=Decimal("74050"),
            at=self.start + timedelta(hours=2),
        )

        self.assertIsNone(state["active_cycle"])
        closed = state["cycles"][-1]
        self.assertEqual(closed["close_reason"], "rebuy_limit_filled")
        self.assertGreater(Decimal(closed["btc_delta"]), Decimal("0"))

    def test_time_cap_market_buy_can_close_losing_cycle(self):
        state = self._open_cycle(self._active_state())
        state = tick(
            state,
            bid=Decimal("77900"),
            ask=Decimal("77950"),
            at=self.start + timedelta(hours=1),
        )
        state = tick(
            state,
            bid=Decimal("79000"),
            ask=Decimal("79000"),
            at=self.start + timedelta(hours=73),
        )

        self.assertIsNone(state["active_cycle"])
        closed = state["cycles"][-1]
        self.assertEqual(closed["close_reason"], "time_cap_market_buy")
        self.assertLess(Decimal(closed["btc_delta"]), Decimal("0"))

    def test_rejects_cycle_that_cannot_fit_time_cap_inside_campaign(self):
        state = self._active_state()

        with self.assertRaisesRegex(ValueError, "time-cap"):
            open_cycle(
                state,
                cycle_id="paper-too-late",
                playbook_setup="catalyst_driven_breakdown",
                grade="B",
                btc_to_sell=Decimal("0.02000000"),
                sell_trigger_price=Decimal("78000"),
                rebuy_limit_price=Decimal("74000"),
                worst_case_rebuy_price=Decimal("82000"),
                current_price=Decimal("80000"),
                opened_at=self.start + timedelta(days=13),
            )

    def test_campaign_end_cancels_untriggered_cycle(self):
        state = self._open_cycle(self._active_state())
        state = tick(
            state,
            bid=Decimal("81000"),
            ask=Decimal("81100"),
            at=self.start + timedelta(days=14),
        )

        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state["active_cycle"])
        self.assertEqual(state["cycles"][-1]["close_reason"], "campaign_end_untriggered")
        self.assertEqual(state["balances"]["btc_available"], "0.10000000")

    def test_campaign_completes_after_fourteen_days_when_no_cycle_active(self):
        state = self._active_state()
        state = tick(
            state,
            bid=Decimal("81000"),
            ask=Decimal("81100"),
            at=self.start + timedelta(days=14),
        )

        self.assertEqual(state["status"], "complete")
        self.assertEqual(summary(state)["cycles_opened"], 0)


if __name__ == "__main__":
    unittest.main()
