from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.route_capture import _find_playwright_root  # noqa: E402


class RouteCaptureTests(unittest.TestCase):
    def test_finds_playwright_test_workspace_dependency(self) -> None:
        root = tempfile.mkdtemp()
        automation = os.path.join(root, "turbo", "apps", "automation")
        package = os.path.join(automation, "node_modules", "@playwright", "test")
        os.makedirs(package)
        with open(os.path.join(package, "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}")

        self.assertEqual(_find_playwright_root(root), automation)


if __name__ == "__main__":
    unittest.main()
