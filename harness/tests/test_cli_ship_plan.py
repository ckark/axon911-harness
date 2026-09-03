"""Read-only ship-plan evaluation."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.ledger import append_record, current_state  # noqa: E402
from lib.plan_profile import register_plan_profile  # noqa: E402
from lib.shipping import evaluate_ship_plan  # noqa: E402


class ShipPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_ship_plan_is_read_only(self) -> None:
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp",
            "plan",
            "T0",
            ["harness/**"],
            "",
            "",
            {},
            base=self.base,
        )
        before = current_state(base=self.base)
        report = evaluate_ship_plan(
            "personal-harness",
            HARNESS,
            "wt",
            "fp",
            base=self.base,
        )
        after = current_state(base=self.base)
        self.assertEqual(before, after)
        self.assertIn("required_obligation_ids", report)
        self.assertIn("recovery", report.get("gate") or report)


if __name__ == "__main__":
    unittest.main()
