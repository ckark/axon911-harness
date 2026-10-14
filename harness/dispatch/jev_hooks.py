#!/usr/bin/env python3
"""User-level Cursor hooks that compute Jev routing and plan preflight.

Every handler fails open: a crash, a missing field, or a Jev error never
blocks the prompt or the tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from lib.jev_policy import MID_NOUL  # noqa: E402
from lib.jev_provenance import append_turn_event, runtime_dir, turns_dir  # noqa: E402
from lib.jev_redaction import sanitize_excerpt, sanitize_user_request  # noqa: E402
from lib.judgments import (  # noqa: E402
    DOC_MENU,
    assess_plan,
    rank_docs,
    route_task,
    skill_path_for,
)
from lib.paths import PathError, harness_root, identify_root  # noqa: E402

RESULT_TTL_S = 300
MAX_TOOL_CALLS = 10
PLAN_ASSESS_TIMEOUT_S = 15
CREATE_PLAN_TOOLS = {"createplan", "create_plan"}
PLAN_SECTIONS = (
    "Target roots",
    "Ref manifest",
    "Self-authored claim ledger",
    "Blast radius and tier",
    "Affected consumers",
    "Verification plan",
    "Generated-artifact and docs obligations",
    "Deferred and out-of-scope",
)
DOC_RELATIVE = {
    "plan-contract": os.path.join("docs", "plan-contract.md"),
    "review-contract": os.path.join("docs", "review-contract.md"),
    "routing-matrix": os.path.join("docs", "routing-matrix.md"),
    "evidence-capture": os.path.join(
        ".cursor", "skills", "adversarial-review", "references", "evidence-capture.md"
    ),
    "implementation-contract": os.path.join("docs", "implementation-contract.md"),
    "session-budget": os.path.join("docs", "session-budget.md"),
}

Spawn = Callable[[str], None]


def _safe_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    return cleaned[:80]


def turn_key(payload: Mapping[str, Any]) -> str:
    """Stable per-turn filename stem. `conversation_id` alone is enough."""
    conversation = _safe_token(str(payload.get("conversation_id") or ""))
    generation = _safe_token(str(payload.get("generation_id") or ""))
    if conversation and generation:
        return "%s-%s" % (conversation, generation)
    if conversation:
        return conversation
    digest = hashlib.sha256(json.dumps(sorted(payload.keys())).encode("utf-8")).hexdigest()[:12]
    return "anon-%s" % digest


def conversation_hash(payload: Mapping[str, Any]) -> str:
    raw = str(payload.get("conversation_id") or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_private(path: str, text: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            parsed = json.load(handle)
    except (OSError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _registered_workspace(payload: Mapping[str, Any]) -> bool:
    roots = payload.get("workspace_roots")
    if not isinstance(roots, list):
        return False
    for item in roots:
        if not isinstance(item, str) or not item:
            continue
        try:
            identify_root(item)
        except PathError:
            continue
        else:
            return True
    return False


def _recording_enabled() -> bool:
    return os.environ.get("HARNESS_JEV_RECORD", "1") == "1"


def _slash_prompt(prompt: str) -> bool:
    return prompt.lstrip().startswith("/")


def request_path(key: str) -> str:
    return os.path.join(turns_dir(), "request-%s.txt" % key)


def result_path(key: str) -> str:
    return os.path.join(turns_dir(), "%s.json" % key)


def meta_path(key: str) -> str:
    return os.path.join(turns_dir(), "%s.meta.json" % key)


def default_spawn(path: str) -> None:
    """Start the worker detached. The prompt stays in the temp file, not argv."""
    cli = os.path.join(HARNESS_DIR, "cli.py")
    subprocess.Popen(
        [sys.executable, cli, "jev", "hook-turn", "--turn", path],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.dirname(HARNESS_DIR),
        env=os.environ.copy(),
    )


def handle_before_submit(payload: Mapping[str, Any], *, spawn: Spawn = default_spawn) -> Dict[str, Any]:
    """Queue routing for a registered-root prompt and return immediately."""
    allow = {"continue": True}
    if not _recording_enabled():
        return allow
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or _slash_prompt(prompt):
        return allow
    if not _registered_workspace(payload):
        return allow
    key = turn_key(payload)
    sanitized = sanitize_user_request(prompt)
    path = request_path(key)
    _write_private(path, sanitized)
    _write_private(
        meta_path(key),
        json.dumps({"ts": int(time.time()), "tool_calls": 0, "delivered": False}),
    )
    append_turn_event(
        {
            "kind": "eligible",
            "turn_id": key,
            "conversation_hash": conversation_hash(payload),
        }
    )
    try:
        spawn(path)
    except Exception:
        append_turn_event({"kind": "failed", "turn_id": key})
    return allow


def _doc_path(doc_id: str) -> str:
    relative = DOC_RELATIVE.get(doc_id)
    if not relative:
        return doc_id
    return os.path.join(harness_root(), relative)


def _routing_context(result: Mapping[str, Any]) -> str:
    action = result.get("policy_action")
    if action == "route":
        lead = (
            "Jev routed this request to %s; read %s and no other skill body."
            % (result.get("skill_id") or "unknown", result.get("skill_path") or "(missing)")
        )
    else:
        lead = "Jev routing abstained (%s). Choose the skill yourself." % (
            result.get("fallback_reason") or "fallback"
        )
    keep = result.get("keep") or []
    drop = result.get("drop") or []
    docs = "Harness contracts to read: %s." % (", ".join(keep) or "(none)")
    if result.get("docs_policy") == "fallback":
        docs = "Doc rank failed open; read every listed contract. " + docs
    unread = "Leave unread: %s." % (", ".join(drop) if drop else "(none)")
    return " ".join((lead, docs, unread))


def handle_post_tool(payload: Mapping[str, Any], *, now: Optional[float] = None) -> Dict[str, Any]:
    """Deliver a ready routing result once. No network call."""
    if not _recording_enabled():
        return {}
    key = turn_key(payload)
    meta_file = meta_path(key)
    if not os.path.isfile(meta_file):
        return {}
    meta = _read_json(meta_file)
    clock = time.time() if now is None else now
    calls = int(meta.get("tool_calls") or 0) + 1
    meta["tool_calls"] = calls
    started = float(meta.get("ts") or clock)
    expired = bool(meta.get("delivered")) or calls > MAX_TOOL_CALLS or (clock - started) > RESULT_TTL_S
    if expired:
        meta["dropped"] = not bool(meta.get("delivered"))
        _write_private(meta_file, json.dumps(meta))
        return {}
    ready = result_path(key)
    if not os.path.isfile(ready):
        _write_private(meta_file, json.dumps(meta))
        return {}
    result = _read_json(ready)
    meta["delivered"] = True
    _write_private(meta_file, json.dumps(meta))
    append_turn_event({"kind": "delivered", "turn_id": key})
    return {"additional_context": _routing_context(result)}


def missing_plan_sections(text: str) -> List[str]:
    """Headings required by the plan contract that the text does not contain."""
    missing: List[str] = []
    for section in PLAN_SECTIONS:
        pattern = r"(?im)^#{1,6}\s+%s\s*$" % re.escape(section)
        if re.search(pattern, text or "") is None:
            missing.append(section)
    return missing


def _plan_text(payload: Mapping[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    tool_output = payload.get("tool_output")
    candidates: List[str] = []
    for blob in (tool_output, tool_input):
        parsed: Any = blob
        if isinstance(blob, str):
            try:
                parsed = json.loads(blob)
            except ValueError:
                parsed = blob
        if isinstance(parsed, dict):
            for key in ("plan_path", "path", "file", "filePath", "uri"):
                value = parsed.get(key)
                if isinstance(value, str) and value.endswith(".md") and os.path.isfile(value):
                    with open(value, encoding="utf-8") as handle:
                        return handle.read()
            for key in ("plan", "contents", "overview"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value)
        elif isinstance(parsed, str) and parsed.strip():
            candidates.append(parsed)
    return "\n\n".join(candidates)


def plan_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def record_plan_assessment(text: str, status: str) -> str:
    digest = plan_hash(text)
    directory = os.path.join(runtime_dir(), "jev-plans")
    _write_private(
        os.path.join(directory, "%s.json" % digest),
        json.dumps({"ts": int(time.time()), "status": status}),
    )
    return digest


def _low_scores(decision: Mapping[str, Any]) -> List[str]:
    scores = decision.get("scores")
    if not isinstance(scores, dict):
        return []
    low: List[str] = []
    for key, value in scores.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number < MID_NOUL:
            low.append("%s=%.2f" % (key, number))
    return low


def handle_plan_preflight(
    payload: Mapping[str, Any],
    *,
    assess: Callable[..., Dict[str, Any]] = assess_plan,
) -> Dict[str, Any]:
    """Section check plus assess-plan. The section check runs even if Jev fails."""
    name = str(payload.get("tool_name") or "").replace("-", "").replace("_", "").lower()
    if name not in CREATE_PLAN_TOOLS and "createplan" not in name:
        return {}
    text = _plan_text(payload)
    missing = missing_plan_sections(text)
    lines = ["Plan preflight. Fix the plan file before handing it to the user."]
    if missing:
        lines.append("Missing plan-contract sections: %s." % ", ".join(missing))
    else:
        lines.append("All required plan-contract section headings are present.")
    status = "sections-only"
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(assess, sanitize_excerpt(text))
            decision = future.result(timeout=PLAN_ASSESS_TIMEOUT_S)
    except (FuturesTimeout, Exception):
        decision = {}
    if decision.get("policy_action") == "advisory":
        low = _low_scores(decision)
        if low:
            lines.append("Low assess-plan scores: %s." % ", ".join(low))
        else:
            lines.append("assess-plan did not flag a low score.")
        status = "assessed"
    else:
        lines.append("assess-plan failed open; the section check above still stands.")
        status = "inconclusive"
    if text.strip():
        record_plan_assessment(text, status)
    return {"additional_context": " ".join(lines)}


def run_hook_turn(
    path: str,
    *,
    route: Callable[..., Dict[str, Any]] = route_task,
    rank: Callable[..., Dict[str, Any]] = rank_docs,
) -> None:
    """Read the sanitized request, delete it, and write the routing result."""
    key = os.path.basename(path)
    if key.startswith("request-") and key.endswith(".txt"):
        key = key[len("request-") : -len(".txt")]
    request = ""
    try:
        with open(path, encoding="utf-8") as handle:
            request = handle.read()
    except OSError:
        append_turn_event({"kind": "failed", "turn_id": key})
        return
    try:
        os.remove(path)
    except OSError:
        pass
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            route_future = pool.submit(route, request)
            rank_future = pool.submit(rank, request)
            routed = route_future.result()
            ranked = rank_future.result()
    except Exception:
        append_turn_event({"kind": "failed", "turn_id": key})
        return
    skill_id = ""
    skill_file = ""
    if routed.get("policy_action") == "route":
        skill_id = "%s#%s" % (routed.get("skill_root") or "", routed.get("skill") or "")
        skill_file = skill_path_for(skill_id)
    keep_ids = list(ranked.get("keep") or [item[0] for item in DOC_MENU])
    drop_ids = list(ranked.get("drop") or [])
    payload = {
        "policy_action": routed.get("policy_action") or "fallback",
        "fallback_reason": routed.get("fallback_reason") or "",
        "skill_id": skill_id,
        "skill_path": skill_file,
        "docs_policy": ranked.get("policy_action") or "fallback",
        "keep": [_doc_path(item) for item in keep_ids],
        "drop": [_doc_path(item) for item in drop_ids],
    }
    _write_private(result_path(key), json.dumps(payload))
    append_turn_event({"kind": "routed", "turn_id": key})


def main(argv: Optional[Sequence[str]] = None, stdin: Optional[bytes] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    event = args[0] if args else ""
    raw = sys.stdin.buffer.read() if stdin is None else stdin
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        payload = parsed if isinstance(parsed, dict) else {}
    except (UnicodeDecodeError, ValueError):
        payload = {}
    try:
        if event == "beforeSubmitPrompt":
            output: Dict[str, Any] = handle_before_submit(payload)
        elif event == "postToolUse":
            output = handle_post_tool(payload)
        elif event == "planPreflight":
            output = handle_plan_preflight(payload)
        else:
            output = {"continue": True} if event == "beforeSubmitPrompt" else {}
    except Exception:
        output = {"continue": True} if event == "beforeSubmitPrompt" else {}
    json.dump(output, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
