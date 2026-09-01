"""Transparent attest-wrapping: recognize a registered check command and route
it through the attesting wrapper without changing what it actually runs.
"""

from __future__ import annotations

import os
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.attest_rewrite import already_wrapped, matching_obligation, rewrite  # noqa: E402

CLI = "/opt/harness/cli.py"


class MatchingObligationTests(unittest.TestCase):
    def test_exact_registered_command_matches(self) -> None:
        obligation = matching_obligation("axon911-frontend", "pnpm turbo run typecheck")
        self.assertEqual(obligation, "axon911-frontend.ui-allowlist")

    def test_whitespace_differences_still_match(self) -> None:
        obligation = matching_obligation("axon911-frontend", "pnpm  turbo   run typecheck")
        self.assertEqual(obligation, "axon911-frontend.ui-allowlist")

    def test_near_miss_does_not_match(self) -> None:
        """A sharded or flagged variant is a different invocation, not a match.

        Matching is exact-string on purpose: a near-miss like adding
        `-- --shard=1/4` to the storybook check is a materially different run
        and must not be silently credited to the same obligation.
        """
        self.assertIsNone(
            matching_obligation("axon911-frontend", "pnpm test:storybook:ci -- --shard=1/4")
        )

    def test_unrelated_command_does_not_match(self) -> None:
        self.assertIsNone(matching_obligation("axon911-frontend", "pnpm install"))

    def test_bare_rtk_prefix_is_peeled_for_matching(self) -> None:
        obligation = matching_obligation("axon911-frontend", "rtk pnpm turbo run typecheck")
        self.assertEqual(obligation, "axon911-frontend.ui-allowlist")

    def test_rtk_hook_invocation_is_not_peeled(self) -> None:
        """RTK's own hook invocation is not a user command to unwrap."""
        self.assertIsNone(matching_obligation("axon911-frontend", "rtk hook claude"))

    def test_prepared911_has_no_registered_checks_yet(self) -> None:
        self.assertIsNone(matching_obligation("prepared911", "pnpm turbo run typecheck"))

    def test_docs_page_obligation_has_no_shell_check(self) -> None:
        """docs-page is asserted by a human, not attestable by any command."""
        for command in ("pnpm turbo run typecheck", "pnpm --filter docs docs:generate-component-docs"):
            obligation = matching_obligation("axon911-frontend", command)
            self.assertNotEqual(obligation, "axon911-frontend.docs-page")

    def test_all_six_registered_checks_resolve_to_distinct_obligations(self) -> None:
        checks = {
            "pnpm turbo run typecheck": "axon911-frontend.ui-allowlist",
            "pnpm --filter docs docs:generate-component-docs": "axon911-frontend.docs-registry",
            "pnpm test:storybook:ci": "axon911-frontend.rendered-evidence",
            "pnpm mf:types:check": "axon911-frontend.mf-types",
            "pnpm feature-flags:check": "axon911-frontend.flag-manifest",
        }
        for command, expected in checks.items():
            self.assertEqual(matching_obligation("axon911-frontend", command), expected, command)


class AlreadyWrappedTests(unittest.TestCase):
    def test_recognizes_the_current_entry_point(self) -> None:
        self.assertTrue(already_wrapped("python3 /x/harness/cli.py attest --root a -- pnpm typecheck"))

    def test_recognizes_the_cursor_shim(self) -> None:
        self.assertTrue(already_wrapped("python3 .cursor/hooks/runtime_gate.py attest --root a"))

    def test_recognizes_a_shell_quoted_path(self) -> None:
        """`rewrite()` shell-quotes the harness path via shlex.quote(), which
        closes the quote right after the filename when the path needs one
        (e.g. it contains a space) -- so a plain substring check for
        'cli.py attest' would miss its own output and re-wrap an already
        attested command."""
        self.assertTrue(already_wrapped('python3 "/x/harness/cli.py" attest --root a -- pnpm typecheck'))
        self.assertTrue(already_wrapped("python3 '/x/harness/cli.py' attest --root a"))

    def test_plain_command_is_not_wrapped(self) -> None:
        self.assertFalse(already_wrapped("pnpm turbo run typecheck"))

    def test_mentioning_attest_without_the_entry_point_is_not_wrapped(self) -> None:
        self.assertFalse(already_wrapped("echo attest this later"))


class RewriteTests(unittest.TestCase):
    def test_rewrite_produces_the_expected_argv_shape(self) -> None:
        wrapped = rewrite("axon911-frontend", "/repo/axon", "pnpm turbo run typecheck", CLI)
        self.assertIsNotNone(wrapped)
        self.assertIn('python3 %s attest' % CLI, wrapped)
        self.assertIn("--root axon911-frontend", wrapped)
        self.assertIn("--obligation-id axon911-frontend.ui-allowlist", wrapped)
        # The original command is appended verbatim after `--`, so the outer
        # shell's own tokenization is what argparse.REMAINDER receives.
        self.assertTrue(wrapped.endswith("-- pnpm turbo run typecheck"))

    def test_rewrite_preserves_an_rtk_prefix_in_what_actually_runs(self) -> None:
        """Recognizing the command under an rtk wrapper must not silently drop
        the wrapper from what is actually executed."""
        wrapped = rewrite("axon911-frontend", "/repo/axon", "rtk pnpm turbo run typecheck", CLI)
        self.assertIsNotNone(wrapped)
        self.assertTrue(wrapped.endswith("-- rtk pnpm turbo run typecheck"))

    def test_already_wrapped_command_is_returned_unchanged_as_none(self) -> None:
        already = 'python3 %s attest --root axon911-frontend --obligation-id x -- pnpm turbo run typecheck' % CLI
        self.assertIsNone(rewrite("axon911-frontend", "/repo/axon", already, CLI))

    def test_unrecognized_command_is_not_rewritten(self) -> None:
        self.assertIsNone(rewrite("axon911-frontend", "/repo/axon", "pnpm install", CLI))

    def test_no_registered_checks_means_no_rewrite(self) -> None:
        self.assertIsNone(rewrite("prepared911", "/repo/prepared911", "pnpm turbo run typecheck", CLI))

    def test_no_active_plan_omits_the_plan_hash_flag_rather_than_an_empty_one(self) -> None:
        wrapped = rewrite("axon911-frontend", "/repo/axon-nonexistent-%d" % os.getpid(), "pnpm turbo run typecheck", CLI)
        self.assertIsNotNone(wrapped)
        self.assertNotIn("--plan-hash", wrapped)

    def test_rewrite_stays_idempotent_even_when_the_harness_path_needs_quoting(self) -> None:
        """End-to-end regression for the quoted-path idempotence gap: feeding
        rewrite()'s own output back into rewrite() must be a no-op, including
        when the harness CLI path contains a space and gets shell-quoted."""
        spaced_cli = "/opt/harness install/cli.py"
        first = rewrite("axon911-frontend", "/repo/axon", "pnpm turbo run typecheck", spaced_cli)
        self.assertIsNotNone(first)
        self.assertIn("'%s'" % spaced_cli, first)
        second = rewrite("axon911-frontend", "/repo/axon", first, spaced_cli)
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
