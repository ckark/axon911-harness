"""T0/T1/T2 review cardinality and higher-tier substitution."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.receipts import evaluate_gate, issue_review_receipt  # noqa: E402

T2_PANEL = (
    "frontend-architecture-critic",
    "security-privacy-critic",
    "review-adjudicator",
)


class TierRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_t0_requires_one_critic(self) -> None:
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T0",
            ["frontend-architecture-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_PASS)

    def test_t1_rejects_a_single_critic(self) -> None:
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T1",
            ["frontend-architecture-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_BLOCKED)

    def test_t1_accepts_two_independent_critics(self) -> None:
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T1",
            ["frontend-architecture-critic", "security-privacy-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_PASS)

    def test_t2_requires_adjudicator_and_panel(self) -> None:
        missing = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T2",
            ["frontend-architecture-critic", "security-privacy-critic"],
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(missing["status"], STATUS_BLOCKED)
        ok = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp2",
            "T2",
            T2_PANEL,
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        self.assertEqual(ok["status"], STATUS_PASS)

    def test_t2_receipt_satisfies_t0_gate(self) -> None:
        issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T2",
            T2_PANEL,
            STATUS_PASS,
            "plan",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            ["review.T0"],
            "plan",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "allow")

    def test_t0_receipt_does_not_satisfy_t2_gate(self) -> None:
        issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T0",
            ["frontend-architecture-critic"],
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


if __name__ == "__main__":
    unittest.main()
