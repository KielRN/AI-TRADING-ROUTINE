from __future__ import annotations

import json
import sys
import unittest

from scripts.research_collect import collect, run_source


class ResearchCollectTests(unittest.TestCase):
    def test_run_source_captures_json_output(self):
        result = run_source(
            "fake",
            [sys.executable, "-c", "import json; print(json.dumps({'value': 1}))"],
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["value"], 1)

    def test_run_source_reports_nonzero_exit(self):
        result = run_source(
            "fake",
            [sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 3)
        self.assertEqual(result["stdout"], "bad")

    def test_collect_marks_missing_slots_but_keeps_successful_sources(self):
        commands = {
            "ok_source": [
                sys.executable,
                "-c",
                "import json; print(json.dumps({'source': 'ok'}))",
            ],
            "bad_source": [sys.executable, "-c", "import sys; sys.exit(2)"],
        }

        payload = collect(commands)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "validated_sources_plus_websearch")
        self.assertIn("bad_source", payload["missing_slots"])
        self.assertEqual(payload["sources"]["ok_source"]["data"]["source"], "ok")
        self.assertTrue(payload["websearch_required"])


if __name__ == "__main__":
    unittest.main()
