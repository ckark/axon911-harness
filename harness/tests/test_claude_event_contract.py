"""Claude Code event contracts for every registered lifecycle hook.

Mirrors test_cursor_event_contract.py. Payloads use the field names Claude Code
documents; assertions pin the exact hookSpecificOutput envelope, because a
silently-wrong envelope reads as "no decision" and opens the gate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from dispatch import claude  # noqa: E402
from lib.constants import MAX_EVENT_BYTES  # noqa: E402
from lib.schema import SchemaError, parse_event  # noqa: E402


def _git_repo(parent: str, name: str) -> str:
    path = os.path.join(parent, name)
    os.makedirs(path)
    subprocess.check_call(["git", "init", "-q"], cwd=path)
    subprocess.check_call(["git", "config", "user.email", "dev@example.com"], cwd=path)
    subprocess.check_call(["git", "config", "user.name", "Dev"], cwd=path)
    with open(os.path.join(path, "README"), "w", encoding="utf-8") as handle:
        handle.write("one\n")
    subprocess.check_call(["git", "add", "README"], cwd=path)
    subprocess.check_call(["git", "commit", "-qm", "init"], cwd=path)
    return path


class ClaudeEventContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.previous = {
            key: os.environ.get(key) for key in ("HARNESS_RUNTIME_DIR", "HARNESS_ROOTS_JSON")
        }
        os.environ["HARNESS_RUNTIME_DIR"] = self.tmp
        self.axon = _git_repo(self.tmp, "axon911-frontend")
        self.prepared = _git_repo(self.tmp, "prepared911")
        self.vault = _git_repo(self.tmp, "vault-core-ux")
        os.environ["HARNESS_ROOTS_JSON"] = json.dumps(
            {
                "axon911-frontend": self.axon,
                "prepared911": self.prepared,
                "vault-core-ux": self.vault,
            }
        )

    def tearDown(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # --- helpers ---

    def _send(self, event: str, payload: dict) -> dict:
        return claude.handle_event(event, json.dumps(payload).encode("utf-8"))

    def _decision(self, result: dict) -> str:
        return (result.get("hookSpecificOutput") or {}).get("permissionDecision", "")

    def _reason(self, result: dict) -> str:
        return (result.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")

    def _bash(self, command: str, **extra) -> dict:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.axon}
        payload.update(extra)
        return self._send("PreToolUse", payload)

    def _touch_ui_file(self, root: str) -> str:
        """Write an untracked file under packages/ui-core so path-triggered
        obligations (ui-allowlist, docs-registry, rendered-evidence) actually
        have something concrete to require -- the end-of-turn gate has
        nothing to check against a clean tree."""
        target = os.path.join(root, "packages/ui-core/src/components/widget/index.tsx")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("export const Widget = () => null;\n")
        return target

    # --- envelope ---

    def test_every_event_parses_and_returns_a_mapping(self) -> None:
        samples = {
            "SessionStart": {"trigger": "startup", "cwd": self.axon},
            "PreToolUse": {"tool_name": "Read", "tool_input": {}, "cwd": self.axon},
            "PostToolUse": {"tool_name": "Read", "tool_input": {}, "cwd": self.axon},
            "SubagentStart": {"agent_type": "x", "agent_id": "a", "cwd": self.axon},
            "SubagentStop": {"agent_type": "x", "agent_id": "a", "cwd": self.axon},
            "PreCompact": {"trigger": "auto"},
            "Stop": {"session_id": "s", "stop_hook_active": False, "cwd": self.axon},
            "TaskCreated": {"task_id": "t", "task_name": "n", "cwd": self.axon},
            "TaskCompleted": {"task_id": "t", "task_name": "n", "result": "failure", "cwd": self.axon},
        }
        self.assertEqual(set(samples), set(claude.EVENTS))
        for event, payload in samples.items():
            parsed = parse_event(event, json.dumps(payload).encode("utf-8"))
            self.assertEqual(parsed["event"], event)
            self.assertIsInstance(self._send(event, payload), dict)

    def test_envelope_names_its_own_event(self) -> None:
        result = self._bash("git push --force origin trunk")
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self._touch_ui_file(self.axon)
        result = self._send("Stop", {"session_id": "s1", "cwd": self.axon})
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "Stop")

    def test_unknown_event_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            parse_event("NotAnEvent", b"{}")

    def test_oversized_payload_rejected(self) -> None:
        raw = b'{"tool_name":"Bash","tool_input":{"command":"' + (b"a" * MAX_EVENT_BYTES) + b'"}}'
        with self.assertRaises(SchemaError):
            parse_event("PreToolUse", raw)

    # --- normalization ---

    def test_nested_tool_input_is_flattened(self) -> None:
        parsed = parse_event(
            "PreToolUse",
            json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}).encode(),
        )
        self.assertEqual(parsed["command"], "git commit -m x")
        parsed = parse_event(
            "PostToolUse",
            json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/a/b.ts"}}).encode(),
        )
        self.assertEqual(parsed["file_path"], "/a/b.ts")

    def test_notebook_edit_path_is_recognized(self) -> None:
        parsed = parse_event(
            "PostToolUse",
            json.dumps(
                {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/a/n.ipynb"}}
            ).encode(),
        )
        self.assertEqual(parsed["file_path"], "/a/n.ipynb")

    # --- PreToolUse mutation preflight ---

    def test_benign_command_is_not_gated(self) -> None:
        self.assertEqual(self._bash("ls -la"), {})

    def test_non_bash_tool_is_not_gated(self) -> None:
        self.assertEqual(
            self._send("PreToolUse", {"tool_name": "Read", "tool_input": {}, "cwd": self.axon}), {}
        )

    def test_force_push_denied_and_names_root(self) -> None:
        result = self._bash("git push --force origin trunk")
        self.assertEqual(self._decision(result), "deny")
        self.assertIn("root=axon911-frontend", self._reason(result))
        self.assertIn("force-push", self._reason(result))

    def test_commit_without_receipts_denied_with_recovery_command(self) -> None:
        result = self._bash("git commit -m x")
        self.assertEqual(self._decision(result), "deny")
        # Must name the plugin-namespaced skill: the bare Cursor form is not a
        # command under Claude Code, so it would send the reader nowhere.
        self.assertIn("/a911-harness:implementation-check", self._reason(result))

    def test_commit_and_push_together_denied(self) -> None:
        result = self._bash("git commit -m x && git push")
        self.assertEqual(self._decision(result), "deny")

    def test_plan_mode_is_never_gated(self) -> None:
        self.assertEqual(self._bash("git commit -m x", permission_mode="plan"), {})
        self.assertEqual(
            self._send("Stop", {"session_id": "s", "cwd": self.axon, "permission_mode": "plan"}), {}
        )
        self.assertEqual(
            self._send(
                "TaskCompleted",
                {"task_id": "t", "result": "success", "cwd": self.axon, "permission_mode": "plan"},
            ),
            {},
        )

    def test_rtk_wrapped_mutation_is_still_classified(self) -> None:
        result = self._bash("rtk git push --force origin trunk")
        self.assertEqual(self._decision(result), "deny")

    # --- transparent attest wrapping ---

    def test_recognized_check_command_is_rewritten(self) -> None:
        result = self._bash("pnpm turbo run typecheck")
        output = result["hookSpecificOutput"]
        self.assertEqual(output.get("permissionDecision"), "allow")
        wrapped = output["updatedInput"]["command"]
        self.assertIn("attest", wrapped)
        self.assertIn("--obligation-id axon911-frontend.ui-allowlist", wrapped)
        self.assertTrue(wrapped.endswith("-- pnpm turbo run typecheck"))

    def test_already_wrapped_command_passes_through_unchanged(self) -> None:
        already = (
            'python3 "%s/harness/cli.py" attest --root axon911-frontend '
            "--obligation-id axon911-frontend.ui-allowlist -- pnpm turbo run typecheck" % HARNESS
        )
        self.assertEqual(self._bash(already), {})

    def test_unrecognized_command_is_not_rewritten(self) -> None:
        self.assertEqual(self._bash("pnpm install"), {})

    def test_mutation_commands_are_unaffected_by_the_rewrite_path(self) -> None:
        """The rewrite only runs after mutation-preflight already allowed the
        command, so a git commit must still deny exactly as before."""
        result = self._bash("git commit -m x")
        self.assertEqual(self._decision(result), "deny")
        self.assertNotIn("updatedInput", result["hookSpecificOutput"])

    def test_kill_switch_disables_the_rewrite(self) -> None:
        previous = os.environ.get("CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE")
        os.environ["CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE"] = "false"
        try:
            self.assertEqual(self._bash("pnpm turbo run typecheck"), {})
        finally:
            if previous is None:
                os.environ.pop("CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE", None)
            else:
                os.environ["CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE"] = previous

    def test_rewrite_is_scoped_to_the_configured_roots(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send(
            "PreToolUse",
            {"tool_name": "Bash", "tool_input": {"command": "pnpm turbo run typecheck"}, "cwd": outside},
        )
        self.assertEqual(result, {})

    def test_prepared911_has_no_rewrite_targets_yet(self) -> None:
        result = self._send(
            "PreToolUse",
            {"tool_name": "Bash", "tool_input": {"command": "pnpm turbo run typecheck"}, "cwd": self.prepared},
        )
        self.assertEqual(result, {})

    # --- PostToolUse ---

    def test_edit_outside_deprecating_tree_is_silent(self) -> None:
        result = self._send(
            "PostToolUse",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": os.path.join(self.axon, "packages/ui-core/src/index.ts")},
                "cwd": self.axon,
            },
        )
        self.assertEqual(result, {})

    def test_edit_to_prepared911_ui_package_warns_without_blocking(self) -> None:
        target = os.path.join(self.prepared, "turbo/packages/ui-core/src/index.ts")
        result = self._send(
            "PostToolUse",
            {"tool_name": "Edit", "tool_input": {"file_path": target}, "cwd": self.prepared},
        )
        message = result["hookSpecificOutput"]["systemMessage"]
        self.assertIn("axon911-frontend", message)
        self.assertIn("packages/ui-core/", message)
        self.assertNotIn("permissionDecision", result["hookSpecificOutput"])

    def test_edit_to_prepared911_app_code_does_not_warn(self) -> None:
        target = os.path.join(self.prepared, "turbo/apps/dispatch/src/index.ts")
        result = self._send(
            "PostToolUse",
            {"tool_name": "Edit", "tool_input": {"file_path": target}, "cwd": self.prepared},
        )
        self.assertEqual(result, {})

    # --- identity ---

    def test_subagent_stop_records_host_supplied_identity(self) -> None:
        self._send(
            "SubagentStop",
            {
                "agent_type": "a911-harness:design-system-critic",
                "agent_id": "ag_1",
                "session_id": "s1",
                "cwd": self.axon,
            },
        )
        records = self._ledger_records("critic_return")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["critic_id"], "a911-harness:design-system-critic")
        self.assertEqual(records[0]["agent_id"], "ag_1")
        self.assertEqual(records[0]["root"], "axon911-frontend")

    def test_subagent_start_and_stop_are_distinct_kinds(self) -> None:
        payload = {"agent_type": "c", "agent_id": "a", "cwd": self.axon}
        self._send("SubagentStart", payload)
        self._send("SubagentStop", payload)
        self.assertEqual(len(self._ledger_records("critic_dispatch")), 1)
        self.assertEqual(len(self._ledger_records("critic_return")), 1)

    def _ledger_records(self, kind: str) -> list:
        found = []
        ledger_dir = os.path.join(self.tmp, "ledger")
        if not os.path.isdir(ledger_dir):
            # Nothing has been appended yet -- an out-of-scope event correctly
            # writes nothing at all, so the directory never gets created.
            return found
        for name in sorted(os.listdir(ledger_dir)):
            with open(os.path.join(ledger_dir, name), "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if record.get("kind") == kind:
                        found.append(record)
        return found

    # --- lifecycle gates ---

    def test_task_completed_with_nothing_relevant_changed_is_not_gated(self) -> None:
        """A clean tree has nothing for the end-of-turn gate to require; see
        test_task_completed_denied_for_an_unevidenced_ui_change for the case
        where it does."""
        result = self._send(
            "TaskCompleted",
            {"task_id": "t1", "task_name": "n", "result": "success", "cwd": self.axon},
        )
        self.assertEqual(result, {})

    def test_task_completed_denied_for_an_unevidenced_ui_change(self) -> None:
        self._touch_ui_file(self.axon)
        result = self._send(
            "TaskCompleted",
            {"task_id": "t1", "task_name": "n", "result": "success", "cwd": self.axon},
        )
        self.assertEqual(self._decision(result), "deny")
        self.assertIn("axon911-frontend.ui-allowlist", self._reason(result))
        self.assertIn("/a911-harness:implementation-check", self._reason(result))

    def test_failed_task_is_not_gated(self) -> None:
        result = self._send(
            "TaskCompleted",
            {"task_id": "t1", "task_name": "n", "result": "failure", "cwd": self.axon},
        )
        self.assertEqual(result, {})

    def test_stop_with_nothing_relevant_changed_is_never_gated(self) -> None:
        """Ordinary iteration with no commit in sight -- e.g. another agent
        working through several turns on an unrelated part of the repo --
        must never be interrupted. This is the exact behavior that motivated
        decoupling Stop from the blanket review requirement."""
        for _ in range(6):
            self.assertEqual(self._send("Stop", {"session_id": "quiet", "cwd": self.axon}), {})

    def test_stop_denied_for_an_unevidenced_ui_change_then_bounded(self) -> None:
        self._touch_ui_file(self.axon)
        denials = 0
        last = {}
        for _ in range(6):
            last = self._send("Stop", {"session_id": "loop", "cwd": self.axon})
            if self._decision(last) == "deny":
                denials += 1
        self.assertGreaterEqual(denials, 1)
        self.assertLessEqual(denials, 3)
        self.assertEqual(last, {}, "the stop gate must not trap the turn indefinitely")

    def test_session_start_injects_rule_only_inside_a_configured_root(self) -> None:
        inside = self._send("SessionStart", {"trigger": "startup", "cwd": self.axon})
        self.assertIn("Axon 911 Workspace Rule", inside["hookSpecificOutput"]["additionalContext"])
        outside = self._send("SessionStart", {"trigger": "startup", "cwd": tempfile.mkdtemp()})
        self.assertNotIn("additionalContext", outside.get("hookSpecificOutput", {}))

    # --- four-root scope guard ---
    #
    # Claude Code plugin hooks run for every session on the machine, unlike
    # Cursor's project-scoped hooks, which only ever ran inside the four-root
    # workspace. A directory outside axon911-frontend, prepared911,
    # vault-core-ux, and personal-harness must be a complete no-op: no denial,
    # no ledger record, no Stop or TaskCompleted gate. This is what actually
    # blocked a live session mid-development before the guard was added.

    def test_bash_mutation_outside_configured_roots_is_not_gated(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send(
            "PreToolUse",
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}, "cwd": outside},
        )
        self.assertEqual(result, {})

    def test_force_push_outside_configured_roots_is_not_gated(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send(
            "PreToolUse",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git push --force origin trunk"},
                "cwd": outside,
            },
        )
        self.assertEqual(result, {})

    def test_stop_outside_configured_roots_is_not_gated(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send("Stop", {"session_id": "outside-1", "cwd": outside})
        self.assertEqual(result, {})

    def test_task_completed_outside_configured_roots_is_not_gated(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send(
            "TaskCompleted",
            {"task_id": "t1", "task_name": "n", "result": "success", "cwd": outside},
        )
        self.assertEqual(result, {})

    def test_edit_outside_configured_roots_produces_no_warning(self) -> None:
        outside = tempfile.mkdtemp()
        result = self._send(
            "PostToolUse",
            {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(outside, "x.ts")}, "cwd": outside},
        )
        self.assertEqual(result, {})

    def test_subagent_events_outside_configured_roots_do_not_record(self) -> None:
        outside = tempfile.mkdtemp()
        payload = {"agent_type": "c", "agent_id": "a", "cwd": outside}
        self._send("SubagentStart", payload)
        self._send("SubagentStop", payload)
        self.assertEqual(self._ledger_records("critic_dispatch"), [])
        self.assertEqual(self._ledger_records("critic_return"), [])

    def test_git_dash_c_into_configured_root_from_outside_is_still_gated(self) -> None:
        """The scope check must resolve the command's actual target directory
        (git -C <path>), not just the payload cwd, or `-C` becomes a bypass."""
        outside = tempfile.mkdtemp()
        result = self._send(
            "PreToolUse",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git -C %s commit -m x" % self.axon},
                "cwd": outside,
            },
        )
        self.assertEqual(self._decision(result), "deny")

    def test_in_scope_gating_is_unchanged_by_the_guard(self) -> None:
        """Sanity check paired with the above: axon itself must still gate a
        real commit attempt. Stop's own behavior on a clean tree changed
        deliberately (see test_stop_with_nothing_relevant_changed_is_never_gated)
        and is not re-asserted here."""
        result = self._bash("git commit -m x")
        self.assertEqual(self._decision(result), "deny")

    # --- failure posture ---

    def test_malformed_payload_fails_closed_on_gates(self) -> None:
        for event in ("PreToolUse", "Stop", "TaskCompleted"):
            result = claude.handle_event(event, b"{not json")
            self.assertEqual(self._decision(result), "deny", event)

    def test_malformed_payload_fails_open_on_observations(self) -> None:
        for event in claude.OBSERVATIONAL:
            self.assertEqual(claude.handle_event(event, b"{not json"), {})

    def test_every_denial_names_a_command_that_exists(self) -> None:
        for result in (
            self._bash("git commit -m x"),
            self._send("Stop", {"session_id": "s", "cwd": self.axon}),
            self._send("TaskCompleted", {"task_id": "t", "result": "success", "cwd": self.axon}),
        ):
            blob = json.dumps(result)
            if "deny" not in blob:
                continue
            self.assertIn("/a911-harness:implementation-check", blob)
            self.assertNotIn('"/implementation-check', blob)

    def test_run_never_raises(self) -> None:
        for event in claude.EVENTS:
            self.assertIsInstance(claude.run(event, b"\xff\xfe not utf8"), dict)


if __name__ == "__main__":
    unittest.main()
