"""Strict event payload schemas for Cursor hooks."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from .constants import MAX_EVENT_BYTES, RECOVERY_COMMAND
from .paths import PathError, identify_root

EVENT_FIELDS = {
    "sessionStart": ("session_id", "is_background_agent", "composer_mode"),
    "afterFileEdit": ("file_path", "edits"),
    "postToolUse": ("tool_name", "tool_input", "tool_output", "cwd", "duration"),
    "subagentStop": ("status", "task", "description", "summary", "duration"),
    "preCompact": ("is_automatic",),
    "beforeShellExecution": ("command", "cwd", "timeout"),
    "stop": ("status", "loop_count"),
}

ALL_EVENT_FIELDS = dict(EVENT_FIELDS)


class SchemaError(ValueError):
    """Invalid hook payload."""


def parse_event(event_name: str, raw: bytes) -> Dict[str, Any]:
    if event_name not in ALL_EVENT_FIELDS:
        raise SchemaError("unknown event")
    if len(raw) > MAX_EVENT_BYTES:
        raise SchemaError("payload too large")
    if b"\x00" in raw:
        raise SchemaError("NUL in payload")
    try:
        text = raw.decode("utf-8")
        data = json.loads(text) if text.strip() else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SchemaError("malformed json")
    if not isinstance(data, dict):
        raise SchemaError("payload must be an object")
    parsed: Dict[str, Any] = {"event": event_name}
    for field in ALL_EVENT_FIELDS[event_name]:
        parsed[field] = data.get(field)
    if event_name in ("afterFileEdit",):
        path = parsed.get("file_path") or data.get("path")
        parsed["file_path"] = path
    if event_name == "postToolUse" and isinstance(parsed.get("tool_output"), str):
        try:
            parsed["tool_output_parsed"] = json.loads(parsed["tool_output"])
        except json.JSONDecodeError:
            parsed["tool_output_parsed"] = None
    parsed["cwd"] = data.get("cwd") or data.get("working_directory") or ""
    parsed["workspace_roots"] = data.get("workspace_roots") or []
    return parsed


def root_from_payload(payload: Mapping[str, Any], fallback_cwd: str) -> str:
    path = payload.get("file_path") or payload.get("cwd") or fallback_cwd
    if not path:
        raise SchemaError("no path for root identification")
    try:
        root_id, _root_path = identify_root(str(path))
    except PathError as exc:
        raise SchemaError(str(exc))
    return root_id


def sanitized_message(status: str, root: str, obligation_ids: Optional[str] = None) -> str:
    extra = " obligations=%s" % obligation_ids if obligation_ids else ""
    return "runtime-gate %s root=%s%s recovery=%s" % (status, root, extra, RECOVERY_COMMAND)
