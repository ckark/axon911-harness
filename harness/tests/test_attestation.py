"""Attesting wrapper: PASS only when the worktree is unchanged."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_BLOCKED, STATUS_INCONCLUSIVE, STATUS_PASS  # noqa: E402
from lib.receipts import (  # noqa: E402
    evaluate_gate,
    invalidate,
    issue_review_receipt,
    issue_verification_receipt,
    mutation_required_ids,
    register_plan,
)


class AttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.previous = os.environ.get("HARNESS_REVIEW_MODE")
        os.environ["HARNESS_REVIEW_MODE"] = "always"

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop("HARNESS_REVIEW_MODE", None)
        else:
            os.environ["HARNESS_REVIEW_MODE"] = self.previous

    def test_matching_fingerprints_can_pass(self) -> None:
        record = issue_verification_receipt(
            "personal-harness",
            "wt",
            "abc",
            "harness.unittests",
            STATUS_PASS,
            "abc",
            "plan-1",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_PASS)

    def test_mutation_during_verification_is_inconclusive(self) -> None:
        record = issue_verification_receipt(
            "personal-harness",
            "wt",
            "after",
            "harness.unittests",
            STATUS_PASS,
            "before",
            "plan-1",
            base=self.base,
        )
        self.assertEqual(record["status"], STATUS_INCONCLUSIVE)
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "after",
            ["harness.unittests"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_blocked_receipt_never_satisfies_gate(self) -> None:
        issue_verification_receipt(
            "personal-harness",
            "wt",
            "abc",
            "harness.unittests",
            STATUS_BLOCKED,
            "abc",
            "plan-1",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "abc",
            ["harness.unittests"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_stale_fingerprint_is_rejected(self) -> None:
        issue_verification_receipt(
            "personal-harness",
            "wt",
            "old",
            "harness.unittests",
            STATUS_PASS,
            "old",
            "plan-1",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "new",
            ["harness.unittests"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_wrong_root_receipt_is_rejected(self) -> None:
        issue_verification_receipt(
            "prepared911",
            "wt",
            "abc",
            "prepared911.ui-allowlist",
            STATUS_PASS,
            "abc",
            "plan-1",
            base=self.base,
        )
        gate = evaluate_gate(
            "axon911-frontend",
            "wt",
            "abc",
            ["axon911-frontend.ui-allowlist"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_invalidate_drops_receipts_for_that_fingerprint(self) -> None:
        issue_verification_receipt(
            "personal-harness",
            "wt",
            "abc",
            "harness.unittests",
            STATUS_PASS,
            "abc",
            "plan-1",
            base=self.base,
        )
        invalidate("personal-harness", "wt", "abc", base=self.base)
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "abc",
            ["harness.unittests"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_plan_hash_mismatch_is_rejected(self) -> None:
        register_plan("personal-harness", "wt", "abc", "plan-1", tier="T0", base=self.base)
        issue_review_receipt(
            "personal-harness",
            "wt",
            "abc",
            "T0",
            ["design-system-critic"],
            STATUS_PASS,
            "plan-other",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "abc",
            ["review.T0"],
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_registered_plan_is_used_when_gate_plan_hash_omitted(self) -> None:
        register_plan("personal-harness", "wt", "fp", "plan-1", tier="T0", base=self.base)
        issue_review_receipt(
            "personal-harness",
            "wt",
            "fp",
            "T0",
            ["design-system-critic"],
            STATUS_PASS,
            "plan-1",
            base=self.base,
        )
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            ["review.T0"],
            "",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "allow")

    def test_git_push_requires_push_oid_when_review_off(self) -> None:
        os.environ["HARNESS_REVIEW_MODE"] = "off"
        required = mutation_required_ids("personal-harness", [], "git-push", "T0")
        self.assertIn("push.oid", required)
        self.assertNotIn("review.T0", required)
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            required,
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")

    def test_gt_submit_requires_stack_oid_set(self) -> None:
        os.environ["HARNESS_REVIEW_MODE"] = "off"
        required = mutation_required_ids("personal-harness", [], "gt-submit", "T0")
        self.assertIn("stack-oid-set", required)
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            required,
            "plan-1",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")


if __name__ == "__main__":
    unittest.main()
