"""Review receipt cardinality and tier substitution."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.receipts import (  # noqa: E402
    evaluate_gate,
    issue_review_receipt,
    review_mode,
)


class TierRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.previous = os.environ.get("HARNESS_REVIEW_MODE")
        os.environ["HARNESS_REVIEW_MODE"] = "always"

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop("HARNESS_REVIEW_MODE", None)
        else:
            os.environ["HARNESS_REVIEW_MODE"] = self.previous

    def test_matching_tier_satisfies_gate(self) -> None:
        issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T2",
            ["design-system-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            ["review.T2"],
            "plan",
            "T2",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "allow")

    def test_lower_tier_receipt_does_not_satisfy_higher_tier(self) -> None:
        issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T0",
            ["design-system-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            ["review.T2"],
            "plan",
            "T2",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")
        recovery = gate.get("recovery") or {}
        self.assertIn("review.T2", recovery.get("missing") or [])

    def test_empty_critic_list_is_blocked(self) -> None:
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T1",
            [],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_BLOCKED)

    def test_review_off_by_default(self) -> None:
        os.environ["HARNESS_REVIEW_MODE"] = "off"
        from lib.receipts import default_required

        ids = default_required("personal-harness", [], False, False, "T2")
        self.assertNotIn("review.T2", ids)
        self.assertEqual(review_mode(), "off")


if __name__ == "__main__":
    unittest.main()
