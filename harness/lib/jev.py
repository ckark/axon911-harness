"""Zero-dependency TypeSafe Jev HTTP client."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Sequence

from .constants import STATUS_INCONCLUSIVE
from .jev_redaction import JevState, build_state, redact_secrets

SYSTEMONE_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_TIMEOUT_S = 45.0
MAX_RETRIES = 3
KEYCHAIN_SERVICE = "typesafe-ai-api-key"

Transport = Callable[[Mapping[str, Any]], Dict[str, Any]]


class JevError(RuntimeError):
    """Non-recoverable Jev client error."""


def _load_api_key() -> str:
    key = (os.environ.get("TYPESAFE_API_KEY") or "").strip()
    if key:
        return key
    try:
        proc = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                os.environ.get("USER") or "",
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def question_set_hash(questions: Mapping[str, Any]) -> str:
    payload = json.dumps(questions, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def state_hash(state: JevState) -> str:
    if isinstance(state, str):
        payload = state
    else:
        payload = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(redact_secrets(payload).encode("utf-8")).hexdigest()


def _default_transport(body: Mapping[str, Any]) -> Dict[str, Any]:
    api_key = _load_api_key()
    if not api_key:
        raise JevError("missing-api-key")
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        SYSTEMONE_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_S) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise JevError("invalid-response-shape")
    return parsed


def evaluate(
    state: JevState,
    questions: Mapping[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    transport: Optional[Transport] = None,
) -> Dict[str, Any]:
    """Evaluate state against typed questions; never raises to callers."""
    started = time.time()
    body = {"state": state, "model": model, "questions": dict(questions)}
    q_hash = question_set_hash(questions)
    s_hash = state_hash(state)
    send = transport or _default_transport
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            response = send(body)
            answers = response.get("answers")
            if not isinstance(answers, dict):
                return _inconclusive(
                    "invalid-answers",
                    model=response.get("model") or model,
                    question_set_hash=q_hash,
                    state_hash=s_hash,
                    latency_ms=int((time.time() - started) * 1000),
                )
            return {
                "status": "ok",
                "outcome": "ok",
                "model": str(response.get("model") or model),
                "answers": answers,
                "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
                "question_set_hash": q_hash,
                "state_hash": s_hash,
                "latency_ms": int((time.time() - started) * 1000),
            }
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 422):
                return _inconclusive(
                    "http-%s" % exc.code,
                    model=model,
                    question_set_hash=q_hash,
                    state_hash=s_hash,
                    latency_ms=int((time.time() - started) * 1000),
                )
            if exc.code in (429, 529) and attempt + 1 < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
            last_error = "http-%s" % exc.code
        except (urllib.error.URLError, json.JSONDecodeError, JevError, TimeoutError, OSError) as exc:
            last_error = str(exc) or exc.__class__.__name__
            if attempt + 1 < MAX_RETRIES:
                time.sleep(0.25 * (2**attempt))
                continue
    return _inconclusive(
        last_error or "transport-failed",
        model=model,
        question_set_hash=q_hash,
        state_hash=s_hash,
        latency_ms=int((time.time() - started) * 1000),
    )


def _inconclusive(
    reason: str,
    *,
    model: str,
    question_set_hash: str,
    state_hash: str,
    latency_ms: int,
) -> Dict[str, Any]:
    return {
        "status": STATUS_INCONCLUSIVE,
        "outcome": "inconclusive",
        "reason": reason,
        "model": model,
        "answers": {},
        "usage": {},
        "question_set_hash": question_set_hash,
        "state_hash": state_hash,
        "latency_ms": latency_ms,
    }


def noul_probability(result: Mapping[str, Any], question_id: str) -> Optional[float]:
    if result.get("status") == STATUS_INCONCLUSIVE:
        return None
    answers = result.get("answers") or {}
    answer = answers.get(question_id)
    if not isinstance(answer, dict):
        return None
    if answer.get("type") != "noul":
        return None
    try:
        return float(answer.get("noul"))
    except (TypeError, ValueError):
        return None


def choice_answer(result: Mapping[str, Any], question_id: str) -> Optional[str]:
    if result.get("status") == STATUS_INCONCLUSIVE:
        return None
    answers = result.get("answers") or {}
    answer = answers.get(question_id)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        return None
    choice = answer.get("choice")
    return str(choice) if choice is not None else None


def choice_confidence(result: Mapping[str, Any], question_id: str) -> Optional[float]:
    if result.get("status") == STATUS_INCONCLUSIVE:
        return None
    answers = result.get("answers") or {}
    answer = answers.get(question_id)
    if not isinstance(answer, dict):
        return None
    try:
        return float(answer.get("confidence"))
    except (TypeError, ValueError):
        return None


def smoke_question() -> Mapping[str, Any]:
    return {
        "harness_smoke": {
            "type": "noul",
            "instructions": "Does this state describe a harness connectivity smoke check?",
        }
    }


def run_smoke(*, transport: Optional[Transport] = None) -> Dict[str, Any]:
    state = build_state(user_request="harness jev smoke check")
    result = evaluate(state, smoke_question(), transport=transport)
    prob = noul_probability(result, "harness_smoke")
    result["policy_action"] = "pass" if prob is not None and prob >= 0.5 else "fallback"
    if prob is None:
        result["fallback_reason"] = result.get("reason") or "inconclusive"
    return result
