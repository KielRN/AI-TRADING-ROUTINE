from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.state import (
    close_cycle,
    force_close_cycle,
    mark_sell_filled,
    open_cycle,
    set_drawdown_halt,
    validate_state,
    write_state_atomic,
)


def base_state() -> dict:
    return {
        "schema_version": 1,
        "updated_at_utc": None,
        "quarterly_start_btc": "0.05342287",
        "drawdown_halt": False,
        "active_cycle": False,
        "active_cycle_detail": None,
        "last_losing_cycle_utc": None,
        "consecutive_losing_cycles": 0,
        "cycles_opened": [],
    }


class StateTests(unittest.TestCase):
    def test_valid_inactive_state(self):
        state = base_state()

        self.assertEqual(validate_state(state), [])

    def test_active_cycle_requires_detail(self):
        state = base_state()
        state["active_cycle"] = True

        self.assertIn(
            "active_cycle_detail must be an object when active_cycle=true",
            validate_state(state),
        )

    def test_open_cycle_adds_phase_and_fill_fields(self):
        state = open_cycle(
            base_state(),
            cycle_id="cycle-1",
            sell_order_id="sell-1",
            rebuy_order_id="rebuy-1",
            sell_client_order_id="cycle-1-sell-trigger",
            rebuy_client_order_id="cycle-1-rebuy-limit",
            btc_to_sell="0.01000000",
            sell_trigger_price="78000",
            rebuy_limit_price="74000",
            worst_case_rebuy_price="79500",
            expected_usd="780.00",
            stop_limit_price="77610.00",
            cycle_opened_at_utc="2026-04-25T12:00:00Z",
            time_cap_utc="2026-04-28T12:00:00Z",
            playbook_setup="catalyst_driven_breakdown",
        )

        self.assertEqual(validate_state(state), [])
        self.assertTrue(state["active_cycle"])
        active = state["active_cycle_detail"]
        self.assertEqual(active["phase"], "A")
        self.assertIsNone(active["sell_filled_at_utc"])
        self.assertIsNone(active["rebuy_fill_price"])
        self.assertEqual(state["cycles_opened"][0]["cycle_id"], "cycle-1")

    def test_sell_fill_and_clean_close_update_state_and_cooldown(self):
        state = open_cycle(
            base_state(),
            cycle_id="cycle-1",
            sell_order_id="sell-1",
            rebuy_order_id="rebuy-1",
            btc_to_sell="0.01000000",
            sell_trigger_price="78000",
            rebuy_limit_price="74000",
            worst_case_rebuy_price="79500",
            cycle_opened_at_utc="2026-04-25T12:00:00Z",
            time_cap_utc="2026-04-28T12:00:00Z",
            playbook_setup="catalyst_driven_breakdown",
        )

        state = mark_sell_filled(
            state,
            sell_filled_at_utc="2026-04-25T13:00:00Z",
            sell_fill_price="78000",
            usd_from_sell="780.00",
        )
        self.assertEqual(state["active_cycle_detail"]["phase"], "B")
        self.assertEqual(state["active_cycle_detail"]["sell_fill_price"], "78000")

        state = close_cycle(
            state,
            closed_at_utc="2026-04-25T14:00:00Z",
            rebuy_fill_price="76000",
            rebuy_filled_size="0.01026315",
        )

        self.assertEqual(validate_state(state), [])
        self.assertFalse(state["active_cycle"])
        self.assertIsNone(state["active_cycle_detail"])
        self.assertEqual(state["consecutive_losing_cycles"], 0)
        self.assertIsNone(state["last_losing_cycle_utc"])
        self.assertEqual(state["cycles_opened"][0]["phase"], "C")
        self.assertEqual(state["cycles_opened"][0]["close_reason"], "clean_close")

    def test_forced_close_loss_sets_cooldown_and_drawdown_halt_helper(self):
        state = open_cycle(
            base_state(),
            cycle_id="cycle-1",
            sell_order_id="sell-1",
            rebuy_order_id="rebuy-1",
            btc_to_sell="0.01000000",
            sell_trigger_price="78000",
            rebuy_limit_price="74000",
            worst_case_rebuy_price="79500",
            cycle_opened_at_utc="2026-04-25T12:00:00Z",
            time_cap_utc="2026-04-28T12:00:00Z",
            playbook_setup="catalyst_driven_breakdown",
        )

        state = force_close_cycle(
            state,
            closed_at_utc="2026-04-25T14:00:00Z",
            market_buy_fill_price="81000",
            rebuy_filled_size="0.00962962",
        )

        self.assertEqual(validate_state(state), [])
        self.assertEqual(state["last_losing_cycle_utc"], "2026-04-25T14:00:00Z")
        self.assertEqual(state["consecutive_losing_cycles"], 1)

        state = set_drawdown_halt(
            state,
            active=True,
            updated_at_utc="2026-04-25T15:00:00Z",
            reason="unit test",
        )
        self.assertTrue(state["drawdown_halt"])
        self.assertEqual(state["drawdown_halt_reason"], "unit test")

    def test_write_state_atomic_validates_before_replace(self):
        state = base_state()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            write_state_atomic(state, path)
            self.assertTrue(path.exists())

            invalid = dict(state)
            invalid["active_cycle"] = "yes"
            with self.assertRaises(ValueError):
                write_state_atomic(invalid, path)


if __name__ == "__main__":
    unittest.main()
