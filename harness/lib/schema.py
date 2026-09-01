"""Strict event payload schemas."""

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


# Claude Code sends PascalCase event names and nests tool arguments under
# `tool_input`. Names cannot collide with Cursor's camelCase set, so one parser
# serves both hosts and normalizes them to a single internal shape below.
# Sent on every Claude Code event, so they are merged into each entry below
# rather than repeated. Omitting `permission_mode` here would hide plan mode
# from the gates, which would then fight a mode that changes nothing on disk.
CLAUDE_COMMON_FIELDS = (
    "session_id",
    "cwd",
    "permission_mode",
    "hook_event_name",
    "agent_id",
    "agent_type",
)

CLAUDE_EVENT_FIELDS = {
    "SessionStart": ("model", "trigger"),
    "PreToolUse": ("tool_name", "tool_input", "tool_use_id"),
    "PostToolUse": ("tool_name", "tool_input", "tool_use_id", "tool_response"),
    "SubagentStart": (),
    "SubagentStop": ("last_assistant_message", "stop_hook_active"),
    "PreCompact": ("trigger",),
    "Stop": ("last_assistant_message", "stop_hook_active"),
    "TaskCreated": ("task_id", "task_name", "task_description", "assigned_to"),
    "TaskCompleted": (
        "task_id",
        "task_name",
        "task_description",
        "assigned_to",
        "result",
        "result_summary",
    ),
}

CLAUDE_EVENT_FIELDS = {
    event: tuple(fields) + CLAUDE_COMMON_FIELDS for event, fields in CLAUDE_EVENT_FIELDS.items()
}

ALL_EVENT_FIELDS = dict(EVENT_FIELDS)
ALL_EVENT_FIELDS.update(CLAUDE_EVENT_FIELDS)

MUTATING_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


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
        # Cursor stringifies JSON output.
        try:
            parsed["tool_output_parsed"] = json.loads(parsed["tool_output"])
        except json.JSONDecodeError:
            parsed["tool_output_parsed"] = None
    if event_name in CLAUDE_EVENT_FIELDS:
        _normalize_claude(parsed)
    parsed["cwd"] = data.get("cwd") or data.get("working_directory") or ""
    parsed["workspace_roots"] = data.get("workspace_roots") or []
    return parsed


def _normalize_claude(parsed: Dict[str, Any]) -> None:
    """Flatten `tool_input` so Claude events reach the gates in Cursor's shape.

    The shell gate reads `command`; receipt invalidation reads `file_path`. Both
    arrive nested under `tool_input` on Claude's PreToolUse/PostToolUse.
    """
    raw_input = parsed.get("tool_input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    tool_name = parsed.get("tool_name") or ""
    if tool_name == "Bash":
        parsed["command"] = tool_input.get("command") or ""
    if tool_name in MUTATING_TOOLS:
        parsed["file_path"] = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    parsed["stop_hook_active"] = bool(parsed.get("stop_hook_active"))


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
