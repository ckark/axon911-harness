"""Cursor hook event dispatcher.

Event names, payload shape, and response envelope are Cursor's. The decisions
come from `lib.receipts.evaluate_gate` and `lib.shell_gate.classify`, shared
with the Claude Code dispatcher in `dispatch.claude`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping

from dispatch.common import required_for, root_for, shell_decision, snap
from lib.constants import RECOVERY_COMMAND, STATUS_PASS
from lib.ledger import append_record
from lib.paths import PathError
from lib.receipts import evaluate_gate, increment_stop_loop, invalidate, stop_followup_allowed
from lib.schema import SchemaError, parse_event, sanitized_message

EVENTS = (
    "sessionStart",
    "afterFileEdit",
    "postToolUse",
    "subagentStop",
    "preCompact",
    "beforeShellExecution",
    "stop",
)

OBSERVATIONAL = {"sessionStart", "preCompact", "afterFileEdit", "postToolUse", "subagentStop"}


def _observe(event_name: str, root_id: str, cwd: str) -> None:
    append_record(
        {
            "kind": "observation",
            "event_id": event_name,
            "root": root_id,
            "worktree_id": cwd,
            "fingerprint": "",
            "status": STATUS_PASS,
        }
    )


def handle_event(event_name: str, raw: bytes) -> Dict[str, Any]:
    try:
        payload = parse_event(event_name, raw)
    except SchemaError:
        if event_name == "beforeShellExecution":
            return {
                "permission": "deny",
                "agent_message": sanitized_message("BLOCKED", "unknown"),
            }
        return {}
    cwd = payload.get("cwd") or os.getcwd()
    try:
        if payload.get("file_path"):
            root_id = root_for(str(payload["file_path"]))
        else:
            root_id = root_for(str(cwd) or os.getcwd())
    except (PathError, SchemaError, KeyError):
        root_id = "personal-harness"

    if event_name == "afterFileEdit":
        try:
            current = snap(root_id)
        except Exception:
            current = {"fingerprint": "unknown", "worktree_id": cwd}
        invalidate(root_id, current["worktree_id"], current.get("fingerprint") or "unknown")
        return {}
    if event_name in ("sessionStart", "preCompact", "postToolUse"):
        _observe(event_name, root_id, cwd)
        return {}
    if event_name == "subagentStop":
        _observe(event_name, root_id, cwd)
        if payload.get("status") in ("error", "aborted"):
            return {
                "followup_message": "Proof is missing or stale. Run %s; unvalidated subagent output is not a receipt."
                % RECOVERY_COMMAND
            }
        return {}
    if event_name == "beforeShellExecution":
        return _before_shell(payload, cwd)
    if event_name == "stop":
        return _stop(payload, root_id, cwd)
    return {}


def _before_shell(payload: Mapping[str, Any], cwd: Any) -> Dict[str, Any]:
    decision = shell_decision(str(payload.get("command") or ""), str(cwd))
    if decision["permission"] == "allow":
        return {"permission": "allow"}
    message = decision.get("message") or sanitized_message("BLOCKED", decision.get("root") or "unknown")
    return {"permission": "deny", "agent_message": message, "user_message": message}


def _stop(payload: Mapping[str, Any], root_id: str, cwd: Any) -> Dict[str, Any]:
    session_id = str(
        payload.get("session_id") or os.environ.get("CURSOR_SESSION_ID") or "default"
    )
    try:
        current = snap(root_id)
    except Exception:
        current = {"fingerprint": "", "worktree_id": cwd, "plan_hash": ""}
    count = increment_stop_loop(current.get("worktree_id") or cwd, session_id)
    if not stop_followup_allowed(count):
        return {}
    required, registered = required_for(
        root_id,
        "git-commit",
        current.get("plan_hash") or "",
        current.get("worktree_id") or cwd,
    )
    gate = evaluate_gate(
        root_id,
        current.get("worktree_id") or cwd,
        current.get("fingerprint") or "",
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
    )
    if gate["status"] != STATUS_PASS:
        return {
            "followup_message": "Proof is missing or stale. Run %s and continue."
            % RECOVERY_COMMAND
        }
    return {}


def run(event_name: str, raw: bytes) -> Dict[str, Any]:
    """Fail-open envelope for observational events; fail-closed for the shell gate."""
    try:
        return handle_event(event_name, raw)
    except Exception:
        if event_name == "beforeShellExecution":
            message = sanitized_message("BLOCKED", "unknown")
            return {"permission": "deny", "agent_message": message, "user_message": message}
        return {}
