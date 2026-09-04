"""Fresh-context visual acceptance receipts for user-visible work."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .constants import STATUS_BLOCKED, STATUS_PASS
from .ledger import append_record, current_state
from .migration_evidence import load_manifest, manifest_sha256, revalidate_migration_manifest


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def validate_acceptance_report(
    report_path: str,
    *,
    expected_change_ids: Sequence[str],
    authoring_session_id: str,
    reviewer_session_id: str,
) -> List[str]:
    """Validate a visual acceptance report file."""
    errors: List[str] = []
    if not report_path or not os.path.isfile(report_path):
        return ["missing-acceptance-report"]
    if not reviewer_session_id.strip():
        errors.append("missing-reviewer-session-id")
    if authoring_session_id.strip() and reviewer_session_id.strip():
        if authoring_session_id.strip() == reviewer_session_id.strip():
            errors.append("reviewer-session-must-differ-from-author")
    try:
        with open(report_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return ["acceptance-report-unreadable:%s" % exc]
    if not isinstance(data, dict):
        return ["acceptance-report-not-object"]
    verdicts = data.get("change_verdicts")
    if not isinstance(verdicts, dict):
        errors.append("acceptance-report-missing-change-verdicts")
        return errors
    for change_id in expected_change_ids:
        verdict = str(verdicts.get(change_id) or "").upper()
        if verdict not in ("PASS", "FAIL"):
            errors.append("missing-verdict:%s" % change_id)
        elif verdict == "FAIL":
            errors.append("change-verdict-fail:%s" % change_id)
    for change_id in verdicts:
        if change_id not in expected_change_ids:
            errors.append("unexpected-verdict:%s" % change_id)
    if str(data.get("overall") or "").upper() == "FAIL":
        errors.append("acceptance-overall-fail")
    elif str(data.get("overall") or "").upper() not in ("PASS", ""):
        errors.append("acceptance-overall-invalid")
    return errors


def issue_visual_acceptance_receipt(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    plan_context_hash: str,
    *,
    reviewer_session_id: str,
    authoring_session_id: str,
    manifest_pointer: str,
    report_path: str,
    subject_tree_oid: str,
    root_path: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Issue a visual acceptance receipt after validating the report."""
    manifest = load_manifest(manifest_pointer)
    manifest_hash = manifest_sha256(manifest)
    change_ids = [
        str(item.get("change_id") or "")
        for item in manifest.get("changes") or []
        if isinstance(item, dict) and item.get("change_id")
    ]
    errors = validate_acceptance_report(
        report_path,
        expected_change_ids=change_ids,
        authoring_session_id=authoring_session_id,
        reviewer_session_id=reviewer_session_id,
    )
    state = current_state(base=base, validate=False)
    evidence_root = root_path.strip() or os.path.dirname(os.path.abspath(manifest_pointer))
    evidence_errors = revalidate_migration_manifest(
        evidence_root,
        state,
        root,
        worktree_id,
        manifest,
        plan_context_hash,
        fingerprint=fingerprint,
        active_plan_hash=plan_hash,
        require_hosted_urls=False,
    )
    errors.extend(evidence_errors)
    if subject_tree_oid.strip() and report_path:
        try:
            with open(report_path, encoding="utf-8") as handle:
                report_data = json.load(handle)
            if str(report_data.get("subject_tree_oid") or "").strip():
                if str(report_data.get("subject_tree_oid") or "") != subject_tree_oid.strip():
                    errors.append("acceptance-subject-tree-mismatch")
        except (OSError, json.JSONDecodeError):
            pass
    status = STATUS_PASS if not errors else STATUS_BLOCKED
    report_hash = _hash_file(report_path) if os.path.isfile(report_path) else ""
    return append_record(
        {
            "kind": "visual_acceptance_receipt",
            "root": root,
            "worktree_id": worktree_id,
            "session_id": reviewer_session_id,
            "authoring_session_id": authoring_session_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "plan_context_hash": plan_context_hash,
            "obligation_id": "visual.acceptance",
            "status": status,
            "manifest_hash": manifest_hash,
            "subject_tree_oid": subject_tree_oid,
            "report_path": report_path,
            "report_hash": report_hash,
            "validation_errors": errors,
        },
        base=base,
    )


def visual_acceptance_satisfied(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    plan_context_hash: str,
    *,
    manifest_hash: str = "",
) -> bool:
    """Return True when a passing visual acceptance receipt exists for this tree."""
    key = "%s:%s:%s" % (root, worktree_id, fingerprint)
    for item in (state.get("receipts") or {}).get(key) or []:
        if item.get("kind") != "visual_acceptance_receipt":
            continue
        if item.get("status") != STATUS_PASS:
            continue
        if plan_hash and item.get("plan_hash") != plan_hash:
            continue
        if plan_context_hash and item.get("plan_context_hash") != plan_context_hash:
            continue
        if manifest_hash and item.get("manifest_hash") != manifest_hash:
            continue
        return True
    return False
