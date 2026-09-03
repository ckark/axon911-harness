"""Privacy-safe session handoff."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.ledger import current_state  # noqa: E402
from lib.sessions import create_handoff  # noqa: E402


class SessionHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        os.environ["HARNESS_RUNTIME_DIR"] = self.base

    def tearDown(self) -> None:
        os.environ.pop("HARNESS_RUNTIME_DIR", None)

    def test_handoff_stores_only_safe_fields(self) -> None:
        payload = create_handoff(
            "personal-harness",
            HARNESS,
            "wt",
            "fp",
            "session-1",
            "implementation",
            base=self.base,
        )
        allowed = {
            "session_id",
            "phase",
            "plan_hash",
            "plan_context_hash",
            "tier",
            "head",
            "fingerprint",
            "changed_paths",
            "obligation_statuses",
            "next_command",
        }
        self.assertTrue(set(payload.keys()).issubset(allowed))
        state = current_state(base=self.base)
        self.assertIn("handoffs", state)


if __name__ == "__main__":
    unittest.main()
