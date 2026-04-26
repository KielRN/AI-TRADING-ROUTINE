from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.research_gate import (
    latest_report_path,
    parse_utc,
    validate_research_report,
)


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


def write_report(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class ResearchGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = parse_utc("2026-04-25T12:00:00Z")

    def test_valid_fresh_report_with_trade_idea_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-04-25-11.json"
            write_report(path, report())

            gate = validate_research_report(
                path,
                now=self.now,
                require_trade_idea=True,
            )

            self.assertTrue(gate["ok"], gate)
            self.assertEqual(gate["trade_idea_count"], 1)
            self.assertEqual(gate["age_seconds"], 1800)

    def test_stale_report_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-04-25-10.json"
            write_report(
                path,
                report(
                    ts="2026-04-25T10:00:00Z",
                    data_health={
                        "fetched_at": "2026-04-25T10:00:00Z",
                        "missing_slots": [],
                        "websearch_gaps": [],
                        "stale_warnings": [],
                    },
                ),
            )

            gate = validate_research_report(
                path,
                now=self.now,
                require_trade_idea=True,
            )

            self.assertFalse(gate["ok"])
            self.assertIn("research report is stale", gate["errors"])

    def test_require_trade_idea_rejects_hold_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-04-25-11.json"
            write_report(path, report(trade_ideas=[]))

            gate = validate_research_report(
                path,
                now=self.now,
                require_trade_idea=True,
            )

            self.assertFalse(gate["ok"])
            self.assertIn("no actionable A/B trade idea in research report", gate["errors"])

    def test_trade_idea_requires_positive_technical_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-04-25-11.json"
            write_report(
                path,
                report(
                    rubric={
                        "catalyst": True,
                        "sentiment_extreme_or_divergence": True,
                        "onchain_or_structure": False,
                        "macro_aligned": True,
                        "technical_level": False,
                        "score": 3,
                        "grade": "B",
                    },
                ),
            )

            gate = validate_research_report(
                path,
                now=self.now,
                require_trade_idea=True,
            )

            self.assertFalse(gate["ok"])
            self.assertIn(
                "research rubric technical_level must be true for trade ideas",
                gate["errors"],
            )

    def test_latest_report_uses_newest_report_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            old = report_dir / "2026-04-25-00.json"
            new = report_dir / "2026-04-25-12.json"
            write_report(old, report(ts="2026-04-25T00:00:00Z"))
            write_report(new, report(ts="2026-04-25T12:00:00Z"))

            self.assertEqual(latest_report_path(report_dir), new)

    def test_schema_rejects_stale_v1_trade_idea_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-04-25-11.json"
            payload = report(
                trade_ideas=[
                    {
                        "playbook_setup": "catalyst_driven_breakdown",
                        "entry": "78000",
                        "stop": "79500",
                        "target": "74000",
                    }
                ]
            )
            write_report(path, payload)

            gate = validate_research_report(path, now=self.now)

            self.assertFalse(gate["ok"])
            self.assertIn("trade_ideas[0] uses stale v1 field entry", gate["errors"])


if __name__ == "__main__":
    unittest.main()
