"""Receipt issuance and gate evaluation."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .constants import (
    RECOVERY_COMMAND,
    REVIEW_MODE_ALWAYS,
    REVIEW_MODE_OFF,
    REVIEW_MODE_ON_REQUEST,
    STATUS_BLOCKED,
    STATUS_INCONCLUSIVE,
    STATUS_PASS,
    STOP_LOOP_LIMIT,
)
from .ledger import LedgerError, append_record, current_state
from .obligations import required_ids, triggered_obligations

TIER_RANK = {"T0": 0, "T1": 1, "T2": 2}


def review_mode() -> str:
    """Whether mutation gates require a review receipt."""
    raw = os.environ.get("HARNESS_REVIEW_MODE", REVIEW_MODE_OFF).strip().lower()
    if raw in (REVIEW_MODE_OFF, REVIEW_MODE_ON_REQUEST, REVIEW_MODE_ALWAYS):
        return raw
    return REVIEW_MODE_OFF


def review_required(tier: str) -> bool:
    mode = review_mode()
    if mode == REVIEW_MODE_ALWAYS:
        return True
    if mode == REVIEW_MODE_ON_REQUEST:
        return os.environ.get("HARNESS_REVIEW_REQUESTED", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    return False


def issue_verification_receipt(
    root: str,
    worktree_id: str,
    fingerprint: str,
    obligation_id: str,
    status: str,
    pre_fingerprint: str,
    plan_hash: str,
    session_id: str = "",
    evidence_pointer: str = "",
    exit_status: int = 0,
    duration_ms: int = 0,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    if pre_fingerprint != fingerprint:
        status = STATUS_INCONCLUSIVE
    record = {
        "kind": "verification_receipt",
        "root": root,
        "worktree_id": worktree_id,
        "session_id": session_id,
        "fingerprint": fingerprint,
        "obligation_id": obligation_id,
        "status": status,
        "plan_hash": plan_hash,
        "evidence_pointer": evidence_pointer,
        "exit_status": exit_status,
        "duration_ms": duration_ms,
        "receipt_id": "%s:%s:%s" % (root, obligation_id, fingerprint[:12]),
    }
    return append_record(record, base=base)


def issue_review_receipt(
    root: str,
    worktree_id: str,
    fingerprint: str,
    tier: str,
    critic_ids: Sequence[str],
    status: str,
    plan_hash: str,
    session_id: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    unique = []
    for critic in critic_ids:
        if critic not in unique:
            unique.append(critic)
    if len(unique) < 1:
        status = STATUS_BLOCKED
    record = {
        "kind": "review_receipt",
        "root": root,
        "worktree_id": worktree_id,
        "session_id": session_id,
        "fingerprint": fingerprint,
        "obligation_id": "review.%s" % tier,
        "status": status,
        "plan_hash": plan_hash,
        "tier": tier,
        "critic_id": ",".join(unique),
        "receipt_id": "%s:review:%s" % (root, fingerprint[:12]),
    }
    return append_record(record, base=base)


def register_plan(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    session_id: str = "",
    tier: str = "T0",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    return append_record(
        {
            "kind": "register_plan",
            "root": root,
            "worktree_id": worktree_id,
            "session_id": session_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "obligation_id": "plan",
            "status": STATUS_PASS,
            "tier": tier,
        },
        base=base,
    )


def invalidate(
    root: str,
    worktree_id: str,
    fingerprint: str,
    session_id: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    return append_record(
        {
            "kind": "invalidate",
            "root": root,
            "worktree_id": worktree_id,
            "session_id": session_id,
            "fingerprint": fingerprint,
            "status": STATUS_BLOCKED,
            "obligation_id": "*",
        },
        base=base,
    )


def _key(root: str, worktree_id: str, fingerprint: str) -> str:
    return "%s:%s:%s" % (root, worktree_id, fingerprint)


def matching_receipts(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    fingerprint: str,
) -> List[Dict[str, Any]]:
    return list((state.get("receipts") or {}).get(_key(root, worktree_id, fingerprint)) or [])


def active_plan(state: Mapping[str, Any], root: str, worktree_id: str) -> Dict[str, str]:
    plans = state.get("plans") or {}
    found = plans.get("%s:%s" % (root, worktree_id)) or {}
    return {
        "plan_hash": str(found.get("plan_hash") or ""),
        "tier": str(found.get("tier") or "T0"),
    }


def _review_satisfied(receipts: Sequence[Mapping[str, Any]], min_tier: str, plan_hash: str) -> bool:
    for item in receipts:
        if item.get("kind") != "review_receipt":
            continue
        obligation_id = str(item.get("obligation_id") or "")
        if not obligation_id.startswith("review."):
            continue
        if item.get("status") != STATUS_PASS:
            continue
        if item.get("plan_hash") != plan_hash:
            continue
        return True
    return False


def _confined_review_satisfied(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    fingerprint: str,
    min_tier: str,
    plan_hash: str,
    changed_paths: Sequence[str],
) -> bool:
    """Accept a review receipt from a prior fingerprint when edits stay confined."""
    if not changed_paths:
        return False
    bucket = (state.get("receipts") or {}).get(_key(root, worktree_id, fingerprint)) or []
    for item in bucket:
        if item.get("kind") != "review_receipt":
            continue
        if item.get("status") != STATUS_PASS:
            continue
        if item.get("plan_hash") != plan_hash:
            continue
        if not item.get("confined"):
            continue
        allowed = set(str(path) for path in item.get("confined_paths") or [])
        if allowed and all(path in allowed for path in changed_paths):
            obligation_id = str(item.get("obligation_id") or "")
            got = obligation_id.split(".", 1)[-1] if obligation_id.startswith("review.") else ""
            if TIER_RANK.get(got, -1) >= TIER_RANK.get(min_tier, 0):
                return True
    for prior_fp, receipts in (state.get("receipts") or {}).items():
        if not prior_fp.startswith("%s:%s:" % (root, worktree_id)):
            continue
        if prior_fp.endswith(":%s" % fingerprint):
            continue
        for item in receipts:
            if item.get("kind") != "review_receipt":
                continue
            if item.get("status") != STATUS_PASS:
                continue
            if item.get("plan_hash") != plan_hash:
                continue
            if not item.get("confined"):
                continue
            allowed = set(str(path) for path in item.get("confined_paths") or [])
            if allowed and all(path in allowed for path in changed_paths):
                obligation_id = str(item.get("obligation_id") or "")
                got = obligation_id.split(".", 1)[-1] if obligation_id.startswith("review.") else ""
                if TIER_RANK.get(got, -1) >= TIER_RANK.get(min_tier, 0):
                    return True
    return False


def evaluate_gate(
    root: str,
    worktree_id: str,
    fingerprint: str,
    required_obligation_ids: Sequence[str],
    plan_hash: str,
    tier: str,
    changed_paths: Optional[Sequence[str]] = None,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        state = current_state(base=base, validate=False)
    except LedgerError:
        return {
            "permission": "deny",
            "status": STATUS_BLOCKED,
            "reason": "corrupt-ledger",
            "agent_message": "runtime-gate BLOCKED root=%s recovery=%s" % (root, RECOVERY_COMMAND),
        }
    registered = active_plan(state, root, worktree_id)
    expected_plan = plan_hash or registered.get("plan_hash") or ""
    expected_tier = tier or registered.get("tier") or "T0"
    receipts = matching_receipts(state, root, worktree_id, fingerprint)
    missing = []
    for obligation_id in required_obligation_ids:
        if obligation_id.startswith("review."):
            continue
        found = [
            item
            for item in receipts
            if item.get("kind") == "verification_receipt"
            and item.get("obligation_id") == obligation_id
            and item.get("status") == STATUS_PASS
            and item.get("plan_hash") == expected_plan
        ]
        if not found:
            missing.append(obligation_id)
    review_needed = any(item.startswith("review.") for item in required_obligation_ids)
    if review_needed:
        review_ok = _review_satisfied(receipts, expected_tier, expected_plan)
        if not review_ok and changed_paths:
            review_ok = _confined_review_satisfied(
                state,
                root,
                worktree_id,
                fingerprint,
                expected_tier,
                expected_plan,
                changed_paths,
            )
        if not review_ok:
            missing.append("review.%s" % expected_tier)
    if missing:
        ids = ",".join(sorted(set(missing)))
        return {
            "permission": "deny",
            "status": STATUS_BLOCKED,
            "reason": "missing-or-stale",
            "agent_message": "runtime-gate BLOCKED root=%s obligations=%s recovery=%s"
            % (root, ids, RECOVERY_COMMAND),
        }
    return {
        "permission": "allow",
        "status": STATUS_PASS,
        "reason": "receipts-match",
        "agent_message": "runtime-gate PASS root=%s" % root,
    }


def increment_stop_loop(
    worktree_id: str,
    session_id: str,
    base: Optional[str] = None,
) -> int:
    state = current_state(base=base)
    session_key = "%s:%s" % (worktree_id, session_id)
    current = int(((state.get("sessions") or {}).get(session_key) or {}).get("stop_loops") or 0)
    nxt = current + 1
    append_record(
        {
            "kind": "session_cursor",
            "worktree_id": worktree_id,
            "session_id": session_id,
            "exit_status": nxt,
            "status": STATUS_PASS if nxt <= STOP_LOOP_LIMIT else STATUS_BLOCKED,
            "root": "personal-harness",
            "fingerprint": "",
        },
        base=base,
    )
    return nxt


def stop_followup_allowed(count: int) -> bool:
    return count <= STOP_LOOP_LIMIT


def default_required(
    root: str,
    changed_paths: Sequence[str],
    user_visible: bool,
    existing_surface: bool,
    tier: str,
) -> List[str]:
    ids = required_ids(root, changed_paths, user_visible, existing_surface)
    if review_required(tier):
        ids.append("review.%s" % tier)
    return ids


def mutation_required_ids(
    root: str,
    changed_paths: Sequence[str],
    family: str,
    tier: str,
) -> List[str]:
    ui = bool(triggered_obligations(root, changed_paths))
    ids = default_required(root, changed_paths, ui, ui, tier)
    if family == "git-push":
        ids.append("push.oid")
    if family == "gt-submit":
        ids.append("stack-oid-set")
    return ids
