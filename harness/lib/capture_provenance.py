"""Git-derived capture provenance with fail-closed OID validation."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Mapping, Optional

from .git_subject import head_oid, is_commit_oid, subject_tree_oid, worktree_is_clean


class ProvenanceError(ValueError):
    """Raised when capture provenance cannot be derived or validated."""


def checkout_commit(root_path: str, commit_oid: str) -> None:
    """Switch a normal checkout to an exact commit after verifying cleanliness."""
    real = os.path.realpath(root_path)
    if not worktree_is_clean(real):
        raise ProvenanceError("checkout blocked: worktree is not clean")
    if not is_commit_oid(commit_oid, real):
        raise ProvenanceError("checkout blocked: invalid commit oid")
    result = subprocess.run(
        ["git", "checkout", "--detach", commit_oid],
        cwd=real,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise ProvenanceError(result.stderr.strip() or result.stdout.strip() or "git checkout failed")
    resolved = head_oid(real)
    if resolved != commit_oid:
        raise ProvenanceError("checkout did not resolve to expected head")


def resolve_capture_provenance(
    root_path: str,
    *,
    expected_commit: str = "",
    role: str = "",
    staged: bool = False,
) -> Dict[str, Any]:
    """Derive commit, tree, and cleanliness for a capture receipt."""
    real = os.path.realpath(root_path)
    commit = expected_commit.strip() or head_oid(real)
    if not commit:
        raise ProvenanceError("missing commit oid")
    if not is_commit_oid(commit, real):
        raise ProvenanceError("unresolved commit oid: %s" % commit)
    actual_head = head_oid(real)
    if actual_head != commit:
        raise ProvenanceError("head mismatch: expected %s got %s" % (commit, actual_head))
    tree = subject_tree_oid(real, staged=staged, commit_oid=commit)
    if not tree:
        raise ProvenanceError("missing tree oid for %s" % commit)
    clean = worktree_is_clean(real)
    if role == "after" and not clean:
        raise ProvenanceError("after capture requires clean worktree")
    return {
        "source_sha": commit,
        "source_tree": tree,
        "source_clean": clean,
        "repo_path": real,
    }


def validate_expected_binding(
    provenance: Mapping[str, Any],
    *,
    expected_commit: str,
    expected_tree: str = "",
) -> List[str]:
    """Return errors when provenance does not match execution-pinned refs."""
    errors: List[str] = []
    commit = str(provenance.get("source_sha") or "")
    tree = str(provenance.get("source_tree") or "")
    if expected_commit and commit != expected_commit:
        errors.append("provenance-commit-mismatch")
    if expected_tree and tree != expected_tree:
        errors.append("provenance-tree-mismatch")
    if provenance.get("source_clean") is False:
        errors.append("provenance-dirty-worktree")
    return errors


def git_diff_paths(root_path: str, base_oid: str, head_oid_value: str) -> List[str]:
    """Return changed paths between two commits."""
    real = os.path.realpath(root_path)
    result = subprocess.run(
        ["git", "diff", "--name-only", "%s..%s" % (base_oid, head_oid_value)],
        cwd=real,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise ProvenanceError(result.stderr.strip() or "git diff failed")
    return sorted(path.strip() for path in result.stdout.splitlines() if path.strip())
