"""Dormant PR automation templates stay self-contained and inactive."""

from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PACK = os.path.join(ROOT, "automations", "pr-verification")


def _read(name: str) -> str:
    with open(os.path.join(PACK, name), "r", encoding="utf-8") as handle:
        return handle.read()


class AutomationTemplateTests(unittest.TestCase):
    def test_pack_files_exist(self) -> None:
        for name in (
            "README.md",
            "config.json",
            "static-pr-inspect.md",
            "deep-runtime-verify.md",
            "activation-checklist.md",
        ):
            self.assertTrue(os.path.isfile(os.path.join(PACK, name)), name)

    def test_config_is_dormant(self) -> None:
        with open(os.path.join(PACK, "config.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["status"], "dormant")
        self.assertFalse(data["static_inspect"]["executes_pr_head_code"])
        self.assertFalse(data["deep_verify"]["active"])
        self.assertFalse(data["deep_verify"]["isolation_proven"])

    def test_templates_do_not_reference_the_harness(self) -> None:
        for name in ("static-pr-inspect.md", "deep-runtime-verify.md"):
            text = _read(name)
            lowered = text.lower()
            self.assertNotIn("personal-harness", lowered)
            self.assertNotIn("/users/", lowered)
            self.assertNotIn("prepared911-harness", lowered)
            self.assertNotIn("axon911-harness", lowered)

    def test_static_inspect_never_executes_pr_code(self) -> None:
        text = _read("static-pr-inspect.md").lower()
        self.assertIn("never execute pr-head code", text)
        self.assertIn("schema-constrained", text)

    def test_deep_verify_stays_inconclusive_until_isolation(self) -> None:
        text = _read("deep-runtime-verify.md").lower()
        self.assertIn("inconclusive", text)
        self.assertIn("isolation", text)
        self.assertIn("inactive", text)

    def test_activation_checklist_is_explicit(self) -> None:
        text = _read("activation-checklist.md").lower()
        for needle in (
            "repo/trigger/tool scope",
            "self-contained prompt",
            "harmless test pr",
            "adversarial fixture",
            "head-movement",
            "inconclusive",
        ):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
