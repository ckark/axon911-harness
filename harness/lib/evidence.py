"""Hash-bound rendered evidence registration and gate revalidation."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, Mapping, Optional, Sequence

from .capture_receipt import (
    CAPTURE_PRODUCER,
    load_capture_receipt,
    receipt_digest,
    validate_capture_receipt_binding,
)
from .constants import EVIDENCE_SCHEMA_VERSION, STATUS_PASS
from .ledger import append_record, current_state
from .media_validation import validate_image_artifact

ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
EVIDENCE_BEFORE = "before"
EVIDENCE_AFTER = "after"
EVIDENCE_KINDS = (EVIDENCE_BEFORE, EVIDENCE_AFTER)


def _normalize(path: str) -> str:
    return path.replace(os.sep, "/")


def _artifact_id(root: str, obligation_id: str, kind: str, digest: str) -> str:
    return "%s:%s:%s:%s" % (root, obligation_id, kind, digest[:16])


def _hash_file(path: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def validate_artifact(root_path: str, artifact_path: str) -> tuple[str, int]:
    """Ensure artifact is a regular image file inside root with valid signature."""
    real_root = os.path.realpath(root_path)
    real_artifact = os.path.realpath(os.path.join(real_root, artifact_path))
    if not real_artifact.startswith(real_root + os.sep) and real_artifact != real_root:
        raise ValueError("artifact escapes root")
    if not os.path.isfile(real_artifact):
        raise ValueError("artifact is not a regular file")
    if os.path.islink(real_artifact):
        raise ValueError("artifact must not be a symlink")
    ext = os.path.splitext(real_artifact)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("unsupported artifact extension: %s" % ext)
    size = os.path.getsize(real_artifact)
    if size <= 0:
        raise ValueError("artifact is empty")
    validate_image_artifact(real_artifact)
    return _hash_file(real_artifact)


def register_evidence(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    plan_context_hash: str,
    obligation_id: str,
    kind: str,
    artifact_path: str,
    artifact_hash: str,
    artifact_size: int,
    base_oid: str = "",
    session_id: str = "",
    change_id: str = "",
    capture: Optional[Mapping[str, str]] = None,
    capture_receipt_hash: str = "",
    capture_receipt_pointer: str = "",
    capture_id: str = "",
    source_sha: str = "",
    capture_role: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    if kind not in EVIDENCE_KINDS:
        raise ValueError("invalid evidence kind")
    capture = capture or {}
    return append_record(
        {
            "kind": "evidence_record",
            "root": root,
            "worktree_id": worktree_id,
            "session_id": session_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "plan_context_hash": plan_context_hash,
            "obligation_id": obligation_id,
            "evidence_kind": kind,
            "evidence_pointer": _normalize(artifact_path),
            "artifact_hash": artifact_hash,
            "artifact_size": artifact_size,
            "base_oid": base_oid,
            "change_id": change_id,
            "capture_story_id": str(capture.get("story_id") or ""),
            "capture_theme": str(capture.get("theme") or ""),
            "capture_brand": str(capture.get("brand") or ""),
            "capture_viewport": str(capture.get("viewport") or ""),
            "capture_state": str(capture.get("state") or ""),
            "capture_receipt_hash": capture_receipt_hash,
            "capture_receipt_pointer": capture_receipt_pointer,
            "capture_id": capture_id,
            "capture_producer": CAPTURE_PRODUCER if capture_receipt_hash else "",
            "source_sha": source_sha,
            "capture_role": capture_role or kind,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "status": STATUS_PASS,
        },
        base=base,
    )


def record_evidence(
    root: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    plan_context_hash: str,
    obligation_id: str,
    kind: str,
    artifact_path: str,
    base_oid: str = "",
    session_id: str = "",
    change_id: str = "",
    capture: Optional[Mapping[str, str]] = None,
    capture_receipt_path: str = "",
    source_sha: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    digest, size = validate_artifact(root_path, artifact_path)
    capture_receipt_hash = ""
    capture_receipt_pointer = ""
    capture_id = ""
    if not capture_receipt_path:
        raise ValueError("capture receipt required for schema v%s evidence" % EVIDENCE_SCHEMA_VERSION)
    real_root = os.path.realpath(root_path)
    real_receipt = os.path.realpath(os.path.join(real_root, capture_receipt_path))
    if not real_receipt.startswith(real_root + os.sep):
        raise ValueError("capture receipt escapes root")
    receipt = load_capture_receipt(real_receipt)
    errors = validate_capture_receipt_binding(
        receipt,
        os.path.join(real_root, artifact_path),
        source_sha=source_sha,
        role=kind,
        capture=capture,
    )
    if errors:
        raise ValueError("; ".join(errors))
    capture_receipt_hash = receipt_digest(receipt)
    capture_receipt_pointer = _normalize(capture_receipt_path)
    capture_id = str(receipt.get("capture_id") or "")
    return register_evidence(
        root,
        worktree_id,
        fingerprint,
        plan_hash,
        plan_context_hash,
        obligation_id,
        kind,
        artifact_path,
        digest,
        size,
        base_oid=base_oid,
        session_id=session_id,
        change_id=change_id,
        capture=capture,
        capture_receipt_hash=capture_receipt_hash,
        capture_receipt_pointer=capture_receipt_pointer,
        capture_id=capture_id,
        source_sha=source_sha or str(receipt.get("source_sha") or ""),
        capture_role=kind,
        base=base,
    )


def evidence_index(state: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(state.get("evidence") or {})


def matching_evidence(
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    obligation_id: str,
    plan_context_hash: str,
) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    for item in evidence_index(state).values():
        if item.get("root") != root:
            continue
        if item.get("worktree_id") != worktree_id:
            continue
        if item.get("obligation_id") != obligation_id:
            continue
        if plan_context_hash and item.get("plan_context_hash") != plan_context_hash:
            continue
        kind = str(item.get("evidence_kind") or "")
        if kind:
            found[kind] = item
    return found


def _legacy_record(item: Mapping[str, Any]) -> bool:
    return str(item.get("evidence_schema_version") or "") != EVIDENCE_SCHEMA_VERSION


def _receipt_errors(root_path: str, item: Mapping[str, Any], capture: Optional[Mapping[str, str]] = None) -> Sequence[str]:
    if _legacy_record(item):
        return ["legacy-evidence-record-rejected"]
    pointer = str(item.get("capture_receipt_pointer") or "")
    if not pointer:
        return ["missing-capture-receipt"]
    receipt_path = os.path.join(root_path, pointer)
    if not os.path.isfile(receipt_path):
        return ["capture-receipt-missing"]
    try:
        receipt = load_capture_receipt(receipt_path)
    except (OSError, ValueError) as exc:
        return ["capture-receipt-unreadable:%s" % exc]
    artifact_path = os.path.join(root_path, str(item.get("evidence_pointer") or ""))
    return validate_capture_receipt_binding(
        receipt,
        artifact_path,
        source_sha=str(item.get("source_sha") or ""),
        role=str(item.get("capture_role") or item.get("evidence_kind") or ""),
        capture=capture,
    )


def revalidate_evidence(
    root_path: str,
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    obligation_id: str,
    plan_context_hash: str,
    require_before: bool,
    require_after: bool,
    base_oid: str = "",
    fingerprint: str = "",
) -> Sequence[str]:
    """Return missing or invalid evidence kinds for an obligation."""
    errors: list[str] = []
    found = matching_evidence(state, root, worktree_id, obligation_id, plan_context_hash)
    kinds_needed = []
    if require_before:
        kinds_needed.append(EVIDENCE_BEFORE)
    if require_after:
        kinds_needed.append(EVIDENCE_AFTER)
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    seen_capture_ids: set[str] = set()
    for kind in kinds_needed:
        item = found.get(kind)
        if not item:
            errors.append("missing-%s-evidence" % kind)
            continue
        pointer = str(item.get("evidence_pointer") or "")
        if pointer in seen_paths:
            errors.append("duplicate-evidence-artifact")
        seen_paths.add(pointer)
        capture_id = str(item.get("capture_id") or "")
        if capture_id:
            if capture_id in seen_capture_ids:
                errors.append("duplicate-capture-id")
            seen_capture_ids.add(capture_id)
        if kind == EVIDENCE_BEFORE and base_oid and item.get("base_oid") != base_oid:
            errors.append("before-evidence-base-mismatch")
        if kind == EVIDENCE_AFTER and fingerprint and item.get("fingerprint") != fingerprint:
            errors.append("after-evidence-fingerprint-mismatch")
        try:
            digest, size = validate_artifact(root_path, pointer)
        except ValueError as exc:
            errors.append("invalid-evidence-artifact:%s" % exc)
            continue
        if digest != item.get("artifact_hash") or size != item.get("artifact_size"):
            errors.append("evidence-artifact-changed:%s" % kind)
        errors.extend(_receipt_errors(root_path, item))
        seen_hashes.add(str(item.get("artifact_hash") or ""))
    if EVIDENCE_BEFORE in found and EVIDENCE_AFTER in found:
        before_path = str(found[EVIDENCE_BEFORE].get("evidence_pointer") or "")
        after_path = str(found[EVIDENCE_AFTER].get("evidence_pointer") or "")
        if before_path and before_path == after_path:
            errors.append("before-after-artifact-not-distinct")
        before_hash = str(found[EVIDENCE_BEFORE].get("artifact_hash") or "")
        after_hash = str(found[EVIDENCE_AFTER].get("artifact_hash") or "")
        before_capture = str(found[EVIDENCE_BEFORE].get("capture_id") or "")
        after_capture = str(found[EVIDENCE_AFTER].get("capture_id") or "")
        if before_hash and before_hash == after_hash and before_capture == after_capture:
            errors.append("before-after-capture-not-distinct")
    return errors
