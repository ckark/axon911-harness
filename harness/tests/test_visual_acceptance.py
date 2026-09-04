"""Visual acceptance report and receipt validation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.visual_acceptance import validate_acceptance_report  # noqa: E402


class VisualAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp()

    def _write_report(self, payload: dict) -> str:
        path = os.path.join(self.root, "report.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return path

    def test_per_change_fail_blocks_even_when_overall_pass(self) -> None:
        path = self._write_report(
            {
                "overall": "PASS",
                "change_verdicts": {"change-a": "FAIL", "change-b": "PASS"},
            }
        )
        errors = validate_acceptance_report(
            path,
            expected_change_ids=["change-a", "change-b"],
            authoring_session_id="author",
            reviewer_session_id="reviewer",
        )
        self.assertIn("change-verdict-fail:change-a", errors)

    def test_same_reviewer_and_author_session_blocked(self) -> None:
        path = self._write_report({"change_verdicts": {"change-a": "PASS"}})
        errors = validate_acceptance_report(
            path,
            expected_change_ids=["change-a"],
            authoring_session_id="same",
            reviewer_session_id="same",
        )
        self.assertIn("reviewer-session-must-differ-from-author", errors)

    def test_unexpected_change_id_blocked(self) -> None:
        path = self._write_report({"change_verdicts": {"change-a": "PASS", "extra": "PASS"}})
        errors = validate_acceptance_report(
            path,
            expected_change_ids=["change-a"],
            authoring_session_id="author",
            reviewer_session_id="reviewer",
        )
        self.assertIn("unexpected-verdict:extra", errors)


if __name__ == "__main__":
    unittest.main()
