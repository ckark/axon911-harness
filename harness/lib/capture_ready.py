"""Deterministic preflight before starting a screenshot campaign."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .conformance import UNIMPLEMENTED, UNDECLARED, evaluate_against_base
from .constants import (
    MIGRATION_EVIDENCE_SCHEMA_VERSION,
    RECOVERY_COMMAND,
    STATUS_BLOCKED,
    STATUS_PASS,
)
from .evidence import EVIDENCE_AFTER, EVIDENCE_BEFORE
from .fingerprint import changed_paths
from .git_subject import head_oid, is_commit_oid, subject_tree_oid, worktree_is_clean
from .ledger import current_state
from .migration_evidence import load_manifest, validate_manifest_shape
from .path_selector import select_obligations
from .plan_profile import active_profile
from .receipts import build_recovery, matching_receipts
from .sessions import budget_verdict, estimate_transcript_cost


def _non_evidence_obligations(required: Sequence[str]) -> List[str]:
    return sorted(
        item
        for item in required
        if not item.endswith(".rendered-evidence")
        and ".migration-evidence." not in item
    )


def evaluate_capture_ready(
    root_id: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    *,
    kind: str = "after",
    transcript_path: str = "",
    family: str = "git-commit",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Return structured readiness for baseline or after capture."""
    errors: List[str] = []
    next_commands: List[str] = []
    try:
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    profile = active_profile(state, root_id, worktree_id)
    if not profile.get("profiled"):
        errors.append("missing-strict-plan-profile")
        next_commands.append(
            "python3 harness/cli.py register-plan --root %s --manifest execution-manifest.json"
            % root_id
        )
    if profile.get("strict") and not str(profile.get("execution_manifest_hash") or "").strip():
        errors.append("missing-execution-manifest-hash")
    if profile.get("strict") and not str(profile.get("base_oid") or "").strip():
        errors.append("missing-base-oid")
    base_oid = str(profile.get("base_oid") or "")
    if base_oid and not is_commit_oid(base_oid, root_path):
        errors.append("invalid-base-oid")
    manifest_pointer = str(profile.get("evidence_manifest_pointer") or "")
    manifest: Dict[str, Any] = {}
    if profile.get("strict") and not manifest_pointer:
        errors.append("missing-evidence-manifest")
    elif manifest_pointer:
        if not os.path.isfile(manifest_pointer):
            errors.append("evidence-manifest-not-found")
        else:
            try:
                manifest = load_manifest(manifest_pointer)
                errors.extend(validate_manifest_shape(manifest))
                if int(manifest.get("schema_version") or 0) != MIGRATION_EVIDENCE_SCHEMA_VERSION:
                    errors.append("legacy-evidence-manifest-rejected")
                if str(manifest.get("plan_hash") or "") != str(profile.get("plan_hash") or ""):
                    errors.append("manifest-plan-hash-mismatch")
            except (OSError, ValueError) as exc:
                errors.append("invalid-evidence-manifest:%s" % exc)

    changed = changed_paths(root_path)
    if manifest and changed:
        from .conformance import _matches

        for item in manifest.get("changes") or []:
            if not isinstance(item, dict):
                continue
            change_id = str(item.get("change_id") or "")
            source_paths = item.get("source_paths")
            if not isinstance(source_paths, list):
                continue
            for source_path in source_paths:
                normalized = str(source_path).replace(os.sep, "/")
                if not any(_matches(path, [normalized]) for path in changed):
                    errors.append("manifest-source-path-not-in-diff:%s:%s" % (change_id, normalized))
    conformance = evaluate_against_base(
        root_id,
        worktree_id,
        changed,
        profile,
        root_path=root_path,
        base=base,
    )
    if conformance.get(UNDECLARED):
        errors.append("undeclared-paths")
    if conformance.get(UNIMPLEMENTED):
        errors.append("unimplemented-required-paths")
    tier = str(profile.get("tier") or "T0")
    selection = select_obligations(
        root_id,
        changed,
        profile,
        tier,
        family=family,
        include_review=False,
    )
    if selection.get("classification_errors"):
        errors.extend(list(selection["classification_errors"]))
    for obligation_id in _non_evidence_obligations(selection["required_obligation_ids"]):
        receipts = [
            item
            for item in matching_receipts(state, root_id, worktree_id, fingerprint)
            if item.get("obligation_id") == obligation_id and item.get("status") == STATUS_PASS
        ]
        if not receipts:
            errors.append("missing-verification:%s" % obligation_id)

    if transcript_path:
        cost = estimate_transcript_cost(transcript_path)
        budget = budget_verdict(cost, profile)
        if budget["status"] != STATUS_PASS:
            errors.extend(list(budget.get("reasons") or []))
            next_commands.append("python3 harness/cli.py handoff --root %s --phase capture" % root_id)

    if kind == EVIDENCE_AFTER and not worktree_is_clean(root_path):
        errors.append("after-capture-requires-clean-staged-tree")
        next_commands.append("git add -A && git status --short")

    subject_tree = ""
    if kind == EVIDENCE_BEFORE and base_oid:
        subject_tree = subject_tree_oid(root_path, commit_oid=base_oid)
    elif kind == EVIDENCE_AFTER:
        subject_tree = subject_tree_oid(root_path, staged=True) or subject_tree_oid(root_path)

    recovery = build_recovery(
        {
            "missing": [item for item in errors if item.startswith("missing-")],
            "conformance": [item for item in errors if "path" in item],
            "evidence": [item for item in errors if "manifest" in item or "capture" in item],
        },
        str(profile.get("plan_hash") or ""),
    )
    if not next_commands:
        next_commands.append(RECOVERY_COMMAND)
    return {
        "status": STATUS_PASS if not errors else STATUS_BLOCKED,
        "ready": not errors,
        "kind": kind,
        "errors": errors,
        "recovery": recovery,
        "next_command": next_commands[0],
        "plan_hash": profile.get("plan_hash") or "",
        "plan_context_hash": profile.get("plan_context_hash") or "",
        "base_oid": base_oid,
        "head_oid": head_oid(root_path),
        "subject_tree_oid": subject_tree,
        "changed_paths": changed,
        "required_obligation_ids": selection["required_obligation_ids"],
    }
