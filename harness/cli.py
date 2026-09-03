#!/usr/bin/env python3
"""Harness entry point: Cursor hook dispatch, attesting wrapper, and receipts.

Invoked as:

  cli.py <cursorEvent>   camelCase  -> dispatch.cursor  (Cursor hooks.json)
  cli.py attest|register-plan|issue-review-receipt|benchmark|tier|verify|cost
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
from lib.ledger import append_record, current_state, gc_segments  # noqa: E402
from lib.receipts import (  # noqa: E402
    active_plan,
    evaluate_gate,
    issue_review_receipt,
    issue_verification_receipt,
    register_plan,
)
from lib.command_specs import validate_attestation_command  # noqa: E402
from lib.plan_profile import (  # noqa: E402
    parse_path_surface_args,
    register_plan_profile,
    validate_mirror_intent,
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
    plan_hash = args.plan_hash
    if not plan_hash:
        unbound = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
        plan_hash = active_plan(
            current_state(), args.root, unbound["worktree_id"]
        ).get("plan_hash", "")
    from lib.plan_profile import profile_from_state

    profile = profile_from_state(args.root, snapshot(args.root, root_path, plan_hash=plan_hash)["worktree_id"])
    plan_context_hash = profile.get("plan_context_hash") or ""
    ok, reason = validate_attestation_command(args.obligation_id, command)
    if not ok:
        sys.stderr.write("attest: invalid command for %s: %s\n" % (args.obligation_id, reason))
        return 2
    pre = snapshot(args.root, root_path, plan_hash=plan_hash, plan_context_hash=plan_context_hash)
    started = time.time()
    result = subprocess.run(command, cwd=root_path)
    duration = int((time.time() - started) * 1000)
    post = snapshot(args.root, root_path, plan_hash=plan_hash, plan_context_hash=plan_context_hash)
    status = STATUS_PASS if result.returncode == 0 else STATUS_INCONCLUSIVE
    record = issue_verification_receipt(
        args.root,
        post["worktree_id"],
        post["fingerprint"],
        args.obligation_id,
        status,
        pre["fingerprint"],
        plan_hash,
        exit_status=result.returncode,
        duration_ms=duration,
        plan_context_hash=plan_context_hash,
    )
    return 0 if record.get("status") == STATUS_PASS else 1


def cmd_register_plan(argv: Sequence[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="register-plan")
    parser.add_argument("--root", required=True)
    parser.add_argument("--plan-hash", required=True)
    parser.add_argument("--tier", default="T0")
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--base-oid", default="")
    parser.add_argument("--mirror-intent", default="")
    parser.add_argument("--path-surface", action="append", default=[])
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash=args.plan_hash, plan_context_hash="")
    path_surfaces, surface_errors = parse_path_surface_args(args.path_surface)
    if surface_errors:
        for item in surface_errors:
            sys.stderr.write("register-plan: %s\n" % item)
        return 2
    mirror_intent = ""
    if args.mirror_intent:
        mirror = validate_mirror_intent(args.mirror_intent)
        if not mirror:
            sys.stderr.write("register-plan: invalid mirror-intent\n")
            return 2
        mirror_intent = mirror
    from lib.conformance import normalize_scope

    scope = normalize_scope(args.scope)
    if scope or args.base_oid or mirror_intent or path_surfaces:
        register_plan_profile(
            args.root,
            current["worktree_id"],
            current["fingerprint"],
            args.plan_hash,
            args.tier,
            scope,
            args.base_oid,
            mirror_intent,
            path_surfaces,
        )
    else:
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
                args.root,
                current["worktree_id"],
                current["fingerprint"],
                args.plan_hash,
                scope,
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
    current = snapshot(args.root, resolve_cli_root(args.root), plan_hash=args.plan_hash, plan_context_hash="")
    from lib.plan_profile import profile_from_state

    profile = profile_from_state(args.root, current["worktree_id"])
    current = snapshot(
        args.root,
        resolve_cli_root(args.root),
        plan_hash=args.plan_hash or profile.get("plan_hash") or "",
        plan_context_hash=profile.get("plan_context_hash") or "",
    )
    issue_review_receipt(
        args.root,
        current["worktree_id"],
        current["fingerprint"],
        args.tier,
        args.critic,
        args.status,
        args.plan_hash,
        plan_context_hash=profile.get("plan_context_hash") or "",
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
    # Score against the worktree the changed files actually came from. `configured()`
    # holds one static path per root, so on a linked worktree the file list would be
    # collected here and then diffed somewhere else -- where those same files are
    # untouched, making every surface delta read as `none` and every tier collapse
    # to T0.
    scoring_roots = dict(all_roots)
    for root_id in selected:
        if root_id not in all_roots:
            sys.stderr.write("tier: unknown root %s\n" % root_id)
            return 2
        root_path = resolve_cli_root(root_id)
        scoring_roots[root_id] = root_path
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
    computed = compute_tier(changes, scoring_roots, base_ref=base_ref, stated=args.stated)
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


def cmd_verify(argv: Sequence[str]) -> int:
    """Mechanical verification: obligations and receipt coverage for the current tree."""
    import argparse

    from dispatch.common import resolve_cli_root, roots as configured
    from lib.fingerprint import changed_paths, snapshot
    from lib.obligations import triggered_obligations
    from lib.receipts import evaluate_gate, mutation_required_ids

    parser = argparse.ArgumentParser(prog="verify")
    parser.add_argument("--root", default="axon911-frontend")
    parser.add_argument("--family", default="git-commit")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args(argv)

    all_roots = configured()
    if args.root not in all_roots:
        sys.stderr.write("verify: unknown root %s\n" % args.root)
        return 2
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    try:
        changed = changed_paths(root_path)
    except Exception:
        changed = []
    state_plan = active_plan(current_state(), args.root, current["worktree_id"])
    tier = state_plan.get("tier") or "T0"
    plan_hash = state_plan.get("plan_hash") or ""
    from lib.plan_profile import active_profile
    from lib.path_selector import select_obligations
    from lib.conformance import evaluate_against_base

    profile = active_profile(current_state(), args.root, current["worktree_id"])
    if plan_hash or profile.get("plan_context_hash"):
        current = snapshot(
            args.root,
            root_path,
            plan_hash=plan_hash,
            plan_context_hash=profile.get("plan_context_hash") or "",
        )
    selection = select_obligations(
        args.root,
        changed,
        profile,
        tier,
        family=args.family,
    )
    conformance = evaluate_against_base(
        args.root,
        current["worktree_id"],
        changed,
        profile,
        root_path=root_path,
    )
    required = selection["required_obligation_ids"]
    gate = evaluate_gate(
        args.root,
        current["worktree_id"],
        current["fingerprint"],
        required,
        plan_hash,
        tier,
        changed_paths=changed,
        root_path=root_path,
        selection=selection,
        conformance=conformance,
        explain=args.explain,
    )
    report = {
        "root": args.root,
        "fingerprint": current["fingerprint"],
        "plan_hash": plan_hash,
        "tier": tier,
        "changed_paths": changed,
        "triggered_obligations": selection["triggered_obligation_ids"],
        "required_obligation_ids": required,
        "classification_errors": selection["classification_errors"],
        "conformance": conformance,
        "gate": gate,
        "recovery": gate.get("recovery"),
    }
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            "verify %s gate=%s obligations=%s\n"
            % (gate.get("status"), args.root, ",".join(required))
        )
    return 0 if gate.get("permission") == "allow" else 1


def cmd_preview_obligations(argv: Sequence[str]) -> int:
    import argparse

    from lib.fingerprint import changed_paths
    from lib.path_selector import preview_obligations

    parser = argparse.ArgumentParser(prog="preview-obligations")
    parser.add_argument("--root", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--family", default="git-commit")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    paths = []
    for raw in args.path:
        cleaned = raw.replace("\\", "/").lstrip("./")
        if cleaned.startswith("/") or ".." in cleaned.split("/"):
            sys.stderr.write("preview-obligations: path must be root-relative\n")
            return 2
        paths.append(cleaned)
    if not paths:
        paths = changed_paths(root_path)
    report = preview_obligations(
        args.root,
        paths,
        current["worktree_id"],
        family=args.family,
        root_path=root_path,
    )
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            "preview blocked=%s required=%s\n"
            % (report.get("blocked"), ",".join(report["selection"]["required_obligation_ids"]))
        )
    return 1 if report.get("blocked") else 0


def cmd_record_evidence(argv: Sequence[str]) -> int:
    import argparse

    from lib.evidence import record_evidence
    from lib.plan_profile import profile_from_state

    parser = argparse.ArgumentParser(prog="record-evidence")
    parser.add_argument("--root", required=True)
    parser.add_argument("--obligation-id", required=True)
    parser.add_argument("--kind", required=True, choices=("before", "after"))
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    profile = profile_from_state(args.root, current["worktree_id"])
    try:
        record_evidence(
            args.root,
            root_path,
            current["worktree_id"],
            current["fingerprint"],
            profile.get("plan_hash") or "",
            profile.get("plan_context_hash") or "",
            args.obligation_id,
            args.kind,
            args.artifact,
            base_oid=str(profile.get("base_oid") or ""),
        )
    except ValueError as exc:
        sys.stderr.write("record-evidence: %s\n" % exc)
        return 2
    return 0


def cmd_ship_plan(argv: Sequence[str]) -> int:
    import argparse

    from lib.shipping import evaluate_ship_plan

    parser = argparse.ArgumentParser(prog="ship-plan")
    parser.add_argument("--root", required=True)
    parser.add_argument("--family", default="git-push")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    from lib.plan_profile import profile_from_state

    profile = profile_from_state(args.root, current["worktree_id"])
    current = snapshot(
        args.root,
        root_path,
        plan_hash=profile.get("plan_hash") or "",
        plan_context_hash=profile.get("plan_context_hash") or "",
    )
    report = evaluate_ship_plan(
        args.root,
        root_path,
        current["worktree_id"],
        current["fingerprint"],
        family=args.family,
    )
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            "ship-plan ready=%s root=%s required=%s\n"
            % (
                report.get("ready"),
                args.root,
                ",".join(report.get("required_obligation_ids") or []),
            )
        )
    return 0 if report.get("ready") else 1


def cmd_session_status(argv: Sequence[str]) -> int:
    import argparse

    from lib.sessions import session_status

    parser = argparse.ArgumentParser(prog="session-status")
    parser.add_argument("--root", required=True)
    parser.add_argument("--session-id", default="default")
    parser.add_argument("--family", default="git-commit")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    report = session_status(
        args.root,
        root_path,
        current["worktree_id"],
        current["fingerprint"],
        args.session_id,
        family=args.family,
    )
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("session-status phase=%s\n" % report.get("phase"))
    return 0


def cmd_handoff(argv: Sequence[str]) -> int:
    import argparse

    from lib.sessions import create_handoff

    parser = argparse.ArgumentParser(prog="handoff")
    parser.add_argument("--root", required=True)
    parser.add_argument("--session-id", default="default")
    parser.add_argument("--phase", default="implementation")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    root_path = resolve_cli_root(args.root)
    current = snapshot(args.root, root_path, plan_hash="", plan_context_hash="")
    payload = create_handoff(
        args.root,
        root_path,
        current["worktree_id"],
        current["fingerprint"],
        args.session_id,
        args.phase,
    )
    if args.as_json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("handoff phase=%s next=%s\n" % (payload.get("phase"), payload.get("next_command")))
    return 0


def cmd_bundle(argv: Sequence[str]) -> int:
    import argparse

    from dispatch.common import roots as configured
    from lib.bundles import (
        STAGE_CANDIDATE,
        build_root_entry,
        bundle_manifest,
        load_bundle,
        verify_bundle_manifest,
        write_bundle,
    )

    parser = argparse.ArgumentParser(prog="bundle")
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--plan-hash", required=True)
    create.add_argument("--tier", default="T0")
    create.add_argument("--stage", default=STAGE_CANDIDATE)
    create.add_argument("--root", action="append", default=[])
    create.add_argument("--json", action="store_true", dest="as_json")
    verify = sub.add_parser("verify")
    verify.add_argument("path")
    verify.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    if args.action == "verify":
        manifest = load_bundle(args.path)
        report = verify_bundle_manifest(manifest)
        if args.as_json:
            json.dump(report, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            sys.stdout.write("bundle verify status=%s\n" % report.get("status"))
        return 0 if report.get("status") == STATUS_PASS else 1
    all_roots = configured()
    selected = args.root or [item for item in all_roots if item != "personal-harness"]
    entries = {}
    for root_id in selected:
        root_path = resolve_cli_root(root_id)
        from lib.plan_profile import profile_from_state

        profile = profile_from_state(root_id, snapshot(root_id, root_path, plan_hash=args.plan_hash)["worktree_id"])
        current = snapshot(
            root_id,
            root_path,
            plan_hash=args.plan_hash,
            plan_context_hash=profile.get("plan_context_hash") or "",
        )
        entries[root_id] = build_root_entry(
            root_id,
            root_path,
            current["worktree_id"],
            current["fingerprint"],
        )
    manifest = bundle_manifest(args.plan_hash, args.tier, args.stage, entries)
    path = write_bundle(manifest)
    report = {"path": path, "digest": verify_bundle_manifest(manifest)["digest"], "manifest": manifest}
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("bundle created %s\n" % path)
    return 0


def cmd_cost(argv: Sequence[str]) -> int:
    """Estimate billed input tokens from a Cursor transcript JSONL file."""
    import argparse

    parser = argparse.ArgumentParser(prog="cost")
    parser.add_argument("transcript", help="Path to main thread .jsonl file")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    main_running = 0
    main_billed = 0
    main_turns = 0
    for line in open(args.transcript, encoding="utf-8"):
        main_running += len(line)
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("role") == "assistant":
            main_turns += 1
            main_billed += main_running

    subagent_dir = os.path.join(os.path.dirname(args.transcript), "subagents")
    sub_billed = 0
    sub_count = 0
    if os.path.isdir(subagent_dir):
        for name in os.listdir(subagent_dir):
            if not name.endswith(".jsonl"):
                continue
            sub_count += 1
            running = 0
            for line in open(os.path.join(subagent_dir, name), encoding="utf-8"):
                running += len(line)
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("role") == "assistant":
                    sub_billed += running

    total = main_billed + sub_billed
    report = {
        "main_assistant_turns": main_turns,
        "main_billed_tokens_estimate": int(main_billed / 4),
        "subagent_count": sub_count,
        "subagent_billed_tokens_estimate": int(sub_billed / 4),
        "total_billed_tokens_estimate": int(total / 4),
        "main_thread_share": round(main_billed / total, 3) if total else 1.0,
    }
    if args.as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            "cost total~%s tokens main=%s subagents=%s turns=%s\n"
            % (
                report["total_billed_tokens_estimate"],
                report["main_thread_share"],
                sub_count,
                main_turns,
            )
        )
    return 0


SUBCOMMANDS = {
    "tier": cmd_tier,
    "ui-principles": cmd_ui_principles,
    "conformance": cmd_conformance,
    "attest": cmd_attest,
    "register-plan": cmd_register_plan,
    "issue-review-receipt": cmd_review,
    "benchmark": cmd_benchmark,
    "verify": cmd_verify,
    "preview-obligations": cmd_preview_obligations,
    "record-evidence": cmd_record_evidence,
    "ship-plan": cmd_ship_plan,
    "session-status": cmd_session_status,
    "handoff": cmd_handoff,
    "bundle": cmd_bundle,
    "cost": cmd_cost,
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

    sys.stderr.write("harness: unknown command %s\n" % command)
    return 2


if __name__ == "__main__":
    sys.exit(main())
