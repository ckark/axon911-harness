"""Synthetic transcript mining: corrections, retries, redaction, and ledger join."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.episodes import (  # noqa: E402
    FAILURE_KINDS,
    flag_episodes,
    label_errors,
    mine,
    parse_transcript,
    promotion_target,
    report,
    run_routing,
)
from lib.jev_provenance import append_turn_event  # noqa: E402

SECRET = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
CONVERSATION = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _line(role: str, text: str = "", tool: str = "") -> str:
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if tool:
        content.append({"type": "tool_use", "name": "Shell", "input": {"command": tool}})
    return json.dumps({"role": role, "message": {"content": content}})


class EpisodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.projects = os.path.join(self.base, "projects")
        root_name = "Users-ckark-Documents-GitHub-fixture"
        transcript_dir = os.path.join(self.projects, root_name, "agent-transcripts", CONVERSATION)
        os.makedirs(transcript_dir)
        self.transcript = os.path.join(transcript_dir, CONVERSATION + ".jsonl")
        self.roots = {"personal-harness": "/Users/ckark/Documents/GitHub/fixture"}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, body: str) -> None:
        with open(self.transcript, "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_parse_flags_redaction_and_retry(self) -> None:
        query = "<timestamp>Monday, Sep 21, 2026, 8:35 AM (UTC-4)</timestamp>\n<user_query>add a remote %s</user_query>" % SECRET
        cli = "python3 harness/cli.py attest && python3 harness/cli.py attest && python3 harness/cli.py attest"
        skill = "cat .cursor/skills/plan-check/SKILL.md"
        body = "\n".join(
            [
                _line("user", query),
                _line("assistant", "running", cli),
                _line("assistant", "reading", skill),
                _line("user", "<user_query>no, revert that</user_query>"),
                _line("assistant", "ok"),
            ]
        )
        self._write(body)
        episodes = parse_transcript(self.transcript, root_id="personal-harness")
        self.assertEqual(len(episodes), 2)
        self.assertNotIn(SECRET, episodes[0]["excerpt"])
        self.assertIn("[REDACTED:openai-key]", episodes[0]["excerpt"])
        self.assertTrue(episodes[0]["next_is_correction"])
        self.assertEqual(episodes[0]["commands"].count("attest"), 3)
        self.assertIn("plan-check", episodes[0]["skills"])
        flags = flag_episodes(episodes)
        reasons = {reason for item in flags for reason in item["reasons"]}
        self.assertIn("correction-after-harness", reasons)
        self.assertIn("retry-loop", reasons)
        self.assertIn("plan-check-override", reasons)
        self.assertTrue(all(os.path.isabs(str(item["source_path"])) for item in flags))
        self.assertTrue(all(item["line"] for item in flags))

    def test_mine_joins_ledger_and_skips_other_projects(self) -> None:
        self._write(
            "\n".join(
                [
                    _line("user", "<user_query>check the plan</user_query>"),
                    _line("assistant", "done"),
                ]
            )
        )
        other = os.path.join(self.projects, "Users-other-repo", "agent-transcripts", "x", "x.jsonl")
        os.makedirs(os.path.dirname(other))
        with open(other, "w", encoding="utf-8") as handle:
            handle.write(_line("user", "<user_query>ignore me</user_query>"))
        append_turn_event(
            {"kind": "eligible", "turn_id": CONVERSATION + "-11111111-2222-3333-4444-555555555555"},
            base=self.base,
        )
        append_turn_event(
            {"kind": "delivered", "turn_id": CONVERSATION + "-11111111-2222-3333-4444-555555555555"},
            base=self.base,
        )
        summary = mine(projects_dir=self.projects, base=self.base, roots=self.roots)
        self.assertEqual(summary["episodes"], 1)
        path = os.path.join(self.base, "evals", "episodes.jsonl")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as handle:
            episode = json.loads(handle.read())
        self.assertTrue(episode["jev"]["eligible"])
        self.assertTrue(episode["jev"]["delivered"])
        again = mine(projects_dir=self.projects, base=self.base, roots=self.roots)
        self.assertEqual(again["reused"], 1)
        self.assertEqual(again["parsed"], 0)

    def test_report_counts_fallbacks(self) -> None:
        observations = os.path.join(self.base, "jev-observations.jsonl")
        with open(observations, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "question_set": "route-task-rank",
                        "policy_action": "fallback",
                        "fallback_reason": "low-confidence-or-no-match",
                        "usage": {"input_tokens": 10},
                    }
                )
                + "\n"
            )
            handle.write(
                json.dumps(
                    {
                        "question_set": "rank-docs",
                        "policy_action": "fallback",
                        "fallback_reason": "docs-rank-empty",
                        "usage": {"input_tokens": 5},
                    }
                )
                + "\n"
            )
        payload = report(base=self.base, episodes=[])
        self.assertEqual(payload["route_task_rank_low_confidence"], 1)
        self.assertEqual(payload["rank_docs_empty"], 1)
        self.assertEqual(payload["input_tokens"], 15)

    def test_label_schema_and_promotion_paths(self) -> None:
        self.assertEqual(
            label_errors({"episode_id": "a", "failure_kind": "routing", "expected": "abstain", "note": ""}),
            [],
        )
        self.assertIn(
            "unknown-failure-kind",
            label_errors({"episode_id": "a", "failure_kind": "nope", "expected": "", "note": ""}),
        )
        self.assertEqual(promotion_target("routing"), "evals/jev-routing/cases.jsonl")
        self.assertEqual(promotion_target("tier"), "harness/tests/fixtures/core819_regression_cases.json")
        self.assertEqual(
            promotion_target("plan-check"),
            ".cursor/skills/adversarial-review/evals/seeded-design-system-cases.md",
        )
        self.assertEqual(promotion_target("none"), "")
        self.assertIn("budget", FAILURE_KINDS)

    def test_routing_runner_scores_without_calling_network(self) -> None:
        cases = os.path.join(self.base, "cases.jsonl")
        with open(cases, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"id": "1", "request": "plan this", "expected": "personal-harness#plan-check"}) + "\n")
            handle.write(json.dumps({"id": "2", "request": "what time is it", "expected": "abstain"}) + "\n")

        def route(request: str) -> dict:
            if request == "plan this":
                return {
                    "policy_action": "route",
                    "decision": "personal-harness#plan-check",
                    "skill_root": "personal-harness",
                    "skill": "plan-check",
                    "jev": {"rank": {"usage": {"input_tokens": 4}}},
                }
            return {"policy_action": "fallback", "decision": "", "jev": {"rank": {"usage": {"input_tokens": 2}}}}

        scored = run_routing(cases, route=route)
        self.assertEqual(scored["cases"], 2)
        self.assertEqual(scored["precision"], 1.0)
        self.assertEqual(scored["abstain_rate"], 0.5)
        self.assertEqual(scored["input_tokens"], 6)
        empty = run_routing(os.path.join(self.base, "missing.jsonl"), route=route)
        self.assertEqual(empty["cases"], 0)
        self.assertEqual(empty["skipped"], "no cases")


if __name__ == "__main__":
    unittest.main()
