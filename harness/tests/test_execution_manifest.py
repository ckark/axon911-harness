"""Strict execution manifest registration and conformance."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.conformance import classify  # noqa: E402
from lib.plan_profile import register_plan_profile, validate_strict_profile  # noqa: E402


class ExecutionManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_strict_profile_requires_manifest_and_base(self) -> None:
        errors = validate_strict_profile(
            scope=["packages/**"],
            base_oid="",
            tier="T1",
            strict=True,
            evidence_manifest_pointer="",
        )
        self.assertIn("strict-profile-missing-base-oid", errors)
        self.assertIn("strict-profile-missing-evidence-manifest", errors)

    def test_strict_mode_does_not_exempt_stories(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout/index.tsx"],
            ["packages/ui-core/src/components/callout/index.stories.tsx"],
            strict=True,
        )
        self.assertEqual(result["undeclared"], ["packages/ui-core/src/components/callout/index.stories.tsx"])

    def test_required_paths_are_tracked_separately(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout/**"],
            ["packages/ui-core/src/components/callout/index.tsx"],
            required_paths=["packages/ui-blocks/src/**"],
            strict=True,
        )
        self.assertEqual(result["unimplemented"], ["packages/ui-blocks/src/**"])

    def test_register_strict_profile_rejects_incomplete_manifest(self) -> None:
        with self.assertRaises(ValueError):
            register_plan_profile(
                "personal-harness",
                "wt",
                "fp",
                "plan-x",
                "T1",
                ["packages/**"],
                "",
                "",
                {},
                strict=True,
                base=self.base,
            )


if __name__ == "__main__":
    unittest.main()
