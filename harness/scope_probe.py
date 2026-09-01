#!/usr/bin/env python3
"""Record and verify four-root Cursor project-hook scope probes.

This utility is reusable by health checks. It never treats a missing fire as
proof that sibling-root enforcement works. Absence is classified only after a
bounded observation window, using independently recorded attempts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT_IDS = (
    "personal-harness",
    "prepared911",
    "axon911-frontend",
    "vault-core-ux",
)
ALLOWED_FIELDS = (
    "version",
    "nonce",
    "bounded_window_ms",
    "hooks_output_hash",
    "enforcement_scope",
    "limitation",
    "attempts",
)
ATTEMPT_FIELDS = (
    "root",
    "attempted_at",
    "nonce",
    "fired",
    "classified_at",
    "cwd",
    "workspace_roots",
    "project_dir",
    "reason",
)


class ProbeError(Exception):
    """Raised when a probe report cannot be verified."""


def _now() -> float:
    return time.time()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_report(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ProbeError("scope probe report must be an object")
    return data


def _write_report(path: str, data: Mapping[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _empty_report(nonce: str, window_ms: int) -> Dict[str, Any]:
    return {
        "version": 1,
        "nonce": nonce,
        "bounded_window_ms": int(window_ms),
        "hooks_output_hash": "",
        "enforcement_scope": "unproven",
        "limitation": "",
        "attempts": [],
    }


def _find_attempt(attempts: Sequence[Mapping[str, Any]], root: str, nonce: str) -> Optional[int]:
    for index, attempt in enumerate(attempts):
        if attempt.get("root") == root and attempt.get("nonce") == nonce:
            return index
    return None


def record_attempt(
    report_path: str,
    root: str,
    nonce: str,
    window_ms: int,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if root not in ROOT_IDS:
        raise ProbeError("unknown root: %s" % root)
    if os.path.exists(report_path):
        report = _load_report(report_path)
    else:
        report = _empty_report(nonce, window_ms)
    if report.get("nonce") and report["nonce"] != nonce:
        raise ProbeError("nonce mismatch")
    report["nonce"] = nonce
    report["bounded_window_ms"] = int(window_ms)
    attempts = list(report.get("attempts") or [])
    existing = _find_attempt(attempts, root, nonce)
    stamp = now if now is not None else _now()
    payload = {
        "root": root,
        "attempted_at": stamp,
        "nonce": nonce,
        "fired": False,
        "classified_at": None,
        "cwd": "",
        "workspace_roots": [],
        "project_dir": "",
        "reason": "attempted",
    }
    if existing is None:
        attempts.append(payload)
    else:
        attempts[existing] = payload
    report["attempts"] = attempts
    _write_report(report_path, report)
    return report


def record_fire(
    report_path: str,
    root: str,
    nonce: str,
    cwd: str,
    workspace_roots: Iterable[str],
    project_dir: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if not os.path.exists(report_path):
        raise ProbeError("cannot record a fire before an attempt")
    report = _load_report(report_path)
    if report.get("nonce") != nonce:
        raise ProbeError("nonce mismatch")
    attempts = list(report.get("attempts") or [])
    existing = _find_attempt(attempts, root, nonce)
    if existing is None:
        raise ProbeError("fire without matching attempt: %s" % root)
    stamp = now if now is not None else _now()
    attempt = dict(attempts[existing])
    attempt["fired"] = True
    attempt["classified_at"] = stamp
    attempt["cwd"] = cwd
    attempt["workspace_roots"] = list(workspace_roots)
    attempt["project_dir"] = project_dir
    attempt["reason"] = "hook-fired"
    attempts[existing] = attempt
    report["attempts"] = attempts
    _write_report(report_path, report)
    return report


def classify_absences(
    report_path: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    report = _load_report(report_path)
    window_s = float(report.get("bounded_window_ms") or 0) / 1000.0
    stamp = now if now is not None else _now()
    attempts = []
    for attempt in report.get("attempts") or []:
        item = dict(attempt)
        if item.get("fired"):
            attempts.append(item)
            continue
        attempted_at = float(item.get("attempted_at") or 0)
        if stamp - attempted_at < window_s:
            raise ProbeError("observation window still open for %s" % item.get("root"))
        item["classified_at"] = stamp
        item["reason"] = "not-fired-after-bounded-window"
        attempts.append(item)
    report["attempts"] = attempts
    fired_roots = [item["root"] for item in attempts if item.get("fired")]
    if set(fired_roots) >= set(ROOT_IDS):
        report["enforcement_scope"] = "all-workspace-roots"
        report["limitation"] = ""
    elif "personal-harness" in fired_roots:
        report["enforcement_scope"] = "harness-local"
        report["limitation"] = (
            "Harness project hooks did not fire for every sibling root. "
            "Automatic enforcement stays harness-local."
        )
    else:
        report["enforcement_scope"] = "harness-local"
        report["limitation"] = (
            "No live Cursor project-hook fire was observed for any attempted "
            "root during this session. Automatic enforcement stays harness-local "
            "until a later live probe records otherwise."
        )
    _write_report(report_path, report)
    return report


def set_hooks_output_hash(report_path: str, hooks_output: str) -> Dict[str, Any]:
    report = _load_report(report_path)
    report["hooks_output_hash"] = _sha256_text(hooks_output)
    _write_report(report_path, report)
    return report


def verify_report(
    report_path: str,
    expected_roots: Sequence[str],
    require_bounded_window: bool,
    require_hooks_output_hash: bool,
) -> Dict[str, Any]:
    report = _load_report(report_path)
    extra = set(report) - set(ALLOWED_FIELDS)
    if extra:
        raise ProbeError("unexpected report fields: %s" % ", ".join(sorted(extra)))
    attempts = report.get("attempts") or []
    if not isinstance(attempts, list):
        raise ProbeError("attempts must be a list")
    seen = []
    for attempt in attempts:
        extra_attempt = set(attempt) - set(ATTEMPT_FIELDS)
        if extra_attempt:
            raise ProbeError("unexpected attempt fields: %s" % ", ".join(sorted(extra_attempt)))
        root = attempt.get("root")
        if root not in expected_roots:
            raise ProbeError("unexpected attempted root: %s" % root)
        seen.append(root)
        if attempt.get("classified_at") is None:
            raise ProbeError("unclassified attempt for %s" % root)
        if attempt.get("fired") not in (True, False):
            raise ProbeError("fired outcome missing for %s" % root)
        if require_bounded_window and not attempt.get("fired"):
            if attempt.get("reason") != "not-fired-after-bounded-window":
                raise ProbeError("absence was not classified after a bounded window")
    missing = [root for root in expected_roots if root not in seen]
    if missing:
        raise ProbeError("missing attempted roots: %s" % ", ".join(missing))
    if require_bounded_window and int(report.get("bounded_window_ms") or 0) <= 0:
        raise ProbeError("bounded observation window was not recorded")
    if require_hooks_output_hash and not report.get("hooks_output_hash"):
        raise ProbeError("hooks output hash is required")
    if report.get("enforcement_scope") not in ("harness-local", "all-workspace-roots"):
        raise ProbeError("enforcement scope is unproven or invalid")
    return report


def handle_hook_stdin(report_path: str) -> Dict[str, Any]:
    """Record a fire from a Cursor beforeShellExecution payload on stdin."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {"permission": "allow"}
    command = str(payload.get("command") or "")
    nonce = ""
    root = ""
    marker = "PREPARED911_SCOPE_PROBE"
    for token in command.split():
        if token.startswith(marker + "="):
            nonce = token.split("=", 1)[1]
        if token.startswith(marker + "_ROOT="):
            root = token.split("=", 1)[1]
    if nonce and root:
        record_fire(
            report_path,
            root=root,
            nonce=nonce,
            cwd=str(payload.get("cwd") or payload.get("working_directory") or ""),
            workspace_roots=list(payload.get("workspace_roots") or []),
            project_dir=str(
                payload.get("project_dir")
                or os.environ.get("CURSOR_PROJECT_DIR")
                or ""
            ),
        )
    return {"permission": "allow"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record-attempt")
    record.add_argument("--report", required=True)
    record.add_argument("--root", required=True)
    record.add_argument("--nonce", required=True)
    record.add_argument("--window-ms", type=int, default=500)
    fire = sub.add_parser("record-fire")
    fire.add_argument("--report", required=True)
    fire.add_argument("--root", required=True)
    fire.add_argument("--nonce", required=True)
    fire.add_argument("--cwd", default="")
    fire.add_argument("--project-dir", default="")
    fire.add_argument("--workspace-root", action="append", default=[])
    classify = sub.add_parser("classify-absences")
    classify.add_argument("--report", required=True)
    hashed = sub.add_parser("set-hooks-output-hash")
    hashed.add_argument("--report", required=True)
    hashed.add_argument("--hooks-output", required=True)
    verify = sub.add_parser("verify-report")
    verify.add_argument("report")
    verify.add_argument("--attempted-root", action="append", required=True)
    verify.add_argument("--require-bounded-window", action="store_true")
    verify.add_argument("--require-hooks-output-hash", action="store_true")
    hook = sub.add_parser("hook")
    hook.add_argument("--report", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "record-attempt":
            record_attempt(args.report, args.root, args.nonce, args.window_ms)
        elif args.command == "record-fire":
            record_fire(
                args.report,
                args.root,
                args.nonce,
                args.cwd,
                args.workspace_root,
                args.project_dir,
            )
        elif args.command == "classify-absences":
            classify_absences(args.report)
        elif args.command == "set-hooks-output-hash":
            set_hooks_output_hash(args.report, args.hooks_output)
        elif args.command == "verify-report":
            verify_report(
                args.report,
                args.attempted_root,
                args.require_bounded_window,
                args.require_hooks_output_hash,
            )
        elif args.command == "hook":
            result = handle_hook_stdin(args.report)
            json.dump(result, sys.stdout)
            sys.stdout.write("\n")
        return 0
    except ProbeError as exc:
        sys.stderr.write("scope-probe: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
