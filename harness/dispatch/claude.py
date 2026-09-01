"""Claude Code hook event dispatcher.

Event names, payload shape, and response envelope are Claude Code's. The
decisions come from the same `lib.receipts` / `lib.shell_gate` primitives the
Cursor dispatcher uses, so a rule change lands on both hosts at once.

Three capabilities have no Cursor equivalent and are implemented here:

* `SubagentStart` / `SubagentStop` carry `agent_type` and `agent_id`, so a
  returning critic's identity is bound by the host rather than asserted in its
  own prose.
* `TaskCompleted` can be rolled back, so a task cannot be marked done while its
  verification has no receipt at the current fingerprint.
* `Stop` honors a permission decision, so the turn cannot end on missing proof.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Tuple

from dispatch.common import mutation_cwd, required_for, resolve_root, root_for, roots, shell_decision, snap, wrong_root_note
from lib.attest_rewrite import rewrite as build_attest_rewrite
from lib.conformance import evaluate as evaluate_conformance, summarize as summarize_conformance
from lib.constants import RECOVERY_COMMAND, STATUS_PASS
from lib.ledger import append_record
from lib.fingerprint import changed_paths
from lib.paths import PathError, harness_root
from lib.receipts import evaluate_gate, increment_stop_loop, invalidate, stop_followup_allowed
from lib.schema import MUTATING_TOOLS, SchemaError, parse_event, sanitized_message

# Plugin userConfig booleans arrive as this environment variable. Default true,
# matching plugin.json -- set to "false" to disable the rewrite below without
# uninstalling the plugin, e.g. if it conflicts with another PreToolUse/Bash
# hook's own rewriting.
ATTEST_REWRITE_ENV = "CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE"

EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "Stop",
    "TaskCreated",
    "TaskCompleted",
)

# Events whose failure must never interrupt work. Anything not listed here is
# a gate: it fails closed.
OBSERVATIONAL = ("SessionStart", "PreCompact", "SubagentStart", "TaskCreated")

# Claude Code truncates very long injected context; the rule is short by design.
MAX_CONTEXT_BYTES = 8192

# The shared library speaks Cursor's command name. Under Claude Code the skill is
# plugin-namespaced, so every message that reaches a user is rewritten -- sending
# someone to a command that does not exist is worse than not naming one.
CLAUDE_RECOVERY_COMMAND = "/a911-harness:implementation-check"

RECOVERY_HINT = (
    "Proof is missing or stale. Run %s, then continue; an unvalidated summary is "
    "not a receipt." % CLAUDE_RECOVERY_COMMAND
)


def _localize(message: str) -> str:
    """Rewrite the shared library's Cursor command name for this host."""
    if not message:
        return message
    return message.replace(RECOVERY_COMMAND, CLAUDE_RECOVERY_COMMAND)


def _out(event_name: str, **fields: Any) -> Dict[str, Any]:
    """Build Claude Code's hookSpecificOutput envelope, omitting empty fields."""
    payload: Dict[str, Any] = {"hookEventName": event_name}
    for key, value in fields.items():
        if value not in (None, "", {}, []):
            payload[key] = value
    return {"hookSpecificOutput": payload}


def _deny(event_name: str, reason: str) -> Dict[str, Any]:
    return _out(
        event_name, permissionDecision="deny", permissionDecisionReason=_localize(reason)
    )


def _allow(event_name: str) -> Dict[str, Any]:
    return _out(event_name, permissionDecision="allow")


def _observe(event_name: str, root_id: str, cwd: str) -> None:
    append_record(
        {
            "kind": "observation",
            "event_id": event_name,
            "root": root_id,
            "worktree_id": cwd,
            "fingerprint": "",
            "status": STATUS_PASS,
        }
    )


