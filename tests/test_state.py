from __future__ import annotations

import unittest

from scripts.state import validate_state


class StateTests(unittest.TestCase):
    def test_valid_inactive_state(self):
        state = {
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

        self.assertEqual(validate_state(state), [])

    def test_active_cycle_requires_detail(self):
        state = {
            "schema_version": 1,
            "updated_at_utc": None,
            "quarterly_start_btc": "0.05342287",
            "drawdown_halt": False,
            "active_cycle": True,
            "active_cycle_detail": None,
            "last_losing_cycle_utc": None,
            "consecutive_losing_cycles": 0,
            "cycles_opened": [],
        }

        self.assertIn(
            "active_cycle_detail must be an object when active_cycle=true",
            validate_state(state),
        )


if __name__ == "__main__":
    unittest.main()

