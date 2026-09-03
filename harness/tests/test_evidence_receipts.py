"""Evidence registration and gate revalidation."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HARNESS)
sys.path.insert(0, TESTS)

from helpers.evidence_helpers import write_capture_receipt, write_min_png  # noqa: E402
from lib.evidence import record_evidence, revalidate_evidence  # noqa: E402
from lib.ledger import current_state  # noqa: E402
from lib.media_validation import MediaValidationError, validate_image_artifact  # noqa: E402


class EvidenceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.artifact = os.path.join(self.root, "shot.png")
        write_min_png(self.artifact)
        self.receipt = os.path.join(self.root, "shot.receipt.json")
        write_capture_receipt(self.receipt, self.artifact, capture={"story_id": "demo/story"}, role="after")

    def test_record_and_revalidate(self) -> None:
        record_evidence(
            "personal-harness",
            self.root,
            "wt",
            "fp-after",
            "plan",
            "ctx",
            "personal-harness.rendered-evidence",
            "after",
            os.path.basename(self.artifact),
            capture_receipt_path=os.path.basename(self.receipt),
            base=self.base,
        )
        state = current_state(base=self.base)
        errors = revalidate_evidence(
            self.root,
            state,
            "personal-harness",
            "wt",
            "personal-harness.rendered-evidence",
            "ctx",
            require_before=False,
            require_after=True,
            fingerprint="fp-after",
        )
        self.assertEqual(errors, [])

    def test_reject_fake_png(self) -> None:
        fake = os.path.join(self.root, "fake.png")
        with open(fake, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\nnot-a-real-image")
        with self.assertRaises(MediaValidationError):
            validate_image_artifact(fake)


if __name__ == "__main__":
    unittest.main()
