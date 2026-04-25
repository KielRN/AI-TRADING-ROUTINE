from __future__ import annotations

import unittest
from decimal import Decimal

from scripts.risk_math import cycle_unrealized_r


class RiskMathTests(unittest.TestCase):
    def test_positive_r_is_loss_and_triggers_force_close(self):
        result = cycle_unrealized_r(
            btc_to_sell=Decimal("0.01000000"),
            sell_fill_price=Decimal("80000"),
            current_ask=Decimal("87000"),
            worst_case_rebuy_price=Decimal("84000"),
        )

        self.assertGreater(Decimal(result["unrealized_r"]), Decimal("1.5"))
        self.assertEqual(result["force_close"], "true")

    def test_negative_r_is_favorable_and_does_not_force_close(self):
        result = cycle_unrealized_r(
            btc_to_sell=Decimal("0.01000000"),
            sell_fill_price=Decimal("80000"),
            current_ask=Decimal("76000"),
            worst_case_rebuy_price=Decimal("84000"),
        )

        self.assertLess(Decimal(result["unrealized_r"]), Decimal("0"))
        self.assertEqual(result["force_close"], "false")

    def test_worst_case_must_exceed_sell_fill(self):
        with self.assertRaises(ValueError):
            cycle_unrealized_r(
                btc_to_sell=Decimal("0.01000000"),
                sell_fill_price=Decimal("80000"),
                current_ask=Decimal("81000"),
                worst_case_rebuy_price=Decimal("79000"),
            )


if __name__ == "__main__":
    unittest.main()

