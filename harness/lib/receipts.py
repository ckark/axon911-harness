"""Receipt issuance and gate evaluation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .constants import (
    RECOVERY_COMMAND,
    STATUS_BLOCKED,
    STATUS_INCONCLUSIVE,
    STATUS_PASS,
    STOP_LOOP_LIMIT,
)
from .ledger import LedgerError, append_record, current_state
from .obligations import required_ids, triggered_obligations

TIER_RANK = {"T0": 0, "T1": 1, "T2": 2}
T2_MIN_CRITICS = 3


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
    if tier == "T0" and len(unique) < 1:
        status = STATUS_BLOCKED
    elif tier == "T1" and len(unique) < 2:
        status = STATUS_BLOCKED
    elif tier == "T2":
        if "review-adjudicator" not in unique or len(unique) < T2_MIN_CRITICS:
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


# Distinct identity-bound critics a tier requires. T2's panel is selected by
# change signal so its size varies; three plus an adjudicator is the floor.
TIER_CARDINALITY = {"T0": 1, "T1": 2, "T2": 3}
ADJUDICATOR_SUFFIX = "review-adjudicator"


def identity_bound_critics(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
) -> List[str]:
    """Critics whose return was recorded by the host, not claimed in prose.

    Populated from Claude Code's `SubagentStop`, which carries `agent_type` and
    `agent_id`. Empty under hosts that expose no subagent identity.
    """
    bucket = (state.get("critics") or {}).get(_key(root, worktree_id, fingerprint)) or {}
    return sorted(
        critic_id
        for critic_id, meta in bucket.items()
        if critic_id and str(meta.get("plan_hash") or "") == str(plan_hash or "")
    )


def _cardinality_satisfied(critics: Sequence[str], min_tier: str) -> bool:
    needed = TIER_CARDINALITY.get(min_tier, 1)
    if len(critics) < needed:
        return False
    if min_tier == "T2":
        return any(critic.endswith(ADJUDICATOR_SUFFIX) for critic in critics)
    return True


def _review_satisfied(receipts: Sequence[Mapping[str, Any]], min_tier: str, plan_hash: str) -> bool:
    needed = TIER_RANK.get(min_tier, 0)
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
        got = obligation_id.split(".", 1)[-1]
        if TIER_RANK.get(got, -1) >= needed:
            return True
    return False


def evaluate_gate(
    root: str,
    worktree_id: str,
    fingerprint: str,
    required_obligation_ids: Sequence[str],
    plan_hash: str,
    tier: str,
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
        if not _review_satisfied(receipts, expected_tier, expected_plan):
            missing.append("review.%s" % expected_tier)
        else:
            # The review receipt is issued by the orchestrator, so on its own it
            # is self-attested. Where the host records who actually returned,
            # require the tier's cardinality against those identities too. Hosts
            # that expose no subagent identity keep the receipt-only behavior:
            # this supplements review receipts, it never replaces them.
            critics = identity_bound_critics(
                state, root, worktree_id, fingerprint, expected_plan
            )
            if critics and not _cardinality_satisfied(critics, expected_tier):
                missing.append("review.%s.cardinality" % expected_tier)
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
