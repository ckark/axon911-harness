"""Plan conformance: does the implementation match what the plan declared?

The gap this closes is between plan approval and pre-commit. `plan-check` gates
the plan and `implementation-check` gates the commit; in between, plan drift was
only re-checked voluntarily, by the same context doing the work. Two failures
were therefore invisible:

* **undeclared** -- files changed that the plan never named. Silent scope creep.
* **unimplemented** -- files the plan named that were never touched. Work claimed
  but absent.

Both are mechanical, so neither needs a model to notice.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .ledger import append_record, current_state
from .constants import STATUS_BLOCKED, STATUS_PASS
from .plan_profile import active_profile, normalize_scope

IN_SCOPE = "in-scope"
UNDECLARED = "undeclared"
UNIMPLEMENTED = "unimplemented"

# Changes that are never scope creep: they are how the work gets verified and
# documented, and requiring a plan to enumerate them up front would be noise.
ALWAYS_IN_SCOPE = (
    "*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx",
    "*.stories.ts", "*.stories.tsx",
    "*.md", "*.mdx",
    "*.snap",
)


def normalize_scope(values: Sequence[str]) -> List[str]:
    """Split comma-joined scope arguments into individual globs."""
    from .plan_profile import normalize_scope as _normalize_scope

    return _normalize_scope(values)


def register_scope(
    root: str,
    worktree_id: str,
    fingerprint: str,
    plan_hash: str,
    scope: Sequence[str],
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Record the path globs a plan declared as its scope."""
    return append_record(
        {
            "kind": "plan_scope",
            "root": root,
            "worktree_id": worktree_id,
            "fingerprint": fingerprint,
            "plan_hash": plan_hash,
            "scope": [str(item).replace(os.sep, "/") for item in scope if str(item).strip()],
            "status": STATUS_PASS,
        },
        base=base,
    )


def declared_scope(state: Mapping[str, Any], root: str, worktree_id: str) -> Dict[str, Any]:
    found = (state.get("scopes") or {}).get("%s:%s" % (root, worktree_id)) or {}
    return {"scope": list(found.get("scope") or []), "plan_hash": str(found.get("plan_hash") or "")}


def _matches(path: str, patterns: Sequence[str]) -> bool:
    normalized = path.replace(os.sep, "/")
    for pattern in patterns:
        pattern = pattern.replace(os.sep, "/")
        if fnmatch.fnmatch(normalized, pattern):
            return True
        # A declared directory covers everything under it.
        if pattern.endswith("/") and normalized.startswith(pattern):
            return True
        if not pattern.endswith(("*", "/")) and normalized.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def classify(
    scope: Sequence[str], changed: Sequence[str]
) -> Dict[str, List[str]]:
    """Split changed paths against a declared scope.

    With no declared scope every path is `in-scope`: an unregistered plan means
    nothing was promised, which is not the same as a promise broken.
    """
    if not scope:
        return {IN_SCOPE: sorted(changed), UNDECLARED: [], UNIMPLEMENTED: []}

    in_scope, undeclared = [], []
    for path in sorted(changed):
        if _matches(path, scope) or _matches(os.path.basename(path), ALWAYS_IN_SCOPE):
            in_scope.append(path)
        else:
            undeclared.append(path)

    # A declared pattern that nothing matched is work the plan promised and the
    # implementation has not delivered.
    unimplemented = sorted(
        pattern
        for pattern in scope
        if not any(_matches(path, [pattern]) for path in changed)
    )
    return {IN_SCOPE: in_scope, UNDECLARED: undeclared, UNIMPLEMENTED: unimplemented}


def branch_changed_paths(
    root_path: str,
    base_oid: str,
) -> List[str]:
    """Full branch delta against `base_oid`, plus uncommitted worktree paths."""
    if not base_oid.strip():
        from .fingerprint import changed_paths

        return changed_paths(root_path)
    real = os.path.realpath(root_path)
    result = subprocess.run(
        ["git", "diff", "--name-only", "%s...HEAD" % base_oid.strip()],
        cwd=real,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    branch = [line.replace(os.sep, "/") for line in result.stdout.splitlines() if line.strip()]
    from .fingerprint import changed_paths

    worktree = changed_paths(real)
    merged = sorted(set(branch) | set(worktree))
    return merged


def evaluate_against_base(
    root: str,
    worktree_id: str,
    changed: Sequence[str],
    profile: Mapping[str, Any],
    root_path: Optional[str] = None,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Conformance against declared scope using the profile base when set."""
    scope = list(profile.get("scope") or [])
    plan_hash = str(profile.get("plan_hash") or "")
    base_oid = str(profile.get("base_oid") or "")
    if base_oid and root_path:
        effective_changed = branch_changed_paths(root_path, base_oid)
    else:
        effective_changed = list(changed)
    result = classify(scope, effective_changed)
    if not effective_changed:
        result[UNIMPLEMENTED] = []
    status = STATUS_BLOCKED if (result[UNDECLARED] or result[UNIMPLEMENTED]) else STATUS_PASS
    return {
        "status": status,
        "plan_hash": plan_hash,
        "base_oid": base_oid,
        "declared": scope,
        "changed_paths": sorted(effective_changed),
        **result,
    }


def evaluate(
    root: str,
    worktree_id: str,
    changed: Sequence[str],
    base: Optional[str] = None,
    root_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Conformance verdict for the current tree against the registered plan."""
    try:
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    profile = active_profile(state, root, worktree_id)
    return evaluate_against_base(root, worktree_id, changed, profile, root_path=root_path, base=base)


def summarize(result: Mapping[str, Any]) -> str:
    """One-line, actionable message for a hook to surface."""
    parts = []
    if result.get(UNDECLARED):
        shown = ", ".join(result[UNDECLARED][:3])
        extra = "" if len(result[UNDECLARED]) <= 3 else " (+%d more)" % (len(result[UNDECLARED]) - 3)
        parts.append(
            "outside the declared plan scope: %s%s -- widen the plan or say why" % (shown, extra)
        )
    if result.get(UNIMPLEMENTED):
        shown = ", ".join(result[UNIMPLEMENTED][:3])
        extra = "" if len(result[UNIMPLEMENTED]) <= 3 else " (+%d more)" % (len(result[UNIMPLEMENTED]) - 3)
        parts.append("declared but untouched: %s%s" % (shown, extra))
    return "harness plan conformance: " + "; ".join(parts) if parts else ""
