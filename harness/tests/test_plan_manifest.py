"""Plan manifest and plan-context fingerprint binding."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.fingerprint import snapshot  # noqa: E402
from lib.plan_profile import plan_context_hash, register_plan_profile  # noqa: E402
from lib.receipts import issue_verification_receipt, evaluate_gate  # noqa: E402


class PlanManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_same_plan_hash_different_context_invalidates_receipt(self) -> None:
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp1",
            "plan-a",
            "T0",
            ["harness/**"],
            "base1",
            "",
            {},
            base=self.base,
        )
        ctx1 = plan_context_hash("plan-a", ["harness/**"], "base1", "", {})
        issue_verification_receipt(
            "personal-harness",
            "wt",
            "fp1",
            "harness.unittests",
            "PASS",
            "fp1",
            "plan-a",
            plan_context_hash=ctx1,
            base=self.base,
        )
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp2",
            "plan-a",
            "T0",
            ["harness/lib/**"],
            "base1",
            "",
            {},
            base=self.base,
        )
        ctx2 = plan_context_hash("plan-a", ["harness/lib/**"], "base1", "", {})
        self.assertNotEqual(ctx1, ctx2)
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp2",
            ["harness.unittests"],
            "plan-a",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")
        recovery = gate.get("recovery") or {}
        self.assertIn("harness.unittests", recovery.get("missing") or [])


if __name__ == "__main__":
    unittest.main()
