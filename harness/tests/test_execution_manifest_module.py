"""Canonical execution manifest loading and registration mapping."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.execution_manifest import (  # noqa: E402
    EXECUTION_MANIFEST_SCHEMA_VERSION,
    execution_manifest_hash,
    load_execution_manifest,
    profile_kwargs_from_manifest,
    validate_execution_manifest,
)
from lib.plan_profile import register_plan_profile  # noqa: E402


class ExecutionManifestModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        self.head = head
        self.manifest_path = os.path.join(self.base, "execution-manifest.json")
        self.manifest = {
            "schema_version": EXECUTION_MANIFEST_SCHEMA_VERSION,
            "plan_hash": "lean-execution-compliance",
            "tier": "T2",
            "target_roots": {
                "personal-harness": {
                    "base_oid": head,
                    "allowed_paths": ["harness/**", "docs/**"],
                    "required_paths": ["harness/lib/execution_manifest.py"],
                    "mirror_intent": "",
                    "evidence_states": {
                        "harness/**": "none",
                        "docs/**": "none",
                    },
                }
            },
            "budgets": {
                "max_assistant_turns": 60,
                "max_context_bytes": 320000,
            },
        }
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(self.manifest, handle)

    def test_validate_and_hash_manifest(self) -> None:
        errors = validate_execution_manifest(load_execution_manifest(self.manifest_path), repo_path=self.repo)
        self.assertEqual(errors, [])
        digest = execution_manifest_hash(self.manifest)
        self.assertEqual(len(digest), 64)

    def test_profile_kwargs_from_manifest(self) -> None:
        kwargs = profile_kwargs_from_manifest(load_execution_manifest(self.manifest_path), "personal-harness")
        self.assertTrue(kwargs["strict"])
        self.assertEqual(kwargs["plan_hash"], "lean-execution-compliance")
        self.assertIn("harness/**", kwargs["scope"])
        self.assertEqual(kwargs["evidence_states"]["harness/**"], "none")

    def test_register_from_manifest_fields(self) -> None:
        kwargs = profile_kwargs_from_manifest(load_execution_manifest(self.manifest_path), "personal-harness")
        register_plan_profile(
            "personal-harness",
            "wt",
            "fp",
            kwargs["plan_hash"],
            kwargs["tier"],
            kwargs["scope"],
            kwargs["base_oid"],
            kwargs["mirror_intent"],
            {},
            required_paths=kwargs["required_paths"],
            target_roots=kwargs["target_roots"],
            evidence_states=kwargs["evidence_states"],
            execution_manifest_hash=kwargs["execution_manifest_hash"],
            strict=True,
            budget_max_turns=kwargs["budget_max_turns"],
            budget_max_context_bytes=kwargs["budget_max_context_bytes"],
            evidence_manifest_pointer=os.path.join(self.base, "evidence.json"),
            base=self.base,
        )


if __name__ == "__main__":
    unittest.main()
