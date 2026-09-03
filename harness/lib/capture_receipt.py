"""Trusted Storybook capture receipt schema and validation."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .media_validation import validate_image_artifact

CAPTURE_PRODUCER = "prepared911-harness/storybook-capture"
CAPTURE_RECEIPT_VERSION = 1

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

REQUIRED_HEALTH_KEYS = (
    "storybook_ready",
    "fonts_ready",
    "css_tokens_ready",
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
    for key in REQUIRED_RECEIPT_KEYS:
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
    if int(receipt.get("version") or 0) != CAPTURE_RECEIPT_VERSION:
        errors.append("capture-receipt-version-mismatch")
    return errors


def validate_capture_receipt_health(receipt: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    health = receipt.get("health") or {}
    for key in ("storybook_ready", "fonts_ready", "css_tokens_ready", "target_visible", "target_bounds_nonzero", "stylesheets_present"):
        if not health.get(key):
            errors.append("capture-health-failed:%s" % key)
    if health.get("console_errors"):
        errors.append("capture-health-console-errors")
    if health.get("failed_requests"):
        errors.append("capture-health-failed-requests")
    return errors


def validate_capture_receipt_binding(
    receipt: Mapping[str, Any],
    artifact_path: str,
    *,
    source_sha: str = "",
    role: str = "",
    capture: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Validate receipt against artifact bytes and expected capture metadata."""
    errors = list(validate_capture_receipt_shape(receipt))
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
    if source_sha and str(receipt.get("source_sha") or "") != source_sha:
        errors.append("capture-receipt-source-sha-mismatch")
    if role and str(receipt.get("role") or "") != role:
        errors.append("capture-receipt-role-mismatch")
    if capture:
        for key in ("story_id", "theme", "brand", "viewport", "state"):
            if str(receipt.get(key) or "") != str(capture.get(key) or ""):
                errors.append("capture-receipt-metadata-mismatch:%s" % key)
    return errors


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
