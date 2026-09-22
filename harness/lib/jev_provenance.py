"""Persist bounded Jev observations outside indexed gate state."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional

from .constants import JEV_OBSERVATION_KIND
from .paths import runtime_dir


def observations_path(base: Optional[str] = None) -> str:
    root = base or runtime_dir()
    path = os.path.join(root, "jev-observations.jsonl")
    os.makedirs(root, mode=0o700, exist_ok=True)
    return path


def read_observations(base: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every recorded observation, skipping unparsable lines."""
    path = observations_path(base)
    if not os.path.isfile(path):
        return []
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


TURN_COVERAGE_THRESHOLD = 0.9


def turns_dir(base: Optional[str] = None) -> str:
    path = os.path.join(base or runtime_dir(), "jev-turns")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def turn_ledger_path(base: Optional[str] = None) -> str:
    return os.path.join(turns_dir(base), "ledger.jsonl")


def append_turn_event(event: Mapping[str, Any], base: Optional[str] = None) -> None:
    """Append one turn-compliance row. Callers must not include request text."""
    path = turn_ledger_path(base)
    record = dict(event)
    record.setdefault("ts", int(time.time()))
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    os.chmod(path, 0o600)


def read_turn_events(base: Optional[str] = None) -> List[Dict[str, Any]]:
    path = turn_ledger_path(base)
    if not os.path.isfile(path):
        return []
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def routing_status(*, window_hours: int = 24, base: Optional[str] = None) -> Dict[str, Any]:
    """Turn coverage for hook-delivered routing, plus the doc-rank warning signal."""
    cutoff = time.time() - (window_hours * 3600)
    records = read_observations(base)
    docs = [item for item in records if item.get("question_set") == "rank-docs"]
    docs_recent = [item for item in docs if float(item.get("ts") or 0) >= cutoff]
    events = read_turn_events(base)
    eligible = [
        item
        for item in events
        if item.get("kind") == "eligible" and float(item.get("ts") or 0) >= cutoff
    ]
    turn_ids = {str(item.get("turn_id") or "") for item in eligible}
    later = [
        item
        for item in events
        if str(item.get("turn_id") or "") in turn_ids and item.get("kind") in ("routed", "delivered", "failed")
    ]
    routed_ids = {str(item.get("turn_id") or "") for item in later if item.get("kind") == "routed"}
    delivered_ids = {str(item.get("turn_id") or "") for item in later if item.get("kind") == "delivered"}
    failed_ids = {str(item.get("turn_id") or "") for item in later if item.get("kind") == "failed"}
    eligible_count = len(eligible)
    delivered_count = len(delivered_ids & turn_ids)
    coverage_ok = eligible_count == 0 or (delivered_count / float(eligible_count)) >= TURN_COVERAGE_THRESHOLD
    if eligible_count == 0:
        decision = "routing-idle"
    elif coverage_ok:
        decision = "routing-observed"
    else:
        decision = "routing-incomplete"
    return {
        "decision": decision,
        "policy_action": "pass" if coverage_ok else "flag",
        "window_hours": window_hours,
        "eligible_turns": eligible_count,
        "routed_turns": len(routed_ids & turn_ids),
        "delivered_turns": delivered_count,
        "jev_failures": len(failed_ids & turn_ids),
        "docs_rank": "observed" if docs_recent else "absent",
        "docs_rank_in_window": len(docs_recent),
        "observations_path": observations_path(base),
        "ledger_path": turn_ledger_path(base),
        "fallback_reason": "" if coverage_ok else "turn-coverage-below-threshold",
    }


def record_observation(
    *,
    question_set: str,
    question_set_hash: str,
    state_hash: str,
    model: str,
    outcome: str,
    mode: str,
    policy_action: str,
    answers_summary: Mapping[str, Any],
    latency_ms: int = 0,
    usage: Optional[Mapping[str, Any]] = None,
    fallback_reason: str = "",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a non-indexed Jev observation."""
    record = {
        "ts": int(time.time()),
        "kind": JEV_OBSERVATION_KIND,
        "question_set": question_set,
        "question_set_hash": question_set_hash,
        "state_hash": state_hash,
        "model": model,
        "outcome": outcome,
        "mode": mode,
        "policy_action": policy_action,
        "answers_summary": dict(answers_summary),
        "latency_ms": latency_ms,
        "usage": dict(usage or {}),
        "fallback_reason": fallback_reason,
    }
    path = observations_path(base)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    os.chmod(path, 0o600)
    return record
