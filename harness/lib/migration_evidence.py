"""Per-change migration evidence manifests, validation, and PR markdown."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, TypedDict

from .evidence import (
    EVIDENCE_AFTER,
    EVIDENCE_BEFORE,
    matching_evidence,
    validate_artifact,
)


class CaptureSpec(TypedDict, total=False):
    story_id: str
    theme: str
    brand: str
    viewport: str
    state: str


class ChangeSpec(TypedDict, total=False):
    change_id: str
    title: str
    source_paths: List[str]
    capture: CaptureSpec
    before_url: str
    after_url: str


class MigrationManifest(TypedDict, total=False):
    plan_hash: str
    changes: List[ChangeSpec]


REQUIRED_CAPTURE_KEYS = ("story_id", "theme", "brand", "viewport", "state")


def _normalize(path: str) -> str:
    return path.replace(os.sep, "/")


def load_manifest(path: str) -> MigrationManifest:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data  # type: ignore[return-value]


def validate_manifest_shape(manifest: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if not str(manifest.get("plan_hash") or "").strip():
        errors.append("manifest-missing-plan-hash")
    changes = manifest.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append("manifest-missing-changes")
        return errors
    seen: set[str] = set()
    for index, item in enumerate(changes):
        if not isinstance(item, dict):
            errors.append("manifest-change-%d-not-object" % index)
            continue
        change_id = str(item.get("change_id") or "").strip()
        if not change_id:
            errors.append("manifest-change-%d-missing-change-id" % index)
            continue
        if change_id in seen:
            errors.append("manifest-duplicate-change-id:%s" % change_id)
        seen.add(change_id)
        if not str(item.get("title") or "").strip():
            errors.append("manifest-change-%s-missing-title" % change_id)
        capture = item.get("capture")
        if not isinstance(capture, dict):
            errors.append("manifest-change-%s-missing-capture" % change_id)
            continue
        for key in REQUIRED_CAPTURE_KEYS:
            if not str(capture.get(key) or "").strip():
                errors.append("manifest-change-%s-missing-capture-%s" % (change_id, key))
    return errors


def obligation_id_for_change(root: str, change_id: str) -> str:
    return "%s.migration-evidence.%s" % (root, change_id)


def _capture_matches(record: Mapping[str, Any], capture: Mapping[str, Any]) -> bool:
    for key in REQUIRED_CAPTURE_KEYS:
        if str(record.get("capture_%s" % key) or "") != str(capture.get(key) or ""):
            return False
    return True


def revalidate_migration_manifest(
    root_path: str,
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    manifest: Mapping[str, Any],
    plan_context_hash: str,
    base_oid: str = "",
    fingerprint: str = "",
) -> Sequence[str]:
    errors = list(validate_manifest_shape(manifest))
    if errors:
        return errors
    for item in manifest.get("changes") or []:
        if not isinstance(item, dict):
            continue
        change_id = str(item["change_id"])
        obligation_id = obligation_id_for_change(root, change_id)
        found = matching_evidence(state, root, worktree_id, obligation_id, plan_context_hash)
        capture = item.get("capture") or {}
        for kind in (EVIDENCE_BEFORE, EVIDENCE_AFTER):
            record = found.get(kind)
            if not record:
                errors.append("missing-%s-evidence:%s" % (kind, change_id))
                continue
            pointer = str(record.get("evidence_pointer") or "")
            if kind == EVIDENCE_BEFORE and base_oid and record.get("base_oid") != base_oid:
                errors.append("before-evidence-base-mismatch:%s" % change_id)
            if kind == EVIDENCE_AFTER and fingerprint and record.get("fingerprint") != fingerprint:
                errors.append("after-evidence-fingerprint-mismatch:%s" % change_id)
            if not _capture_matches(record, capture):
                errors.append("capture-metadata-mismatch:%s:%s" % (change_id, kind))
            try:
                digest, size = validate_artifact(root_path, pointer)
            except ValueError as exc:
                errors.append("invalid-evidence-artifact:%s:%s" % (change_id, exc))
                continue
            if digest != record.get("artifact_hash") or size != record.get("artifact_size"):
                errors.append("evidence-artifact-changed:%s:%s" % (change_id, kind))
        before_pointer = str((found.get(EVIDENCE_BEFORE) or {}).get("evidence_pointer") or "")
        after_pointer = str((found.get(EVIDENCE_AFTER) or {}).get("evidence_pointer") or "")
        if before_pointer and before_pointer == after_pointer:
            errors.append("before-after-artifact-not-distinct:%s" % change_id)
    return errors


def render_pr_body(manifest: Mapping[str, Any], attachment_urls: Optional[Mapping[str, Mapping[str, str]]] = None) -> str:
    """Render a PR body section with labeled before/after pairs per change."""
    lines = ["## Visual changes", ""]
    urls = attachment_urls or {}
    for item in manifest.get("changes") or []:
        if not isinstance(item, dict):
            continue
        change_id = str(item.get("change_id") or "")
        title = str(item.get("title") or change_id)
        lines.append("### %s" % title)
        lines.append("")
        before = (urls.get(change_id) or {}).get("before") or str(item.get("before_url") or "")
        after = (urls.get(change_id) or {}).get("after") or str(item.get("after_url") or "")
        lines.append("**Before**")
        lines.append("")
        if before:
            lines.append("![%s before](%s)" % (title, before))
        else:
            lines.append("_Before image pending_")
        lines.append("")
        lines.append("**After**")
        lines.append("")
        if after:
            lines.append("![%s after](%s)" % (title, after))
        else:
            lines.append("_After image pending_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
