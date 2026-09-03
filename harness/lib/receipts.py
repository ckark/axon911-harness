"""Receipt issuance and gate evaluation."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, TypedDict

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
from .path_selector import select_obligations
from .plan_profile import active_profile, profile_from_state

TIER_RANK = {"T0": 0, "T1": 1, "T2": 2}


class RecoveryDetail(TypedDict, total=False):
    reason: str
    missing: List[str]
    stale: List[str]
    wrong_plan: List[str]
    wrong_tier: List[str]
    failed: List[str]
    conformance: List[str]
    classification: List[str]
    evidence: List[str]
    next_command: str


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


def build_recovery(
    categories: Mapping[str, Sequence[str]],
    plan_hash: str,
) -> RecoveryDetail:
    missing = sorted(categories.get("missing") or [])
    stale = sorted(categories.get("stale") or [])
    wrong_plan = sorted(categories.get("wrong_plan") or [])
    wrong_tier = sorted(categories.get("wrong_tier") or [])
    failed = sorted(categories.get("failed") or [])
    conformance = sorted(categories.get("conformance") or [])
    classification = sorted(categories.get("classification") or [])
    evidence = sorted(categories.get("evidence") or [])
    if classification or conformance:
        reason = "policy-failure"
    elif missing or stale or wrong_plan or wrong_tier or failed or evidence:
        reason = "missing-or-stale"
    else:
        reason = "ok"
    return {
        "reason": reason,
        "missing": missing,
        "stale": stale,
        "wrong_plan": wrong_plan,
        "wrong_tier": wrong_tier,
        "failed": failed,
        "conformance": conformance,
        "classification": classification,
        "evidence": evidence,
        "next_command": RECOVERY_COMMAND,
        "plan_hash": plan_hash,
    }


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
    plan_context_hash: str = "",
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
        "plan_context_hash": plan_context_hash,
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
    plan_context_hash: str = "",
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
        "plan_context_hash": plan_context_hash,
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
    profile = active_profile(state, root, worktree_id)
    return {
        "plan_hash": profile.get("plan_hash") or "",
        "tier": profile.get("tier") or "T0",
        "plan_context_hash": profile.get("plan_context_hash") or "",
        "base_oid": profile.get("base_oid") or "",
        "mirror_intent": profile.get("mirror_intent") or "",
        "profiled": "true" if profile.get("profiled") else "false",
    }


def _review_satisfied(
    receipts: Sequence[Mapping[str, Any]],
    min_tier: str,
    plan_hash: str,
    plan_context_hash: str,
) -> bool:
    min_rank = TIER_RANK.get(min_tier, 0)
    for item in receipts:
        if item.get("kind") != "review_receipt":
            continue
        obligation_id = str(item.get("obligation_id") or "")
        if not obligation_id.startswith("review."):
            continue
        if item.get("status") != STATUS_PASS:
            continue
        if plan_hash and item.get("plan_hash") != plan_hash:
            continue
        if plan_context_hash:
            receipt_context = str(item.get("plan_context_hash") or "")
            if receipt_context != plan_context_hash:
                continue
        got = obligation_id.split(".", 1)[-1] if obligation_id.startswith("review.") else ""
        if TIER_RANK.get(got, -1) >= min_rank:
            return True
    return False


def _confined_review_satisfied(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    fingerprint: str,
    min_tier: str,
    plan_hash: str,
    plan_context_hash: str,
    changed_paths: Sequence[str],
) -> bool:
    """Accept a review receipt from a prior fingerprint when edits stay confined."""
    if not changed_paths:
        return False
    min_rank = TIER_RANK.get(min_tier, 0)
    buckets = [(fingerprint, matching_receipts(state, root, worktree_id, fingerprint))]
    for prior_fp, receipts in (state.get("receipts") or {}).items():
        if not prior_fp.startswith("%s:%s:" % (root, worktree_id)):
            continue
        if prior_fp.endswith(":%s" % fingerprint):
            continue
        buckets.append((prior_fp.split(":")[-1], receipts))
    for _fp, bucket in buckets:
        for item in bucket:
            if item.get("kind") != "review_receipt":
                continue
            if item.get("status") != STATUS_PASS:
                continue
            if plan_hash and item.get("plan_hash") != plan_hash:
                continue
            if plan_context_hash:
                receipt_context = str(item.get("plan_context_hash") or "")
                if receipt_context != plan_context_hash:
                    continue
            if not item.get("confined"):
                continue
            allowed = set(str(path) for path in item.get("confined_paths") or [])
            if allowed and all(path in allowed for path in changed_paths):
                obligation_id = str(item.get("obligation_id") or "")
                got = obligation_id.split(".", 1)[-1] if obligation_id.startswith("review.") else ""
                if TIER_RANK.get(got, -1) >= min_rank:
                    return True
    return False


def _receipt_categories(
    receipts: Sequence[Mapping[str, Any]],
    obligation_id: str,
    expected_plan: str,
    expected_context: str,
) -> str:
    matches = [
        item
        for item in receipts
        if item.get("kind") == "verification_receipt"
        and item.get("obligation_id") == obligation_id
    ]
    if not matches:
        return "missing"
    for item in matches:
        if item.get("status") == STATUS_PASS:
            if expected_plan and item.get("plan_hash") not in ("", expected_plan):
                return "wrong_plan"
            if expected_context:
                receipt_context = str(item.get("plan_context_hash") or "")
                if receipt_context != expected_context:
                    return "wrong_plan"
            return "ok"
    for item in matches:
        if item.get("status") == STATUS_INCONCLUSIVE:
            return "stale"
    return "failed"


def evaluate_gate(
    root: str,
    worktree_id: str,
    fingerprint: str,
    required_obligation_ids: Sequence[str],
    plan_hash: str,
    tier: str,
    changed_paths: Optional[Sequence[str]] = None,
    root_path: Optional[str] = None,
    base: Optional[str] = None,
    selection: Optional[Mapping[str, Any]] = None,
    conformance: Optional[Mapping[str, Any]] = None,
    explain: bool = False,
    mutation_family: str = "",
) -> Dict[str, Any]:
    categories: Dict[str, List[str]] = {
        "missing": [],
        "stale": [],
        "wrong_plan": [],
        "wrong_tier": [],
        "failed": [],
        "conformance": [],
        "classification": [],
        "evidence": [],
    }
    try:
        state = current_state(base=base, validate=False)
    except LedgerError:
        recovery = build_recovery(categories, plan_hash)
        return {
            "permission": "deny",
            "status": STATUS_BLOCKED,
            "reason": "corrupt-ledger",
            "agent_message": "runtime-gate BLOCKED root=%s recovery=%s"
            % (root, RECOVERY_COMMAND),
            "recovery": recovery,
        }
    registered = active_plan(state, root, worktree_id)
    profile = active_profile(state, root, worktree_id)
    expected_plan = plan_hash or registered.get("plan_hash") or ""
    expected_tier = tier or registered.get("tier") or "T0"
    expected_context = profile.get("plan_context_hash") or ""
    if not profile.get("profiled"):
        expected_context = ""
    receipts = matching_receipts(state, root, worktree_id, fingerprint)

    if selection and selection.get("classification_errors"):
        categories["classification"].extend(list(selection["classification_errors"]))

    if conformance is None and changed_paths is not None:
        from .conformance import evaluate_against_base

        profile = active_profile(state, root, worktree_id)
        conformance = evaluate_against_base(
            root,
            worktree_id,
            changed_paths,
            profile,
            root_path=root_path,
            base=base,
        )
    if conformance and conformance.get("status") != STATUS_PASS:
        from .conformance import UNDECLARED, UNIMPLEMENTED

        for path in conformance.get(UNDECLARED) or []:
            categories["conformance"].append("undeclared:%s" % path)
        if mutation_family not in ("git-commit", "git-push", "gt-submit", "gt-create"):
            for path in conformance.get(UNIMPLEMENTED) or []:
                categories["conformance"].append("unimplemented:%s" % path)

    for obligation_id in required_obligation_ids:
        if obligation_id.startswith("review."):
            continue
        if root_path and (
            obligation_id.endswith(".rendered-evidence")
            or obligation_id.endswith(".rendered-evidence.before-after")
        ):
            from .evidence import revalidate_evidence

            base_oid = ""
            require_before = False
            if obligation_id.endswith(".rendered-evidence.before-after"):
                profile = active_profile(state, root, worktree_id)
                base_oid = str(profile.get("base_oid") or "")
                require_before = True
            errors = revalidate_evidence(
                root_path,
                state,
                root,
                worktree_id,
                obligation_id.replace(".before-after", ""),
                expected_context,
                require_before=require_before,
                require_after=True,
                base_oid=base_oid,
                fingerprint=fingerprint,
            )
            categories["evidence"].extend(errors)
            if errors:
                categories["missing"].append(obligation_id)
            continue
        bucket = _receipt_categories(receipts, obligation_id, expected_plan, expected_context)
        if bucket == "ok":
            continue
        categories[bucket].append(obligation_id)

    review_needed = any(item.startswith("review.") for item in required_obligation_ids)
    if review_needed:
        review_ok = _review_satisfied(receipts, expected_tier, expected_plan, expected_context)
        if not review_ok and changed_paths:
            review_ok = _confined_review_satisfied(
                state,
                root,
                worktree_id,
                fingerprint,
                expected_tier,
                expected_plan,
                expected_context,
                changed_paths,
            )
        if not review_ok:
            categories["missing"].append("review.%s" % expected_tier)

    blocked = any(categories[key] for key in categories)
    recovery = build_recovery(categories, expected_plan)
    if blocked:
        flat = []
        for key in ("classification", "conformance", "missing", "stale", "wrong_plan", "wrong_tier", "failed", "evidence"):
            flat.extend(categories[key])
        ids = ",".join(sorted(set(flat)))
        result = {
            "permission": "deny",
            "status": STATUS_BLOCKED,
            "reason": recovery["reason"],
            "agent_message": "runtime-gate BLOCKED root=%s obligations=%s recovery=%s"
            % (root, ids, RECOVERY_COMMAND),
            "recovery": recovery,
        }
        if explain:
            result["categories"] = categories
        return result
    result = {
        "permission": "allow",
        "status": STATUS_PASS,
        "reason": "receipts-match",
        "agent_message": "runtime-gate PASS root=%s" % root,
        "recovery": recovery,
    }
    if explain:
        result["categories"] = categories
    return result


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
    profile: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    if profile is None:
        profile = {}
    selection = select_obligations(root, changed_paths, profile, tier, include_review=True)
    return selection["required_obligation_ids"]


def mutation_required_ids(
    root: str,
    changed_paths: Sequence[str],
    family: str,
    tier: str,
    profile: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    if profile is None:
        profile = {}
    selection = select_obligations(
        root,
        changed_paths,
        profile,
        tier,
        family=family,
        include_review=True,
    )
    return selection["required_obligation_ids"]
