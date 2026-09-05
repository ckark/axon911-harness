"""Canonical execution manifest: immutable plan definition with evidence states."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .git_subject import is_commit_oid
from .plan_profile import normalize_scope

EXECUTION_MANIFEST_SCHEMA_VERSION = 1
EVIDENCE_NONE = "none"
EVIDENCE_AFTER = "after"
EVIDENCE_BEFORE_AFTER = "before-after"
EVIDENCE_STATES = (EVIDENCE_NONE, EVIDENCE_AFTER, EVIDENCE_BEFORE_AFTER)


def _normalize(path: str) -> str:
    return path.replace(os.sep, "/").lstrip("./")


def load_execution_manifest(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("execution manifest must be a JSON object")
    return data


def canonical_execution_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a normalized manifest payload for checksum computation."""
    target_roots: Dict[str, Any] = {}
    raw_roots = manifest.get("target_roots") or {}
    if isinstance(raw_roots, dict):
        for root_id in sorted(raw_roots):
            entry = raw_roots[root_id]
            if not isinstance(entry, dict):
                continue
            evidence_states = entry.get("evidence_states") or {}
            target_roots[root_id] = {
                "base_oid": str(entry.get("base_oid") or "").strip(),
                "allowed_paths": normalize_scope(list(entry.get("allowed_paths") or [])),
                "required_paths": normalize_scope(list(entry.get("required_paths") or [])),
                "mirror_intent": str(entry.get("mirror_intent") or "").strip(),
                "evidence_states": {
                    _normalize(key): str(value).strip()
                    for key, value in sorted(evidence_states.items())
                    if str(key).strip() and str(value).strip()
                },
            }
    budgets = manifest.get("budgets") or {}
    return {
        "schema_version": int(manifest.get("schema_version") or 0),
        "plan_hash": str(manifest.get("plan_hash") or "").strip(),
        "tier": str(manifest.get("tier") or "T0").strip(),
        "target_roots": target_roots,
        "budgets": {
            "max_assistant_turns": int(budgets.get("max_assistant_turns") or 0),
            "max_context_bytes": int(budgets.get("max_context_bytes") or 0),
        },
    }


def execution_manifest_hash(manifest: Mapping[str, Any]) -> str:
    payload = canonical_execution_manifest(manifest)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_execution_manifest(
    manifest: Mapping[str, Any],
    *,
    repo_path: str = "",
) -> List[str]:
    """Return validation errors for an execution manifest file."""
    errors: List[str] = []
    schema_version = int(manifest.get("schema_version") or 0)
    if schema_version != EXECUTION_MANIFEST_SCHEMA_VERSION:
        errors.append("execution-manifest-schema-version-mismatch")
    plan_hash = str(manifest.get("plan_hash") or "").strip()
    if not plan_hash:
        errors.append("execution-manifest-missing-plan-hash")
    tier = str(manifest.get("tier") or "").strip()
    if tier not in ("T0", "T1", "T2"):
        errors.append("execution-manifest-invalid-tier")
    target_roots = manifest.get("target_roots")
    if not isinstance(target_roots, dict) or not target_roots:
        errors.append("execution-manifest-missing-target-roots")
        return errors
    for root_id, entry in target_roots.items():
        if not isinstance(entry, dict):
            errors.append("execution-manifest-root-%s-not-object" % root_id)
            continue
        if not normalize_scope(list(entry.get("allowed_paths") or [])):
            errors.append("execution-manifest-root-%s-missing-allowed-paths" % root_id)
        base_oid = str(entry.get("base_oid") or "").strip()
        if not base_oid:
            errors.append("execution-manifest-root-%s-missing-base-oid" % root_id)
        elif repo_path and not is_commit_oid(base_oid, repo_path):
            errors.append("execution-manifest-root-%s-invalid-base-oid" % root_id)
        evidence_states = entry.get("evidence_states")
        if not isinstance(evidence_states, dict) or not evidence_states:
            errors.append("execution-manifest-root-%s-missing-evidence-states" % root_id)
            continue
        for pattern, state in evidence_states.items():
            if str(state).strip() not in EVIDENCE_STATES:
                errors.append(
                    "execution-manifest-root-%s-invalid-evidence-state:%s"
                    % (root_id, _normalize(str(pattern)))
                )
    budgets = manifest.get("budgets") or {}
    if int(budgets.get("max_assistant_turns") or 0) <= 0:
        errors.append("execution-manifest-missing-budget-turns")
    if int(budgets.get("max_context_bytes") or 0) <= 0:
        errors.append("execution-manifest-missing-budget-context")
    return errors


def manifest_entry_for_root(manifest: Mapping[str, Any], root_id: str) -> Dict[str, Any]:
    """Return the target-root section for `root_id`."""
    target_roots = manifest.get("target_roots") or {}
    if not isinstance(target_roots, dict):
        return {}
    entry = target_roots.get(root_id) or {}
    return dict(entry) if isinstance(entry, dict) else {}


def profile_kwargs_from_manifest(
    manifest: Mapping[str, Any],
    root_id: str,
    *,
    evidence_manifest_pointer: str = "",
) -> Dict[str, Any]:
    """Map a manifest entry into `register_plan_profile` keyword arguments."""
    entry = manifest_entry_for_root(manifest, root_id)
    budgets = manifest.get("budgets") or {}
    evidence_states = {
        _normalize(key): str(value).strip()
        for key, value in (entry.get("evidence_states") or {}).items()
        if str(key).strip() and str(value).strip()
    }
    return {
        "plan_hash": str(manifest.get("plan_hash") or "").strip(),
        "tier": str(manifest.get("tier") or "T0").strip(),
        "scope": normalize_scope(list(entry.get("allowed_paths") or [])),
        "required_paths": normalize_scope(list(entry.get("required_paths") or [])),
        "target_roots": sorted((manifest.get("target_roots") or {}).keys()),
        "base_oid": str(entry.get("base_oid") or "").strip(),
        "mirror_intent": str(entry.get("mirror_intent") or "").strip(),
        "path_surfaces": {},
        "evidence_states": evidence_states,
        "evidence_manifest_pointer": evidence_manifest_pointer.strip(),
        "strict": True,
        "budget_max_turns": int(budgets.get("max_assistant_turns") or 0),
        "budget_max_context_bytes": int(budgets.get("max_context_bytes") or 0),
        "execution_manifest_hash": execution_manifest_hash(manifest),
    }
