"""Sanitize and redact text before TypeSafe Jev egress."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

JevState = Union[str, Mapping[str, object], List[object]]

MAX_STATE_CHARS = 24_000
MAX_EXCERPT_CHARS = 8_000
MAX_USER_REQUEST_CHARS = 2_000

_DENY_PATH_FRAGMENTS = (
    ".env",
    ".harness/runtime/ledger",
    ".harness/runtime/transcripts",
    "credentials",
    "id_rsa",
    ".pem",
)

_SECRET_PATTERNS: Sequence[Tuple[re.Pattern[str], str]] = (
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED:openai-key]"),
    (re.compile(r"\bapikey_[A-Za-z0-9]+\b"), "[REDACTED:typesafe-key]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]+\b", re.I), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(authorization:\s*)[^\s]+"), r"\1[REDACTED]"),
    (
        re.compile(
            r"(?i)([?&](?:token|access_token|api_key|apikey|key)=)[^&\s\"']+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED:private-key]",
    ),
)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def redact_secrets(text: str) -> str:
    """Redact common secret shapes from a string."""
    cleaned = text or ""
    for pattern, repl in _SECRET_PATTERNS:
        cleaned = pattern.sub(repl, cleaned)
    return cleaned


def is_denied_path(path: str) -> bool:
    lowered = (path or "").lower().replace("\\", "/")
    return any(fragment in lowered for fragment in _DENY_PATH_FRAGMENTS)


def sanitize_excerpt(text: str, *, limit: int = MAX_EXCERPT_CHARS) -> str:
    """Redact and bound a single excerpt for Jev state."""
    return _truncate(redact_secrets(text or ""), limit)


def sanitize_user_request(text: str) -> str:
    """Bounded, redacted user request text allowed for routing."""
    return _truncate(redact_secrets(text or "").strip(), MAX_USER_REQUEST_CHARS)


def build_state(
    *,
    user_request: str = "",
    plan_excerpt: str = "",
    diff_excerpt: str = "",
    report_excerpt: str = "",
    claim: str = "",
    evidence: str = "",
    command: str = "",
    metadata: Optional[Mapping[str, object]] = None,
    candidates: Optional[Sequence[Mapping[str, str]]] = None,
    passages: Optional[Sequence[Mapping[str, str]]] = None,
    extra: Optional[Mapping[str, object]] = None,
) -> JevState:
    """Build a structured Jev state object with bounded fields."""
    state: Dict[str, object] = {}
    if user_request.strip():
        state["user_request"] = sanitize_user_request(user_request)
    for key, value, limit in (
        ("plan_excerpt", plan_excerpt, MAX_EXCERPT_CHARS),
        ("diff_excerpt", diff_excerpt, MAX_EXCERPT_CHARS),
        ("report_excerpt", report_excerpt, MAX_EXCERPT_CHARS),
        ("claim", claim, MAX_EXCERPT_CHARS),
        ("evidence", evidence, MAX_EXCERPT_CHARS),
        ("command", command, 512),
    ):
        if value and str(value).strip():
            state[key] = sanitize_excerpt(str(value), limit=limit)
    if metadata:
        state["metadata"] = {
            str(k): str(v)[:256]
            for k, v in metadata.items()
            if v is not None and str(v).strip()
        }
    if candidates:
        state["candidates"] = [
            {
                "id": redact_secrets(str(item.get("id") or ""))[:128],
                "label": sanitize_excerpt(str(item.get("label") or ""), limit=512),
                "summary": sanitize_excerpt(str(item.get("summary") or ""), limit=1024),
            }
            for item in candidates[:32]
            if isinstance(item, Mapping)
        ]
    if passages:
        state["passages"] = [
            {
                "id": str(item.get("id") or "")[:64],
                "text": sanitize_excerpt(str(item.get("text") or ""), limit=2048),
            }
            for item in passages[:24]
            if isinstance(item, Mapping)
        ]
    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            if isinstance(value, str):
                state[str(key)] = sanitize_excerpt(value)
            elif isinstance(value, (int, float, bool)):
                state[str(key)] = value
    if not state:
        return ""
    serialized = str(state)
    if len(serialized) > MAX_STATE_CHARS:
        state["truncated"] = True
        if "diff_excerpt" in state:
            state["diff_excerpt"] = _truncate(str(state["diff_excerpt"]), 2000)
        if "plan_excerpt" in state:
            state["plan_excerpt"] = _truncate(str(state["plan_excerpt"]), 2000)
    return state


def filter_paths(paths: Iterable[str]) -> List[str]:
    """Drop denied paths from a changed-path list."""
    return [path for path in paths if path and not is_denied_path(path)]
