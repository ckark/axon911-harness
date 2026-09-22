"""CLI handlers for harness jev subcommands."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .judgments import (
    assess_change,
    assess_command,
    assess_plan,
    check_claim,
    check_findings,
    load_skill_roster,
    rank_context,
    rank_docs,
    route_review,
    route_task,
)
from .jev import run_smoke
from .jev_provenance import routing_status


def _emit(payload: Mapping[str, Any], *, as_json: bool) -> int:
    if as_json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for key, value in payload.items():
            if key == "jev":
                continue
            sys.stdout.write("%s=%s\n" % (key, value))
    inconclusive = payload.get("policy_action") == "fallback" or payload.get("outcome") == "inconclusive"
    if payload.get("status") == "INCONCLUSIVE":
        return 2
    return 2 if inconclusive and payload.get("decision") in (None, "fallback") else 0


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cmd_jev(argv: Sequence[str]) -> int:
    args_list = list(argv)
    as_json = "--json" in args_list
    if as_json:
        args_list = [item for item in args_list if item != "--json"]
    parser = argparse.ArgumentParser(prog="jev")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("smoke")

    route = sub.add_parser("route-task")
    route.add_argument("--request", required=True)
    route.add_argument("--root", action="append", default=[])
    route.add_argument("--mode", default="live")

    sub.add_parser("list-skills")

    status = sub.add_parser("routing-status")
    status.add_argument("--window-hours", type=int, default=24)

    plan = sub.add_parser("assess-plan")
    plan.add_argument("--plan", required=True)

    claim = sub.add_parser("check-claim")
    claim.add_argument("--claim", required=True)
    claim.add_argument("--evidence", required=True)

    change = sub.add_parser("assess-change")
    change.add_argument("--diff", required=True)
    change.add_argument("--path", default="")
    change.add_argument("--mode", default="shadow")

    ctx = sub.add_parser("rank-context")
    ctx.add_argument("--purpose", required=True)
    ctx.add_argument("--passage", action="append", default=[])

    docs = sub.add_parser("rank-docs")
    docs.add_argument("--request", required=True)

    review = sub.add_parser("route-review")
    review.add_argument("--fact", action="append", default=[])

    findings = sub.add_parser("check-findings")
    findings.add_argument("--text", default="")
    findings.add_argument("--file", default="")

    command = sub.add_parser("assess-command")
    command.add_argument("--command", required=True)
    command.add_argument("--mode", default="shadow")

    eval_cmd = sub.add_parser("eval")
    eval_cmd.add_argument("--fixture", required=True)

    args = parser.parse_args(args_list)

    if args.command == "smoke":
        return _emit(run_smoke(), as_json=as_json)

    if args.command == "route-task":
        return _emit(
            route_task(args.request, root_ids=args.root or None, mode=args.mode),
            as_json=as_json,
        )

    if args.command == "list-skills":
        roster = load_skill_roster()
        return _emit(
            {"count": len(roster), "skills": [item["id"] for item in roster]},
            as_json=as_json,
        )

    if args.command == "routing-status":
        return _emit(routing_status(window_hours=args.window_hours), as_json=as_json)

    if args.command == "assess-plan":
        import os

        text = _read_text(args.plan) if os.path.isfile(args.plan) else args.plan
        return _emit(assess_plan(text), as_json=as_json)

    if args.command == "check-claim":
        return _emit(check_claim(args.claim, args.evidence), as_json=as_json)

    if args.command == "assess-change":
        import os

        diff = _read_text(args.diff) if os.path.isfile(args.diff) else args.diff
        return _emit(assess_change(diff, path=args.path, mode=args.mode), as_json=as_json)

    if args.command == "rank-context":
        passages = _parse_passages(args.passage)
        return _emit(rank_context(passages, purpose=args.purpose), as_json=as_json)

    if args.command == "rank-docs":
        return _emit(rank_docs(args.request), as_json=as_json)

    if args.command == "route-review":
        facts = _parse_facts(args.fact)
        return _emit(route_review(facts), as_json=as_json)

    if args.command == "check-findings":
        text = args.text
        if args.file:
            text = _read_text(args.file)
        return _emit(check_findings(text), as_json=as_json)

    if args.command == "assess-command":
        return _emit(assess_command(args.command, mode=args.mode), as_json=as_json)

    if args.command == "eval":
        return _run_eval(args.fixture, as_json=as_json)

    sys.stderr.write("jev: unknown subcommand\n")
    return 2


def os_path_like(value: str) -> bool:
    return value.endswith((".md", ".txt", ".diff", ".patch")) or "/" in value


def _parse_passages(values: Sequence[str]) -> List[Dict[str, str]]:
    passages: List[Dict[str, str]] = []
    for index, raw in enumerate(values):
        if "=" in raw:
            pid, text = raw.split("=", 1)
        else:
            pid, text = "p%s" % index, raw
        passages.append({"id": pid.strip(), "text": text.strip()})
    return passages


def _parse_facts(values: Sequence[str]) -> Dict[str, str]:
    facts: Dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        facts[key.strip()] = value.strip()
    return facts


def _run_eval(fixture_path: str, *, as_json: bool) -> int:
    import os

    from .jev import evaluate, noul_probability

    if not os.path.isfile(fixture_path):
        sys.stderr.write("jev eval: missing fixture %s\n" % fixture_path)
        return 2
    with open(fixture_path, encoding="utf-8") as handle:
        fixture = json.load(handle)
    state = fixture.get("state") or ""
    questions = fixture.get("questions") or {}
    expected = fixture.get("expected") or {}
    result = evaluate(state, questions)
    report: Dict[str, Any] = {"result": result, "checks": {}}
    for key, spec in expected.items():
        if spec.get("type") == "noul":
            prob = noul_probability(result, key)
            minimum = float(spec.get("min", 0))
            maximum = float(spec.get("max", 1))
            ok = prob is not None and minimum <= prob <= maximum
            report["checks"][key] = {"ok": ok, "value": prob}
    report["ok"] = all(item.get("ok") for item in report["checks"].values()) if report["checks"] else result.get("status") != "INCONCLUSIVE"
    return _emit(report, as_json=as_json)
