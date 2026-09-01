"""Plan conformance and unmeasurable-tree detection.

Covers the gap between plan approval and pre-commit: scope creep that no other
gate can see, and trees whose state nobody authored.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.conformance import (  # noqa: E402
    IN_SCOPE,
    UNDECLARED,
    UNIMPLEMENTED,
    classify,
    evaluate,
    normalize_scope,
    register_scope,
    summarize,
)
from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.tier import compute_tier, interrupted_operation, unmerged_paths  # noqa: E402


class ConformanceTests(unittest.TestCase):
    def test_no_declared_scope_means_nothing_was_promised(self) -> None:
        result = classify([], ["a.ts", "b.ts"])
        self.assertEqual(result[IN_SCOPE], ["a.ts", "b.ts"])
        self.assertEqual(result[UNDECLARED], [])
        self.assertEqual(result[UNIMPLEMENTED], [])

    def test_undeclared_change_is_detected(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout/**"],
            [
                "packages/ui-core/src/components/callout/index.tsx",
                "packages/ui-core/src/components/badge/index.tsx",
            ],
        )
        self.assertEqual(result[UNDECLARED], ["packages/ui-core/src/components/badge/index.tsx"])

    def test_unimplemented_declaration_is_detected(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout/**", "packages/ui-blocks/src/**"],
            ["packages/ui-core/src/components/callout/index.tsx"],
        )
        self.assertEqual(result[UNIMPLEMENTED], ["packages/ui-blocks/src/**"])

    def test_comma_joined_scope_becomes_separate_globs(self) -> None:
        """`--scope 'a/**,b/**'` reads as two globs and must register as two.

        Stored verbatim it is one pattern that matches no path, which blocks
        with an `unimplemented` entry quoting the whole string back instead of
        naming the real problem."""
        self.assertEqual(
            normalize_scope([".cursor/**,skills/**", " harness/tests/** "]),
            [".cursor/**", "skills/**", "harness/tests/**"],
        )

    def test_normalized_scope_classifies_what_the_raw_string_could_not(self) -> None:
        raw = [".cursor/**,harness/tests/**"]
        changed = [".cursor/agents/critic.md", "harness/tests/test_x.py"]
        self.assertEqual(classify(raw, changed)[UNIMPLEMENTED], raw)
        self.assertEqual(classify(normalize_scope(raw), changed)[UNIMPLEMENTED], [])

    def test_normalize_scope_drops_blanks_and_duplicates(self) -> None:
        self.assertEqual(normalize_scope(["a/**,,a/**", "  ", "b/**"]), ["a/**", "b/**"])

    def test_tests_stories_and_docs_are_never_scope_creep(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout/index.tsx"],
            [
                "packages/ui-core/src/components/callout/index.tsx",
                "packages/ui-core/src/components/callout/index.stories.tsx",
                "packages/ui-core/src/components/callout/index.test.tsx",
                "apps/docs/mdx/design/components/callout/usage.mdx",
            ],
        )
        self.assertEqual(result[UNDECLARED], [])

    def test_declared_directory_covers_its_contents(self) -> None:
        result = classify(
            ["packages/ui-core/src/components/callout"],
            ["packages/ui-core/src/components/callout/deep/nested/file.tsx"],
        )
        self.assertEqual(result[UNDECLARED], [])

    def test_summary_is_actionable_or_empty(self) -> None:
        clean = classify([], ["a.ts"])
        self.assertEqual(summarize(clean), "")
        dirty = classify(["declared/**"], ["undeclared/x.ts"])
        message = summarize(dirty)
        self.assertIn("undeclared/x.ts", message)
        self.assertIn("declared/**", message)


class UnmeasurableTreeTests(unittest.TestCase):
    """A conflicted or mid-operation tree must not produce a confident tier."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "axon911-frontend")
        os.makedirs(os.path.join(self.repo, "packages/ui-core/src"))
        self._git("init", "-q")
        self._git("config", "user.email", "dev@example.com")
        self._git("config", "user.name", "Dev")
        self._write("export const a = 1;\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "base")
        self.base = self._git_out("rev-parse", "--abbrev-ref", "HEAD").strip()
        self._git("checkout", "-qb", "feature")
        self._write("export const a = 2;\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "feature")
        self._git("checkout", "-q", self.base)
        self._write("export const a = 3;\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "other")
        self.roots = {"axon911-frontend": self.repo, "personal-harness": self.tmp}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args: str) -> None:
        subprocess.check_call(
            ["git", *args], cwd=self.repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def _git_out(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, stdout=subprocess.PIPE, text=True
        ).stdout

    def _write(self, content: str) -> None:
        with open(os.path.join(self.repo, "packages/ui-core/src/index.ts"), "w") as handle:
            handle.write(content)

    def test_clean_tree_is_measurable(self) -> None:
        self.assertEqual(unmerged_paths(self.repo), [])
        self.assertEqual(interrupted_operation(self.repo), "")

    def test_conflicted_tree_is_unmeasurable(self) -> None:
        subprocess.run(
            ["git", "merge", "feature"],
            cwd=self.repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.assertEqual(unmerged_paths(self.repo), ["packages/ui-core/src/index.ts"])
        self.assertEqual(interrupted_operation(self.repo), "merge")

        result = compute_tier(
            {"axon911-frontend": ["packages/ui-core/src/index.ts"]}, self.roots
        )
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["predicate"], "unmeasurable")
        self.assertFalse(result["measurable"])
        self.assertTrue(
            any("unresolved conflict" in item for item in result["evidence"]),
            "the reason must name the conflict, not just report T2",
        )


if __name__ == "__main__":
    unittest.main()
