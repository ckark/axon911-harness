"""Concurrent worktrees of the same configured root.

A user routinely has several worktrees of axon911-frontend open at once, one
per branch or task -- eight, in the case that motivated this suite. Only the
first happens to sit at the hardcoded default path. Before this, every other
worktree fell outside all four configured roots entirely: a git commit there
was denied with `root-identity`, and any Claude Code session there was
silently treated as unrelated to the harness altogether.
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

from dispatch import cursor  # noqa: E402
from dispatch.common import resolve_cli_root, resolve_root  # noqa: E402
from lib.paths import PathError, identify_root, worktree_identity  # noqa: E402


def _git(args, cwd):
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _git_out(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, stdout=subprocess.PIPE, text=True).stdout.strip()


class MultiWorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.primary = os.path.join(self.tmp, "axon911-frontend")
        os.makedirs(os.path.join(self.primary, "packages/ui/src"))
        _git(["init", "-q"], self.primary)
        _git(["config", "user.email", "d@e.com"], self.primary)
        _git(["config", "user.name", "D"], self.primary)
        with open(os.path.join(self.primary, "packages/ui/src/index.ts"), "w") as f:
            f.write("export const a = 1;\n")
        _git(["add", "-A"], self.primary)
        _git(["commit", "-qm", "base"], self.primary)

        # A second, linked worktree on its own branch -- exactly the pattern
        # from real usage: one worktree per concurrent task.
        self.second = os.path.join(self.tmp, "axon911-frontend-second-task")
        _git(["worktree", "add", "-q", "-b", "second-task", self.second], self.primary)

        self.prepared = os.path.join(self.tmp, "prepared911")
        os.makedirs(self.prepared)
        _git(["init", "-q"], self.prepared)
        _git(["config", "user.email", "d@e.com"], self.prepared)
        _git(["config", "user.name", "D"], self.prepared)
        with open(os.path.join(self.prepared, "README"), "w") as f:
            f.write("x\n")
        _git(["add", "-A"], self.prepared)
        _git(["commit", "-qm", "base"], self.prepared)

        self.roots = {
            "axon911-frontend": self.primary,
            "prepared911": self.prepared,
            "personal-harness": self.tmp,
        }
        self.previous_env = {
            key: os.environ.get(key) for key in ("HARNESS_RUNTIME_DIR", "HARNESS_ROOTS_JSON")
        }
        os.environ["HARNESS_RUNTIME_DIR"] = os.path.join(self.tmp, "rt")
        os.environ["HARNESS_ROOTS_JSON"] = json.dumps(
            {"axon911-frontend": self.primary, "prepared911": self.prepared}
        )

    def tearDown(self) -> None:
        import shutil

        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- identity ---

    def test_two_worktrees_share_a_common_git_dir(self) -> None:
        _, primary_common = worktree_identity(self.primary)
        _, second_common = worktree_identity(self.second)
        self.assertIsNotNone(primary_common)
        self.assertEqual(primary_common, second_common)

    def test_unrelated_directory_has_no_git_identity_here(self) -> None:
        outside = tempfile.mkdtemp()
        self.assertEqual(worktree_identity(outside), (None, None))

    # --- identify_root ---

    def test_second_worktree_resolves_to_the_same_root_id(self) -> None:
        root_id, root_path = identify_root(self.second, self.roots)
        self.assertEqual(root_id, "axon911-frontend")
        # Critically, its own path -- not the primary's.
        self.assertEqual(root_path, os.path.realpath(self.second))

    def test_nested_path_inside_the_second_worktree_still_resolves(self) -> None:
        nested = os.path.join(self.second, "packages/ui/src/index.ts")
        root_id, root_path = identify_root(nested, self.roots)
        self.assertEqual(root_id, "axon911-frontend")
        self.assertEqual(root_path, os.path.realpath(self.second))

    def test_primary_still_resolves_via_the_fast_path(self) -> None:
        """The prefix-match fast path must still win when it applies, so the
        common case never pays for a git subprocess call."""
        root_id, root_path = identify_root(self.primary, self.roots)
        self.assertEqual(root_id, "axon911-frontend")
        self.assertEqual(root_path, os.path.realpath(self.primary))

    def test_a_worktree_of_an_unconfigured_repo_is_still_out_of_scope(self) -> None:
        other_repo = os.path.join(self.tmp, "totally-unrelated")
        os.makedirs(other_repo)
        _git(["init", "-q"], other_repo)
        with self.assertRaises(PathError):
            identify_root(other_repo, self.roots)

    # --- dispatch.common.resolve_root / resolve_cli_root ---

    def test_dispatch_resolve_root_returns_the_second_worktrees_own_path(self) -> None:
        root_id, root_path = resolve_root(self.second)
        self.assertEqual(root_id, "axon911-frontend")
        self.assertEqual(root_path, os.path.realpath(self.second))

    def test_resolve_cli_root_prefers_cwd_when_it_matches(self) -> None:
        previous = os.getcwd()
        try:
            os.chdir(self.second)
            self.assertEqual(resolve_cli_root("axon911-frontend"), os.path.realpath(self.second))
        finally:
            os.chdir(previous)

    def test_resolve_cli_root_falls_back_when_cwd_is_unrelated(self) -> None:
        previous = os.getcwd()
        try:
            os.chdir(self.tmp)
            self.assertEqual(resolve_cli_root("axon911-frontend"), os.path.realpath(self.primary))
        finally:
            os.chdir(previous)

    # --- end-to-end: each worktree is scored against its own changes ---

    def test_each_worktree_is_gated_by_its_own_changes_not_the_primarys(self) -> None:
        # The primary has an untracked packages/ui file; the second worktree does
        # not touch packages/ui at all. Before threading root_path through every
        # call site, both would have been evaluated against the *primary's*
        # tree regardless of which one the event actually named.
        with open(os.path.join(self.primary, "packages/ui/src/widget.ts"), "w") as f:
            f.write("export const Widget = 1;\n")

        primary_result = cursor.handle_event(
            "stop", json.dumps({"session_id": "p", "cwd": self.primary}).encode()
        )
        second_result = cursor.handle_event(
            "stop", json.dumps({"session_id": "s", "cwd": self.second}).encode()
        )
        primary_message = primary_result.get("followup_message") or ""
        self.assertIn("Proof is missing or stale", primary_message)
        self.assertNotIn("followup_message", second_result)

    def test_bash_mutation_in_the_second_worktree_is_gated_as_axon(self) -> None:
        """A git commit attempted from the second worktree must resolve to
        axon911-frontend, not `root=unknown` and not silently pass through."""
        result = cursor.handle_event(
            "beforeShellExecution",
            json.dumps(
                {
                    "command": "git push --force origin trunk",
                    "cwd": self.second,
                }
            ).encode(),
        )
        message = result.get("agent_message") or result.get("user_message") or ""
        self.assertIn("root=axon911-frontend", message)
        self.assertNotIn("root=unknown", message)
        self.assertNotIn("root=personal-harness", message)


if __name__ == "__main__":
    unittest.main()
