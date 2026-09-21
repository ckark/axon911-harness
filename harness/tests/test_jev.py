"""Jev client, redaction, judgments, and CLI (mocked transport)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from typing import Any, Dict, Mapping

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import STATUS_INCONCLUSIVE  # noqa: E402
from lib.jev import evaluate, noul_probability, run_smoke  # noqa: E402
from lib.jev_cli import cmd_jev  # noqa: E402
from lib.jev_redaction import build_state, redact_secrets, sanitize_user_request  # noqa: E402
from lib.judgments import (  # noqa: E402
    assess_command,
    check_claim,
    route_task,
)


def _mock_response(body: Mapping[str, Any]) -> Dict[str, Any]:
    answers: Dict[str, Any] = {}
    for qid, question in (body.get("questions") or {}).items():
        qtype = question.get("type")
        if qtype == "noul":
            answers[qid] = {"type": "noul", "noul": 0.92}
        elif qtype == "choice":
            criteria = question.get("criteria") or {}
            choice = "no_match" if "no_match" in criteria else next(iter(criteria))
            probs = {key: 0.0 for key in criteria}
            if choice in probs:
                probs[choice] = 1.0
            answers[qid] = {
                "type": "choice",
                "choice": choice,
                "probabilities": probs,
                "confidence": 0.91,
            }
    return {"model": "jev-mock-1.0.0", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}


class JevRedactionTests(unittest.TestCase):
    def test_redact_api_key(self) -> None:
        text = "Authorization: Bearer apikey_secret123"
        cleaned = redact_secrets(text)
        self.assertNotIn("apikey_secret123", cleaned)

    def test_user_request_bounded(self) -> None:
        long_text = "x" * 5000
        self.assertLessEqual(len(sanitize_user_request(long_text)), 2000)


class JevClientTests(unittest.TestCase):
    def test_evaluate_mock(self) -> None:
        result = evaluate("hello", {"ok": {"type": "noul", "instructions": "Is this a greeting?"}}, transport=_mock_response)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(noul_probability(result, "ok") or 0, 0.92)

    def test_smoke_mock(self) -> None:
        result = run_smoke(transport=_mock_response)
        self.assertEqual(result["policy_action"], "pass")

    def test_transport_failure_inconclusive(self) -> None:
        from lib.jev import JevError

        def _fail(_body: Mapping[str, Any]) -> Dict[str, Any]:
            raise JevError("forced")

        result = evaluate("x", {"q": {"type": "noul", "instructions": "?"}}, transport=_fail)
        self.assertEqual(result["status"], STATUS_INCONCLUSIVE)


class JevJudgmentTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["HARNESS_JEV_RECORD"] = "0"

    def test_check_claim_supported(self) -> None:
        def claim_mock(body: Mapping[str, Any]) -> Dict[str, Any]:
            answers = {}
            for qid in body.get("questions") or {}:
                value = 0.95 if qid == "supported" else 0.05
                answers[qid] = {"type": "noul", "noul": value}
            return {"model": "jev-mock", "answers": answers, "usage": {}}

        decision = check_claim(
            "Python is 3.9.6",
            "python3 --version -> Python 3.9.6",
            transport=claim_mock,
        )
        self.assertEqual(decision["decision"], "supported")

    def test_route_task_no_match(self) -> None:
        roster = [{"id": "plan-check", "label": "plan-check", "summary": "Plan gate"}]
        decision = route_task("hello world", roster=roster, transport=_mock_response)
        self.assertIn(decision["policy_action"], ("fallback", "route"))

    def test_assess_command_shadow(self) -> None:
        decision = assess_command("echo hi", transport=_mock_response, mode="shadow")
        self.assertIn(decision["policy_action"], ("allow", "fallback", "ask", "deny"))


class JevCliTests(unittest.TestCase):
    def test_cli_smoke_json(self) -> None:
        os.environ["HARNESS_JEV_RECORD"] = "0"
        from lib import jev as jev_module

        previous = jev_module._default_transport
        jev_module._default_transport = _mock_response  # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                fixture = os.path.join(tmp, "fixture.json")
                with open(fixture, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "state": "test",
                            "questions": {"ok": {"type": "noul", "instructions": "yes?"}},
                            "expected": {"ok": {"type": "noul", "min": 0.5, "max": 1.0}},
                        },
                        handle,
                    )
                self.assertEqual(cmd_jev(["eval", "--fixture", fixture, "--json"]), 0)
        finally:
            jev_module._default_transport = previous


if __name__ == "__main__":
    unittest.main()
