"""Atomic plan profile: scope, base, mirror intent, and per-path surface class."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .ledger import append_record, current_state
from .constants import STATUS_PASS

MIRROR_CONSUMER_ONLY = "consumer-only"
MIRROR_AUTHORING = "authoring"
MIRROR_INTENTS = (MIRROR_CONSUMER_ONLY, MIRROR_AUTHORING)

SURFACE_NON_VISIBLE = "non-visible"
SURFACE_NEW_VISIBLE = "new-visible"
SURFACE_EXISTING_VISIBLE = "existing-visible"
SURFACE_CLASSES = (SURFACE_NON_VISIBLE, SURFACE_NEW_VISIBLE, SURFACE_EXISTING_VISIBLE)


def normalize_scope(values: Sequence[str]) -> List[str]:
    """Split comma-joined scope arguments into individual globs."""
    patterns: List[str] = []
    for value in values:
        for part in value.split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in patterns:
                patterns.append(cleaned)
    return patterns


def _normalize_relpath(path: str) -> str:
    return path.replace(os.sep, "/").lstrip("./")


def validate_surface(value: str) -> Optional[str]:
    cleaned = value.strip()
    if cleaned in SURFACE_CLASSES:
        return cleaned
    return None


def validate_mirror_intent(value: str) -> Optional[str]:
    cleaned = value.strip()
    if cleaned in MIRROR_INTENTS:
        return cleaned
    return None


def plan_context_payload(
    plan_hash: str,
    scope: Sequence[str],
    base_oid: str,
    mirror_intent: str,
    path_surfaces: Mapping[str, str],
    *,
    required_paths: Sequence[str] = (),
    target_roots: Sequence[str] = (),
    evidence_manifest_pointer: str = "",
    strict: bool = False,
    budget_max_turns: int = 0,
    budget_max_context_bytes: int = 0,
) -> Dict[str, Any]:
    """Canonical payload hashed into fingerprints and receipt binding."""
    surfaces = {
        _normalize_relpath(key): value
        for key, value in sorted(path_surfaces.items())
        if str(key).strip() and str(value).strip()
    }
    return {
        "plan_hash": plan_hash,
        "scope": normalize_scope(list(scope)),
        "required_paths": normalize_scope(list(required_paths)),
        "target_roots": normalize_scope(list(target_roots)),
        "base_oid": base_oid.strip(),
        "mirror_intent": mirror_intent.strip(),
        "path_surfaces": surfaces,
        "evidence_manifest_pointer": evidence_manifest_pointer.strip(),
        "strict": bool(strict),
        "budget_max_turns": int(budget_max_turns or 0),
        "budget_max_context_bytes": int(budget_max_context_bytes or 0),
    }


def plan_context_hash(
    plan_hash: str,
    scope: Sequence[str],
    base_oid: str,
    mirror_intent: str,
    path_surfaces: Mapping[str, str],
    **kwargs: Any,
) -> str:
    payload = plan_context_payload(
        plan_hash,
        scope,
        base_oid,
        mirror_intent,
        path_surfaces,
        **kwargs,
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_strict_profile(
    *,
    scope: Sequence[str],
    base_oid: str,
    tier: str,
    strict: bool,
    evidence_manifest_pointer: str = "",
) -> List[str]:
    """Return plan-contract defects for a strict execution manifest."""
    errors: List[str] = []
    if not strict:
        return errors
    if not normalize_scope(list(scope)):
        errors.append("strict-profile-missing-allowed-paths")
    if not base_oid.strip():
        errors.append("strict-profile-missing-base-oid")
    if tier not in ("T0", "T1", "T2"):
        errors.append("strict-profile-invalid-tier")
    if not evidence_manifest_pointer.strip():
        errors.append("strict-profile-missing-evidence-manifest")
    return errors


def register_plan_profile(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    tier: str,
    scope: Sequence[str],
    base_oid: str,
    mirror_intent: str,
    path_surfaces: Mapping[str, str],
    session_id: str = "",
    *,
    required_paths: Sequence[str] = (),
    target_roots: Sequence[str] = (),
    evidence_manifest_pointer: str = "",
    strict: bool = False,
    budget_max_turns: int = 0,
    budget_max_context_bytes: int = 0,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist one atomic plan profile and clear stale scope records."""
    profile_errors = validate_strict_profile(
        scope=scope,
        base_oid=base_oid,
        tier=tier,
        strict=strict,
        evidence_manifest_pointer=evidence_manifest_pointer,
    )
    if profile_errors:
        raise ValueError("; ".join(profile_errors))
    context = plan_context_hash(
        plan_hash,
        scope,
        base_oid,
        mirror_intent,
        path_surfaces,
        required_paths=required_paths,
        target_roots=target_roots,
        evidence_manifest_pointer=evidence_manifest_pointer,
        strict=strict,
        budget_max_turns=budget_max_turns,
        budget_max_context_bytes=budget_max_context_bytes,
    )
    return append_record(
        {
            "kind": "plan_profile",
            "root": root,
            "worktree_id": worktree_id,
            "session_id": session_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "tier": tier,
            "scope": normalize_scope(list(scope)),
            "required_paths": normalize_scope(list(required_paths)),
            "target_roots": normalize_scope(list(target_roots)),
            "base_oid": base_oid.strip(),
            "mirror_intent": mirror_intent.strip(),
            "path_surfaces": {
                _normalize_relpath(key): value
                for key, value in path_surfaces.items()
                if str(key).strip() and str(value).strip()
            },
            "evidence_manifest_pointer": evidence_manifest_pointer.strip(),
            "strict": bool(strict),
            "budget_max_turns": int(budget_max_turns or 0),
            "budget_max_context_bytes": int(budget_max_context_bytes or 0),
            "plan_context_hash": context,
            "obligation_id": "plan",
            "status": STATUS_PASS,
        },
        base=base,
    )


