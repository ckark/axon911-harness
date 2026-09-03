"""Privacy-safe session lifecycle and handoff scaffolds."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .constants import STATUS_PASS
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
