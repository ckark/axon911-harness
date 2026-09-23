"""User-hook Jev routing and plan preflight, with mocked judgments."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from dispatch import jev_hooks  # noqa: E402
from lib.jev_provenance import read_turn_events, routing_status  # noqa: E402


SECRET = "super-secret-phrase"


def _route(_request: str) -> dict:
    return {
        "policy_action": "route",
        "skill_root": "personal-harness",
        "skill": "plan-check",
        "fallback_reason": "",
    }


def _rank(_request: str) -> dict:
    return {"policy_action": "filter", "keep": ["plan-contract"], "drop": ["review-contract"]}


class JevHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_runtime = os.environ.get("HARNESS_RUNTIME_DIR")
        self._old_record = os.environ.get("HARNESS_JEV_RECORD")
        os.environ["HARNESS_RUNTIME_DIR"] = self._tmp.name
        os.environ["HARNESS_JEV_RECORD"] = "1"
        self.spawned = []

    def tearDown(self) -> None:
        if self._old_runtime is None:
            os.environ.pop("HARNESS_RUNTIME_DIR", None)
        else:
            os.environ["HARNESS_RUNTIME_DIR"] = self._old_runtime
        if self._old_record is None:
            os.environ.pop("HARNESS_JEV_RECORD", None)
        else:
            os.environ["HARNESS_JEV_RECORD"] = self._old_record
        self._tmp.cleanup()

    def _payload(self, **extra):
        payload = {
            "conversation_id": "conv-1",
            "generation_id": "gen-1",
            "prompt": "add a remote and " + SECRET,
            "workspace_roots": ["/Users/ckark/Documents/GitHub/axon911-frontend"],
        }
        payload.update(extra)
        return payload

    def test_unregistered_root_spawns_nothing(self) -> None:
        result = jev_hooks.handle_before_submit(
            self._payload(workspace_roots=[self._tmp.name]),
            spawn=self.spawned.append,
        )
        self.assertEqual(result, {"continue": True})
        self.assertEqual(self.spawned, [])
        self.assertEqual(read_turn_events(), [])

    def test_chroma_root_is_registered(self) -> None:
        jev_hooks.handle_before_submit(
            self._payload(workspace_roots=["/Users/ckark/Documents/GitHub/chroma"]),
            spawn=self.spawned.append,
        )
        self.assertEqual(len(self.spawned), 1)

    def test_slash_prompt_is_skipped(self) -> None:
        result = jev_hooks.handle_before_submit(
            self._payload(prompt="/plan-check"),
            spawn=self.spawned.append,
        )
        self.assertEqual(result["continue"], True)
        self.assertEqual(self.spawned, [])

    def test_recording_disabled_skips(self) -> None:
        os.environ["HARNESS_JEV_RECORD"] = "0"
        result = jev_hooks.handle_before_submit(self._payload(), spawn=self.spawned.append)
        self.assertEqual(self.spawned, [])
        self.assertTrue(result["continue"])

    def test_request_file_is_private_and_prompt_is_not_persisted(self) -> None:
        jev_hooks.handle_before_submit(self._payload(), spawn=self.spawned.append)
        self.assertEqual(len(self.spawned), 1)
        path = self.spawned[0]
        self.assertTrue(os.path.isfile(path))
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)
        jev_hooks.run_hook_turn(path, route=_route, rank=_rank)
        self.assertFalse(os.path.exists(path))
        blob = []
        for root, _dirs, files in os.walk(self._tmp.name):
            for name in files:
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    blob.append(handle.read())
        self.assertNotIn(SECRET, "\n".join(blob))
        kinds = [item["kind"] for item in read_turn_events()]
        self.assertEqual(kinds, ["eligible", "routed"])

    def test_result_delivers_once_and_waits_until_ready(self) -> None:
        jev_hooks.handle_before_submit(self._payload(), spawn=self.spawned.append)
        waiting = jev_hooks.handle_post_tool(self._payload())
        self.assertNotIn("additional_context", waiting)
        jev_hooks.run_hook_turn(self.spawned[0], route=_route, rank=_rank)
        first = jev_hooks.handle_post_tool(self._payload())
        self.assertIn("personal-harness#plan-check", first["additional_context"])
        self.assertIn("plan-contract.md", first["additional_context"])
        self.assertIn("review-contract.md", first["additional_context"])
        self.assertNotIn(SECRET, first["additional_context"])
        second = jev_hooks.handle_post_tool(self._payload())
        self.assertNotIn("additional_context", second)
        status = routing_status(base=self._tmp.name)
        self.assertEqual(status["eligible_turns"], 1)
        self.assertEqual(status["routed_turns"], 1)
        self.assertEqual(status["delivered_turns"], 1)

    def test_expired_result_is_dropped(self) -> None:
        jev_hooks.handle_before_submit(self._payload(), spawn=self.spawned.append)
        jev_hooks.run_hook_turn(self.spawned[0], route=_route, rank=_rank)
        key = jev_hooks.turn_key(self._payload())
        meta = jev_hooks.meta_path(key)
        with open(meta, encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["ts"] = 1
        with open(meta, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        result = jev_hooks.handle_post_tool(self._payload(), now=payload["ts"] + jev_hooks.RESULT_TTL_S + 5)
        self.assertNotIn("additional_context", result)

    def test_plan_preflight_lists_missing_sections_when_jev_fails(self) -> None:
        def _boom(_text: str) -> dict:
            raise RuntimeError("down")

        result = jev_hooks.handle_plan_preflight(
            {"tool_name": "CreatePlan", "tool_input": {"plan": "Just build it."}},
            assess=_boom,
        )
        text = result["additional_context"]
        self.assertIn("Target roots", text)
        self.assertIn("failed open", text)

    def test_plan_preflight_merges_low_scores(self) -> None:
        headings = "\n".join("## %s" % section for section in jev_hooks.PLAN_SECTIONS)

        def _assess(_text: str) -> dict:
            return {
                "policy_action": "advisory",
                "scores": {"concrete_scope": 0.1, "verification_alignment": 0.95, "falsifiable_claims": 0.9},
            }

        result = jev_hooks.handle_plan_preflight(
            {"tool_name": "CreatePlan", "tool_input": {"plan": headings}},
            assess=_assess,
        )
        self.assertIn("concrete_scope=0.10", result["additional_context"])
        self.assertNotIn("Missing plan-contract", result["additional_context"])

    def test_malformed_payload_fails_open(self) -> None:
        self.assertEqual(jev_hooks.main(["beforeSubmitPrompt"], b"not-json"), 0)
        self.assertEqual(jev_hooks.main(["postToolUse"], b""), 0)

    def test_routing_status_counts_turns(self) -> None:
        jev_hooks.handle_before_submit(self._payload(), spawn=self.spawned.append)
        jev_hooks.run_hook_turn(self.spawned[0], route=_route, rank=_rank)
        jev_hooks.handle_post_tool(self._payload())
        status = routing_status(base=self._tmp.name)
        self.assertEqual(status["decision"], "routing-observed")
        self.assertEqual(status["jev_failures"], 0)
        self.assertGreaterEqual(status["delivered_turns"] / status["eligible_turns"], 0.9)


if __name__ == "__main__":
    unittest.main()
