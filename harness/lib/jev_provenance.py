"""Persist bounded Jev observations outside indexed gate state."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Mapping, Optional

from .constants import JEV_OBSERVATION_KIND
from .paths import runtime_dir


def observations_path(base: Optional[str] = None) -> str:
    root = base or runtime_dir()
    path = os.path.join(root, "jev-observations.jsonl")
    os.makedirs(root, mode=0o700, exist_ok=True)
    return path


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
