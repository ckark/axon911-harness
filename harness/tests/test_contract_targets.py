"""Contract files name personal-harness as a first-class implementation target."""

from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DOC_DIRS = ("docs", "skills", "agents", ".cursor/skills", ".cursor/agents")

DISCOVER_TARGET = re.compile(r"discover\s+-s\s+(\S+)")
PYTHON_SCRIPT = re.compile(r"python3\s+(\S*?/)?([\w./-]+\.py)")

PLUGIN_ROOT_PREFIX = re.compile(r'"?\$\{CLAUDE_PLUGIN_ROOT\}"?/?')


def _read(relpath: str) -> str:
    with open(os.path.join(ROOT, relpath), "r", encoding="utf-8") as handle:
        return handle.read()


def _markdown_files() -> list[str]:
    found = ["README.md"]
    for doc_dir in DOC_DIRS:
        for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, doc_dir)):
            for filename in filenames:
                if filename.endswith(".md"):
                    absolute = os.path.join(dirpath, filename)
                    found.append(os.path.relpath(absolute, ROOT))
    return sorted(found)


def _normalize(raw: str) -> str:
    cleaned = raw.strip().strip("`'\"")
    return PLUGIN_ROOT_PREFIX.sub("", cleaned).lstrip("/")


def _documented_targets() -> dict[str, list[str]]:
    """Map each runnable path a doc tells a reader to type to its citing docs."""
    targets: dict[str, list[str]] = {}
    for relpath in _markdown_files():
        text = _read(relpath)
        raw_targets = set(DISCOVER_TARGET.findall(text))
        raw_targets.update(
            "%s%s" % (prefix or "", name) for prefix, name in PYTHON_SCRIPT.findall(text)
        )
        for raw in raw_targets:
            target = _normalize(raw)
            if not target or "<" in target or "*" in target:
                continue
            targets.setdefault(target, []).append(relpath)
    return targets


# The runnable surface the contracts actually document. Asserting this set keeps
# the resolution check honest: a guard that silently stops matching anything
# passes exactly as readily as one that works.
EXPECTED_TARGETS = frozenset(
    {
        ".cursor/hooks/runtime_gate.py",
        "harness/cli.py",
        "harness/scope_probe.py",
        "harness/tests",
    }
)


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
        text = _read("docs/workspace-rule.md")
        for root in ("axon911-frontend", "prepared911", "vault-core-ux", "personal-harness"):
            self.assertIn("`%s`" % root, text)
        self.assertIn("docs/runtime-contract.md", text)

    def test_cursor_rule_defers_to_the_shared_workspace_rule(self) -> None:
        """Both hosts must read one document. A Cursor rule that restates the
        roots or source priority drifts from `docs/workspace-rule.md` silently,
        which is how the pre-CORE-754 prepared911-first ordering survived the
        authority inversion."""
        text = _read(".cursor/rules/prepared911-workspace.mdc")
        self.assertIn("docs/workspace-rule.md", text)
        self.assertNotIn("Source priority", text)
        self.assertNotIn("turbo/apps/docs", text)

    def test_documented_command_paths_resolve(self) -> None:
        """Every runnable path a doc tells a reader to type must exist.

        `docs/implementation-contract.md` once directed readers to
        `unittest discover -s .cursor/hooks/tests` after the suite had moved to
        `harness/tests`. Prose review passed it repeatedly because a path that
        reads plausibly is indistinguishable from one that resolves."""
        missing = [
            "%s -> %s" % (", ".join(sources), target)
            for target, sources in sorted(_documented_targets().items())
            if not os.path.exists(os.path.join(ROOT, target))
        ]
        self.assertEqual(missing, [], "documented paths that do not exist: %s" % missing)

    def test_path_guard_still_matches_the_documented_surface(self) -> None:
        """Guard the guard. `test_documented_command_paths_resolve` reports an
        empty `missing` list both when every path resolves and when the patterns
        match nothing at all, so a docs reformat could retire the check in
        silence while the suite stayed green."""
        found = set(_documented_targets())
        self.assertEqual(
            sorted(EXPECTED_TARGETS - found),
            [],
            "path guard no longer sees documented targets it used to cover",
        )


if __name__ == "__main__":
    unittest.main()
