"""Migration evidence manifest validation and recording."""

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
from lib.evidence import record_evidence  # noqa: E402
from lib.ledger import current_state  # noqa: E402
from lib.migration_evidence import (  # noqa: E402
    load_manifest,
    manifest_sha256,
    merge_pr_body,
    migration_obligation_ids,
    obligation_id_for_change,
    revalidate_migration_manifest,
    render_pr_body,
    validate_manifest_shape,
    verify_pr_body_block,
)


class MigrationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.manifest_path = os.path.join(self.root, "manifest.json")
        self.capture = {
            "route": "/chatroom/cr-1",
            "entrypoint": "dispatch",
            "scenario_id": "share-banner-notes",
            "capture_kind": "product-route",
            "theme": "dark",
            "brand": "prepared",
            "viewport": "1280x720",
            "state": "shared-unacknowledged",
        }
        self.manifest = {
            "schema_version": 3,
            "plan_hash": "core819-call-taking",
            "changes": [
                {
                    "change_id": "share-banner-notes",
                    "title": "ShareBanner PSAP share callout",
                    "evidence_state": "changed",
                    "capture_kind": "product-route",
                    "source_paths": ["turbo/apps/dispatch/src/modules/chatroom-psap-sharing/ShareBanner/ShareBanner.tsx"],
                    "capture": self.capture,
                    "before_url": "https://github.com/user-attachments/assets/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "after_url": "https://github.com/user-attachments/assets/11111111-2222-3333-4444-555555555555",
                }
            ],
        }
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(self.manifest, handle)
        self.before_path = os.path.join(self.root, "before.png")
        self.after_path = os.path.join(self.root, "after.png")
        write_min_png(self.before_path)
        write_min_png(self.after_path, width=129)
        self.before_receipt = os.path.join(self.root, "before.receipt.json")
        self.after_receipt = os.path.join(self.root, "after.receipt.json")
        write_capture_receipt(
            self.before_receipt,
            self.before_path,
            capture=self.capture,
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            role="before",
        )
        write_capture_receipt(
            self.after_receipt,
            self.after_path,
            capture=self.capture,
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            role="after",
        )

    def test_manifest_shape_validation(self) -> None:
        errors = validate_manifest_shape(self.manifest)
        self.assertEqual(errors, [])

    def test_migration_obligations_are_scoped_to_root(self) -> None:
        self.assertEqual(
            migration_obligation_ids("prepared911", self.manifest),
            ["prepared911.migration-evidence.share-banner-notes"],
        )
        self.assertEqual(migration_obligation_ids("personal-harness", self.manifest), [])

    def test_parity_rows_do_not_create_screenshot_obligations(self) -> None:
        manifest = {
            "schema_version": 3,
            "plan_hash": "parity",
            "changes": [
                {
                    "change_id": "token-swap",
                    "title": "Navbar token swap",
                    "root": "prepared911",
                    "evidence_state": "expected_unchanged",
                    "capture_kind": "product-route",
                    "source_paths": ["turbo/apps/dispatch/src/modules/app-template/AppNavbar/AppNavbar.tsx"],
                },
                {
                    "change_id": "static-check",
                    "title": "Static only",
                    "root": "prepared911",
                    "evidence_state": "static_only",
                    "capture_kind": "not-applicable",
                    "source_paths": ["turbo/apps/dispatch/package.json"],
                },
            ],
        }
        self.assertEqual(migration_obligation_ids("prepared911", manifest), [])
        self.assertEqual(validate_manifest_shape(manifest), [])

    def test_record_and_revalidate_change_pair(self) -> None:
        obligation = obligation_id_for_change("prepared911", "share-banner-notes")
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-before",
            "core819-call-taking",
            "ctx",
            obligation,
            "before",
            os.path.basename(self.before_path),
            base_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            change_id="share-banner-notes",
            capture=self.capture,
            capture_receipt_path=os.path.basename(self.before_receipt),
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            base=self.base,
        )
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-after",
            "core819-call-taking",
            "ctx",
            obligation,
            "after",
            os.path.basename(self.after_path),
            change_id="share-banner-notes",
            capture=self.capture,
            capture_receipt_path=os.path.basename(self.after_receipt),
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            base=self.base,
        )
        state = current_state(base=self.base)
        errors = revalidate_migration_manifest(
            self.root,
            state,
            "prepared911",
            "wt",
            load_manifest(self.manifest_path),
            "ctx",
            base_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            fingerprint="fp-after",
            active_plan_hash="core819-call-taking",
        )
        self.assertEqual(errors, [])

    def test_render_pr_body_requires_urls(self) -> None:
        body = render_pr_body(
            load_manifest(self.manifest_path),
            base_sha="base123",
            head_sha="head123",
            manifest_hash=manifest_sha256(self.manifest),
        )
        self.assertIn("ShareBanner PSAP share callout", body)
        self.assertIn("visual-evidence:start", body)
        self.assertIn("visual-evidence:end", body)
        self.assertIn("https://github.com/user-attachments/assets/", body)

    def test_merge_pr_body_preserves_cursor_summary(self) -> None:
        existing = "Intro\n\n<!-- CURSOR_SUMMARY -->summary\n"
        block = render_pr_body(self.manifest, base_sha="b", head_sha="h", manifest_hash="abc")
        merged = merge_pr_body(existing, block)
        self.assertLess(merged.index("Visual changes"), merged.index("CURSOR_SUMMARY"))
        self.assertIn("summary", merged)

    def test_identical_before_after_hash_is_rejected(self) -> None:
        obligation = obligation_id_for_change("prepared911", "share-banner-notes")
        import shutil

        shutil.copyfile(self.before_path, self.after_path)
        write_capture_receipt(
            self.after_receipt,
            self.after_path,
            capture=self.capture,
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            role="after",
        )
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-before",
            "core819-call-taking",
            "ctx",
            obligation,
            "before",
            os.path.basename(self.before_path),
            base_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            change_id="share-banner-notes",
            capture=self.capture,
            capture_receipt_path=os.path.basename(self.before_receipt),
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            base=self.base,
        )
        record_evidence(
            "prepared911",
            self.root,
            "wt",
            "fp-after",
            "core819-call-taking",
            "ctx",
            obligation,
            "after",
            os.path.basename(self.after_path),
            change_id="share-banner-notes",
            capture=self.capture,
            capture_receipt_path=os.path.basename(self.after_receipt),
            source_sha="cccccccccccccccccccccccccccccccccccccccc",
            base=self.base,
        )
        state = current_state(base=self.base)
        errors = revalidate_migration_manifest(
            self.root,
            state,
            "prepared911",
            "wt",
            load_manifest(self.manifest_path),
            "ctx",
            base_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            fingerprint="fp-after",
            active_plan_hash="core819-call-taking",
            require_hosted_urls=False,
        )
        self.assertIn("before-after-hash-identical:share-banner-notes", errors)

    def test_verify_pr_body_block(self) -> None:
        body = render_pr_body(
            self.manifest,
            base_sha="base123",
            head_sha="head123",
            manifest_hash=manifest_sha256(self.manifest),
        )
        errors = verify_pr_body_block(
            body,
            base_sha="base123",
            head_sha="head123",
            manifest_hash=manifest_sha256(self.manifest),
            expected_change_count=1,
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
