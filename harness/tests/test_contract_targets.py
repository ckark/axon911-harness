"""Contract files name personal-harness as a first-class implementation target."""

from __future__ import annotations

import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(relpath: str) -> str:
    with open(os.path.join(ROOT, relpath), "r", encoding="utf-8") as handle:
        return handle.read()


class ContractTargetTests(unittest.TestCase):
    def test_plan_contract_lists_personal_harness(self) -> None:
        text = _read("docs/plan-contract.md")
        self.assertIn("`personal-harness`", text)
        self.assertIn("runtime verification", text.lower())

    def test_implementation_contract_owns_personal_harness(self) -> None:
        text = _read("docs/implementation-contract.md")
        self.assertIn("`personal-harness`", text.split("## Per-root verification", 1)[0])
        self.assertIn("### personal-harness", text)
        self.assertIn("docs/runtime-contract.md", text)

    def test_routing_matrix_has_harness_signal(self) -> None:
        text = _read("docs/routing-matrix.md")
        self.assertIn("Harness runtime", text)

    def test_repository_router_is_not_review_only(self) -> None:
        text = _read(".cursor/skills/adversarial-review/references/repository-router.md")
        self.assertIn("explicit harness implementation", text)
        self.assertNotIn("Review orchestration only", text)

    def test_workspace_rule_lists_four_roots(self) -> None:
        text = _read(".cursor/rules/prepared911-workspace.mdc")
        self.assertIn("All four workspace roots", text)
        self.assertIn("docs/runtime-contract.md", text)


if __name__ == "__main__":
    unittest.main()
