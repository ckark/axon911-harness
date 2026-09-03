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

    def test_one_critic_satisfies_any_tier(self) -> None:
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T0",
            ["design-system-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_PASS)
        for tier in ("T0", "T1", "T2"):
            gate = evaluate_gate(
                "personal-harness",
                "wt",
                "fp",
                ["review.%s" % tier],
                "plan",
                tier,
                base=self.base,
            )
            self.assertEqual(gate["permission"], "allow", tier)

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
