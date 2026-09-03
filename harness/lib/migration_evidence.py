"""Per-change migration evidence manifests, validation, and PR markdown."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, TypedDict

from .capture_receipt import validate_capture_receipt_binding
from .constants import (
    MIGRATION_EVIDENCE_SCHEMA_VERSION,
    VISUAL_EVIDENCE_MARKER_END,
    VISUAL_EVIDENCE_MARKER_START,
)
from .evidence import (
    EVIDENCE_AFTER,
    EVIDENCE_BEFORE,
    matching_evidence,
    validate_artifact,
)
from .constants import STATUS_PASS
from .github_attach import USER_ATTACHMENT_URL
from .ledger import append_record


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
    expected_visual_result: str
    url_bindings: Dict[str, str]


class MigrationManifest(TypedDict, total=False):
    schema_version: int
    plan_hash: str
    changes: List[ChangeSpec]


REQUIRED_CAPTURE_KEYS = ("story_id", "theme", "brand", "viewport", "state")
CURSOR_SUMMARY_MARKER = "<!-- CURSOR_SUMMARY"


def _normalize(path: str) -> str:
    return path.replace(os.sep, "/")


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_manifest(path: str) -> MigrationManifest:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data  # type: ignore[return-value]


def validate_manifest_shape(manifest: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    schema_version = int(manifest.get("schema_version") or 0)
    if schema_version and schema_version != MIGRATION_EVIDENCE_SCHEMA_VERSION:
        errors.append("manifest-schema-version-mismatch")
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
        source_paths = item.get("source_paths")
        if not isinstance(source_paths, list) or not source_paths:
            errors.append("manifest-change-%s-missing-source-paths" % change_id)
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


def migration_obligation_ids(root: str, manifest: Mapping[str, Any]) -> List[str]:
    ids: List[str] = []
    for item in manifest.get("changes") or []:
        if isinstance(item, dict) and item.get("change_id"):
            ids.append(obligation_id_for_change(root, str(item["change_id"])))
    return sorted(ids)


def _capture_matches(record: Mapping[str, Any], capture: Mapping[str, Any]) -> bool:
    for key in REQUIRED_CAPTURE_KEYS:
        if str(record.get("capture_%s" % key) or "") != str(capture.get(key) or ""):
            return False
    return True


def _url_binding_errors(item: Mapping[str, Any], found: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    change_id = str(item.get("change_id") or "")
    bindings = item.get("url_bindings") or {}
    if not isinstance(bindings, dict):
        return errors
    for kind in (EVIDENCE_BEFORE, EVIDENCE_AFTER):
        url = str(bindings.get(kind) or item.get("%s_url" % kind) or "")
        if not url:
            continue
        if not USER_ATTACHMENT_URL.match(url):
            errors.append("invalid-attachment-url:%s:%s" % (change_id, kind))
            continue
        record = found.get(kind) or {}
        expected = str(record.get("artifact_hash") or "")
        bound = str(bindings.get("%s_hash" % kind) or bindings.get(kind + "_hash") or "")
        if bound and expected and bound != expected:
            errors.append("url-hash-binding-mismatch:%s:%s" % (change_id, kind))
    return errors


def revalidate_migration_manifest(
    root_path: str,
    state: Mapping[str, Any],
    root: str,
    worktree_id: str,
    manifest: Mapping[str, Any],
    plan_context_hash: str,
    base_oid: str = "",
    fingerprint: str = "",
    active_plan_hash: str = "",
) -> Sequence[str]:
    errors = list(validate_manifest_shape(manifest))
    if active_plan_hash and str(manifest.get("plan_hash") or "") != active_plan_hash:
        errors.append("manifest-plan-hash-mismatch")
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
            receipt_pointer = str(record.get("capture_receipt_pointer") or "")
            if not receipt_pointer:
                errors.append("missing-capture-receipt:%s:%s" % (change_id, kind))
            else:
                receipt_path = os.path.join(root_path, receipt_pointer)
                if os.path.isfile(receipt_path):
                    try:
                        from .capture_receipt import load_capture_receipt

                        receipt = load_capture_receipt(receipt_path)
                        errors.extend(
                            validate_capture_receipt_binding(
                                receipt,
                                os.path.join(root_path, pointer),
                                source_sha=str(record.get("source_sha") or ""),
                                role=kind,
                                capture=capture,
                            )
                        )
                    except (OSError, ValueError) as exc:
                        errors.append("capture-receipt-unreadable:%s:%s" % (change_id, exc))
        before_pointer = str((found.get(EVIDENCE_BEFORE) or {}).get("evidence_pointer") or "")
        after_pointer = str((found.get(EVIDENCE_AFTER) or {}).get("evidence_pointer") or "")
        before_hash = str((found.get(EVIDENCE_BEFORE) or {}).get("artifact_hash") or "")
        after_hash = str((found.get(EVIDENCE_AFTER) or {}).get("artifact_hash") or "")
        before_capture = str((found.get(EVIDENCE_BEFORE) or {}).get("capture_id") or "")
        after_capture = str((found.get(EVIDENCE_AFTER) or {}).get("capture_id") or "")
        if before_pointer and before_pointer == after_pointer:
            errors.append("before-after-artifact-not-distinct:%s" % change_id)
        if (
            before_hash
            and after_hash
            and before_hash == after_hash
            and before_capture == after_capture
            and str(item.get("expected_visual_result") or "") != "unchanged"
        ):
            errors.append("before-after-hash-identical:%s" % change_id)
        errors.extend(_url_binding_errors(item, found))
        before_url = str(item.get("before_url") or "")
        after_url = str(item.get("after_url") or "")
        if not before_url or not after_url:
            errors.append("missing-hosted-url:%s" % change_id)
    return errors


def _render_change_section(
    item: Mapping[str, Any],
    attachment_urls: Optional[Mapping[str, Mapping[str, str]]] = None,
    *,
    base_sha: str = "",
    head_sha: str = "",
) -> List[str]:
    change_id = str(item.get("change_id") or "")
    title = str(item.get("title") or change_id)
    capture = item.get("capture") or {}
    urls = attachment_urls or {}
    before = (urls.get(change_id) or {}).get("before") or str(item.get("before_url") or "")
    after = (urls.get(change_id) or {}).get("after") or str(item.get("after_url") or "")
    lines = [
        "### %s" % title,
        "",
        "**Before**",
        "",
    ]
    if before:
        lines.append("![%s before](%s)" % (title, before))
    else:
        raise ValueError("missing before URL for %s" % change_id)
    lines.extend(
        [
            "",
            "**After**",
            "",
        ]
    )
    if after:
        lines.append("![%s after](%s)" % (title, after))
    else:
        raise ValueError("missing after URL for %s" % change_id)
    lines.extend(
        [
            "",
            "_Capture:_ story `%s`, theme `%s`, brand `%s`, viewport `%s`, state `%s`."
            % (
                capture.get("story_id", ""),
                capture.get("theme", ""),
                capture.get("brand", ""),
                capture.get("viewport", ""),
                capture.get("state", ""),
            ),
            "",
        ]
    )
    if base_sha or head_sha:
        lines.append("_Source SHAs:_ base `%s`, head `%s`." % (base_sha, head_sha))
        lines.append("")
    return lines


def render_pr_body(
    manifest: Mapping[str, Any],
    attachment_urls: Optional[Mapping[str, Mapping[str, str]]] = None,
    *,
    base_sha: str = "",
    head_sha: str = "",
    manifest_hash: str = "",
) -> str:
    """Render a bounded PR body section with labeled before/after pairs per change."""
    if not manifest_hash:
        manifest_hash = manifest_sha256(manifest)
    lines = [
        "%s schema=%s base=%s head=%s manifest-sha256=%s -->"
        % (VISUAL_EVIDENCE_MARKER_START, MIGRATION_EVIDENCE_SCHEMA_VERSION, base_sha, head_sha, manifest_hash),
        "## Visual changes",
        "",
    ]
    for item in manifest.get("changes") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            _render_change_section(
                item,
                attachment_urls,
                base_sha=base_sha,
                head_sha=head_sha,
            )
        )
    lines.append(VISUAL_EVIDENCE_MARKER_END)
    return "\n".join(lines).rstrip() + "\n"


def _find_marker_block(body: str) -> tuple[int, int]:
    start = body.find(VISUAL_EVIDENCE_MARKER_START)
    if start < 0:
        return -1, -1
    end = body.find(VISUAL_EVIDENCE_MARKER_END, start)
    if end < 0:
        return start, -1
    return start, end + len(VISUAL_EVIDENCE_MARKER_END)


def merge_pr_body(existing_body: str, evidence_block: str) -> str:
    """Replace or insert the bounded visual-evidence block before CURSOR_SUMMARY."""
    start, end = _find_marker_block(existing_body)
    if start >= 0 and end > start:
        prefix = existing_body[:start].rstrip()
        suffix = existing_body[end:].lstrip("\n")
        parts = [part for part in (prefix, evidence_block.rstrip(), suffix) if part]
        return "\n\n".join(parts).rstrip() + "\n"
    cursor_idx = existing_body.find(CURSOR_SUMMARY_MARKER)
    block = evidence_block.rstrip()
    if cursor_idx >= 0:
        prefix = existing_body[:cursor_idx].rstrip()
        suffix = existing_body[cursor_idx:].lstrip("\n")
        return "\n\n".join([part for part in (prefix, block, suffix) if part]).rstrip() + "\n"
    base = existing_body.rstrip()
    if base:
        return base + "\n\n" + block + "\n"
    return block + "\n"


def active_migration_manifest_pointer(state: Mapping[str, Any], root: str, worktree_id: str) -> str:
    binding = (state.get("migration_manifests") or {}).get("%s:%s" % (root, worktree_id)) or {}
    return str(binding.get("pointer") or "")


def register_migration_manifest(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    manifest_pointer: str,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    return append_record(
        {
            "kind": "migration_manifest_binding",
            "root": root,
            "worktree_id": worktree_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "migration_manifest_pointer": _normalize(manifest_pointer),
            "obligation_id": "plan",
            "status": STATUS_PASS,
        },
        base=base,
    )


def verify_pr_body_block(
    body: str,
    *,
    base_sha: str,
    head_sha: str,
    manifest_hash: str,
    expected_change_count: int,
) -> List[str]:
    errors: List[str] = []
    start, end = _find_marker_block(body)
    if start < 0 or end < 0:
        errors.append("pr-body-missing-visual-evidence-markers")
        return errors
    block = body[start:end]
    if block.count(VISUAL_EVIDENCE_MARKER_START) != 1 or block.count(VISUAL_EVIDENCE_MARKER_END) != 1:
        errors.append("pr-body-malformed-visual-evidence-markers")
    if "base=%s" % base_sha not in block:
        errors.append("pr-body-base-sha-mismatch")
    if "head=%s" % head_sha not in block:
        errors.append("pr-body-head-sha-mismatch")
    if "manifest-sha256=%s" % manifest_hash not in block:
        errors.append("pr-body-manifest-hash-mismatch")
    if block.lower().count("pending") > 0:
        errors.append("pr-body-pending-image")
    urls = USER_ATTACHMENT_URL.findall(block)
    if len(urls) < expected_change_count * 2:
        errors.append("pr-body-insufficient-attachment-urls")
    return errors
