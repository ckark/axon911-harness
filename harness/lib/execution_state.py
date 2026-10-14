"""Bounded execution phase state for CORE-819 definitive runs."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional

from .paths import runtime_dir


class ExecutionStateError(RuntimeError):
    """Raised when phase transitions violate execution bounds."""


def execution_state_path(execution_id: str) -> str:
    return os.path.join(runtime_dir(), "executions", execution_id, "phase-state.json")


def load_execution_state(execution_id: str) -> Dict[str, Any]:
    path = execution_state_path(execution_id)
    if not os.path.isfile(path):
        return {"execution_id": execution_id, "steps": {}}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ExecutionStateError("invalid execution state")
    return data


def save_execution_state(execution_id: str, state: Mapping[str, Any]) -> None:
    path = execution_state_path(execution_id)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True, indent=2)
        handle.write("\n")
    os.chmod(path, 0o600)


def begin_attempt(
    execution_id: str,
    phase: str,
    *,
    max_attempts: int,
    idempotency_key: str = "",
) -> Dict[str, Any]:
    """Record a phase attempt and enforce max_attempts."""
    state = load_execution_state(execution_id)
    steps = state.setdefault("steps", {})
    entry = steps.setdefault(phase, {"attempts": [], "status": "pending"})
    if entry.get("status") == "passed":
        return entry
    attempts = entry.setdefault("attempts", [])
    if idempotency_key:
        for existing in reversed(attempts):
            if existing.get("idempotency_key") == idempotency_key:
                return existing
    if len(attempts) >= max_attempts:
        raise ExecutionStateError("phase %s exhausted attempts (%d)" % (phase, max_attempts))
    attempt = {
        "attempt": len(attempts) + 1,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "idempotency_key": idempotency_key,
        "status": "running",
    }
    attempts.append(attempt)
    save_execution_state(execution_id, state)
    return attempt


def complete_attempt(
    execution_id: str,
    phase: str,
    *,
    status: str,
    details: Optional[Mapping[str, Any]] = None,
) -> None:
    """Mark the latest attempt and phase status."""
    state = load_execution_state(execution_id)
    entry = (state.get("steps") or {}).get(phase) or {}
    attempts = entry.get("attempts") or []
    if not attempts:
        raise ExecutionStateError("no attempt to complete for %s" % phase)
    attempts[-1]["status"] = status
    attempts[-1]["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if details:
        attempts[-1]["details"] = dict(details)
    entry["status"] = status
    save_execution_state(execution_id, state)
