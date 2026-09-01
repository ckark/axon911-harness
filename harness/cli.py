#!/usr/bin/env python3
"""Harness entry point: hook event dispatch, the attesting wrapper, and receipts.

Invoked three ways:

  cli.py <cursorEvent>   camelCase  -> dispatch.cursor  (Cursor hooks.json)
  cli.py <ClaudeEvent>   PascalCase -> dispatch.claude  (Claude Code hooks.json)
  cli.py attest|register-plan|issue-review-receipt|benchmark

Event names disambiguate the host, so one binary serves both without a flag.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Mapping, Optional, Sequence

HARNESS_DIR = os.path.dirname(os.path.abspath(__file__))
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from dispatch.common import resolve_cli_root, roots  # noqa: E402
from lib.constants import STATUS_INCONCLUSIVE, STATUS_PASS  # noqa: E402
from lib.fingerprint import snapshot  # noqa: E402
from lib.ledger import append_record, gc_segments  # noqa: E402
from lib.receipts import (  # noqa: E402
    evaluate_gate,
    issue_review_receipt,
    issue_verification_receipt,
    register_plan,
)


def _read_stdin() -> bytes:
    return sys.stdin.buffer.read()


def _emit(payload: Mapping[str, Any]) -> int:
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


def cmd_attest(argv: Sequence[str]) -> int:
    """Run a repository-owned command and bind its result to pre/post fingerprints."""
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(prog="attest")
    parser.add_argument("--root", required=True)
    parser.add_argument("--obligation-id", required=True)
    parser.add_argument("--plan-hash", default="")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    root_path = resolve_cli_root(args.root)
    pre = snapshot(args.root, root_path, plan_hash=args.plan_hash)
    started = time.time()
    result = subprocess.run(command, cwd=root_path)
    duration = int((time.time() - started) * 1000)
    post = snapshot(args.root, root_path, plan_hash=args.plan_hash)
    status = STATUS_PASS if result.returncode == 0 else STATUS_INCONCLUSIVE
    record = issue_verification_receipt(
        args.root,
        post["worktree_id"],
        post["fingerprint"],
        args.obligation_id,
        status,
        pre["fingerprint"],
        args.plan_hash,
        exit_status=result.returncode,
        duration_ms=duration,
    )
    return 0 if record.get("status") == STATUS_PASS else 1


def cmd_register_plan(argv: Sequence[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="register-plan")
    parser.add_argument("--root", required=True)
    parser.add_argument("--plan-hash", required=True)
    parser.add_argument("--tier", default="T0")
    parser.add_argument("--scope", action="append", default=[])
    args = parser.parse_args(argv)
    current = snapshot(args.root, resolve_cli_root(args.root), plan_hash=args.plan_hash)
    register_plan(
        args.root,
        current["worktree_id"],
        current["fingerprint"],
        args.plan_hash,
        tier=args.tier,
    )
    if args.scope:
        from lib.conformance import register_scope

        register_scope(
            args.root, current["worktree_id"], current["fingerprint"], args.plan_hash, args.scope
        )
    return 0


def cmd_review(argv: Sequence[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="issue-review-receipt")
    parser.add_argument("--root", required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--critic", action="append", default=[])
    parser.add_argument("--plan-hash", default="")
    parser.add_argument("--status", default=STATUS_PASS)
    args = parser.parse_args(argv)
    current = snapshot(args.root, resolve_cli_root(args.root), plan_hash=args.plan_hash)
    issue_review_receipt(
        args.root,
        current["worktree_id"],
        current["fingerprint"],
        args.tier,
        args.critic,
        args.status,
        args.plan_hash,
    )
    return 0


def cmd_benchmark(argv: Sequence[str]) -> int:
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(prog="benchmark")
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    tmp = tempfile.mkdtemp()
    started = time.time()
    samples = []
    for index in range(args.events):
        started_event = time.time()
        append_record(
            {
                "kind": "observation",
                "event_id": "afterFileEdit",
                "root": "personal-harness",
                "worktree_id": tmp,
                "fingerprint": "bench-%d" % (index // 100),
                "status": STATUS_PASS,
            },
            base=tmp,
        )
        samples.append((time.time() - started_event) * 1000)
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))] if samples else 0
    mean_ms = (time.time() - started) / max(args.events, 1) * 1000
    gate_started = time.time()
    evaluate_gate("personal-harness", tmp, "bench-0", [], "", "T0", base=tmp)
    gate_ms = (time.time() - gate_started) * 1000
    for _ in range(max(args.events // 10, 1)):
        append_record(
            {
                "kind": "observation",
                "event_id": "afterFileEdit",
                "root": "personal-harness",
                "worktree_id": tmp,
                "fingerprint": "bench-extra",
                "status": STATUS_PASS,
            },
            base=tmp,
        )
    gate_started = time.time()
    evaluate_gate("personal-harness", tmp, "bench-0", [], "", "T0", base=tmp)
    gate_ms_grown = (time.time() - gate_started) * 1000
    gc_segments(base=tmp)
    report = {
        "events": args.events,
        "append_p95_ms_estimate": p95,
        "append_mean_ms": mean_ms,
        "gate_ms": gate_ms,
        "gate_ms_after_growth": gate_ms_grown,
        "history_independent": abs(gate_ms_grown - gate_ms) < 50
        or (gate_ms < 50 and gate_ms_grown < 50),
    }
    if args.as_json:
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("%s\n" % report)
    return 0 if p95 <= 100 and gate_ms <= 500 and report["history_independent"] else 1


def cmd_tier(argv: Sequence[str]) -> int:
    """Score the blast-radius tier of the current changes in a root."""
    import argparse
    import subprocess

    from dispatch.common import roots as configured
    from lib.fingerprint import changed_paths
    from lib.tier import compute_tier, reconcile

    parser = argparse.ArgumentParser(prog="tier")
    parser.add_argument("--root", action="append", default=[])
    # No default here: "HEAD" is a legitimate explicit value as well as the
    # eventual fallback, so telling "not passed" apart from "explicitly HEAD"
    # needs a real sentinel, not a string that could be either.
    parser.add_argument("--base-ref", default=None)
    parser.add_argument(
        "--against",
        default=None,
        metavar="REF",
        help=(
            "Score the full branch diff against REF (merge-base relative, "
            "like the plan contract's ref manifest) instead of only the "
            "uncommitted worktree. Live hook gating never passes this: it "
            "always scores the current uncommitted edit, which is what a "
            "PreToolUse or Stop check actually needs. This is for auditing "
            "a complete branch before a PR, once its commits already exist."
        ),
    )
    parser.add_argument("--stated", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    all_roots = configured()
    selected = args.root or [r for r in all_roots if r != "personal-harness"]
    changes = {}
    for root_id in selected:
        if root_id not in all_roots:
            sys.stderr.write("tier: unknown root %s\n" % root_id)
            return 2
        root_path = resolve_cli_root(root_id)
        try:
            if args.against:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "%s...HEAD" % args.against],
                    cwd=root_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=10,
                )
                changes[root_id] = [line for line in result.stdout.splitlines() if line.strip()]
            else:
                changes[root_id] = changed_paths(root_path)
        except Exception:
            changes[root_id] = []

    # Precedence: an explicit --base-ref always wins (even "HEAD"); otherwise
    # the surface diff compares against the same ref the changed-file list
    # came from (--against); otherwise the live-gating default.
    if args.base_ref is not None:
        base_ref = args.base_ref
    elif args.against:
        base_ref = args.against
    else:
        base_ref = "HEAD"
    computed = compute_tier(changes, all_roots, base_ref=base_ref, stated=args.stated)
    verdict = reconcile(computed, args.stated)
    report = {
        "tier": computed["tier"],
        "predicate": computed["predicate"],
        "surface_delta": computed["surface_delta"],
        "risk_signals": computed["risk_signals"],
        "roots_touched": computed["roots_touched"],
        "measurable": computed["measurable"],
        "symbols": computed["symbols"],
        "call_sites": {
            symbol: meta["call_sites"] for symbol, meta in computed["importers"].items()
        },
        "evidence": computed["evidence"],
        "reconciliation": verdict,
    }
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("tier=%s predicate=%s\n" % (report["tier"], report["predicate"]))
        for item in report["evidence"]:
            sys.stdout.write("  - %s\n" % item)
    # Overstatement and understatement are both plan defects.
    return 1 if verdict["verdict"] in ("understated", "overstated") else 0


def cmd_ui_principles(argv: Sequence[str]) -> int:
    """Report ui-* rule findings on changed lines, diff-scoped."""
    import argparse

    from checks import ui_principles
    from dispatch.common import roots as configured
    from lib.fingerprint import changed_paths

    parser = argparse.ArgumentParser(prog="ui-principles")
    parser.add_argument("--root", default="axon911-frontend")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    all_roots = configured()
    if args.root not in all_roots:
        sys.stderr.write("ui-principles: unknown root %s\n" % args.root)
        return 2
    root_path = resolve_cli_root(args.root)
    try:
        changed = changed_paths(root_path)
    except Exception:
        changed = []
    report = ui_principles.check(args.root, root_path, args.base_ref, changed)

    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            "ui-principles %s root=%s ui-files=%d findings=%d\n"
            % (
                report.get("status", "?"),
                report["root"],
                len(report["ui_files_changed"]),
                len(report["findings"]),
            )
        )
        for item in report["findings"][:25]:
            sys.stdout.write(
                "  %s %s:%s %s\n"
                % (item.get("rule") or item.get("check"), item.get("file", ""), item.get("line", ""), item.get("message", ""))
            )
        if report.get("suppressed_legacy"):
            sys.stdout.write(
                "  (%d pre-existing finding(s) on untouched lines suppressed)\n"
                % report["suppressed_legacy"]
            )
        for item in report.get("unavailable") or []:
            sys.stdout.write("  unavailable: %s -- %s\n" % (item["check"], item["reason"]))
    return 1 if report.get("status") == "BLOCKED" else 0


def cmd_conformance(argv: Sequence[str]) -> int:
    """Report declared-scope conformance for the current tree."""
    import argparse

    from dispatch.common import roots as configured
    from lib.conformance import evaluate, summarize
    from lib.fingerprint import changed_paths, snapshot

    parser = argparse.ArgumentParser(prog="conformance")
    parser.add_argument("--root", default="axon911-frontend")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    all_roots = configured()
    if args.root not in all_roots:
        sys.stderr.write("conformance: unknown root %s\n" % args.root)
        return 2
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="")
    try:
        changed = changed_paths(root_path)
    except Exception:
        changed = []
    report = evaluate(args.root, current["worktree_id"], changed)
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("conformance %s root=%s\n" % (report["status"], args.root))
        message = summarize(report)
        if message:
            sys.stdout.write("  %s\n" % message)
    return 1 if report["status"] != STATUS_PASS else 0


SUBCOMMANDS = {
    "tier": cmd_tier,
    "ui-principles": cmd_ui_principles,
    "conformance": cmd_conformance,
    "attest": cmd_attest,
    "register-plan": cmd_register_plan,
    "issue-review-receipt": cmd_review,
    "benchmark": cmd_benchmark,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write("harness: missing command\n")
        return 2
    command = args[0]

    if command in SUBCOMMANDS:
        return SUBCOMMANDS[command](args[1:])

    from dispatch import cursor

    if command in cursor.EVENTS:
        return _emit(cursor.run(command, _read_stdin()))

    from dispatch import claude

    if command in claude.EVENTS:
        return _emit(claude.run(command, _read_stdin()))

    sys.stderr.write("harness: unknown command %s\n" % command)
    return 2


if __name__ == "__main__":
    sys.exit(main())
