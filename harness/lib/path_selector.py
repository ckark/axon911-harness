"""Shared path-by-path obligation selection for preview, verify, hooks, and ship."""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .conformance import ALWAYS_IN_SCOPE, classify
from .obligations import obligations_for, triggered_obligations
from .plan_profile import (
    MIRROR_CONSUMER_ONLY,
    SURFACE_EXISTING_VISIBLE,
    SURFACE_NEW_VISIBLE,
    SURFACE_NON_VISIBLE,
    active_profile,
)

PREPARED911_UI = re.compile(r"(^|/)turbo/packages/ui-[^/]+/")
AXON_UI = re.compile(r"(^|/)packages/ui-[^/]+/")
AXON_MF = re.compile(r"^(remotes/|packages/mfe-core/|apps/(responder|supervisor|switchboard)/)")
AXON_FLAGS = re.compile(r"(^|/)packages/feature-flags/")
PREPARED_DISPATCH = re.compile(r"(^|/)turbo/apps/dispatch/")
AXON_PACKAGES_UI = re.compile(r"(^|/)packages/ui-[^/]+/")
AXON_APPS_REMOTES = re.compile(r"^(apps/|remotes/)")


def _normalize(path: str) -> str:
    return path.replace(os.sep, "/").lstrip("./")


def _matches_scope(path: str, patterns: Sequence[str]) -> bool:
    normalized = _normalize(path)
    for pattern in patterns:
        pattern = pattern.replace(os.sep, "/")
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if pattern.endswith("/") and normalized.startswith(pattern):
            return True
        if not pattern.endswith(("*", "/")) and normalized.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _always_in_scope(path: str) -> bool:
    base = os.path.basename(path)
    for pattern in ALWAYS_IN_SCOPE:
        if fnmatch.fnmatch(base, pattern):
            return True
    return False


def _longest_surface_match(path: str, path_surfaces: Mapping[str, str]) -> Optional[str]:
    normalized = _normalize(path)
    best: Optional[Tuple[int, str]] = None
    for pattern, surface in path_surfaces.items():
        pat = _normalize(pattern)
        matched = False
        if fnmatch.fnmatch(normalized, pat):
            matched = True
        elif pat.endswith("/") and normalized.startswith(pat):
            matched = True
        elif not pat.endswith(("*", "/")) and normalized.startswith(pat.rstrip("/") + "/"):
            matched = True
        elif normalized == pat.rstrip("/"):
            matched = True
        if matched:
            rank = len(pat)
            if best is None or rank > best[0]:
                best = (rank, surface)
    return best[1] if best else None


def _infer_surface(root_id: str, path: str) -> str:
    normalized = _normalize(path)
    if PREPARED911_UI.search(normalized) or AXON_UI.search(normalized):
        return SURFACE_EXISTING_VISIBLE
    if PREPARED_DISPATCH.search(normalized):
        return SURFACE_EXISTING_VISIBLE
    if AXON_APPS_REMOTES.search(normalized):
        return SURFACE_EXISTING_VISIBLE
    return SURFACE_NON_VISIBLE


def _surface_flags(surface: str) -> Tuple[bool, bool]:
    if surface == SURFACE_NON_VISIBLE:
        return False, False
    if surface == SURFACE_NEW_VISIBLE:
        return True, False
    return True, True


def _suppress_for_mirror(root_id: str, obligation_id: str, mirror_intent: str) -> bool:
    if root_id != "prepared911" or mirror_intent != MIRROR_CONSUMER_ONLY:
        return False
    return obligation_id.endswith(".docs-registry") or obligation_id.endswith(".docs-page")


def _triggered_for_path(root_id: str, path: str) -> List[Dict[str, str]]:
    return triggered_obligations(root_id, [path])


def _migration_manifest_path(profile: Mapping[str, Any], root_id: str) -> str:
    pointer = str(
        profile.get("evidence_manifest_pointer")
        or profile.get("migration_manifest_pointer")
        or os.environ.get("HARNESS_MIGRATION_MANIFEST")
        or ""
    )
    if pointer and os.path.isfile(pointer):
        return pointer
    return ""


