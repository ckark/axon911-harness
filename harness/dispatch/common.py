"""Root resolution, fingerprints, and obligation selection shared by dispatchers.

Both the Cursor and Claude Code dispatchers translate their host's event
envelope into these calls. Nothing here is tool-specific; a behavior change
here changes both hosts, which is the point.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from lib.constants import STATUS_PASS
from lib.fingerprint import changed_paths, snapshot
from lib.ledger import current_state
from lib.paths import PathError, configured_roots, identify_root
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
    """(root_id, root_path) for `path`, honoring linked worktrees.

    `root_path` is the *actual* directory `path` lives in, not necessarily the
    configured default -- a user routinely has several concurrent worktrees of
    the same repository open (one per branch or task), and `identify_root`
    recognizes any of them via their shared git history, not just the one that
    happens to sit at the hardcoded default path. Every caller that goes on to
    fingerprint, diff, or run a command against this root must use this path,
    not re-derive it from `roots()[root_id]`, or it silently operates on the
    wrong worktree.
    """
    return identify_root(path, roots())


def root_for(path: str) -> str:
    root_id, _root_path = resolve_root(path)
    return root_id


def resolve_cli_root(root_id: str) -> str:
    """The best root_path for `root_id` given the process's actual cwd.

    CLI subcommands take `--root <id>` rather than a live event payload, so
    they have no cwd hint unless they ask for one. Prefer the invocation's own
    cwd when it resolves to the same root_id -- honoring whichever worktree
    the command is actually being run from, e.g. when the attest-rewrite hook
    invokes this CLI with the agent's real working directory -- and fall back
    to the configured default otherwise (invoked from an unrelated directory,
    or with no better cwd available).
    """
    try:
        candidate_id, candidate_path = resolve_root(os.getcwd())
    except PathError:
        return roots()[root_id]
    if candidate_id == root_id and candidate_path:
        return candidate_path
    return roots()[root_id]


def snap(root_id: str, root_path: Optional[str] = None) -> Dict[str, str]:
    """Fingerprint `root_id` at `root_path`, binding the active plan hash when
    one is registered. `root_path` defaults to the configured path for
    callers that have no more specific worktree in hand."""
    path = root_path or roots()[root_id]
    first = snapshot(root_id, path, plan_hash="")
    try:
        registered = active_plan(current_state(), root_id, first["worktree_id"])
        plan_hash = registered.get("plan_hash") or ""
    except Exception:
        plan_hash = ""
    if not plan_hash:
        return first
    return snapshot(root_id, path, plan_hash=plan_hash)


def required_for(
    root_id: str, family: str, plan_hash: str, worktree_id: str, root_path: Optional[str] = None
) -> Tuple[Any, Dict[str, str]]:
    """Obligation IDs a mutation of `family` must satisfy, plus the active plan."""
    path = root_path or roots().get(root_id) or os.getcwd()
    try:
        paths = changed_paths(path)
    except Exception:
        paths = []
    try:
        registered = active_plan(current_state(), root_id, worktree_id)
    except Exception:
        registered = {"plan_hash": plan_hash, "tier": "T0"}
    tier = registered.get("tier") or "T0"
    return mutation_required_ids(root_id, paths, family, tier), registered


# Ownership moved to axon911-frontend post CORE-754 (AGENTS.md:121,
# docs/VENDORING.md). prepared911's copies are consumed, not authored, and are
# slated for removal. Advisory only: an in-flight branch may legitimately still
# be touching them.
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
    """Host-neutral mutation preflight verdict for an agent-shell command.

    Returns `permission` plus the fields each host needs to render its own
    denial envelope. Never executes the command.
    """
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

    required, registered = required_for(
        root_id,
        classified.get("family") or "",
        current.get("plan_hash") or "",
        current["worktree_id"],
        root_path,
    )
    gate = evaluate_gate(
        root_id,
        current["worktree_id"],
        current["fingerprint"],
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
    )
    return {
        "permission": gate["permission"],
        "root": root_id,
        "reason": classified.get("reason") or "",
        "message": gate.get("agent_message") or "",
        "status": gate.get("status") or STATUS_PASS,
    }
