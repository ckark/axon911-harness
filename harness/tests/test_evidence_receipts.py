"""Evidence registration and gate revalidation."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.evidence import record_evidence, revalidate_evidence  # noqa: E402
from lib.ledger import current_state  # noqa: E402


class EvidenceReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        self.artifact = os.path.join(self.root, "shot.png")
        with open(self.artifact, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n")

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


if __name__ == "__main__":
    unittest.main()
