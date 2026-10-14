"""GitHub attach version gate tests."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.github_attach import GitHubAttachError, parse_gh_version, require_gh_attach  # noqa: E402


class GitHubAttachTests(unittest.TestCase):
    def test_parse_gh_version(self) -> None:
        self.assertEqual(parse_gh_version("gh version 2.99.0 (2026-01-01)"), (2, 99, 0))

    @mock.patch("lib.github_attach.subprocess.run")
    def test_require_gh_attach_rejects_old(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = mock.Mock(stdout="gh version 2.96.0\n", returncode=0)
        with self.assertRaises(GitHubAttachError):
            require_gh_attach()


if __name__ == "__main__":
    unittest.main()
