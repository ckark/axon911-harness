"""Cursor hook event dispatcher.

Event names, payload shape, and response envelope are Cursor's. The decisions
come from `lib.receipts.evaluate_gate` and `lib.shell_gate.classify`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping

from dispatch.common import required_for, resolve_root, root_for, shell_decision, snap
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
            _, root_path = resolve_root(str(payload.get("file_path") or cwd))
            current = snap(root_id, root_path)
        except Exception:
            current = {"fingerprint": "unknown", "worktree_id": cwd}
        invalidate(root_id, current["worktree_id"], current.get("fingerprint") or "unknown")
        return {}
    if event_name in ("sessionStart", "preCompact", "postToolUse"):
        _observe(event_name, root_id, cwd)
        if event_name == "sessionStart":
            try:
                from lib.ledger import current_state
                from lib.sessions import session_status

                _, root_path = resolve_root(str(cwd))
                current = snap(root_id, root_path)
                status = session_status(
                    root_id,
                    root_path,
                    current["worktree_id"],
                    current.get("fingerprint") or "",
                    session_id=str(payload.get("session_id") or os.environ.get("CURSOR_SESSION_ID") or "default"),
                )
                handoff = status.get("recovery")
                if handoff:
                    return {
                        "followup_message": "Resuming harness session. Next: %s"
                        % (handoff.get("next_command") or RECOVERY_COMMAND)
                    }
            except Exception:
                pass
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
        _, root_path = resolve_root(str(cwd))
        current = snap(root_id, root_path)
    except Exception:
        current = {"fingerprint": "", "worktree_id": cwd, "plan_hash": ""}
        root_path = None
    count = increment_stop_loop(current.get("worktree_id") or cwd, session_id)
    if not stop_followup_allowed(count):
        return {}
    required, registered, changed = required_for(
        root_id,
        "git-commit",
        current.get("plan_hash") or "",
        current.get("worktree_id") or cwd,
        root_path,
    )
    from lib.ledger import current_state
    from lib.path_selector import select_obligations
    from lib.conformance import evaluate_against_base
    from lib.plan_profile import active_profile

    try:
        state = current_state()
        profile = active_profile(state, root_id, current.get("worktree_id") or cwd)
    except Exception:
        profile = {}
    selection = select_obligations(
        root_id,
        changed,
        profile,
        registered.get("tier") or "T0",
        family="git-commit",
    )
    conformance = evaluate_against_base(
        root_id,
        current.get("worktree_id") or cwd,
        changed,
        profile,
        root_path=root_path,
    )
    gate = evaluate_gate(
        root_id,
        current.get("worktree_id") or cwd,
        current.get("fingerprint") or "",
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
        changed_paths=changed,
        root_path=root_path,
        selection=selection,
        conformance=conformance,
        explain=True,
    )
    if gate["status"] != STATUS_PASS:
        recovery = gate.get("recovery") or {}
        next_cmd = recovery.get("next_command") or RECOVERY_COMMAND
        return {
            "followup_message": "Proof is missing or stale. Run %s and continue." % next_cmd
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
