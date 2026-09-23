"""Mine local Cursor transcripts into gitignored eval episodes.

Transcript text never leaves the machine here. Live Jev calls happen only in
`run_routing`, and only against hand-minimized cases.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import random
import re
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .jev_provenance import read_observations, read_turn_events, turns_dir
from .jev_redaction import sanitize_user_request
from .paths import configured_roots, runtime_dir

HARNESS_SKILLS = frozenset(
    {
        "plan-check",
        "adversarial-review",
        "implementation-check",
        "harness-health-check",
        "capture-evidence",
        "ponytail-review",
    }
)
FAILURE_KINDS = (
    "routing",
    "gate-false-deny",
    "gate-miss",
    "tier",
    "plan-check",
    "critic",
    "budget",
    "none",
)
LABEL_FIELDS = ("episode_id", "failure_kind", "expected", "note")
ASSISTANT_TURN_LIMIT = 60
SMOKE_SAMPLE = 10
SMOKE_SEED = 911

_USER_QUERY = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
_TIMESTAMP = re.compile(r"<timestamp>(.*?)</timestamp>")
_SKILL = re.compile(r"skills/([\w-]+)/SKILL\.md")
_CLI = re.compile(r"harness/cli\.py(?:\s+jev)?\s+([\w-]+)")
_CORRECTION = re.compile(
    r"^\s*(no[,. ]|actually|stop\b|that'?s wrong|that is wrong|wrong\b|don'?t\b|do not\b|why did you|you didn'?t|revert\b|undo\b)",
    re.I,
)

RouteFn = Callable[[str], Mapping[str, Any]]


def evals_dir(base: Optional[str] = None) -> str:
    path = os.path.join(base or runtime_dir(), "evals")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def episodes_path(base: Optional[str] = None) -> str:
    return os.path.join(evals_dir(base), "episodes.jsonl")


def flags_path(base: Optional[str] = None) -> str:
    return os.path.join(evals_dir(base), "flags.jsonl")


def labels_path(base: Optional[str] = None) -> str:
    return os.path.join(evals_dir(base), "labels.jsonl")


def default_cases_path(harness: Optional[str] = None) -> str:
    root = harness or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(root, "evals", "jev-routing", "cases.jsonl")


def promotion_target(kind: str) -> str:
    """Committed path a labeled failure is copied into. Empty when it stays local."""
    if kind in ("gate-false-deny", "gate-miss", "tier"):
        return "harness/tests/fixtures/core819_regression_cases.json"
    if kind == "routing":
        return "evals/jev-routing/cases.jsonl"
    if kind in ("plan-check", "critic"):
        return ".cursor/skills/adversarial-review/evals/seeded-design-system-cases.md"
    return ""


def label_errors(record: Mapping[str, Any]) -> List[str]:
    """Schema check for one hand-written labels.jsonl row."""
    errors: List[str] = []
    for field in LABEL_FIELDS:
        if field not in record:
            errors.append("missing-%s" % field)
    kind = str(record.get("failure_kind") or "")
    if kind and kind not in FAILURE_KINDS:
        errors.append("unknown-failure-kind")
    return errors


def _cursor_project_name(path: str) -> str:
    return path.lstrip("/").replace("/", "-")


def _configured_project_names(roots: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for root_id, root_path in (roots or configured_roots()).items():
        names[_cursor_project_name(os.path.realpath(root_path))] = root_id
    return names


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
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
                rows.append(parsed)
    return rows


def _write_jsonl(path: str, rows: Sequence[Mapping[str, Any]]) -> None:
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    os.chmod(path, 0o600)


def _query_text(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    chunks: List[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            chunks.append(str(part.get("text") or ""))
    blob = "\n".join(chunks)
    match = _USER_QUERY.search(blob)
    return match.group(1).strip() if match else ""


def _tool_blob(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    pieces: List[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "tool_use":
            try:
                pieces.append(json.dumps(part.get("input") or {}))
            except (TypeError, ValueError):
                continue
    return "\n".join(pieces)


def _is_correction(query: str) -> bool:
    return bool(_CORRECTION.search(query or ""))


def _episode_id(conversation_id: str, index: int) -> str:
    digest = hashlib.sha256(("%s:%s" % (conversation_id, index)).encode("utf-8")).hexdigest()
    return digest[:16]


def parse_transcript(path: str, *, root_id: str) -> List[Dict[str, Any]]:
    """One episode per user turn. Excerpts are redacted and bounded."""
    conversation_id = os.path.splitext(os.path.basename(path))[0]
    raw: List[Tuple[int, str, Mapping[str, Any]]] = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for lineno, line in enumerate(handle, 1):
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict) and parsed.get("role") in ("user", "assistant"):
                raw.append((lineno, str(parsed.get("role")), parsed.get("message") or {}))

    assistant_turns = sum(1 for _lineno, role, _message in raw if role == "assistant")
    user_indexes = [i for i, (_lineno, role, _message) in enumerate(raw) if role == "user"]
    episodes: List[Dict[str, Any]] = []
    for turn_index, start in enumerate(user_indexes):
        end = user_indexes[turn_index + 1] if turn_index + 1 < len(user_indexes) else len(raw)
        lineno, _role, message = raw[start]
        query = _query_text(message)
        if not query:
            continue
        timestamp = ""
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    stamp = _TIMESTAMP.search(str(part.get("text") or ""))
                    if stamp:
                        timestamp = stamp.group(1).strip()
                        break
        excerpt = sanitize_user_request(query)
        skills: List[str] = []
        commands: List[str] = []
        tool_calls = 0
        for _span_line, role, span_message in raw[start + 1 : end]:
            if role != "assistant":
                continue
            blob = _tool_blob(span_message)
            content = span_message.get("content")
            if isinstance(content, list):
                tool_calls += sum(1 for part in content if isinstance(part, dict) and part.get("type") == "tool_use")
            for skill in _SKILL.findall(blob):
                if skill not in skills:
                    skills.append(skill)
            for command in _CLI.findall(blob):
                commands.append(command)
        next_query = ""
        if turn_index + 1 < len(user_indexes):
            next_query = _query_text(raw[user_indexes[turn_index + 1]][2])
        episodes.append(
            {
                "episode_id": _episode_id(conversation_id, turn_index),
                "conversation_id": conversation_id,
                "root_id": root_id,
                "source_path": path,
                "line": lineno,
                "turn_index": turn_index,
                "timestamp": timestamp,
                "query_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "excerpt": excerpt,
                "skills": skills,
                "commands": commands,
                "tool_calls": tool_calls,
                "next_is_correction": _is_correction(next_query),
                "assistant_turns": assistant_turns,
            }
        )
    return episodes


def _join_jev(episodes: List[Dict[str, Any]], *, base: Optional[str]) -> None:
    events = read_turn_events(base)
    by_conversation: Dict[str, Dict[str, bool]] = {}
    for event in events:
        turn_id = str(event.get("turn_id") or "")
        # turn ids are "<conversation uuid>-<generation uuid>".
        if len(turn_id) < 36:
            continue
        conversation_id = turn_id[:36]
        bucket = by_conversation.setdefault(conversation_id, {"eligible": False, "routed": False, "delivered": False})
        kind = str(event.get("kind") or "")
        if kind in bucket:
            bucket[kind] = True

    results: Dict[str, List[Dict[str, Any]]] = {}
    folder = turns_dir(base)
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if not name.endswith(".json") or name.endswith(".meta.json"):
                continue
            conversation_id = name[:36]
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    parsed = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(parsed, dict):
                results.setdefault(conversation_id, []).append(parsed)

    for episode in episodes:
        conversation_id = str(episode.get("conversation_id") or "")
        ledger = by_conversation.get(conversation_id, {"eligible": False, "routed": False, "delivered": False})
        actions = []
        for result in results.get(conversation_id, []):
            action = str(result.get("policy_action") or "")
            if action and action not in actions:
                actions.append(action)
        episode["jev"] = {
            "eligible": bool(ledger["eligible"]),
            "routed": bool(ledger["routed"]),
            "delivered": bool(ledger["delivered"]),
            "policy_action": actions[0] if len(actions) == 1 else ",".join(actions),
            "routed_skill": next(
                (str(item.get("skill_id") or "") for item in results.get(conversation_id, []) if item.get("skill_id")),
                "",
            ),
        }


def discover_transcripts(projects_dir: str) -> List[str]:
    pattern = os.path.join(projects_dir, "*", "agent-transcripts", "*", "*.jsonl")
    return sorted(glob.glob(pattern))


def mine(
    *,
    projects_dir: str,
    base: Optional[str] = None,
    roots: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Incrementally parse configured-root transcripts, plus any chat that calls the harness CLI."""
    names = _configured_project_names(roots)
    index_path = os.path.join(evals_dir(base), "index.json")
    index: Dict[str, float] = {}
    if os.path.isfile(index_path):
        try:
            with open(index_path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                index = {str(key): float(value) for key, value in loaded.items()}
        except (OSError, ValueError, TypeError):
            index = {}
    previous: Dict[str, List[Dict[str, Any]]] = {}
    for row in _read_jsonl(episodes_path(base)):
        previous.setdefault(str(row.get("source_path") or ""), []).append(row)

    kept: List[Dict[str, Any]] = []
    parsed = 0
    reused = 0
    for path in discover_transcripts(projects_dir):
        project = path.split(os.sep + "agent-transcripts" + os.sep, 1)[0]
        project_name = os.path.basename(project)
        root_id = names.get(project_name, "")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if index.get(path) == mtime and path in previous:
            kept.extend(previous[path])
            reused += 1
            continue
        if not root_id:
            try:
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    blob = handle.read()
            except OSError:
                continue
            if "harness/cli.py" not in blob:
                continue
            root_id = "unconfigured"
        kept.extend(parse_transcript(path, root_id=root_id))
        index[path] = mtime
        parsed += 1

    _join_jev(kept, base=base)
    _write_jsonl(episodes_path(base), kept)
    fd = os.open(index_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(index, handle)
    os.chmod(index_path, 0o600)
    return {"episodes": len(kept), "parsed": parsed, "reused": reused}


def _harness_step(episode: Mapping[str, Any]) -> bool:
    if any(skill in HARNESS_SKILLS for skill in episode.get("skills") or []):
        return True
    return bool(episode.get("commands"))


def flag_episodes(episodes: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Rank episodes that look like harness failures. No model calls."""
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for episode in episodes:
        grouped.setdefault(str(episode.get("conversation_id") or ""), []).append(episode)
    flags: List[Dict[str, Any]] = []
    for conversation_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda item: int(item.get("turn_index") or 0))
        budget_marked = False
        for index, episode in enumerate(ordered):
            reasons: List[str] = []
            if _harness_step(episode) and any(
                bool(item.get("next_is_correction")) for item in ordered[index : index + 2]
            ):
                reasons.append("correction-after-harness")
            counts: Dict[str, int] = {}
            for command in episode.get("commands") or []:
                counts[str(command)] = counts.get(str(command), 0) + 1
            if any(count >= 3 for count in counts.values()):
                reasons.append("retry-loop")
            skills = [str(skill) for skill in episode.get("skills") or []]
            routed_skill = str((episode.get("jev") or {}).get("routed_skill") or "")
            policy = str((episode.get("jev") or {}).get("policy_action") or "")
            if routed_skill and skills and routed_skill.split("#")[-1] not in skills and "route" in policy:
                reasons.append("route-skill-mismatch")
            if "fallback" in policy and len(skills) == 1:
                reasons.append("fallback-single-skill")
            if int(episode.get("assistant_turns") or 0) > ASSISTANT_TURN_LIMIT and not budget_marked:
                reasons.append("over-budget")
                budget_marked = True
            if "plan-check" in skills and episode.get("next_is_correction"):
                reasons.append("plan-check-override")
            if not reasons:
                continue
            flags.append(
                {
                    "episode_id": episode.get("episode_id"),
                    "conversation_id": conversation_id,
                    "source_path": episode.get("source_path"),
                    "line": episode.get("line"),
                    "reasons": reasons,
                    "weight": len(reasons),
                    "excerpt": episode.get("excerpt") or "",
                }
            )
    flags.sort(key=lambda item: (-int(item["weight"]), str(item.get("episode_id") or "")))
    return flags


def write_flags(episodes: Sequence[Mapping[str, Any]], *, base: Optional[str] = None) -> List[Dict[str, Any]]:
    flags = flag_episodes(episodes)
    _write_jsonl(flags_path(base), flags)
    return flags


def report(*, base: Optional[str] = None, episodes: Optional[Sequence[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    """Outcome metrics from episodes and the Jev ledgers. No model calls."""
    observations = read_observations(base)
    events = read_turn_events(base)
    rows = list(episodes) if episodes is not None else _read_jsonl(episodes_path(base))

    def _count(question_set: str, reason: str) -> int:
        return sum(
            1
            for item in observations
            if item.get("question_set") == question_set and item.get("fallback_reason") == reason
        )

    def _set_count(question_set: str) -> int:
        return sum(1 for item in observations if item.get("question_set") == question_set)

    eligible_ids = {str(item.get("turn_id") or "") for item in events if item.get("kind") == "eligible"}
    delivered_ids = {str(item.get("turn_id") or "") for item in events if item.get("kind") == "delivered"}
    input_tokens = 0
    for item in observations:
        usage = item.get("usage") or {}
        if isinstance(usage, dict):
            input_tokens += int(usage.get("input_tokens") or 0)
    flags = flag_episodes(rows)
    conversations = {str(item.get("conversation_id") or "") for item in rows}
    over_budget = {str(item.get("conversation_id") or "") for item in flags if "over-budget" in (item.get("reasons") or [])}
    assistant_total = 0
    seen = set()
    for item in rows:
        conversation_id = str(item.get("conversation_id") or "")
        if conversation_id in seen:
            continue
        seen.add(conversation_id)
        assistant_total += int(item.get("assistant_turns") or 0)
    eligible_count = len(eligible_ids)
    return {
        "route_task_rank": _set_count("route-task-rank"),
        "route_task_rank_low_confidence": _count("route-task-rank", "low-confidence-or-no-match"),
        "rank_docs": _set_count("rank-docs"),
        "rank_docs_empty": _count("rank-docs", "docs-rank-empty"),
        "eligible_turns": eligible_count,
        "delivered_turns": len(delivered_ids & eligible_ids) if eligible_ids else len(delivered_ids),
        "input_tokens": input_tokens,
        "input_tokens_per_eligible": (input_tokens / float(eligible_count)) if eligible_count else 0,
        "corrections_after_harness": sum(1 for item in flags if "correction-after-harness" in item["reasons"]),
        "retry_loops": sum(1 for item in flags if "retry-loop" in item["reasons"]),
        "sessions": len(conversations),
        "assistant_turns_per_session": (assistant_total / float(len(seen))) if seen else 0,
        "over_budget_sessions": len(over_budget),
    }


def _usage_tokens(decision: Mapping[str, Any]) -> int:
    total = 0
    jev = decision.get("jev")
    if not isinstance(jev, dict):
        return 0
    for value in jev.values():
        if isinstance(value, dict):
            usage = value.get("usage") or {}
            if isinstance(usage, dict):
                total += int(usage.get("input_tokens") or 0)
    return total


def run_routing(
    cases_path: str,
    *,
    sample: Optional[int] = None,
    seed: int = SMOKE_SEED,
    route: Optional[RouteFn] = None,
) -> Dict[str, Any]:
    """Score hand-minimized routing cases. `expected` is a skill id or `abstain`."""
    cases = _read_jsonl(cases_path)
    if sample is not None and sample < len(cases):
        picker = random.Random(seed)
        cases = picker.sample(cases, sample)
    if not cases:
        return {"cases": 0, "skipped": "no cases", "precision": None, "abstain_rate": None, "input_tokens": 0}
    if route is None:
        from .judgments import route_task

        route = route_task
    correct = 0
    abstained = 0
    tokens = 0
    for case in cases:
        expected = str(case.get("expected") or "")
        decision = route(str(case.get("request") or ""))
        tokens += _usage_tokens(decision)
        action = str(decision.get("policy_action") or "")
        if action != "route":
            abstained += 1
        if expected == "abstain":
            if action != "route":
                correct += 1
            continue
        skill_id = str(decision.get("decision") or "")
        if not skill_id and decision.get("skill_root"):
            skill_id = "%s#%s" % (decision.get("skill_root"), decision.get("skill"))
        if action == "route" and skill_id == expected:
            correct += 1
    count = len(cases)
    return {
        "cases": count,
        "correct": correct,
        "precision": correct / float(count),
        "abstain_rate": abstained / float(count),
        "input_tokens": tokens,
        "input_tokens_per_case": tokens / float(count),
    }


def format_flags(flags: Sequence[Mapping[str, Any]], *, limit: int = 30) -> str:
    lines = []
    for item in list(flags)[:limit]:
        lines.append(
            "%s  %s:%s  %s"
            % (
                ",".join(item.get("reasons") or []),
                item.get("source_path") or "",
                item.get("line") or "",
                item.get("episode_id") or "",
            )
        )
    return "\n".join(lines)


def cmd_evals(argv: Sequence[str]) -> int:
    """`evals mine|flag|report|daily|run`."""
    args = list(argv)
    as_json = "--json" in args
    if as_json:
        args = [item for item in args if item != "--json"]
    if not args:
        sys.stderr.write("evals: missing subcommand\n")
        return 2
    command = args[0]
    projects = os.path.expanduser("~/.cursor/projects")
    if command == "mine":
        summary = mine(projects_dir=projects)
        return _emit(summary, as_json=as_json)
    if command == "flag":
        flags = write_flags(_read_jsonl(episodes_path()))
        if as_json:
            return _emit({"flags": flags}, as_json=True)
        sys.stdout.write(format_flags(flags) + ("\n" if flags else ""))
        return 0
    if command == "report":
        return _emit(report(), as_json=as_json or True)
    if command == "daily":
        mined = mine(projects_dir=projects)
        flags = write_flags(_read_jsonl(episodes_path()))
        payload = {"mine": mined, "flags": len(flags), "report": report()}
        return _emit(payload, as_json=True)
    if command == "run" and len(args) >= 2 and args[1] == "routing":
        sample = None
        cases = default_cases_path()
        rest = args[2:]
        index = 0
        while index < len(rest):
            if rest[index] == "--sample" and index + 1 < len(rest):
                sample = int(rest[index + 1])
                index += 2
                continue
            if rest[index] == "--cases" and index + 1 < len(rest):
                cases = rest[index + 1]
                index += 2
                continue
            sys.stderr.write("evals run routing: unknown argument %s\n" % rest[index])
            return 2
        return _emit(run_routing(cases, sample=sample), as_json=True)
    sys.stderr.write("evals: unknown subcommand %s\n" % command)
    return 2


def _emit(payload: Mapping[str, Any], *, as_json: bool) -> int:
    if as_json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for key, value in payload.items():
            sys.stdout.write("%s=%s\n" % (key, value))
    return 0
