"""Vendored ponytail ruleset and review skill."""

from __future__ import annotations

import os
import re
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(HARNESS, ".."))
sys.path.insert(0, HARNESS)

from lib.judgments import load_skill_roster  # noqa: E402
from lib.review_reports import ALLOWED_CRITICS  # noqa: E402

PINNED_SHA = "e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156"
PINNED_VERSION = "4.10.0"


class PonytailVendorTests(unittest.TestCase):
    def test_docs_provenance_and_adaptations(self) -> None:
        path = os.path.join(REPO, "docs", "ponytail.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(PINNED_SHA, text)
        self.assertIn(PINNED_VERSION, text)
        self.assertIn("Precedence", text)
        self.assertIn("override", text.lower())
        self.assertNotIn("ponytail:", text)
        self.assertNotIn("no frameworks", text.lower())
        self.assertNotIn("no fixtures", text.lower())

    def test_license_present(self) -> None:
        license_path = os.path.join(REPO, "third_party", "ponytail", "LICENSE")
        self.assertTrue(os.path.isfile(license_path))
        with open(license_path, encoding="utf-8") as handle:
            self.assertIn("MIT License", handle.read())

    def test_review_skill_frontmatter(self) -> None:
        path = os.path.join(REPO, ".cursor", "skills", "ponytail-review", "SKILL.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("---"))
        self.assertIn("name: ponytail-review", text)
        self.assertIn("SIMPLIFY-###", text)
        self.assertIn("ponytail-review-<fingerprint>.md", text)

    def test_roster_includes_ponytail_review(self) -> None:
        ids = [item["id"] for item in load_skill_roster(["personal-harness"])]
        self.assertIn("personal-harness#ponytail-review", ids)

    def test_ponytail_review_not_receipt_critic(self) -> None:
        self.assertNotIn("ponytail-review", ALLOWED_CRITICS)

    def test_project_hooks_no_ponytail(self) -> None:
        hooks_path = os.path.join(REPO, ".cursor", "hooks.json")
        with open(hooks_path, encoding="utf-8") as handle:
            raw = handle.read()
        self.assertNotRegex(raw, re.compile(r"ponytail", re.I))


if __name__ == "__main__":
    unittest.main()
