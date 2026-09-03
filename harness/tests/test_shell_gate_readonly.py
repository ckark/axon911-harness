"""Read-only Git compound chains."""

from __future__ import annotations

import os
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.shell_gate import classify  # noqa: E402


class ReadonlyGitChainTests(unittest.TestCase):
    def test_git_log_and_status_allowed(self) -> None:
        result = classify("git log -1 --oneline && git status --short --branch")
        self.assertEqual(result["permission"], "allow")
        self.assertEqual(result["reason"], "readonly-git-chain")

    def test_mixed_read_and_commit_denied(self) -> None:
        result = classify("git status && git commit -m x")
        self.assertEqual(result["permission"], "deny")

    def test_fetch_in_chain_allowed(self) -> None:
        result = classify("git fetch origin && git rev-parse HEAD")
        self.assertEqual(result["permission"], "allow")


if __name__ == "__main__":
    unittest.main()
