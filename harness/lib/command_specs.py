"""Obligation command specifications: attestation must run the real check."""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .obligations import obligations_for

GENERATOR_SUFFIXES = (
    "ui-allowlist",
    "docs-registry",
    "flag-manifest",
    "mf-types",
)

TYPECHECK_MARKERS = (
    "typecheck",
    "tsc",
    "mf:types:check",
)

EVIDENCE_MARKERS = (
    "storybook",
    "playwright",
    "test:storybook",
)

PUSH_MARKERS = ("push", "git push")


def obligation_spec(obligation_id: str) -> Dict[str, str]:
    root = obligation_id.split(".", 1)[0]
    for item in obligations_for(root):
        if item["id"] == obligation_id:
            return dict(item)
    if obligation_id == "push.oid":
        return {"id": obligation_id, "kind": "push_attestation", "check": "git push"}
    if obligation_id == "stack-oid-set":
        return {"id": obligation_id, "kind": "stack_attestation", "check": "gt submit"}
    if obligation_id.startswith("review."):
        return {"id": obligation_id, "kind": "review", "check": ""}
    if obligation_id.endswith(".rendered-evidence.before-after"):
        return {"id": obligation_id, "kind": "rendered_evidence", "check": "evidence"}
    if obligation_id.endswith(".rendered-evidence"):
        return {"id": obligation_id, "kind": "rendered_evidence", "check": "evidence"}
    if ".docs-page" in obligation_id:
        return {"id": obligation_id, "kind": "docs_page", "check": ""}

    return {"id": obligation_id, "kind": "unknown", "check": ""}


def _tokens(command: Sequence[str]) -> str:
    return " ".join(str(part) for part in command).lower()


def validate_attestation_command(
    obligation_id: str,
    command: Sequence[str],
) -> Tuple[bool, str]:
    """Return whether `command` is an acceptable attestation for `obligation_id`."""
    if not command:
        return False, "empty-command"
    text = _tokens(command)
    if text in ("true", ":", "false") or text.startswith("echo "):
        return False, "vacuous-command"
    spec = obligation_spec(obligation_id)
    expected_check = str(spec.get("check") or "").lower()
    expected_regenerate = str(spec.get("regenerate") or "").lower()
    kind = str(spec.get("kind") or "")

    if obligation_id == "push.oid":
        if list(command) == ["git", "rev-parse", "HEAD"]:
            return True, "ok"
        if list(command) == ["git", "rev-parse", "head"]:
            return True, "ok"
        return False, "push.oid-requires-git-rev-parse-head"

    if obligation_id == "stack-oid-set":
        joined = _tokens(command)
        if joined.startswith("gt submit") or joined == "gt submit":
            return True, "ok"
        return False, "stack-oid-set-requires-gt-submit"

    if obligation_id.startswith("review."):
        return False, "review-not-attestable"

    if kind == "docs_page":
        return False, "docs-page-not-attestable"

    if obligation_id.endswith(".rendered-evidence") or obligation_id.endswith(".before-after"):
        if any(marker in text for marker in EVIDENCE_MARKERS):
            return True, "ok"
        return False, "rendered-evidence-requires-storybook-or-playwright"

    if ".migration-evidence." in obligation_id:
        if "migration-evidence" in text or any(marker in text for marker in EVIDENCE_MARKERS):
            return True, "ok"
        return False, "migration-evidence-requires-storybook-or-playwright"

    if kind == "docs_registry" and expected_regenerate:
        if expected_regenerate not in text and expected_check not in text:
            return False, "docs-registry-requires-generator"
        return True, "ok"

    if any(obligation_id.endswith(suffix) for suffix in GENERATOR_SUFFIXES):
        if expected_regenerate and expected_regenerate in text:
            return True, "ok"
        if expected_check and expected_check in text:
            return True, "ok"
        if expected_regenerate and all(part in command for part in expected_regenerate.split()):
            return True, "ok"
        return False, "generator-requires-direct-check"

    if expected_check:
        if expected_check in text:
            return True, "ok"
        if any(marker in text for marker in TYPECHECK_MARKERS) and any(
            marker in expected_check for marker in TYPECHECK_MARKERS
        ):
            return True, "ok"
        return False, "check-command-mismatch"

    return True, "ok"
