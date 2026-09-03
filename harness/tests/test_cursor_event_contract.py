"""Synthetic Cursor event contracts for every registered lifecycle hook."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from dispatch.cursor import handle_event  # noqa: E402
from lib.schema import SchemaError, parse_event  # noqa: E402

EVENTS = (
    "sessionStart",
    "afterFileEdit",
    "postToolUse",
    "subagentStop",
    "preCompact",
    "beforeShellExecution",
    "stop",
)


class CursorEventContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        os.environ["HARNESS_RUNTIME_DIR"] = self.tmp
        self.previous_review = os.environ.get("HARNESS_REVIEW_MODE")
        os.environ["HARNESS_REVIEW_MODE"] = "always"

    def tearDown(self) -> None:
        if self.previous_review is None:
            os.environ.pop("HARNESS_REVIEW_MODE", None)
        else:
            os.environ["HARNESS_REVIEW_MODE"] = self.previous_review

    def test_valid_payloads_parse(self) -> None:
        samples = {
            "sessionStart": {"session_id": "s", "is_background_agent": False, "composer_mode": "agent"},
            "afterFileEdit": {"file_path": os.getcwd(), "edits": []},
            "postToolUse": {
                "tool_name": "Shell",
                "tool_input": "{}",
                "tool_output": "{\"ok\":true}",
                "cwd": os.getcwd(),
                "duration": 1,
            },
            "subagentStop": {"status": "completed", "task": "t", "description": "d", "summary": "s", "duration": 1},
            "preCompact": {"is_automatic": True},
            "beforeShellExecution": {"command": "echo hi", "cwd": os.getcwd(), "timeout": 10},
            "stop": {"status": "completed", "loop_count": 0},
        }
        for event in EVENTS:
            parsed = parse_event(event, json.dumps(samples[event]).encode("utf-8"))
            self.assertEqual(parsed["event"], event)

    def test_post_tool_use_parses_stringified_output(self) -> None:
        parsed = parse_event(
            "postToolUse",
            json.dumps({"tool_output": "{\"code\":0}"}).encode("utf-8"),
        )
        self.assertEqual(parsed["tool_output_parsed"], {"code": 0})

    def test_malformed_before_shell_denies(self) -> None:
        result = handle_event("beforeShellExecution", b"{")
        self.assertEqual(result.get("permission"), "deny")

    def test_malformed_observational_fails_open(self) -> None:
        result = handle_event("sessionStart", b"{")
        self.assertEqual(result, {})

    def test_echo_is_allowed(self) -> None:
        payload = json.dumps({"command": "echo hi", "cwd": os.getcwd()}).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "allow")

    def test_compound_git_is_denied(self) -> None:
        payload = json.dumps({"command": "git commit -am x && git push", "cwd": os.getcwd()}).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "deny")

    def test_git_commit_without_receipts_is_denied(self) -> None:
        payload = json.dumps({"command": "git commit -m x", "cwd": os.getcwd()}).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "deny")
        self.assertIn("/implementation-check", result.get("agent_message", ""))

    def test_subagent_error_followup_is_not_a_receipt(self) -> None:
        payload = json.dumps({"status": "error", "summary": "failed"}).encode("utf-8")
        result = handle_event("subagentStop", payload)
        self.assertIn("followup_message", result)
        self.assertIn("/implementation-check", result["followup_message"])
        from lib.ledger import iter_records

        kinds = [item.get("kind") for item in iter_records(self.tmp)]
        self.assertIn("observation", kinds)
        self.assertNotIn("review_receipt", kinds)
        self.assertNotIn("verification_receipt", kinds)

    def test_stop_asks_for_proof_when_receipts_missing(self) -> None:
        payload = json.dumps({"status": "completed", "loop_count": 0}).encode("utf-8")
        result = handle_event("stop", payload)
        self.assertIn("followup_message", result)
        self.assertIn("/implementation-check", result["followup_message"])

    def test_stop_followup_stops_after_limit(self) -> None:
        payload = json.dumps({"status": "completed", "loop_count": 0, "session_id": "loop"}).encode(
            "utf-8"
        )
        saw_followup = 0
        last = {}
        for _ in range(5):
            last = handle_event("stop", payload)
            if last.get("followup_message"):
                saw_followup += 1
        self.assertGreaterEqual(saw_followup, 1)
        self.assertLessEqual(saw_followup, 3)
        self.assertEqual(last, {})

    def test_unknown_event_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            parse_event("notAnEvent", b"{}")

    def test_hooks_json_registers_required_events(self) -> None:
        path = os.path.join(os.path.dirname(HARNESS), ".cursor", "hooks.json")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for event in EVENTS:
            self.assertIn(event, data["hooks"])
            self.assertTrue(data["hooks"][event][0]["command"].endswith("runtime_gate.py %s" % event))
        self.assertEqual(data["hooks"]["stop"][0]["loop_limit"], 3)
        self.assertEqual(data["hooks"]["subagentStop"][0]["loop_limit"], 3)

    def test_git_dash_c_outside_cwd_does_not_use_harness_root(self) -> None:
        prepared = "/Users/ckark/Documents/GitHub/prepared911"
        payload = json.dumps(
            {
                "command": "git -C %s commit -m x" % prepared,
                "cwd": os.getcwd(),
            }
        ).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "deny")
        message = result.get("agent_message", "")
        self.assertIn("root=prepared911", message)
        self.assertNotIn("root=personal-harness", message)

    def test_git_dash_c_axon_does_not_use_harness_root(self) -> None:
        axon = "/Users/ckark/Documents/GitHub/axon911-frontend"
        payload = json.dumps(
            {
                "command": "git -C %s commit -m x" % axon,
                "cwd": os.getcwd(),
            }
        ).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "deny")
        message = result.get("agent_message", "")
        self.assertIn("root=axon911-frontend", message)
        self.assertNotIn("root=personal-harness", message)

    def test_git_commit_outside_configured_roots_is_denied(self) -> None:
        payload = json.dumps({"command": "git commit -m x", "cwd": "/tmp"}).encode("utf-8")
        result = handle_event("beforeShellExecution", payload)
        self.assertEqual(result.get("permission"), "deny")
        self.assertIn("root-identity", result.get("agent_message", ""))

    def test_observational_events_do_not_fingerprint(self) -> None:
        from dispatch import cursor

        def boom(*_args, **_kwargs):
            raise AssertionError("snapshot must not run for observational events")

        original = cursor.snap
        cursor.snap = boom
        try:
            result = handle_event("sessionStart", b"{}")
            self.assertEqual(result, {})
            result = handle_event("preCompact", b"{}")
            self.assertEqual(result, {})
            result = handle_event("postToolUse", b"{}")
            self.assertEqual(result, {})
        finally:
            cursor.snap = original


if __name__ == "__main__":
    unittest.main()
