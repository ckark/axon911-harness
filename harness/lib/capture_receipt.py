"""Trusted Storybook capture receipt schema and validation."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .git_subject import is_commit_oid, worktree_is_clean
from .media_validation import validate_image_artifact


def is_plausible_commit_sha(value: str) -> bool:
    """Return True when `value` looks like a Git commit object name."""
    cleaned = value.strip().lower()
    if len(cleaned) < 7 or len(cleaned) > 40:
        return False
    try:
        int(cleaned, 16)
    except ValueError:
        return False
    return True

CAPTURE_PRODUCER = "prepared911-harness/storybook-capture"
CAPTURE_RECEIPT_VERSION = 4
SUPPORTED_RECEIPT_VERSIONS = (4,)
CAPTURE_KINDS = ("storybook", "product-route", "not-applicable")

CONTENT_ORIGINS = ("product", "synthetic")
CAPTURE_SCOPES = ("contextual", "isolated")

REQUIRED_RECEIPT_KEYS = (
    "version",
    "capture_id",
    "producer",
    "source_sha",
    "role",
    "artifact_path",
    "artifact_hash",
    "story_id",
    "story_url",
    "theme",
    "brand",
    "viewport",
    "state",
    "target_selector",
    "mime",
    "width",
    "height",
    "timestamp",
    "health",
)

REQUIRED_V4_KEYS = (
    "capture_kind",
    "server_port",
)

REQUIRED_HEALTH_KEYS = (
    "storybook_ready",
    "fonts_ready",
    "css_tokens_ready",
    "theme_applied",
    "target_visible",
    "target_bounds_nonzero",
    "stylesheets_present",
    "console_errors",
    "failed_requests",
)


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_capture_receipt(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("capture receipt must be a JSON object")
    return data


def validate_capture_receipt_shape(receipt: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    version = int(receipt.get("version") or 0)
    if version not in SUPPORTED_RECEIPT_VERSIONS:
        errors.append("capture-receipt-version-mismatch")
        return errors
    base_keys = (
        "version",
        "capture_id",
        "producer",
        "source_sha",
        "role",
        "artifact_path",
        "artifact_hash",
        "mime",
        "width",
        "height",
        "timestamp",
        "health",
        "capture_kind",
    )
    for key in base_keys:
        if key not in receipt or receipt.get(key) in ("", None):
            errors.append("capture-receipt-missing-%s" % key)
    capture_kind = str(receipt.get("capture_kind") or "")
    if capture_kind == "storybook":
        for key in ("story_id", "story_url", "theme", "brand", "viewport", "state", "target_selector"):
            if key not in receipt or receipt.get(key) in ("", None):
                errors.append("capture-receipt-missing-%s" % key)
    elif capture_kind == "product-route":
        for key in ("route", "entrypoint", "theme", "brand", "viewport", "state", "target_selector"):
            if key not in receipt or receipt.get(key) in ("", None):
                errors.append("capture-receipt-missing-%s" % key)
    health = receipt.get("health")
    if not isinstance(health, dict):
        errors.append("capture-receipt-missing-health")
        return errors
    for key in REQUIRED_HEALTH_KEYS:
        if key not in health:
            errors.append("capture-receipt-missing-health-%s" % key)
    if str(receipt.get("producer") or "") != CAPTURE_PRODUCER:
        errors.append("capture-receipt-invalid-producer")
    return errors


def validate_capture_receipt_provenance(
    receipt: Mapping[str, Any],
    *,
    require_v4: bool = False,
    require_v3: bool = False,
    expected_manifest_hash: str = "",
    expected_change_id: str = "",
    expected_content_origin: str = "",
    expected_capture_scope: str = "",
    repo_path: str = "",
) -> List[str]:
    """Validate v4 provenance and DOM assertion fields."""
    errors: List[str] = []
    version = int(receipt.get("version") or 0)
    if version < 4 and (require_v4 or require_v3):
        errors.append("capture-receipt-legacy-version-rejected")
        return errors
    if version < 4:
        return errors
    for key in (
        "source_tree",
        "source_clean",
        "manifest_hash",
        "change_id",
        "content_origin",
        "capture_scope",
        "clip_selector",
        "clip_bounds",
        "dom_assertions",
    ):
        if key not in receipt:
            if key == "dom_assertions" and isinstance(receipt.get("dom_assertions"), list):
                continue
            errors.append("capture-receipt-missing-%s" % key)
    for key in REQUIRED_V4_KEYS:
        if key not in receipt or receipt.get(key) in ("", None):
            errors.append("capture-receipt-missing-%s" % key)
    capture_kind = str(receipt.get("capture_kind") or "")
    if capture_kind not in CAPTURE_KINDS:
        errors.append("capture-receipt-invalid-capture-kind")
    if capture_kind == "storybook" and not str(receipt.get("story_id") or "").strip():
        errors.append("capture-receipt-missing-story-id")
    if capture_kind == "product-route" and not str(receipt.get("route") or "").strip():
        errors.append("capture-receipt-missing-route")
    content_origin = str(receipt.get("content_origin") or "")
    capture_scope = str(receipt.get("capture_scope") or "")
    if content_origin and content_origin not in CONTENT_ORIGINS:
        errors.append("capture-receipt-invalid-content-origin")
    if capture_scope and capture_scope not in CAPTURE_SCOPES:
        errors.append("capture-receipt-invalid-capture-scope")
    if expected_content_origin and content_origin != expected_content_origin:
        errors.append("capture-receipt-content-origin-mismatch")
    if expected_capture_scope and capture_scope != expected_capture_scope:
        errors.append("capture-receipt-capture-scope-mismatch")
    if expected_manifest_hash and str(receipt.get("manifest_hash") or "") != expected_manifest_hash:
        errors.append("capture-receipt-manifest-hash-mismatch")
    if expected_change_id and str(receipt.get("change_id") or "") != expected_change_id:
        errors.append("capture-receipt-change-id-mismatch")
    source_tree = str(receipt.get("source_tree") or "")
    if source_tree:
        if len(source_tree) != 40:
            errors.append("capture-receipt-invalid-source-tree")
        elif repo_path:
            from .git_subject import tree_oid_at_commit

            expected_tree = tree_oid_at_commit(repo_path, str(receipt.get("source_sha") or ""))
            if expected_tree and expected_tree != source_tree:
                errors.append("capture-receipt-source-tree-mismatch")
    if receipt.get("source_clean") is False and str(receipt.get("role") or "") == "after":
        errors.append("capture-receipt-dirty-after-source")
    dom_assertions = receipt.get("dom_assertions")
    health = receipt.get("health") or {}
    if isinstance(dom_assertions, list) and dom_assertions:
        if health.get("dom_assertions_passed") is False:
            errors.append("capture-health-dom-assertions-failed")
        elif health.get("dom_assertions_passed") is not True:
            errors.append("capture-receipt-missing-dom-assertion-result")
    clip_bounds = receipt.get("clip_bounds")
    if isinstance(clip_bounds, dict):
        for axis in ("x", "y", "width", "height"):
            if axis not in clip_bounds:
                errors.append("capture-receipt-incomplete-clip-bounds")
                break
    return errors


def validate_dom_assertion_results(assertions: Sequence[Mapping[str, Any]]) -> List[str]:
    """Return errors for failed DOM assertion records."""
    errors: List[str] = []
    for index, item in enumerate(assertions):
        if not isinstance(item, dict):
            errors.append("dom-assertion-%d-not-object" % index)
            continue
        if item.get("passed") is False:
            kind = str(item.get("type") or "unknown")
            errors.append("dom-assertion-failed:%s" % kind)
    return errors


def validate_capture_receipt_health(receipt: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    health = receipt.get("health") or {}
    for key in (
        "storybook_ready",
        "fonts_ready",
        "css_tokens_ready",
        "theme_applied",
        "target_visible",
        "target_bounds_nonzero",
        "stylesheets_present",
    ):
        if not health.get(key):
            errors.append("capture-health-failed:%s" % key)
    if health.get("console_errors"):
        errors.append("capture-health-console-errors")
    if health.get("failed_requests"):
        errors.append("capture-health-failed-requests")
    dom_assertions = receipt.get("dom_assertions")
    if isinstance(dom_assertions, list) and dom_assertions:
        errors.extend(validate_dom_assertion_results(dom_assertions))
    return errors


def validate_capture_receipt_binding(
    receipt: Mapping[str, Any],
    artifact_path: str,
    *,
    source_sha: str = "",
    role: str = "",
    capture: Optional[Mapping[str, str]] = None,
    require_resolved_commit_sha: bool = False,
    require_v4: bool = False,
    require_v3: bool = False,
    repo_path: str = "",
    expected_manifest_hash: str = "",
    expected_change_id: str = "",
    expected_content_origin: str = "",
    expected_capture_scope: str = "",
) -> List[str]:
    """Validate receipt against artifact bytes and expected capture metadata."""
    errors = list(validate_capture_receipt_shape(receipt))
    errors.extend(
        validate_capture_receipt_provenance(
            receipt,
            require_v4=require_v4,
            require_v3=require_v3,
            expected_manifest_hash=expected_manifest_hash,
            expected_change_id=expected_change_id,
            expected_content_origin=expected_content_origin,
            expected_capture_scope=expected_capture_scope,
            repo_path=repo_path,
        )
    )
    errors.extend(validate_capture_receipt_health(receipt))
    if errors:
        return errors
    if not os.path.isfile(artifact_path):
        errors.append("capture-artifact-missing")
        return errors
    try:
        mime, width, height = validate_image_artifact(artifact_path)
    except ValueError as exc:
        errors.append("capture-artifact-invalid:%s" % exc)
        return errors
    digest = _hash_file(artifact_path)
    if digest != str(receipt.get("artifact_hash") or ""):
        errors.append("capture-receipt-hash-mismatch")
    if mime != str(receipt.get("mime") or ""):
        errors.append("capture-receipt-mime-mismatch")
    if int(receipt.get("width") or 0) != width or int(receipt.get("height") or 0) != height:
        errors.append("capture-receipt-dimension-mismatch")
    receipt_source = str(receipt.get("source_sha") or "")
    if source_sha and receipt_source != source_sha:
        errors.append("capture-receipt-source-sha-mismatch")
    if receipt_source and not is_plausible_commit_sha(receipt_source):
        errors.append("capture-receipt-invalid-source-sha")
    if require_resolved_commit_sha and receipt_source:
        if not is_commit_oid(receipt_source, repo_path):
            errors.append("capture-receipt-unresolved-source-sha")
    if role and str(receipt.get("role") or "") != role:
        errors.append("capture-receipt-role-mismatch")
    if capture:
        capture_kind = str(receipt.get("capture_kind") or capture.get("capture_kind") or "storybook")
        if capture_kind == "product-route":
            keys = ("route", "entrypoint", "scenario_id", "theme", "brand", "viewport", "state")
        else:
            keys = ("story_id", "theme", "brand", "viewport", "state")
        for key in keys:
            if str(receipt.get(key) or "") != str(capture.get(key) or ""):
                errors.append("capture-receipt-metadata-mismatch:%s" % key)
    return errors


def capture_source_provenance(
    repo_path: str,
    *,
    source_sha: str = "",
    staged: bool = False,
) -> Dict[str, Any]:
    """Resolve commit, tree, and cleanliness for capture receipts."""
    from .git_subject import head_oid, subject_tree_oid

    resolved_sha = source_sha.strip() or head_oid(repo_path)
    if staged:
        tree = subject_tree_oid(repo_path, staged=True)
    else:
        tree = subject_tree_oid(repo_path, commit_oid=resolved_sha)
    return {
        "source_sha": resolved_sha,
        "source_tree": tree,
        "source_clean": worktree_is_clean(repo_path),
    }


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_capture_receipt(path: str, receipt: Mapping[str, Any]) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, sort_keys=True, indent=2)
        handle.write("\n")
    os.chmod(path, 0o600)
    return receipt_digest(receipt)