def _longest_evidence_state(path: str, evidence_states: Mapping[str, str]) -> Optional[str]:
    normalized = _normalize(path)
    best: Optional[Tuple[int, str]] = None
    for pattern, state in evidence_states.items():
        pat = _normalize(pattern)
        matched = _matches_scope(normalized, [pat])
        if matched:
            rank = len(pat)
            if best is None or rank > best[0]:
                best = (rank, str(state).strip())
    return best[1] if best else None


def _evidence_flags_from_states(
    changed_paths: Sequence[str],
    evidence_states: Mapping[str, str],
) -> Tuple[bool, bool, bool]:
    """Return (needs_any_evidence, needs_before_after, all_none)."""
    if not evidence_states:
        return False, False, False
    states: List[str] = []
    for path in changed_paths:
        state = _longest_evidence_state(path, evidence_states)
        if state:
            states.append(state)
    if not states:
        return False, False, True
    from .execution_manifest import EVIDENCE_AFTER, EVIDENCE_BEFORE_AFTER, EVIDENCE_NONE

    if all(item == EVIDENCE_NONE for item in states):
        return False, False, True
    needs_before_after = any(item == EVIDENCE_BEFORE_AFTER for item in states)
    needs_any = any(item in (EVIDENCE_AFTER, EVIDENCE_BEFORE_AFTER) for item in states)
    return needs_any, needs_before_after, False


