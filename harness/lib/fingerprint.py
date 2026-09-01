"""Canonical fingerprinting of a Git worktree."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import (
    COMMAND_SPEC_VERSION,
    FINGERPRINT_VERSION,
    OBLIGATION_SCHEMA_VERSION,
    VERIFIER_VERSION,
)
from .paths import canonical_path, ensure_root_id

GitRunner = Callable[[Sequence[str], str], str]


def _default_git(args: Sequence[str], cwd: str) -> str:
    result = subprocess.run(
        ["git", *list(args)],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git %s failed" % " ".join(args))
    return result.stdout.decode("utf-8", "replace")


def _length_prefix(items: Iterable[Tuple[str, str]]) -> bytes:
    encoded = []
    for key, value in sorted(items):
        key_b = key.encode("utf-8")
        value_b = value.encode("utf-8")
        encoded.append(("%d:" % len(key_b)).encode("ascii") + key_b)
        encoded.append(("%d:" % len(value_b)).encode("ascii") + value_b)
    return b"|".join(encoded)


def _file_record(root: str, relpath: str, git: Optional[GitRunner] = None) -> Tuple[str, str]:
    full = os.path.join(root, relpath)
    runner = git or _default_git
    if os.path.islink(full):
        target = os.readlink(full)
        return relpath, "symlink:%s" % target
    if os.path.isdir(full):
        gitfile = os.path.join(full, ".git")
        if os.path.isfile(gitfile) or os.path.isdir(gitfile):
            try:
                oid = runner(["rev-parse", "HEAD"], full).strip()
            except RuntimeError:
                oid = "unknown"
            return relpath, "submodule:%s" % oid
        return relpath, "dir"
    if not os.path.isfile(full):
        return relpath, "missing"
    mode = stat.S_IMODE(os.lstat(full).st_mode)
    digest = hashlib.sha256()
    with open(full, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    return relpath, "file:%o:%s" % (mode, digest.hexdigest())


def snapshot(
    root_id: str,
    root_path: str,
    plan_hash: str = "",
    git: Optional[GitRunner] = None,
    extra_untracked: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    ensure_root_id(root_id)
    real = canonical_path(root_path)
    runner = git or _default_git
    head = runner(["rev-parse", "HEAD"], real).strip()
    git_dir = runner(["rev-parse", "--git-dir"], real).strip()
    index = runner(["ls-files", "-s"], real)
    status = runner(["status", "--porcelain=v1", "-uall"], real)
    name_status = runner(["diff", "--name-status", "HEAD"], real)
    tracked: List[Tuple[str, str]] = []
    untracked: List[Tuple[str, str]] = []
    deletions: List[str] = []
    renames: List[str] = []
    for line in name_status.splitlines():
        if not line:
            continue
        code = line[0]
        rest = line[1:].lstrip()
        if code == "D":
            deletions.append(rest)
        elif code == "R":
            renames.append(rest)
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        record = _file_record(real, path, git=runner)
        if line.startswith("??"):
            untracked.append(record)
        else:
            tracked.append(record)
    if extra_untracked:
        for path in extra_untracked:
            untracked.append(_file_record(real, path, git=runner))
    records = [
        ("fingerprint_version", FINGERPRINT_VERSION),
        ("root_id", root_id),
        ("real_path", real),
        ("worktree_id", os.path.realpath(os.path.join(real, git_dir))),
        ("head", head),
        ("index_tree", hashlib.sha256(index.encode("utf-8")).hexdigest()),
        ("tracked", hashlib.sha256(_length_prefix(tracked)).hexdigest()),
        ("untracked", hashlib.sha256(_length_prefix(untracked)).hexdigest()),
        ("deletions", hashlib.sha256("\n".join(sorted(deletions)).encode("utf-8")).hexdigest()),
        ("renames", hashlib.sha256("\n".join(sorted(renames)).encode("utf-8")).hexdigest()),
        ("plan_hash", plan_hash),
        ("obligation_schema_version", OBLIGATION_SCHEMA_VERSION),
        ("command_spec_version", COMMAND_SPEC_VERSION),
        ("verifier_version", VERIFIER_VERSION),
    ]
    digest = hashlib.sha256(_length_prefix(records)).hexdigest()
    return {
        "fingerprint": digest,
        "head": head,
        "root": root_id,
        "worktree_id": os.path.realpath(os.path.join(real, git_dir)),
        "plan_hash": plan_hash,
        "schema_version": OBLIGATION_SCHEMA_VERSION,
        "command_spec_version": COMMAND_SPEC_VERSION,
    }


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def changed_paths(root_path: str, git: Optional[GitRunner] = None) -> List[str]:
    runner = git or _default_git
    real = canonical_path(root_path)
    status = runner(["status", "--porcelain=v1", "-uall"], real)
    paths: List[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths
