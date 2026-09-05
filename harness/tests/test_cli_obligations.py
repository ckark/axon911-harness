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

    def test_strict_evidence_state_classifies_ui_surface(self) -> None:
        profile = {
            "profiled": True,
            "strict": True,
            "scope": ["packages/ui-core/**"],
            "path_surfaces": {},
            "evidence_states": {"packages/ui-core/**": "before-after"},
        }
        selection = select_obligations(
            "axon911-frontend",
            ["packages/ui-core/src/components/typography/styles.scss"],
            profile,
            "T0",
        )
        self.assertEqual(selection["classification_errors"], [])
        self.assertEqual(
            selection["path_surfaces"]["packages/ui-core/src/components/typography/styles.scss"],
            "existing-visible",
        )

    def test_commit_family_defers_rendered_evidence(self) -> None:
        profile = {
            "profiled": True,
            "strict": True,
            "scope": ["packages/ui-core/**"],
            "path_surfaces": {},
            "evidence_states": {"packages/ui-core/**": "before-after"},
        }
        selection = select_obligations(
            "axon911-frontend",
            ["packages/ui-core/src/components/typography/styles.scss"],
            profile,
            "T0",
            family="git-commit",
        )
        required = selection["required_obligation_ids"]
        self.assertIn("axon911-frontend.docs-page", required)
        self.assertNotIn("axon911-frontend.rendered-evidence", required)
        self.assertNotIn("axon911-frontend.rendered-evidence.before-after", required)

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
            evidence_states={"harness/lib/**": "none"},
            execution_manifest_hash="manifest-hash",
            base=self.base,
        )
        from lib.ledger import current_state
        from lib.plan_profile import active_profile

        profile = active_profile(current_state(base=self.base), "personal-harness", "wt")
        self.assertTrue(profile["profiled"])
        self.assertEqual(profile["base_oid"], "abc123")
        self.assertEqual(profile["scope"], ["harness/**"])
        self.assertEqual(profile["evidence_states"], {"harness/lib/**": "none"})
        self.assertEqual(profile["execution_manifest_hash"], "manifest-hash")


if __name__ == "__main__":
    unittest.main()
