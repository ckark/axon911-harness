"""Attestation command specifications."""

from __future__ import annotations

import os
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.command_specs import validate_attestation_command  # noqa: E402


class CommandSpecTests(unittest.TestCase):
    def test_vacuous_true_rejected(self) -> None:
        ok, reason = validate_attestation_command("axon911-frontend.ui-allowlist", ["true"])
        self.assertFalse(ok)
        self.assertEqual(reason, "vacuous-command")

    def test_generator_requires_real_check(self) -> None:
        ok, _ = validate_attestation_command(
            "axon911-frontend.ui-allowlist",
            ["pnpm", "gen:ui-components"],
        )
        self.assertTrue(ok)

    def test_push_oid_requires_rev_parse_head(self) -> None:
        ok, _ = validate_attestation_command("push.oid", ["git", "rev-parse", "HEAD"])
        self.assertTrue(ok)
        ok, reason = validate_attestation_command("push.oid", ["git", "push", "origin", "HEAD"])
        self.assertFalse(ok)
        self.assertEqual(reason, "push.oid-requires-git-rev-parse-head")

    def test_design_system_gates_require_the_package_check(self) -> None:
        ok, _ = validate_attestation_command(
            "axon911-frontend.ds-gates",
            ["pnpm", "--filter", "./packages/ui", "check"],
        )
        self.assertTrue(ok)
        # Root `pnpm check` ignores packages/ui, so it cannot attest the gate.
        ok, reason = validate_attestation_command("axon911-frontend.ds-gates", ["pnpm", "check"])
        self.assertFalse(ok)
        self.assertEqual(reason, "check-command-mismatch")


if __name__ == "__main__":
    unittest.main()
