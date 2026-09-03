"""Root resolution, fingerprints, and obligation selection for Cursor hooks."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from lib.constants import STATUS_PASS
from lib.fingerprint import changed_paths, snapshot
from lib.ledger import current_state
from lib.paths import PathError, configured_roots, identify_root
from lib.plan_profile import active_profile
from lib.receipts import active_plan, evaluate_gate, mutation_required_ids
from lib.schema import SchemaError, sanitized_message
from lib.shell_gate import classify, mutation_cwd

FALLBACK_ROOT_ID = "personal-harness"


def roots() -> Dict[str, str]:
    """Configured roots, degrading to a harness-only view when unresolvable."""
    try:
        return configured_roots()
    except PathError:
        return {FALLBACK_ROOT_ID: os.getcwd()}


def resolve_root(path: str) -> Tuple[str, str]:
    """(root_id, root_path) for `path`, honoring linked worktrees."""
    return identify_root(path, roots())


def root_for(path: str) -> str:
    root_id, _root_path = resolve_root(path)
    return root_id


def resolve_cli_root(root_id: str) -> str:
    """The best root_path for `root_id` given the process's actual cwd."""
    try:
        candidate_id, candidate_path = resolve_root(os.getcwd())
    except PathError:
        return roots()[root_id]
    if candidate_id == root_id and candidate_path:
        return candidate_path
    return roots()[root_id]


def snap(root_id: str, root_path: Optional[str] = None) -> Dict[str, str]:
    """Fingerprint `root_id` at `root_path`, binding active plan context."""
    path = root_path or roots()[root_id]
    first = snapshot(root_id, path, plan_hash="", plan_context_hash="")
    try:
        state = current_state()
        registered = active_plan(state, root_id, first["worktree_id"])
        profile = active_profile(state, root_id, first["worktree_id"])
        plan_hash = registered.get("plan_hash") or ""
        plan_context_hash = profile.get("plan_context_hash") or ""
    except Exception:
        plan_hash = ""
        plan_context_hash = ""
    if not plan_hash and not plan_context_hash:
        return first
    return snapshot(
        root_id,
        path,
        plan_hash=plan_hash,
        plan_context_hash=plan_context_hash,
    )


def required_for(
    root_id: str, family: str, plan_hash: str, worktree_id: str, root_path: Optional[str] = None
) -> Tuple[Any, Dict[str, str], list]:
    """Obligation IDs a mutation of `family` must satisfy, plus the active plan."""
    path = root_path or roots().get(root_id) or os.getcwd()
    try:
        state = current_state()
        profile = active_profile(state, root_id, worktree_id)
        registered = active_plan(state, root_id, worktree_id)
    except Exception:
        profile = {}
        registered = {"plan_hash": plan_hash, "tier": "T0", "plan_context_hash": ""}
    tier = registered.get("tier") or "T0"
    from lib.conformance import branch_changed_paths

    base_oid = str(profile.get("base_oid") or "")
    try:
        if base_oid:
            paths = branch_changed_paths(path, base_oid)
        else:
            paths = changed_paths(path)
    except Exception:
        paths = []
    return mutation_required_ids(root_id, paths, family, tier, profile=profile), registered, paths


PREPARED911_UI_PREFIX = "turbo/packages/ui-"


def wrong_root_note(root_id: str, file_path: str, root_path: Optional[str] = None) -> Optional[str]:
    """Advisory when a prepared911 `ui-*` file is edited instead of axon's copy."""
    if root_id != "prepared911" or not file_path:
        return None
    root_path = root_path or roots().get("prepared911")
    if not root_path:
        return None
    try:
        relative = os.path.relpath(os.path.realpath(file_path), root_path)
    except ValueError:
        return None
    relative = relative.replace(os.sep, "/")
    if not relative.startswith(PREPARED911_UI_PREFIX):
        return None
    package = relative[len("turbo/packages/") :].split("/", 1)[0]
    return (
        "harness: %s is owned by axon911-frontend post CORE-754 "
        "(AGENTS.md:121, docs/VENDORING.md); prepared911 consumes the published "
        "artifact and this copy is slated for removal. The upstream path is "
        "packages/%s/. Land the fix there unless this change is deliberately "
        "scoped to the prepared911 copy." % (relative, package)
    )


def shell_decision(command: str, cwd: str) -> Dict[str, Any]:
    """Host-neutral mutation preflight verdict for an agent-shell command."""
    classified = classify(command)
    if classified["permission"] == "allow":
        return {"permission": "allow", "root": "", "reason": classified["reason"]}

    try:
        root_id, root_path = resolve_root(mutation_cwd(command, cwd))
    except (PathError, SchemaError, KeyError):
        return {
            "permission": "deny",
            "root": "unknown",
            "reason": "root-identity",
            "message": sanitized_message("BLOCKED", "unknown", "root-identity"),
        }

    if classified["permission"] == "deny":
        return {
            "permission": "deny",
            "root": root_id,
            "reason": classified["reason"],
            "message": sanitized_message("BLOCKED", root_id, classified["reason"]),
        }

    try:
        current = snap(root_id, root_path)
    except Exception:
        return {
            "permission": "deny",
            "root": root_id,
            "reason": "fingerprint",
            "message": sanitized_message("BLOCKED", root_id, "fingerprint"),
        }

    required, registered, changed = required_for(
        root_id,
        classified.get("family") or "",
        current.get("plan_hash") or "",
        current["worktree_id"],
        root_path,
    )
    from lib.path_selector import select_obligations
    from lib.conformance import evaluate_against_base
    from lib.plan_profile import active_profile

    try:
        state = current_state()
        profile = active_profile(state, root_id, current["worktree_id"])
    except Exception:
        profile = {}
    selection = select_obligations(
        root_id,
        changed,
        profile,
        registered.get("tier") or "T0",
        family=classified.get("family") or "",
    )
    conformance = evaluate_against_base(
        root_id,
        current["worktree_id"],
        changed,
        profile,
        root_path=root_path,
    )
    gate = evaluate_gate(
        root_id,
        current["worktree_id"],
        current["fingerprint"],
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
        changed_paths=changed,
        root_path=root_path,
        selection=selection,
        conformance=conformance,
    )
    return {
        "permission": gate["permission"],
        "root": root_id,
        "reason": classified.get("reason") or "",
        "message": gate.get("agent_message") or "",
        "status": gate.get("status") or STATUS_PASS,
        "recovery": gate.get("recovery"),
    }
