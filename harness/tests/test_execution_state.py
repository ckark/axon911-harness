from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.execution_state import begin_attempt, complete_attempt, load_execution_state  # noqa: E402


class ExecutionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = tempfile.mkdtemp()
        self.runtime_patch = patch("lib.execution_state.runtime_dir", return_value=self.runtime)
        self.runtime_patch.start()

    def tearDown(self) -> None:
        self.runtime_patch.stop()

    def test_repeated_idempotency_key_reuses_attempt(self) -> None:
        first = begin_attempt("execution", "capture", max_attempts=2, idempotency_key="same")
        second = begin_attempt("execution", "capture", max_attempts=2, idempotency_key="same")

        self.assertEqual(first, second)
        self.assertEqual(len(load_execution_state("execution")["steps"]["capture"]["attempts"]), 1)

    def test_new_key_consumes_next_attempt_after_failure(self) -> None:
        begin_attempt("execution", "capture", max_attempts=2, idempotency_key="first")
        complete_attempt("execution", "capture", status="failed")
        second = begin_attempt("execution", "capture", max_attempts=2, idempotency_key="second")

        self.assertEqual(second["attempt"], 2)


if __name__ == "__main__":
    unittest.main()
