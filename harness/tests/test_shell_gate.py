"""Classify supported Agent-shell mutation commands without executing them."""

from __future__ import annotations

import os
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.shell_gate import classify  # noqa: E402


class ShellGateTests(unittest.TestCase):
    def test_non_mutation_is_allowed(self) -> None:
        result = classify("echo hi")
        self.assertEqual(result["permission"], "allow")

    def test_direct_git_commit_is_supported(self) -> None:
        result = classify("git commit -m 'ok'")
        self.assertEqual(result["permission"], "ask")
        self.assertEqual(result["family"], "git-commit")

    def test_direct_git_push_is_supported(self) -> None:
        result = classify("git push origin HEAD")
        self.assertEqual(result["permission"], "ask")
        self.assertEqual(result["family"], "git-push")

    def test_git_dash_c_commit(self) -> None:
        result = classify("git -C /tmp/repo commit -m x")
        self.assertEqual(result["family"], "git-commit")
        self.assertEqual(result["permission"], "ask")

    def test_mutation_cwd_reads_git_dash_c(self) -> None:
        from lib.shell_gate import mutation_cwd

        self.assertEqual(
            mutation_cwd("git -C /tmp/repo commit -m x", "/harness"),
            "/tmp/repo",
        )
        self.assertEqual(
            mutation_cwd("rtk git -C /tmp/repo commit -m x", "/harness"),
            "/tmp/repo",
        )
        self.assertEqual(mutation_cwd("git commit -m x", "/harness"), "/harness")

    def test_absolute_git_path(self) -> None:
        result = classify("/usr/bin/git commit -m x")
        self.assertEqual(result["family"], "git-commit")

    def test_rtk_git_commit(self) -> None:
        result = classify("rtk git commit -m x")
        self.assertEqual(result["family"], "git-commit")

    def test_rtk_hook_cursor_is_not_a_git_mutation(self) -> None:
        result = classify("rtk hook cursor")
        self.assertEqual(result["permission"], "allow")

    def test_gt_create_and_submit(self) -> None:
        create = classify("gt create -m x")
        submit = classify("gt submit")
        self.assertEqual(create["family"], "gt-create")
        self.assertEqual(submit["family"], "gt-submit")
        self.assertEqual(create["permission"], "ask")
        self.assertEqual(submit["permission"], "ask")

    def test_compound_commit_and_push_denied(self) -> None:
        result = classify("git commit -am x && git push")
        self.assertEqual(result["permission"], "deny")
        self.assertEqual(result["family"], "compound")

    def test_force_push_denied(self) -> None:
        self.assertEqual(classify("git push --force origin HEAD")["permission"], "deny")
        self.assertEqual(classify("git push -f origin HEAD")["permission"], "deny")

    def test_push_all_mirror_delete_denied(self) -> None:
        self.assertEqual(classify("git push --all")["reason"], "push-all")
        self.assertEqual(classify("git push --mirror")["reason"], "push-mirror")
        self.assertEqual(classify("git push --delete origin topic")["reason"], "push-delete")

    def test_unattested_tags_and_refspecs_denied(self) -> None:
        self.assertEqual(classify("git push --tags")["reason"], "unattested-tags")
        self.assertEqual(classify("git push origin HEAD:refs/heads/topic")["reason"], "unattested-refspec")

    def test_unknown_wrapper_is_outside_guarantee(self) -> None:
        result = classify("GIT_DIR=.git git commit -m x")
        self.assertEqual(result["permission"], "allow")
        self.assertEqual(result["reason"], "not-mutation")

    def test_quoted_mention_of_a_mutation_command_is_not_a_chain(self) -> None:
        """A script that mentions the phrase inside a string is not chaining it.

        This is the exact shape that blocked real edits during development: a
        multi-line Python/JSON script whose test payload happens to contain
        'git commit' inside a quoted string. The newline alone must not turn
        that into a denied compound mutation.
        """
        script = 'payload = {"command": "git commit -m x"}\nprint(payload)\n'
        result = classify(script)
        self.assertEqual(result["permission"], "allow")
        self.assertEqual(result["reason"], "not-mutation")

    def test_quoted_mention_of_push_is_not_a_chain(self) -> None:
        script = "message = 'remember to git push when ready'\nprint(message)\n"
        result = classify(script)
        self.assertEqual(result["permission"], "allow")

    def test_unquoted_chain_is_still_denied(self) -> None:
        """Stripping quoted spans must not blind the check to a real chain."""
        result = classify("echo hi && git commit -m x")
        self.assertEqual(result["permission"], "deny")
        self.assertEqual(result["reason"], "compound-or-ambiguous-mutation")

    def test_newline_chained_mutation_is_still_denied(self) -> None:
        result = classify("git commit -m x\ngit push")
        self.assertEqual(result["permission"], "deny")
        self.assertEqual(result["reason"], "compound-or-ambiguous-mutation")

    def test_backtick_substitution_of_a_mutation_is_still_denied(self) -> None:
        """Backticks are real shell syntax and are deliberately not stripped."""
        result = classify("echo `git commit -m x`")
        self.assertEqual(result["permission"], "deny")
        self.assertEqual(result["reason"], "compound-or-ambiguous-mutation")

    def test_quote_stripping_does_not_merge_adjacent_tokens(self) -> None:
        """Replacing a quoted span with a space must not fuse the words around
        it into a new false match, e.g. 'a "x" commit' must not read as one
        token spanning the gap."""
        script = 'a = "x"\ncommit = 1\nprint(a, commit)\n'
        result = classify(script)
        self.assertEqual(result["permission"], "allow")


if __name__ == "__main__":
    unittest.main()
