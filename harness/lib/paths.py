"""Path containment and runtime directory helpers."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from typing import Dict, Mapping, Optional, Tuple

from .constants import ROOT_IDS

DEFAULT_ROOT_PATHS = {
    "axon911-frontend": "/Users/ckark/Documents/GitHub/axon911-frontend",
    "prepared911": "/Users/ckark/Documents/GitHub/prepared911",
    "vault-core-ux": "/Users/ckark/Documents/GitHub/vault-core-ux",
}

# Override per-root paths without a plugin host. See docs/cursor-onboarding.md.
ROOT_ENV_KEYS = {
    "axon911-frontend": "HARNESS_AXON911_ROOT",
    "prepared911": "HARNESS_PREPARED911_ROOT",
    "vault-core-ux": "HARNESS_VAULT_ROOT",
}


class PathError(ValueError):
    """Raised when a path escapes the configured roots."""


def _is_harness_root(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "docs", "review-contract.md"))


def harness_root(start: Optional[str] = None) -> str:
    """Locate the harness checkout without depending on the working directory."""
    if start is not None:
        current = os.path.realpath(start)
        while True:
            if _is_harness_root(current):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                raise PathError("personal-harness root not found")
            current = parent

    override = os.environ.get("HARNESS_ROOT")
    if override and _is_harness_root(os.path.realpath(override)):
        return os.path.realpath(override)

    # <harness_root>/harness/lib/paths.py -> up three.
    anchored = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    if _is_harness_root(anchored):
        return anchored

    current = os.path.realpath(os.getcwd())
    while True:
        if _is_harness_root(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise PathError("personal-harness root not found")
        current = parent


def runtime_dir(root: Optional[str] = None) -> str:
    override = os.environ.get("HARNESS_RUNTIME_DIR")
    if override and root is None:
        path = override
    else:
        path = os.path.join(root or harness_root(), ".harness", "runtime")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def configured_roots(harness: Optional[str] = None) -> Dict[str, str]:
    """Resolve every root path.

    Precedence per root: HARNESS_ROOTS_JSON, then HARNESS_*_ROOT env vars,
    then the on-disk default. `personal-harness` always resolves to the checkout
    the running code belongs to.
    """
    base = harness_root(harness)
    roots = {"personal-harness": base}

    overrides: Dict[str, str] = {}
    raw = os.environ.get("HARNESS_ROOTS_JSON")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                overrides = {
                    str(key): str(value) for key, value in parsed.items() if isinstance(value, str)
                }
        except (ValueError, TypeError):
            overrides = {}

    for root_id, default in DEFAULT_ROOT_PATHS.items():
        roots[root_id] = (
            overrides.get(root_id)
            or os.environ.get(ROOT_ENV_KEYS[root_id], "")
            or default
        )
    return {key: os.path.realpath(value) for key, value in roots.items()}


# Every worktree of one repository shares this single common .git directory,
# even though each has its own toplevel path, HEAD, and index. That is what
# makes it possible to recognize a second worktree of a configured root as
# that same root_id -- a user routinely has several concurrent worktrees of
# axon911-frontend open (one per branch/task), and only the first one happens
# to sit at the hardcoded default path. Cached per process: a single hook
# invocation may resolve the same path several times.
_WORKTREE_IDENTITY_CACHE: Dict[str, Tuple[Optional[str], Optional[str]]] = {}


def _run_git(args: Tuple[str, ...], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def worktree_identity(path: str) -> Tuple[Optional[str], Optional[str]]:
    """(toplevel, common-git-dir) for the repository containing `path`.

    `(None, None)` when `path` does not exist or is not inside a git
    repository at all.
    """
    if path in _WORKTREE_IDENTITY_CACHE:
        return _WORKTREE_IDENTITY_CACHE[path]
    result: Tuple[Optional[str], Optional[str]] = (None, None)
    if os.path.isdir(path):
        toplevel = _run_git(("rev-parse", "--show-toplevel"), path)
        common = _run_git(("rev-parse", "--git-common-dir"), path)
        if toplevel and common:
            if not os.path.isabs(common):
                common = os.path.join(toplevel, common)
            result = (os.path.realpath(toplevel), os.path.realpath(common))
    _WORKTREE_IDENTITY_CACHE[path] = result
    return result


def identify_root(path: str, roots: Optional[Mapping[str, str]] = None) -> Tuple[str, str]:
    real = canonical_path(path)
    mapping = roots or configured_roots()
    matches = []
    for root_id, root_path in mapping.items():
        prefix = root_path.rstrip(os.sep) + os.sep
        if real == root_path or real.startswith(prefix):
            matches.append((len(root_path), root_id, root_path))
    if matches:
        matches.sort(reverse=True)
        _, root_id, root_path = matches[0]
        return root_id, root_path

    # No configured path contains `real` directly. It may still be a *linked*
    # worktree of a configured repository -- a different directory sharing
    # that repository's history -- which a plain path-prefix check can never
    # recognize. `real` itself might be a file, so walk up to an existing
    # directory before asking git about it.
    probe = real if os.path.isdir(real) else os.path.dirname(real)
    while probe and probe != os.path.dirname(probe) and not os.path.isdir(probe):
        probe = os.path.dirname(probe)
    candidate_top, candidate_common = worktree_identity(probe) if probe else (None, None)
    if candidate_common:
        for root_id, root_path in mapping.items():
            if root_id == "personal-harness":
                continue
            _, configured_common = worktree_identity(root_path)
            if configured_common and configured_common == candidate_common:
                return root_id, candidate_top or real

    raise PathError("path is outside the four configured roots")


def canonical_path(path: str) -> str:
    if not path:
        raise PathError("empty path")
    if "\x00" in path:
        raise PathError("NUL in path")
    real = os.path.realpath(path)
    return real


def contained_path(path: str, root_path: str) -> str:
    real = canonical_path(path)
    root = os.path.realpath(root_path)
    prefix = root.rstrip(os.sep) + os.sep
    if real != root and not real.startswith(prefix):
        raise PathError("path escapes root")
    if os.path.islink(path):
        raise PathError("symlink rejected")
    if os.path.exists(path):
        mode = os.lstat(path).st_mode
        if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            raise PathError("special file rejected")
    return real


def relative_pointer(path: str, root_path: str) -> str:
    real = contained_path(path, root_path)
    rel = os.path.relpath(real, os.path.realpath(root_path))
    if rel.startswith(".."):
        raise PathError("relative pointer escaped root")
    return rel.replace(os.sep, "/")


def ensure_root_id(root_id: str) -> str:
    if root_id not in ROOT_IDS:
        raise PathError("unknown root: %s" % root_id)
    return root_id