def select_obligations(
    root_id: str,
    changed_paths: Sequence[str],
    profile: Mapping[str, Any],
    tier: str,
    family: str = "",
    include_review: bool = True,
) -> Dict[str, Any]:
    """Select obligations and classification errors for changed paths."""
    from .receipts import review_required

    scope = list(profile.get("scope") or [])
    strict = bool(profile.get("strict"))
    evidence_states = dict(profile.get("evidence_states") or {})
    path_surfaces = dict(profile.get("path_surfaces") or {})
    mirror_intent = str(profile.get("mirror_intent") or "")
    profiled = bool(profile.get("profiled"))

    classification_errors: List[str] = []
    path_surfaces_resolved: Dict[str, str] = {}
    required: Set[str] = set()
    triggered: Set[str] = set()
    user_visible = False
    existing_surface = False

    normalized_paths = sorted({_normalize(path) for path in changed_paths if str(path).strip()})

    if scope:
        conf = classify(
            scope,
            normalized_paths,
            required_paths=list(profile.get("required_paths") or []),
            strict=strict,
        )
        for path in conf.get("undeclared") or []:
            if not strict and _always_in_scope(path):
                continue
            classification_errors.append("undeclared path outside plan scope: %s" % path)

    overlapping: Dict[str, Set[str]] = {}
    for path in normalized_paths:
        matches = []
        for pattern in path_surfaces:
            if _matches_scope(path, [pattern]):
                matches.append(pattern)
        if len(matches) > 1:
            overlapping[path] = set(matches)

    for path, patterns in overlapping.items():
        surfaces = {path_surfaces[pattern] for pattern in patterns}
        if len(surfaces) > 1:
            classification_errors.append(
                "overlapping path classifications for %s: %s" % (path, ", ".join(sorted(patterns)))
            )

    for path in normalized_paths:
        declared = _longest_surface_match(path, path_surfaces)
        if declared:
            surface = declared
        elif profiled and evidence_states:
            evidence_state = _longest_evidence_state(path, evidence_states)
            if evidence_state == "none":
                surface = SURFACE_NON_VISIBLE
            elif evidence_state == "after":
                surface = SURFACE_NEW_VISIBLE
            elif evidence_state == "before-after":
                surface = SURFACE_EXISTING_VISIBLE
            else:
                surface = _infer_surface(root_id, path)
        elif profiled and PREPARED911_UI.search(path):
            classification_errors.append("missing surface classification for prepared911 ui path: %s" % path)
            surface = _infer_surface(root_id, path)
        elif profiled and AXON_UI.search(path):
            classification_errors.append("missing surface classification for axon ui path: %s" % path)
            surface = _infer_surface(root_id, path)
        else:
            surface = _infer_surface(root_id, path)
        path_surfaces_resolved[path] = surface
        uv, es = _surface_flags(surface)
        user_visible = user_visible or uv
        existing_surface = existing_surface or es

        for obligation in _triggered_for_path(root_id, path):
            oid = obligation["id"]
            if _suppress_for_mirror(root_id, oid, mirror_intent):
                continue
            triggered.add(oid)
            required.add(oid)

    if user_visible:
        rendered = "%s.rendered-evidence" % root_id
        if obligations_for(root_id) and rendered not in required:
            if not any(item.endswith(".rendered-evidence") for item in required):
                required.add(rendered)
    if evidence_states:
        needs_any, needs_before_after, all_none = _evidence_flags_from_states(
            normalized_paths,
            evidence_states,
        )
        required = {item for item in required if not item.endswith(".rendered-evidence")}
        required.discard("%s.rendered-evidence.before-after" % root_id)
        if all_none:
            user_visible = False
        elif needs_any:
            user_visible = True
            rendered = "%s.rendered-evidence" % root_id
            if obligations_for(root_id):
                required.add(rendered)
            if needs_before_after:
                required.add("%s.rendered-evidence.before-after" % root_id)
                existing_surface = True
    elif not user_visible:
        required = {item for item in required if not item.endswith(".rendered-evidence")}
    if not user_visible and not evidence_states:
        required = {item for item in required if not item.endswith(".rendered-evidence")}
    if user_visible and existing_surface and not evidence_states:
        required.add("%s.rendered-evidence.before-after" % root_id)

    migration_manifest_path = _migration_manifest_path(profile, root_id)
    if migration_manifest_path:
        try:
            from .migration_evidence import load_manifest, migration_obligation_ids

            manifest = load_manifest(migration_manifest_path)
            required.update(migration_obligation_ids(root_id, manifest))
        except (OSError, ValueError):
            classification_errors.append("invalid migration manifest: %s" % migration_manifest_path)

    if family == "git-commit":
        required = {
            item
            for item in required
            if ".migration-evidence." not in item
            and not item.endswith(".rendered-evidence")
            and not item.endswith(".rendered-evidence.before-after")
        }

    if include_review and review_required(tier):
        required.add("review.%s" % tier)
    if family == "git-push":
        required.add("push.oid")
    if family == "gt-submit":
        required.add("stack-oid-set")

    return {
        "required_obligation_ids": sorted(required),
        "triggered_obligation_ids": sorted(triggered),
        "path_surfaces": path_surfaces_resolved,
        "user_visible": user_visible,
        "existing_surface": existing_surface,
        "classification_errors": classification_errors,
        "mirror_intent": mirror_intent,
        "profiled": profiled,
    }


def preview_obligations(
    root_id: str,
    changed_paths: Sequence[str],
    worktree_id: str,
    family: str = "",
    root_path: Optional[str] = None,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Read-only obligation preview with conformance when a profile exists."""
    from .conformance import evaluate_against_base

    try:
        from .ledger import current_state
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    profile = active_profile(state, root_id, worktree_id)
    selection = select_obligations(
        root_id,
        changed_paths,
        profile,
        profile.get("tier") or "T0",
        family=family,
    )
    conformance = evaluate_against_base(
        root_id,
        worktree_id,
        changed_paths,
        profile,
        root_path=root_path,
        base=base,
    )
    blocked = bool(selection["classification_errors"]) or conformance.get("status") != "PASS"
    return {
        "root": root_id,
        "worktree_id": worktree_id,
        "plan_hash": profile.get("plan_hash") or "",
        "plan_context_hash": profile.get("plan_context_hash") or "",
        "tier": profile.get("tier") or "T0",
        "changed_paths": sorted(changed_paths),
        "selection": selection,
        "conformance": conformance,
        "blocked": blocked,
    }
