"""Privacy-safe session lifecycle and handoff scaffolds."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .constants import (
    SESSION_MAX_ASSISTANT_TURNS,
    SESSION_MAX_CONTEXT_BYTES,
    STATUS_BLOCKED,
    STATUS_PASS,
)
from .ledger import append_record, current_state
from .path_selector import select_obligations
from .plan_profile import active_profile
from .receipts import build_recovery, evaluate_gate, matching_receipts


def session_key(worktree_id: str, session_id: str) -> str:
    return "%s:%s" % (worktree_id, session_id)


def record_session_phase(
    worktree_id: str,
    session_id: str,
    phase: str,
    root: str,
    fingerprint: str,
    plan_hash: str,
    tier: str,
    changed_paths: Sequence[str],
    obligation_statuses: Mapping[str, str],
    base: Optional[str] = None,
) -> Dict[str, Any]:
    return append_record(
        {
            "kind": "session_phase",
            "worktree_id": worktree_id,
            "session_id": session_id,
            "root": root,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "tier": tier,
            "phase": phase,
            "changed_paths": sorted(changed_paths),
            "obligation_statuses": dict(obligation_statuses),
            "status": STATUS_PASS,
        },
        base=base,
    )


def session_status(
    root_id: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    session_id: str,
    family: str = "git-commit",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    profile = active_profile(state, root_id, worktree_id)
    from .fingerprint import changed_paths

    changed = changed_paths(root_path)
    selection = select_obligations(
        root_id,
        changed,
        profile,
        profile.get("tier") or "T0",
        family=family,
    )
    gate = evaluate_gate(
        root_id,
        worktree_id,
        fingerprint,
        selection["required_obligation_ids"],
        profile.get("plan_hash") or "",
        profile.get("tier") or "T0",
        changed_paths=changed,
        root_path=root_path,
        base=base,
        selection=selection,
    )
    session = ((state.get("sessions") or {}).get(session_key(worktree_id, session_id)) or {})
    handoff = ((state.get("handoffs") or {}).get(session_key(worktree_id, session_id)) or {})
    obligation_statuses = {}
    for obligation_id in selection["required_obligation_ids"]:
        receipts = [
            item
            for item in matching_receipts(state, root_id, worktree_id, fingerprint)
            if item.get("obligation_id") == obligation_id and item.get("status") == STATUS_PASS
        ]
        obligation_statuses[obligation_id] = "satisfied" if receipts else "missing"
    return {
        "session_id": session_id,
        "phase": session.get("phase") or handoff.get("phase") or "unknown",
        "root": root_id,
        "fingerprint": fingerprint,
        "plan_hash": profile.get("plan_hash") or "",
        "plan_context_hash": profile.get("plan_context_hash") or "",
        "tier": profile.get("tier") or "T0",
        "changed_paths": changed,
        "required_obligation_ids": selection["required_obligation_ids"],
        "obligation_statuses": obligation_statuses,
        "gate": gate,
        "recovery": gate.get("recovery"),
        "stop_loops": session.get("stop_loops") or 0,
    }


def create_handoff(
    root_id: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    session_id: str,
    phase: str,
    family: str = "git-commit",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    status = session_status(
        root_id,
        root_path,
        worktree_id,
        fingerprint,
        session_id,
        family=family,
        base=base,
    )
    recovery = status.get("recovery") or build_recovery([], status.get("plan_hash") or "")
    next_command = recovery.get("next_command") or "/implementation-check"
    payload = {
        "session_id": session_id,
        "phase": phase,
        "plan_hash": status.get("plan_hash") or "",
        "plan_context_hash": status.get("plan_context_hash") or "",
        "tier": status.get("tier") or "T0",
        "head": _git_head(root_path),
        "fingerprint": fingerprint,
        "changed_paths": status.get("changed_paths") or [],
        "obligation_statuses": status.get("obligation_statuses") or {},
        "next_command": next_command,
    }
    append_record(
        {
            "kind": "session_handoff",
            "worktree_id": worktree_id,
            "session_id": session_id,
            "root": root_id,
            "fingerprint": fingerprint,
            "phase": phase,
            "handoff": payload,
            "status": STATUS_PASS,
        },
        base=base,
    )
    return payload


def _git_head(root_path: str) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def estimate_transcript_cost(transcript_path: str) -> Dict[str, Any]:
    """Estimate assistant turns and transcript bytes from a Cursor JSONL file."""
    main_running = 0
    main_turns = 0
    with open(transcript_path, encoding="utf-8") as handle:
        for line in handle:
            main_running += len(line.encode("utf-8"))
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("role") == "assistant":
                main_turns += 1

    subagent_dir = os.path.join(os.path.dirname(transcript_path), "subagents")
    sub_running = 0
    sub_count = 0
    if os.path.isdir(subagent_dir):
        for name in os.listdir(subagent_dir):
            if not name.endswith(".jsonl"):
                continue
            sub_count += 1
            with open(os.path.join(subagent_dir, name), encoding="utf-8") as handle:
                running = 0
                for line in handle:
                    running += len(line.encode("utf-8"))
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("role") == "assistant":
                        sub_running += running

    context_bytes = main_running + sub_running
    return {
        "main_assistant_turns": main_turns,
        "context_bytes": context_bytes,
        "subagent_count": sub_count,
        "total_billed_tokens_estimate": int(context_bytes / 4),
    }


def budget_verdict(
    cost: Mapping[str, Any],
    profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return PASS/BLOCKED when a session exceeds configured turn or context limits."""
    profile = profile or {}
    max_turns = int(profile.get("budget_max_turns") or SESSION_MAX_ASSISTANT_TURNS)
    max_bytes = int(profile.get("budget_max_context_bytes") or SESSION_MAX_CONTEXT_BYTES)
    turns = int(cost.get("main_assistant_turns") or 0)
    context_bytes = int(cost.get("context_bytes") or 0)
    reasons: List[str] = []
    if turns > max_turns:
        reasons.append("session-budget-exceeded-turns")
    if context_bytes > max_bytes:
        reasons.append("session-budget-exceeded-context")
    status = STATUS_PASS if not reasons else STATUS_BLOCKED
    return {
        "status": status,
        "reasons": reasons,
        "main_assistant_turns": turns,
        "context_bytes": context_bytes,
        "max_turns": max_turns,
        "max_context_bytes": max_bytes,
    }


def compact_runtime_state(index: Dict[str, Any]) -> Dict[str, Any]:
    """Drop stale indexes while preserving active plan, receipts, session, evidence."""
    compact = {
        "seq": index.get("seq") or 0,
        "tail_hash": index.get("tail_hash") or "",
        "updated": index.get("updated") or time.time(),
        "receipts": index.get("receipts") or {},
        "plans": index.get("plans") or {},
        "profiles": index.get("profiles") or {},
        "scopes": index.get("scopes") or {},
        "sessions": index.get("sessions") or {},
        "handoffs": index.get("handoffs") or {},
        "evidence": index.get("evidence") or {},
        "invalidated": index.get("invalidated") or {},
        "critics": index.get("critics") or {},
    }
    return compact
