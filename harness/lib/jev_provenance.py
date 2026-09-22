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


def routing_status(*, window_hours: int = 24, base: Optional[str] = None) -> Dict[str, Any]:
    """Whether task routing ran recently, for the health check's required-routing gate."""
    cutoff = time.time() - (window_hours * 3600)
    records = read_observations(base)
    routing = [
        item
        for item in records
        if str(item.get("question_set") or "").startswith("route-task")
    ]
    recent = [item for item in routing if float(item.get("ts") or 0) >= cutoff]
    routed = [item for item in recent if item.get("policy_action") == "route"]
    last_ts = max((float(item.get("ts") or 0) for item in routing), default=0.0)
    return {
        "decision": "routing-observed" if recent else "routing-absent",
        "policy_action": "pass" if recent else "flag",
        "window_hours": window_hours,
        "observations_total": len(records),
        "routing_total": len(routing),
        "routing_in_window": len(recent),
        "routed_in_window": len(routed),
        "fallback_in_window": len(recent) - len(routed),
        "last_routing_ts": int(last_ts),
        "observations_path": observations_path(base),
        "fallback_reason": "" if recent else "no-route-task-observations-in-window",
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
