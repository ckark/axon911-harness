"""Migration evidence manifest validation and recording."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.evidence import record_evidence  # noqa: E402
from lib.ledger import current_state  # noqa: E402
from lib.migration_evidence import (  # noqa: E402
    load_manifest,
    obligation_id_for_change,
    revalidate_migration_manifest,
    render_pr_body,
    validate_manifest_shape,
)


class MigrationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.manifest_path = os.path.join(self.root, "manifest.json")
        self.manifest = {
            "plan_hash": "core819-call-taking",
            "changes": [
                {
                    "change_id": "share-banner-notes",
                    "title": "ShareBanner PSAP share callout",
                    "source_paths": ["turbo/apps/dispatch/src/modules/chatroom-psap-sharing/ShareBanner/ShareBanner.tsx"],
                    "capture": {
                        "story_id": "Dispatch App/chatroom/ShareBanner",
                        "theme": "dark",
                        "brand": "prepared",
                        "viewport": "1280x720",
                        "state": "shared-unacknowledged",
                    },
                    "before_url": "https://example.com/before.png",
                    "after_url": "https://example.com/after.png",
                }
            ],
        }
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(self.manifest, handle)
        self.before_path = os.path.join(self.root, "before.png")
        self.after_path = os.path.join(self.root, "after.png")
        with open(self.before_path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\nbefore")
        with open(self.after_path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\nafter")

    def test_manifest_shape_validation(self) -> None:
        errors = validate_manifest_shape(self.manifest)
        self.assertEqual(errors, [])

    def test_record_and_revalidate_change_pair(self) -> None:
        capture = self.manifest["changes"][0]["capture"]
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
            base_oid="base123",
            change_id="share-banner-notes",
            capture=capture,
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
            capture=capture,
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
            base_oid="base123",
            fingerprint="fp-after",
        )
        self.assertEqual(errors, [])

    def test_render_pr_body_uses_urls(self) -> None:
        body = render_pr_body(load_manifest(self.manifest_path))
        self.assertIn("ShareBanner PSAP share callout", body)
        self.assertIn("https://example.com/before.png", body)
        self.assertIn("https://example.com/after.png", body)


if __name__ == "__main__":
    unittest.main()
