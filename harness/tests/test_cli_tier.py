"""CLI-level coverage for `cli.py tier`, in particular `--against`.

The library-level tier tests (`test_tier_scoring.py`) exercise `compute_tier`
directly. This covers the CLI wiring itself: `cmd_tier` defaults to only the
uncommitted worktree (what a live PreToolUse/Stop hook needs), and `--against
<ref>` switches to the full branch diff -- the gap that let a real PR's
already-committed public API addition score as `surface_delta: none` when
scored through the plain CLI default.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)


def _git(root: str, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _write(root: str, relative: str, content: str) -> None:
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


class CliTierAgainstTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.axon = os.path.join(self.tmp, "axon911-frontend")
        os.makedirs(self.axon)
        _git(self.axon, "init", "-q")
        _git(self.axon, "config", "user.email", "dev@example.com")
        _git(self.axon, "config", "user.name", "Dev")
        _write(self.axon, "packages/ui-core/package.json", '{"name": "@prepared/ui-core"}\n')
        _write(
            self.axon,
            "packages/ui-core/src/index.ts",
            'export * from "./components/menu/menu-exports";\n',
        )
        _write(
            self.axon,
            "packages/ui-core/src/components/menu/menu-exports.ts",
            'export { Menu } from "./index";\n',
        )
        _write(self.axon, "packages/ui-core/src/components/menu/index.tsx", "export const Menu = () => null;\n")
        _git(self.axon, "add", "-A")
        _git(self.axon, "commit", "-qm", "trunk")

        # A "branch": a real commit adding a new export to the barrel,
        # never touching index.ts -- exactly the MenuCollapsibleGroup shape.
        _write(
            self.axon,
            "packages/ui-core/src/components/menu/menu-exports.ts",
            'export { Menu } from "./index";\nexport { NewThing } from "./new-thing";\n',
        )
        _write(self.axon, "packages/ui-core/src/components/menu/new-thing.tsx", "export const NewThing = () => null;\n")
        _git(self.axon, "add", "-A")
        _git(self.axon, "commit", "-qm", "feature")

        self.env = dict(
            os.environ,
            HARNESS_RUNTIME_DIR=os.path.join(self.tmp, "rt"),
            HARNESS_ROOTS_JSON=json.dumps({"axon911-frontend": self.axon}),
            PYTHONDONTWRITEBYTECODE="1",
        )

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args: str):
        return subprocess.run(
            [sys.executable, os.path.join(HARNESS, "cli.py"), "tier", "--root", "axon911-frontend", *args],
            cwd=self.axon,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )

    def test_default_sees_nothing_on_a_clean_committed_branch(self) -> None:
        """The default scope is the uncommitted worktree, which is empty
        right after a commit -- exactly what a live Stop/PreToolUse hook
        needs, and why it must never silently widen to the whole branch."""
        result = self._run("--json")
        report = json.loads(result.stdout)
        self.assertEqual(report["tier"], "T0")
        self.assertEqual(report["surface_delta"], "none")

    def test_against_trunk_sees_the_full_branch_and_scores_additive(self) -> None:
        result = self._run("--against", "HEAD~1", "--json")
        report = json.loads(result.stdout)
        self.assertEqual(report["surface_delta"], "additive")
        self.assertEqual(report["tier"], "T1")
        self.assertTrue(any("NewThing" in item for item in report["evidence"]))

    def test_against_implies_the_same_base_ref_for_surface_diffing(self) -> None:
        """Without this, --against would list committed files but still diff
        each one against HEAD for surface classification, comparing the
        feature commit to itself and finding no delta at all."""
        result = self._run("--against", "HEAD~1")
        self.assertIn("surface-additive", result.stdout)

    def test_explicit_base_ref_still_overrides_against(self) -> None:
        result = self._run("--against", "HEAD~1", "--base-ref", "HEAD", "--json")
        report = json.loads(result.stdout)
        # Diffing the feature commit against itself finds nothing, even
        # though the file list (from --against) is the same.
        self.assertEqual(report["surface_delta"], "none")

    def test_scores_the_worktree_the_changes_are_in(self) -> None:
        """`HARNESS_ROOTS_JSON` names one static path per root, but work
        happens in linked worktrees. Collecting changed files from the
        worktree and then diffing them in the configured checkout -- where
        those same files are untouched -- reports `none` for every surface
        change and collapses every tier to T0."""
        worktree = os.path.join(self.tmp, "axon-feature-worktree")
        _git(self.axon, "worktree", "add", "-q", "-b", "feature-wt", worktree, "HEAD")
        # An uncommitted new export, present only in the linked worktree.
        _write(
            worktree,
            "packages/ui-core/src/components/menu/menu-exports.ts",
            'export { Menu } from "./index";\n'
            'export { NewThing } from "./new-thing";\n'
            'export { WorktreeOnly } from "./worktree-only";\n',
        )
        _write(
            worktree,
            "packages/ui-core/src/components/menu/worktree-only.tsx",
            "export const WorktreeOnly = () => null;\n",
        )

        result = subprocess.run(
            [sys.executable, os.path.join(HARNESS, "cli.py"), "tier", "--root", "axon911-frontend", "--json"],
            cwd=worktree,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["surface_delta"], "additive")
        self.assertEqual(report["tier"], "T1")
        self.assertTrue(any("WorktreeOnly" in item for item in report["evidence"]))


if __name__ == "__main__":
    unittest.main()
