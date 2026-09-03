"""CLI obligation preview and plan profile registration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(HARNESS, ".."))
sys.path.insert(0, HARNESS)

from lib.conformance import normalize_scope  # noqa: E402
from lib.path_selector import select_obligations  # noqa: E402
from lib.plan_profile import plan_context_hash, register_plan_profile  # noqa: E402


class PlanProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_plan_context_hash_changes_when_scope_changes(self) -> None:
        first = plan_context_hash("plan-a", ["a/**"], "base", "", {})
        second = plan_context_hash("plan-a", ["b/**"], "base", "", {})
        self.assertNotEqual(first, second)

    def test_consumer_only_suppresses_prepared_docs_obligations(self) -> None:
        profile = {
            "profiled": True,
            "scope": ["turbo/apps/dispatch/**"],
            "mirror_intent": "consumer-only",
            "path_surfaces": {"turbo/apps/dispatch/**": "existing-visible"},
        }
        selection = select_obligations(
            "prepared911",
            ["turbo/packages/ui-core/src/x.tsx"],
            profile,
            "T0",
        )
        self.assertIn("prepared911.ui-allowlist", selection["required_obligation_ids"])
        self.assertNotIn("prepared911.docs-registry", selection["required_obligation_ids"])
        self.assertNotIn("prepared911.docs-page", selection["required_obligation_ids"])

    def test_profile_registration_is_atomic(self) -> None:
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp",
            "plan-1",
            "T1",
            normalize_scope(["harness/**"]),
            "abc123",
            "authoring",
            {"harness/lib/**": "non-visible"},
            base=self.base,
        )
        from lib.ledger import current_state
        from lib.plan_profile import active_profile

        profile = active_profile(current_state(base=self.base), "personal-harness", "wt")
        self.assertTrue(profile["profiled"])
        self.assertEqual(profile["base_oid"], "abc123")
        self.assertEqual(profile["scope"], ["harness/**"])


if __name__ == "__main__":
    unittest.main()
