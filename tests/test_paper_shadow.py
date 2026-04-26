from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from decimal import Decimal
from pathlib import Path

from scripts.paper_shadow import run_shadow
from scripts.paper_trade import init_campaign, parse_utc, seed_state, write_state


def report(**overrides) -> dict:
    payload = {
        "ts": "2026-04-25T11:30:00Z",
        "bias": "hold",
        "confidence": "medium",
        "rubric": {
            "catalyst": True,
            "sentiment_extreme_or_divergence": True,
            "onchain_or_structure": False,
            "macro_aligned": True,
            "technical_level": True,
            "score": 4,
            "grade": "B",
        },
        "numeric_context": {"btc_price_usd": 80000},
        "trade_ideas": [
            {
                "grade": "B",
                "playbook_setup": "catalyst_driven_breakdown",
                "sell_trigger_price": "78000",
                "rebuy_limit_price": "74000",
                "worst_case_rebuy_price": "79500",
                "btc_r_r": "2.67",
            }
        ],
        "data_health": {
            "fetched_at": "2026-04-25T11:30:00Z",
            "missing_slots": [],
            "websearch_gaps": [],
            "stale_warnings": [],
        },
    }
    payload.update(overrides)
    return payload


def base_args(tmp: str, state_path: Path, report_path: Path) -> Namespace:
    return Namespace(
        path=state_path,
        report_dir=Path(tmp),
        research_report=report_path,
        max_age_minutes="45",
        product="BTC-USD",
        bid="80000",
        ask="80001",
        at="2026-04-25T12:00:00Z",
        cycle_id=None,
        playbook_setup=None,
        grade=None,
        btc_to_sell=None,
        sell_trigger_price=None,
        rebuy_limit_price=None,
        worst_case_rebuy_price=None,
    )


class PaperShadowTests(unittest.TestCase):
    def write_active_state(self, path: Path) -> None:
        state = init_campaign(
            starting_btc=Decimal("0.10000000"),
            starting_usd=Decimal("100.00"),
            starting_btc_price=Decimal("80000"),
            start=parse_utc("2026-04-25T12:00:00Z"),
        )
        write_state(state, path)

    def test_shadow_tick_runs_without_opening_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            report_path = Path(tmp) / "research.json"
            self.write_active_state(state_path)
            report_path.write_text(json.dumps(report()), encoding="utf-8")

            code, payload = run_shadow(base_args(tmp, state_path, report_path))

            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["open_requested"])
            self.assertEqual(payload["tick"]["summary"]["active_cycle"], None)

    def test_shadow_refuses_uninitialized_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            report_path = Path(tmp) / "research.json"
            write_state(seed_state(), state_path)
            report_path.write_text(json.dumps(report()), encoding="utf-8")

            code, payload = run_shadow(base_args(tmp, state_path, report_path))

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["reason"], "paper_campaign_not_started")

    def test_shadow_open_blocks_on_stale_research_but_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            report_path = Path(tmp) / "research.json"
            self.write_active_state(state_path)
            stale = report(
                ts="2026-04-25T10:00:00Z",
                data_health={
                    "fetched_at": "2026-04-25T10:00:00Z",
                    "missing_slots": [],
                    "websearch_gaps": [],
                    "stale_warnings": [],
                },
            )
            report_path.write_text(json.dumps(stale), encoding="utf-8")
            args = base_args(tmp, state_path, report_path)
            args.cycle_id = "paper-test-1"
            args.playbook_setup = "catalyst_driven_breakdown"
            args.grade = "B"
            args.btc_to_sell = "0.02000000"
            args.sell_trigger_price = "78000"
            args.rebuy_limit_price = "74000"
            args.worst_case_rebuy_price = "79500"

            code, payload = run_shadow(args)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["open_result"]["reason"], "research_gate")
            self.assertIn("research report is stale", payload["research"]["errors"])

    def test_shadow_can_open_paper_cycle_after_valid_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            report_path = Path(tmp) / "research.json"
            self.write_active_state(state_path)
            report_path.write_text(json.dumps(report()), encoding="utf-8")
            args = base_args(tmp, state_path, report_path)
            args.cycle_id = "paper-test-1"
            args.playbook_setup = "catalyst_driven_breakdown"
            args.grade = "B"
            args.btc_to_sell = "0.02000000"
            args.sell_trigger_price = "78000"
            args.rebuy_limit_price = "74000"
            args.worst_case_rebuy_price = "79500"

            code, payload = run_shadow(args)

            self.assertEqual(code, 0, payload)
            self.assertTrue(payload["open_result"]["ok"])
            self.assertEqual(
                payload["open_result"]["active_cycle"]["cycle_id"],
                "paper-test-1",
            )


if __name__ == "__main__":
    unittest.main()
