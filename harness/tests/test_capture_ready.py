"""Capture-ready preflight and session budget gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.capture_ready import evaluate_capture_ready  # noqa: E402
from lib.constants import STATUS_BLOCKED, STATUS_PASS  # noqa: E402
from lib.plan_profile import register_plan_profile  # noqa: E402
from lib.sessions import budget_verdict, estimate_transcript_cost  # noqa: E402


class CaptureReadyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=False)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=False)
        self.manifest_path = os.path.join(self.root, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": 2,
                    "plan_hash": "plan-x",
                    "changes": [
                        {
                            "change_id": "change-a",
                            "title": "Change A",
                            "source_paths": ["packages/ui-core/src/components/callout/index.tsx"],
                            "capture": {
                                "story_id": "Callout/Default",
                                "theme": "dark",
                                "brand": "prepared",
                                "viewport": "1280x720",
                                "state": "default",
                            },
                        }
                    ],
                },
                handle,
            )

    def test_strict_profile_required_for_capture_ready(self) -> None:
        result = evaluate_capture_ready(
            "personal-harness",
            self.root,
            "wt",
            "fp",
            base=self.base,
        )
        self.assertFalse(result["ready"])
        self.assertIn("missing-strict-plan-profile", result["errors"])

    def test_budget_verdict_blocks_over_limit(self) -> None:
        verdict = budget_verdict(
            {"main_assistant_turns": 61, "context_bytes": 1000},
            {"budget_max_turns": 60, "budget_max_context_bytes": 320_000},
        )
        self.assertEqual(verdict["status"], STATUS_BLOCKED)
        self.assertIn("session-budget-exceeded-turns", verdict["reasons"])

    def test_estimate_transcript_cost_counts_assistant_turns(self) -> None:
        transcript = os.path.join(self.root, "thread.jsonl")
        with open(transcript, "w", encoding="utf-8") as handle:
            handle.write('{"role":"user","text":"hi"}\n')
            handle.write('{"role":"assistant","text":"hello"}\n')
            handle.write('{"role":"assistant","text":"again"}\n')
        cost = estimate_transcript_cost(transcript)
        self.assertEqual(cost["main_assistant_turns"], 2)

    def test_strict_profile_with_manifest_passes_shape(self) -> None:
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp",
            "plan-x",
            "T1",
            ["packages/ui-core/**"],
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "",
            {},
            required_paths=["packages/ui-core/src/components/callout/index.tsx"],
            evidence_manifest_pointer=self.manifest_path,
            strict=True,
            base=self.base,
        )
        result = evaluate_capture_ready(
            "personal-harness",
            self.root,
            "wt",
            "fp",
            base=self.base,
        )
        self.assertNotIn("missing-evidence-manifest", result["errors"])
        self.assertNotIn("missing-base-oid", result["errors"])


if __name__ == "__main__":
    unittest.main()
