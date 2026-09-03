#!/usr/bin/env python3
"""Capture one fingerprint batch for CORE-819 evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HARNESS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HARNESS)

from lib.storybook_capture import capture_batch, start_storybook, stop_storybook  # noqa: E402

PREPARED911 = os.environ.get("HARNESS_PREPARED911_ROOT", "/Users/ckark/Documents/GitHub/prepared911")


def install_fixtures(worktree: str, variant: str) -> None:
    source = os.path.join(HARNESS, "fixtures", "core819-stories-%s" % variant)
    target = os.path.join(worktree, "turbo", "apps", "dispatch", "src", "modules", "evidence-fixtures")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--variant", choices=("base", "head"), required=True)
    parser.add_argument("--role", choices=("before", "after"), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--plan-hash", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--port", type=int, default=3015)
    args = parser.parse_args()

    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    out_dir = os.path.join(os.path.dirname(HARNESS), ".harness", "runtime", "evidence", args.plan_hash)
    os.makedirs(out_dir, exist_ok=True)

    install_fixtures(args.worktree, args.variant)
    process = start_storybook(args.worktree, port=args.port)
    try:
        captures = []
        for item in manifest.get("changes") or []:
            change_id = str(item["change_id"])
            capture = item.get("capture") or {}
            output_path = os.path.join(out_dir, "%s-%s.png" % (change_id, args.role))
            story_id = str(capture.get("story_id") or "")
            if story_id and not story_id.startswith("Dispatch App/"):
                story_id = "Dispatch App/%s" % story_id
            captures.append(
                {
                    "capture_id": "%s-%s-%s" % (args.plan_hash, change_id, args.role),
                    "story_id": story_id,
                    "theme": capture.get("theme", "dark"),
                    "brand": capture.get("brand", "prepared"),
                    "viewport": capture.get("viewport", "1280x720"),
                    "state": capture.get("state", "default"),
                    "output_path": output_path,
                    "receipt_path": output_path + ".receipt.json",
                    "actions": capture.get("actions") or [],
                }
            )
        capture_batch(
            args.worktree,
            captures,
            source_sha=args.source_sha,
            role=args.role,
            port=args.port,
            storybook_process=process,
            manage_storybook=False,
        )
    finally:
        stop_storybook(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
