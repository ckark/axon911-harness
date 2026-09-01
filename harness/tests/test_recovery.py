"""Ledger recovery, permissions, locks, and retention."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.ledger import (  # noqa: E402
    LedgerError,
    acquire_lock,
    append_record,
    gc_segments,
    iter_records,
    recover_segment,
    release_lock,
)
from lib.receipts import evaluate_gate, issue_review_receipt  # noqa: E402


def _record(base: str, fingerprint: str = "fp") -> None:
    append_record(
        {
            "kind": "observation",
            "event_id": "sessionStart",
            "root": "personal-harness",
            "worktree_id": "wt",
            "fingerprint": fingerprint,
            "status": STATUS_PASS,
        },
        base=base,
    )


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def _segment(self) -> str:
        ledger = os.path.join(self.base, "ledger")
        names = [name for name in os.listdir(ledger) if name.endswith(".jsonl")]
        self.assertTrue(names)
        return os.path.join(ledger, sorted(names)[-1])

    def test_owner_only_permissions(self) -> None:
        _record(self.base)
        runtime_mode = stat.S_IMODE(os.stat(self.base).st_mode)
        self.assertEqual(runtime_mode, 0o700)
        segment = self._segment()
        self.assertEqual(stat.S_IMODE(os.stat(segment).st_mode), 0o600)
        index = os.path.join(self.base, "state.json")
        self.assertEqual(stat.S_IMODE(os.stat(index).st_mode), 0o600)

    def test_truncated_tail_is_dropped(self) -> None:
        _record(self.base)
        segment = self._segment()
        with open(segment, "ab") as handle:
            handle.write(b'{"kind":"observation","fingerprint":"partial"')
        recover_segment(segment)
        records = list(iter_records(self.base))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["fingerprint"], "fp")

    def test_earlier_corruption_fails_closed_at_gate(self) -> None:
        _record(self.base)
        segment = self._segment()
        with open(segment, "wb") as handle:
            handle.write(b"{not-json}\n")
            handle.write(b'{"kind":"observation","status":"PASS"}\n')
        with self.assertRaises(LedgerError):
            recover_segment(segment)
        index = os.path.join(self.base, "state.json")
        with open(index, "w", encoding="utf-8") as handle:
            handle.write("{not-json")
        gate = evaluate_gate(
            "personal-harness",
            "wt",
            "fp",
            ["review.T0"],
            "",
            "T0",
            base=self.base,
        )
        self.assertEqual(gate["permission"], "deny")
        self.assertEqual(gate["status"], STATUS_BLOCKED)

    def test_lock_timeout(self) -> None:
        _record(self.base)
        held = acquire_lock(self.base, timeout_s=0.2)

        def _contend() -> None:
            with self.assertRaises(LedgerError):
                acquire_lock(self.base, timeout_s=0.1)

        worker = threading.Thread(target=_contend)
        worker.start()
        worker.join(2)
        release_lock(held)
        self.assertFalse(worker.is_alive())

    def test_gc_removes_stale_unreferenced_segments(self) -> None:
        _record(self.base)
        segment = self._segment()
        old = time.time() - (31 * 24 * 60 * 60)
        os.utime(segment, (old, old))
        gc_segments(base=self.base, now=time.time())
        self.assertFalse(os.path.exists(segment))

    def test_index_lookup_does_not_scan_history(self) -> None:
        for index in range(20):
            issue_review_receipt(
                "personal-harness",
                "wt",
                "fp-%d" % index,
                "T0",
                ["frontend-architecture-critic"],
                STATUS_PASS,
                "",
                base=self.base,
            )
        started = time.time()
        gate = evaluate_gate("personal-harness", "wt", "fp-19", ["review.T0"], "", "T0", base=self.base)
        elapsed = time.time() - started
        self.assertEqual(gate["permission"], "allow")
        self.assertLess(elapsed, 0.5)


if __name__ == "__main__":
    unittest.main()
