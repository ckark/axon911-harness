"""Validate specialist review reports before issuing review receipts."""

from __future__ import annotations

import hashlib
import os
import re
from typing import List, Mapping, Optional, Sequence, Tuple

from .constants import STATUS_BLOCKED, STATUS_PASS
from .jev_policy import VERDICT_BLOCK, VERDICT_PASS

VERDICT_RE = re.compile(
    r"(?im)^(?:##\s*verdict|\*\*verdict\*\*)\s*\n+\s*([A-Z][A-Z \-]+)\s*$"
)
FINDING_ID_RE = re.compile(r"\b([A-Z]{2,}(?:-[A-Z0-9]+)*-\d+)\b")
ALLOWED_CRITICS = frozenset(
    {
        "design-system-critic",
        "security-critic",
        "architecture-critic",
        "docs-drift-critic",
    }
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


def _parse_verdict(text: str) -> str:
    match = VERDICT_RE.search(text)
    if match:
        return " ".join(match.group(1).strip().upper().split())
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper() in VERDICT_PASS | VERDICT_BLOCK:
            return stripped.upper()
    return ""


def _critic_from_filename(path: str) -> str:
    base = os.path.basename(path)
    if base.endswith(".md"):
        base = base[:-3]
    if "-" not in base:
        return base
    return base.rsplit("-", 1)[0]


def validate_review_report(
    report_path: str,
    *,
    expected_critic_ids: Sequence[str],
    fingerprint: str,
    plan_hash: str,
    tier: str,
) -> Tuple[List[str], str, str]:
    """Return validation errors, normalized verdict, and report hash."""
    errors: List[str] = []
    if not report_path or not os.path.isfile(report_path):
        return ["missing-review-report"], "", ""
    report_hash = _hash_file(report_path)
    try:
        with open(report_path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        return ["review-report-unreadable:%s" % exc], "", report_hash
    if not text.strip():
        errors.append("review-report-empty")
    verdict = _parse_verdict(text)
    if not verdict:
        errors.append("review-report-missing-verdict")
    elif verdict not in VERDICT_PASS | VERDICT_BLOCK:
        errors.append("review-report-invalid-verdict:%s" % verdict)
    file_critic = _critic_from_filename(report_path)
    expected = [critic for critic in expected_critic_ids if critic]
    if not expected:
        errors.append("review-report-missing-critic")
    elif file_critic not in expected:
        errors.append("review-report-critic-mismatch:%s" % file_critic)
    for critic in expected:
        if critic not in ALLOWED_CRITICS:
            errors.append("review-report-unknown-critic:%s" % critic)
    basename = os.path.basename(report_path)
    if fingerprint and fingerprint[:12] not in basename and fingerprint not in text:
        errors.append("review-report-fingerprint-unbound")
    if plan_hash and plan_hash not in text and plan_hash not in basename:
        if plan_hash != "plan":
            errors.append("review-report-plan-hash-unbound")
    if tier and tier not in text:
        errors.append("review-report-tier-unbound")
    finding_ids = sorted(set(FINDING_ID_RE.findall(text)))
    if verdict in VERDICT_BLOCK and not finding_ids:
        errors.append("review-report-blocking-without-findings")
    return errors, verdict, report_hash


def receipt_status_for_verdict(verdict: str) -> str:
    if verdict in VERDICT_PASS:
        return STATUS_PASS
    if verdict in VERDICT_BLOCK:
        return STATUS_BLOCKED
    return STATUS_BLOCKED


def summarize_report(report_path: str, max_chars: int = 4000) -> str:
    if not os.path.isfile(report_path):
        return ""
    with open(report_path, encoding="utf-8") as handle:
        text = handle.read()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
