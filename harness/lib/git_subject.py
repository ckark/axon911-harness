"""Git tree and commit helpers for evidence provenance."""

from __future__ import annotations

import os
import subprocess
from typing import Optional


def is_commit_oid(value: str, root_path: str = "") -> bool:
    """Return True when `value` resolves to a Git commit object."""
    cleaned = value.strip()
    if len(cleaned) < 7:
        return False
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "timeout": 10,
    }
    if root_path.strip():
        kwargs["cwd"] = os.path.realpath(root_path)
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", "%s^{commit}" % cleaned],
            **kwargs,
        )
        return result.returncode == 0
    except Exception:
        return False


def worktree_is_clean(root_path: str) -> bool:
    """Return True when the worktree has no unstaged or uncommitted changes."""
    real = os.path.realpath(root_path)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=real,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and not result.stdout.strip()
    except Exception:
        return False


def staged_tree_oid(root_path: str) -> str:
    """Return the tree OID for the index (staged content)."""
    real = os.path.realpath(root_path)
    try:
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=real,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def tree_oid_at_commit(root_path: str, commit_oid: str) -> str:
    """Return the tree OID at a commit."""
    real = os.path.realpath(root_path)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "%s^{tree}" % commit_oid.strip()],
            cwd=real,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def head_oid(root_path: str) -> str:
    """Return HEAD commit OID for a repository."""
    real = os.path.realpath(root_path)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=real,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def subject_tree_oid(root_path: str, *, staged: bool = False, commit_oid: str = "") -> str:
    """Resolve the content tree used as an evidence subject."""
    if staged:
        return staged_tree_oid(root_path)
    if commit_oid.strip():
        return tree_oid_at_commit(root_path, commit_oid)
    return tree_oid_at_commit(root_path, head_oid(root_path))
