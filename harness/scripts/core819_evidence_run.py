#!/usr/bin/env python3
"""Orchestrate CORE-819 Storybook evidence capture across git worktrees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from lib.capture_receipt import write_capture_receipt  # noqa: E402
from lib.paths import harness_root, runtime_dir  # noqa: E402
from lib.storybook_capture import capture_batch, start_storybook, stop_storybook  # noqa: E402

PREPARED911 = os.environ.get("HARNESS_PREPARED911_ROOT", "/Users/ckark/Documents/GitHub/prepared911")
FIXTURES = os.path.join(harness_root(), "harness", "fixtures", "core819-stories-modules")
EVIDENCE_ROOT = os.path.join(runtime_dir(), "evidence")


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def ensure_worktree(sha: str, name: str) -> str:
    path = os.path.join(runtime_dir(), "worktrees", name)
    if os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git")):
        _run_git(["checkout", sha], path)
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _run_git(["worktree", "add", "--detach", path, sha], PREPARED911)
    return path


def install_fixtures(worktree: str) -> None:
    target = os.path.join(worktree, "turbo", "apps", "dispatch", "src", "modules", "evidence-fixtures")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(FIXTURES, target)


def capture_plan(
    plan_hash: str,
    manifest_path: str,
    *,
    before_sha: str,
    after_sha: str,
    port: int = 3005,
) -> None:
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    out_dir = os.path.join(EVIDENCE_ROOT, plan_hash)
    os.makedirs(out_dir, exist_ok=True)

    for role, sha in (("before", before_sha), ("after", after_sha)):
        worktree = ensure_worktree(sha, "%s-%s" % (plan_hash, role))
        install_fixtures(worktree)
        process = start_storybook(worktree, port=port)
        try:
            captures = []
            for item in manifest.get("changes") or []:
                change_id = str(item["change_id"])
                capture = item.get("capture") or {}
                output_path = os.path.join(out_dir, "%s-%s.png" % (change_id, role))
                receipt_path = output_path + ".receipt.json"
                captures.append(
                    {
                        "capture_id": "%s-%s-%s" % (plan_hash, change_id, role),
                        "story_id": capture.get("story_id", ""),
                        "theme": capture.get("theme", "dark"),
                        "brand": capture.get("brand", "prepared"),
                        "viewport": capture.get("viewport", "1280x720"),
                        "state": capture.get("state", "default"),
                        "output_path": output_path,
                        "receipt_path": receipt_path,
                        "actions": capture.get("actions") or [],
                    }
                )
            capture_batch(
                worktree,
                captures,
                source_sha=sha,
                role=role,
                port=port,
                storybook_process=process,
            )
        finally:
            stop_storybook(process)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-hash", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--before-sha", required=True)
    parser.add_argument("--after-sha", required=True)
    parser.add_argument("--port", type=int, default=3005)
    args = parser.parse_args()
    capture_plan(args.plan_hash, args.manifest, before_sha=args.before_sha, after_sha=args.after_sha, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