def active_profile(state: Mapping[str, Any], root: str, worktree_id: str) -> Dict[str, Any]:
    """Return the registered atomic profile or legacy plan/scopes only."""
    profiles = state.get("profiles") or {}
    found = profiles.get("%s:%s" % (root, worktree_id)) or {}
    plans = state.get("plans") or {}
    plan_entry = plans.get("%s:%s" % (root, worktree_id)) or {}
    scopes = state.get("scopes") or {}
    scope_entry = scopes.get("%s:%s" % (root, worktree_id)) or {}
    plan_hash = str(found.get("plan_hash") or plan_entry.get("plan_hash") or "")
    tier = str(found.get("tier") or plan_entry.get("tier") or "T0")
    scope = list(found.get("scope") or scope_entry.get("scope") or [])
    required_paths = list(found.get("required_paths") or [])
    target_roots = list(found.get("target_roots") or [])
    base_oid = str(found.get("base_oid") or "")
    mirror_intent = str(found.get("mirror_intent") or "")
    path_surfaces = dict(found.get("path_surfaces") or {})
    evidence_manifest_pointer = str(found.get("evidence_manifest_pointer") or "")
    strict = bool(found.get("strict"))
    budget_max_turns = int(found.get("budget_max_turns") or 0)
    budget_max_context_bytes = int(found.get("budget_max_context_bytes") or 0)
    context = str(found.get("plan_context_hash") or "")
    if plan_hash and not context:
        context = plan_context_hash(
            plan_hash,
            scope,
            base_oid,
            mirror_intent,
            path_surfaces,
            required_paths=required_paths,
            target_roots=target_roots,
            evidence_manifest_pointer=evidence_manifest_pointer,
            strict=strict,
            budget_max_turns=budget_max_turns,
            budget_max_context_bytes=budget_max_context_bytes,
        )
    migration_manifests = state.get("migration_manifests") or {}
    manifest_entry = migration_manifests.get("%s:%s" % (root, worktree_id)) or {}
    if not evidence_manifest_pointer:
        evidence_manifest_pointer = str(manifest_entry.get("pointer") or "")
    return {
        "plan_hash": plan_hash,
        "tier": tier,
        "scope": scope,
        "required_paths": required_paths,
        "target_roots": target_roots,
        "base_oid": base_oid,
        "mirror_intent": mirror_intent,
        "path_surfaces": path_surfaces,
        "evidence_manifest_pointer": evidence_manifest_pointer,
        "migration_manifest_pointer": str(manifest_entry.get("pointer") or ""),
        "strict": strict,
        "budget_max_turns": budget_max_turns,
        "budget_max_context_bytes": budget_max_context_bytes,
        "plan_context_hash": context,
        "profiled": bool(found),
    }


def profile_from_state(
    root: str,
    worktree_id: str,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    return active_profile(state, root, worktree_id)


def parse_path_surface_args(values: Sequence[str]) -> Tuple[Dict[str, str], List[str]]:
    """Parse repeated `--path-surface PATH=SURFACE` declarations."""
    surfaces: Dict[str, str] = {}
    errors: List[str] = []
    for raw in values:
        if "=" not in raw:
            errors.append("invalid path-surface (expected PATH=SURFACE): %s" % raw)
            continue
        path, surface = raw.split("=", 1)
        path = _normalize_relpath(path.strip())
        surface_clean = validate_surface(surface)
        if not path:
            errors.append("empty path in path-surface: %s" % raw)
            continue
        if not surface_clean:
            errors.append(
                "invalid surface for %s (expected one of %s)"
                % (path, ", ".join(SURFACE_CLASSES))
            )
            continue
        if path in surfaces and surfaces[path] != surface_clean:
            errors.append("conflicting surface for %s" % path)
            continue
        surfaces[path] = surface_clean
    return surfaces, errors
