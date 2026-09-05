"""Regression corpus for known CORE-819 evidence defects."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HARNESS)
sys.path.insert(0, TESTS)

from helpers.evidence_helpers import write_capture_receipt, write_min_png  # noqa: E402
from lib.capture_receipt import (  # noqa: E402
    load_capture_receipt,
    validate_capture_receipt_binding,
    validate_dom_assertion_results,
)
from lib.evidence import record_evidence  # noqa: E402
from lib.ledger import current_state  # noqa: E402
from lib.migration_evidence import (  # noqa: E402
    load_manifest,
    obligation_id_for_change,
    revalidate_migration_manifest,
)


class Core819RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.capture = {
            "story_id": "Demo/Story",
            "theme": "dark",
            "brand": "prepared",
            "viewport": "1280x720",
            "state": "default",
        }

    def _record_pair(
        self,
        change_id: str,
        before_path: str,
        after_path: str,
        *,
        before_receipt_path: str,
        after_receipt_path: str,
    ) -> None:
        obligation = obligation_id_for_change("prepared911", change_id)
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-before",
            "core819",
            "ctx",
            obligation,
            "before",
            os.path.basename(before_path),
            base_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            change_id=change_id,
            capture=self.capture,
            capture_receipt_path=os.path.basename(before_receipt_path),
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            base=self.base,
        )
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-after",
            "core819",
            "ctx",
            obligation,
            "after",
            os.path.basename(after_path),
            change_id=change_id,
            capture=self.capture,
            capture_receipt_path=os.path.basename(after_receipt_path),
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            base=self.base,
        )

    def test_row_layout_identical_hash_rejected(self) -> None:
        manifest = {
            "schema_version": 2,
            "plan_hash": "core819",
            "changes": [
                {
                    "change_id": "row-layout",
                    "title": "Row layout rhythm",
                    "source_paths": ["packages/ui-core/src/components/typography/styles.scss"],
                    "capture": self.capture,
                }
            ],
        }
        before_path = os.path.join(self.root, "row-before.png")
        after_path = os.path.join(self.root, "row-after.png")
        write_min_png(before_path)
        write_min_png(after_path)
        before_receipt = os.path.join(self.root, "row-before.receipt.json")
        after_receipt = os.path.join(self.root, "row-after.receipt.json")
        write_capture_receipt(
            before_receipt,
            before_path,
            capture={**self.capture, "change_id": "row-layout"},
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            role="before",
        )
        write_capture_receipt(
            after_receipt,
            after_path,
            capture={**self.capture, "change_id": "row-layout"},
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            role="after",
        )
        self._record_pair(
            "row-layout",
            before_path,
            after_path,
            before_receipt_path=before_receipt,
            after_receipt_path=after_receipt,
        )
        state = current_state(base=self.base)
        errors = revalidate_migration_manifest(
            self.root,
            state,
            "prepared911",
            "wt",
            manifest,
            "ctx",
            fingerprint="fp-after",
            require_hosted_urls=False,
        )
        self.assertIn("before-after-hash-identical:row-layout", errors)

    def test_critical_misses_dom_assertion_failure(self) -> None:
        receipt_path = os.path.join(self.root, "critical.receipt.json")
        artifact = os.path.join(self.root, "critical.png")
        write_min_png(artifact)
        write_capture_receipt(receipt_path, artifact, capture=self.capture, role="after")
        receipt = load_capture_receipt(receipt_path)
        receipt["dom_assertions"] = [
            {"type": "required-descendant", "selector": ".rt-CalloutRoot", "passed": False}
        ]
        receipt["health"]["dom_assertions_passed"] = False
        with open(receipt_path, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle)
        errors = validate_capture_receipt_binding(receipt, artifact)
        self.assertIn("dom-assertion-failed:required-descendant", errors)

    def test_anet_cta_overflow_assertion_failure(self) -> None:
        assertions = [{"type": "no-overflow", "selector": ".rt-CalloutRoot", "passed": False}]
        errors = validate_dom_assertion_results(assertions)
        self.assertIn("dom-assertion-failed:no-overflow", errors)

    def test_unresolved_source_sha_rejected(self) -> None:
        artifact = os.path.join(self.root, "anet.png")
        receipt_path = os.path.join(self.root, "anet.receipt.json")
        write_min_png(artifact)
        write_capture_receipt(
            receipt_path,
            artifact,
            capture=self.capture,
            source_sha="not-a-real-commit",
            role="after",
        )
        receipt = load_capture_receipt(receipt_path)
        errors = validate_capture_receipt_binding(
            receipt,
            artifact,
            require_resolved_commit_sha=True,
            repo_path=self.root,
        )
        self.assertIn("capture-receipt-unresolved-source-sha", errors)

    def test_regression_case_catalog_matches_handlers(self) -> None:
        catalog_path = os.path.join(TESTS, "fixtures", "core819_regression_cases.json")
        with open(catalog_path, encoding="utf-8") as handle:
            cases = json.load(handle)
        self.assertGreaterEqual(len(cases), 4)
        for case in cases:
            self.assertIn("case_id", case)
            self.assertIn("expected_errors", case)


if __name__ == "__main__":
    unittest.main()