def _resolve_root(payload: Mapping[str, Any], cwd: str) -> Tuple[str, str]:
    """(root_id, root_path) for this event, honoring linked worktrees.

    A user routinely has several concurrent worktrees of the same repository
    open at once (one per branch or task); `resolve_root` recognizes any of
    them via shared git history, not just whichever sits at the hardcoded
    default path, and returns that worktree's own path so everything
    downstream operates against the tree actually being worked in.
    """
    for candidate in (payload.get("file_path"), cwd):
        if not candidate:
            continue
        try:
            return resolve_root(str(candidate))
        except (PathError, SchemaError, KeyError):
            continue
    return "personal-harness", cwd


def _in_configured_root(cwd: str) -> bool:
    try:
        root_for(cwd)
        return True
    except (PathError, SchemaError, KeyError):
        return False


def _in_scope(*candidates: str) -> bool:
    """True when any candidate path resolves inside one of the four configured
    roots.

    Claude Code plugin hooks run for every session on the machine, unlike
    Cursor's project-scoped hooks, which only ever ran inside the four-root
    workspace. Without this check, any path outside those roots falls through
    to the personal-harness default and gets gated as if it were the harness
    itself, denying a mutation attempt in a completely unrelated repository, or
    nagging an idle session that never touched a configured root. The stated
    design is harness-local until a live scope probe records otherwise
    (docs/runtime-contract.md); this restores that boundary for a host whose
    hooks are not project-scoped.
    """
    return any(candidate and _in_configured_root(candidate) for candidate in candidates)


def _planning(payload: Mapping[str, Any]) -> bool:
    """Plan mode makes no durable change, so gates must not fight it."""
    return str(payload.get("permission_mode") or "") == "plan"


def handle_event(event_name: str, raw: bytes) -> Dict[str, Any]:
    try:
        payload = parse_event(event_name, raw)
    except SchemaError:
        # A malformed payload on a gate must not become an open door.
        if event_name in ("PreToolUse", "Stop", "TaskCompleted"):
            return _deny(event_name, sanitized_message("BLOCKED", "unknown"))
        return {}

    cwd = str(payload.get("cwd") or os.getcwd())
    root_id, root_path = _resolve_root(payload, cwd)

    if event_name == "SessionStart":
        _observe(event_name, root_id, cwd)
        return _out(event_name, additionalContext=_workspace_rule(cwd))
    if event_name == "PreCompact":
        _observe(event_name, root_id, cwd)
        return {}
    if event_name == "PreToolUse":
        return _pre_tool_use(event_name, payload, cwd)
    if event_name == "PostToolUse":
        return _post_tool_use(event_name, payload, root_id, root_path, cwd)
    if event_name == "SubagentStart":
        if _in_scope(cwd):
            _record_critic(event_name, "critic_dispatch", payload, root_id, root_path, cwd)
        return {}
    if event_name == "SubagentStop":
        if _in_scope(cwd):
            _record_critic(event_name, "critic_return", payload, root_id, root_path, cwd)
        return {}
    if event_name == "TaskCreated":
        _observe(event_name, root_id, cwd)
        return {}
    if event_name == "TaskCompleted":
        return _task_completed(event_name, payload, root_id, root_path, cwd)
    if event_name == "Stop":
        return _stop(event_name, payload, root_id, root_path, cwd)
    return {}


def _workspace_rule(cwd: str) -> str:
    """The always-on rule, injected only inside a configured root.

    A plugin cannot ship `.claude/rules/`, and `~/.claude/rules/` would apply to
    every unrelated project, so the rule arrives as session context instead.
    """
    if not _in_configured_root(cwd):
        return ""
    try:
        path = os.path.join(harness_root(), "docs", "workspace-rule.md")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read(MAX_CONTEXT_BYTES)
    except (OSError, PathError):
        return ""


def _pre_tool_use(event_name: str, payload: Mapping[str, Any], cwd: str) -> Dict[str, Any]:
    if str(payload.get("tool_name") or "") != "Bash":
        return {}
    if _planning(payload):
        return {}
    command = str(payload.get("command") or "")
    if not _in_scope(mutation_cwd(command, cwd), cwd):
        return {}
    decision = shell_decision(command, cwd)
    if decision["permission"] != "allow":
        return _deny(
            event_name,
            decision.get("message") or sanitized_message("BLOCKED", decision.get("root") or "unknown"),
        )
    if _attest_rewrite_enabled():
        rewritten = _maybe_attest_rewrite(command, cwd)
        if rewritten:
            return _out(event_name, permissionDecision="allow", updatedInput={"command": rewritten})
    return {}


