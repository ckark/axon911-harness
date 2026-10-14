"""Structured recovery output from gate evaluation."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.receipts import build_recovery, evaluate_gate, issue_verification_receipt  # noqa: E402


class RecoveryOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_missing_and_stale_are_distinguished(self) -> None:
        issue_verification_receipt(
            "personal-harness",
            "wt",
            "after",
            "harness.unittests",
            "PASS",
            "before",
            "plan-1",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "after",
            ["harness.unittests", "harness.other"],
            "plan-1",
            "T0",
            explain=True,
            base=self.base,
        )
        recovery = gate.get("recovery") or {}
        self.assertEqual(recovery.get("reason"), "missing-or-stale")
        self.assertIn("harness.other", recovery.get("missing") or [])
        self.assertIn("harness.unittests", recovery.get("stale") or [])


if __name__ == "__main__":
    unittest.main()
