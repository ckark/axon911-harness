"""Review report validation before review receipts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.receipts import issue_review_receipt  # noqa: E402
from lib.review_reports import (  # noqa: E402
    receipt_status_for_verdict,
    validate_review_report,
)


def _sample_report(
    *,
    verdict: str = "PASS",
    fingerprint: str = "fp1234567890ab",
    plan_hash: str = "planhash",
    tier: str = "T2",
) -> str:
    return (
        "# Specialist review\n\n"
        "## Verdict\n\n"
        "%s\n\n"
        "## Scope reviewed\n\n"
        "- Tier: %s\n"
        "- Plan hash: %s\n"
        "- Fingerprint: %s\n\n"
        "## Findings\n\n"
        "No material issues found.\n"
    ) % (verdict, tier, plan_hash, fingerprint)


class ReviewReportTests(unittest.TestCase):
    def test_pass_verdict_maps_to_pass_status(self) -> None:
        self.assertEqual(receipt_status_for_verdict("PASS"), STATUS_PASS)
        self.assertEqual(receipt_status_for_verdict("CHANGES REQUIRED"), STATUS_BLOCKED)

    def test_validate_matching_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "design-system-critic-fp1234567890ab.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(_sample_report())
            errors, verdict, report_hash = validate_review_report(
                path,
                expected_critic_ids=["design-system-critic"],
                fingerprint="fp1234567890ab",
                plan_hash="planhash",
                tier="T2",
            )
            self.assertEqual(errors, [])
            self.assertEqual(verdict, "PASS")
            self.assertEqual(len(report_hash), 64)

    def test_issue_review_receipt_validates_report(self) -> None:
        base = tempfile.mkdtemp()
        path = os.path.join(base, "design-system-critic-fp1234567890ab.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_sample_report())
        record = issue_review_receipt(
            "personal-harness",
            "wt",
            "fp1234567890ab",
            "T2",
            ["design-system-critic"],
            STATUS_PASS,
            "planhash",
            report_path=path,
            base=base,
        )
        self.assertEqual(record["status"], STATUS_PASS)
        self.assertTrue(record.get("report_hash"))


if __name__ == "__main__":
    unittest.main()