def _attest_rewrite_enabled() -> bool:
    raw = os.environ.get(ATTEST_REWRITE_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in ("false", "0", "no", "off")


def _maybe_attest_rewrite(command: str, cwd: str) -> Optional[str]:
    """The attest-wrapped form of `command`, or None if nothing applies.

    Verification commands are not `git -C`-shaped, so the resolution target is
    just `cwd`, unlike the mutation-preflight path above.
    """
    try:
        root_id, root_path = resolve_root(cwd)
    except (PathError, SchemaError, KeyError):
        return None
    harness_cli = os.path.join(harness_root(), "harness", "cli.py")
    try:
        return build_attest_rewrite(root_id, root_path, command, harness_cli)
    except Exception:
        # Never let a rewrite failure block or mutate a command that was
        # already cleared to run.
        return None


def _post_tool_use(
    event_name: str, payload: Mapping[str, Any], root_id: str, root_path: str, cwd: str
) -> Dict[str, Any]:
    tool_name = str(payload.get("tool_name") or "")
    if tool_name not in MUTATING_TOOLS:
        _observe(event_name, root_id, cwd)
        return {}
    if not _in_scope(str(payload.get("file_path") or ""), cwd):
        return {}

    try:
        current = snap(root_id, root_path)
    except Exception:
        current = {"fingerprint": "unknown", "worktree_id": cwd}
    invalidate(root_id, current["worktree_id"], current.get("fingerprint") or "unknown")

    messages = []
    note = wrong_root_note(root_id, str(payload.get("file_path") or ""), root_path)
    if note:
        messages.append(note)
    # Scope creep is only visible here: nothing downstream knows what the plan
    # declared. Warn while editing; the Stop gate is what actually blocks.
    drift = _conformance_message(root_id, root_path, current.get("worktree_id") or cwd)
    if drift:
        messages.append(drift)
    if messages:
        return _out(event_name, systemMessage="\n".join(messages))
    return {}


def _conformance_message(root_id: str, root_path: str, worktree_id: str) -> str:
    try:
        if not root_path:
            return ""
        result = evaluate_conformance(root_id, worktree_id, changed_paths(root_path))
        return summarize_conformance(result)
    except Exception:
        # Observational: a conformance failure must never block an edit.
        return ""


def _record_critic(
    event_name: str, kind: str, payload: Mapping[str, Any], root_id: str, root_path: str, cwd: str
) -> None:
    """Persist a critic dispatch or return with host-supplied identity."""
    try:
        current = snap(root_id, root_path)
    except Exception:
        current = {"fingerprint": "", "worktree_id": cwd, "plan_hash": ""}
    append_record(
        {
            "kind": kind,
            "event_id": event_name,
            "root": root_id,
            "worktree_id": current.get("worktree_id") or cwd,
            "fingerprint": current.get("fingerprint") or "",
            "plan_hash": current.get("plan_hash") or "",
            "critic_id": str(payload.get("agent_type") or ""),
            "agent_id": str(payload.get("agent_id") or ""),
            "session_id": str(payload.get("session_id") or ""),
            "status": STATUS_PASS,
        }
    )


def _gate_for(root_id: str, root_path: str, family: str) -> Dict[str, Any]:
    """The full mutation gate, including the blanket review requirement.

    This is the actual enforcement boundary: a commit or push must not
    proceed without a review receipt. Used only by the PreToolUse mutation
    preflight -- Stop and TaskCompleted use `_end_of_turn_gate` instead.
    """
    try:
        current = snap(root_id, root_path)
    except Exception:
        return {"status": "INCONCLUSIVE", "agent_message": sanitized_message("BLOCKED", root_id, "fingerprint")}
    required, registered = required_for(
        root_id, family, current.get("plan_hash") or "", current.get("worktree_id") or root_path, root_path
    )
    return evaluate_gate(
        root_id,
        current.get("worktree_id") or root_path,
        current.get("fingerprint") or "",
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
    )


def _end_of_turn_gate(root_id: str, root_path: str) -> Dict[str, Any]:
    """Path-triggered obligations only, deliberately excluding the blanket
    review requirement `_gate_for` adds for an actual commit.

    `default_required()` (shared with Cursor) appends `review.<tier>`
    unconditionally on every call, regardless of whether anything relevant
    changed. Wiring that into Stop and TaskCompleted meant every turn in
    every session touching a configured root demanded a review receipt --
    nagging that fired on ordinary iteration with no commit anywhere in
    sight. The commit itself is still fully gated by `_gate_for` in
    `_pre_tool_use`, which is the point that actually matters. This keeps
    only the specific, path-triggered checks -- stale generated files,
    missing rendered evidence for a real UI change -- that fire for a
    concrete, named reason instead of unconditionally.
    """
    from lib.ledger import current_state
    from lib.obligations import required_ids, triggered_obligations
    from lib.receipts import active_plan

    try:
        current = snap(root_id, root_path)
        paths = changed_paths(root_path)
    except Exception:
        return {"status": STATUS_PASS}

    ui_touched = bool(triggered_obligations(root_id, paths))
    required = required_ids(root_id, paths, user_visible=ui_touched, existing_surface=False)
    if not required:
        return {"status": STATUS_PASS}

    try:
        registered = active_plan(current_state(), root_id, current.get("worktree_id") or root_path)
    except Exception:
        registered = {}
    return evaluate_gate(
        root_id,
        current.get("worktree_id") or root_path,
        current.get("fingerprint") or "",
        required_obligation_ids=required,
        plan_hash=registered.get("plan_hash") or current.get("plan_hash") or "",
        tier=registered.get("tier") or "T0",
    )


def _task_completed(
    event_name: str, payload: Mapping[str, Any], root_id: str, root_path: str, cwd: str
) -> Dict[str, Any]:
    if not _in_scope(cwd):
        return {}
    if _planning(payload):
        return {}
    if str(payload.get("result") or "") != "success":
        return {}
    gate = _end_of_turn_gate(root_id, root_path)
    if gate.get("status") == STATUS_PASS:
        return {}
    return _deny(event_name, gate.get("agent_message") or RECOVERY_HINT)


def _stop(
    event_name: str, payload: Mapping[str, Any], root_id: str, root_path: str, cwd: str
) -> Dict[str, Any]:
    if not _in_scope(cwd):
        return {}
    if _planning(payload):
        return {}
    session_id = str(payload.get("session_id") or "default")
    try:
        current = snap(root_id, root_path)
    except Exception:
        current = {"worktree_id": cwd}
    count = increment_stop_loop(current.get("worktree_id") or cwd, session_id)
    # Never trap the turn: after the bounded number of follow-ups, let it end.
    if not stop_followup_allowed(count):
        return {}
    gate = _end_of_turn_gate(root_id, root_path)
    drift = _conformance_message(root_id, root_path, current.get("worktree_id") or cwd)
    if gate.get("status") == STATUS_PASS and not drift:
        return {}
    reason = gate.get("agent_message") or RECOVERY_HINT
    if drift:
        # Plan drift is more specific and more actionable than a missing receipt,
        # so lead with it.
        reason = "%s | %s" % (drift, reason)
    return _out(
        event_name,
        permissionDecision="deny",
        permissionDecisionReason=_localize(reason),
        systemMessage=RECOVERY_HINT,
    )


def run(event_name: str, raw: bytes) -> Dict[str, Any]:
    """Fail open on observational events; fail closed on gates."""
    try:
        return handle_event(event_name, raw)
    except Exception:
        if event_name in OBSERVATIONAL:
            return {}
        return _deny(event_name, sanitized_message("BLOCKED", "unknown"))
