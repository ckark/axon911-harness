"""Append-only JSONL ledger with locking, recovery, and a compact index."""

from __future__ import annotations

import fcntl
import json
import os
import time
from typing import Any, Dict, Iterator, List, Mapping, Optional

from .constants import (
    ALLOWED_PERSISTED_FIELDS,
    LEDGER_VERSION,
    LOCK_TIMEOUT_S,
    RETENTION_S,
    SEGMENT_MAX_AGE_S,
    SEGMENT_MAX_BYTES,
    STATUS_BLOCKED,
)
from .paths import runtime_dir


class LedgerError(RuntimeError):
    """Raised when the ledger is corrupt or unwritable."""


def _lock_path(base: str) -> str:
    return os.path.join(base, "ledger.lock")


def _index_path(base: str) -> str:
    return os.path.join(base, "state.json")


def _segments_dir(base: str) -> str:
    path = os.path.join(base, "ledger")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def acquire_lock(base: str, timeout_s: float = LOCK_TIMEOUT_S) -> Any:
    os.makedirs(base, mode=0o700, exist_ok=True)
    handle = open(_lock_path(base), "a+")
    os.chmod(_lock_path(base), 0o600)
    deadline = time.time() + timeout_s
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.time() >= deadline:
                handle.close()
                raise LedgerError("lock timeout")
            time.sleep(0.02)


def release_lock(handle: Any) -> None:
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def _open_nofollow(path: str, mode: str) -> Any:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if "a" in mode:
        flags |= os.O_APPEND
    fd = os.open(path, flags, 0o600)
    os.chmod(path, 0o600)
    return os.fdopen(fd, mode)


def _sanitize(record: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {"version": LEDGER_VERSION}
    for key, value in record.items():
        if key in ALLOWED_PERSISTED_FIELDS:
            clean[key] = value
    return clean


def _segment_paths(base: str) -> List[str]:
    directory = _segments_dir(base)
    names = sorted(name for name in os.listdir(directory) if name.endswith(".jsonl"))
    return [os.path.join(directory, name) for name in names]


def _current_segment(base: str, now: Optional[float] = None) -> str:
    stamp = now if now is not None else time.time()
    paths = _segment_paths(base)
    if paths:
        latest = paths[-1]
        age = stamp - os.path.getmtime(latest)
        size = os.path.getsize(latest)
        if size < SEGMENT_MAX_BYTES and age < SEGMENT_MAX_AGE_S:
            return latest
    name = "segment-%d.jsonl" % int(stamp)
    path = os.path.join(_segments_dir(base), name)
    _open_nofollow(path, "a").close()
    return path


def recover_segment(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "rb") as handle:
        data = handle.read()
    if not data:
        return
    lines = data.split(b"\n")
    kept = []
    for line in lines:
        if not line.strip():
            continue
        try:
            json.loads(line.decode("utf-8"))
            kept.append(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Truncated final record is dropped; earlier corrupt records fail closed.
            if line is lines[-1] or (line is lines[-2] and not lines[-1]):
                continue
            raise LedgerError("corrupt ledger record")
    rebuilt = b"\n".join(kept)
    if rebuilt:
        rebuilt += b"\n"
    tmp = path + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(rebuilt)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _ensure_clean_tail(path: str) -> None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb") as handle:
        handle.seek(-1, os.SEEK_END)
        last = handle.read(1)
    if last != b"\n":
        recover_segment(path)


def append_record(record: Mapping[str, Any], base: Optional[str] = None) -> Dict[str, Any]:
    runtime = base or runtime_dir()
    lock = acquire_lock(runtime)
    try:
        segment = _current_segment(runtime)
        _ensure_clean_tail(segment)
        clean = _sanitize(record)
        clean["ts"] = clean.get("ts") or time.time()
        index = _load_index(runtime)
        clean["seq"] = int(index.get("seq") or 0) + 1
        clean["prev_hash"] = index.get("tail_hash") or ""
        payload = json.dumps(clean, sort_keys=True, separators=(",", ":"))
        with _open_nofollow(segment, "a") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        index["seq"] = clean["seq"]
        index["tail_hash"] = _hash_line(payload)
        index["updated"] = clean["ts"]
        _apply_record_to_index(index, clean)
        _write_index(runtime, index)
        return clean
    finally:
        release_lock(lock)


def iter_records(base: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    runtime = base or runtime_dir()
    for path in _segment_paths(runtime):
        recover_segment(path)
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def _hash_line(payload: str) -> str:
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_index(base: str) -> Dict[str, Any]:
    path = _index_path(base)
    if not os.path.exists(path):
        return {
            "seq": 0,
            "tail_hash": "",
            "receipts": {},
            "invalidated": {},
            "sessions": {},
            "plans": {},
            "scopes": {},
            "profiles": {},
            "migration_manifests": {},
            "updated": 0,
        }
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            raise LedgerError("corrupt index")


def _write_index(base: str, index: Mapping[str, Any]) -> None:
    path = _index_path(base)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(index, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _apply_record_to_index(index: Dict[str, Any], record: Mapping[str, Any]) -> None:
    kind = record.get("kind")
    key = "%s:%s:%s" % (record.get("root"), record.get("worktree_id"), record.get("fingerprint"))
    receipts = index.setdefault("receipts", {})
    if kind in ("verification_receipt", "review_receipt", "visual_acceptance_receipt"):
        receipts.setdefault(key, [])
        receipts[key] = [
            item
            for item in receipts[key]
            if item.get("kind") != kind or item.get("obligation_id") != record.get("obligation_id")
        ]
        receipts[key].append(dict(record))
    if kind == "register_plan":
        plan_key = "%s:%s" % (record.get("root"), record.get("worktree_id"))
        index.setdefault("plans", {})[plan_key] = {
            "plan_hash": record.get("plan_hash") or "",
            "tier": record.get("tier") or "T0",
            "ts": record.get("ts"),
        }
    if kind == "plan_profile":
        plan_key = "%s:%s" % (record.get("root"), record.get("worktree_id"))
        index.setdefault("profiles", {})[plan_key] = {
            "plan_hash": record.get("plan_hash") or "",
            "tier": record.get("tier") or "T0",
            "scope": list(record.get("scope") or []),
            "required_paths": list(record.get("required_paths") or []),
            "target_roots": list(record.get("target_roots") or []),
            "base_oid": record.get("base_oid") or "",
            "mirror_intent": record.get("mirror_intent") or "",
            "path_surfaces": dict(record.get("path_surfaces") or {}),
            "evidence_manifest_pointer": record.get("evidence_manifest_pointer") or "",
            "evidence_states": dict(record.get("evidence_states") or {}),
            "execution_manifest_hash": record.get("execution_manifest_hash") or "",
            "strict": bool(record.get("strict")),
            "budget_max_turns": int(record.get("budget_max_turns") or 0),
            "budget_max_context_bytes": int(record.get("budget_max_context_bytes") or 0),
            "plan_context_hash": record.get("plan_context_hash") or "",
            "ts": record.get("ts"),
        }
        index.setdefault("plans", {})[plan_key] = {
            "plan_hash": record.get("plan_hash") or "",
            "tier": record.get("tier") or "T0",
            "ts": record.get("ts"),
        }
        index.setdefault("scopes", {})[plan_key] = {
            "scope": list(record.get("scope") or []),
            "plan_hash": record.get("plan_hash") or "",
            "ts": record.get("ts"),
        }
    if kind == "plan_scope":
        scope_key = "%s:%s" % (record.get("root"), record.get("worktree_id"))
        index.setdefault("scopes", {})[scope_key] = {
            "scope": list(record.get("scope") or []),
            "plan_hash": record.get("plan_hash") or "",
            "ts": record.get("ts"),
        }
    if kind == "evidence_record":
        evidence_key = "%s:%s:%s" % (
            record.get("root"),
            record.get("obligation_id"),
            record.get("evidence_kind"),
        )
        index.setdefault("evidence", {})[evidence_key] = dict(record)
    if kind == "migration_manifest_binding":
        manifest_key = "%s:%s" % (record.get("root"), record.get("worktree_id"))
        index.setdefault("migration_manifests", {})[manifest_key] = {
            "pointer": record.get("migration_manifest_pointer") or "",
            "plan_hash": record.get("plan_hash") or "",
            "ts": record.get("ts"),
        }
    if kind == "session_handoff":
        session_key = "%s:%s" % (record.get("worktree_id"), record.get("session_id"))
        index.setdefault("handoffs", {})[session_key] = dict(record.get("handoff") or record)
    if kind == "session_phase":
        session_key = "%s:%s" % (record.get("worktree_id"), record.get("session_id"))
        sessions = index.setdefault("sessions", {})
        current = dict(sessions.get(session_key) or {})
        current.update(
            {
                "phase": record.get("phase") or current.get("phase"),
                "stop_loops": current.get("stop_loops") or 0,
                "ts": record.get("ts"),
            }
        )
        sessions[session_key] = current
    if kind == "critic_return":
        # Deduped by critic identity: two returns from the same critic are one
        # critic, which is what tier cardinality actually means.
        bucket = index.setdefault("critics", {}).setdefault(key, {})
        bucket[str(record.get("critic_id") or "")] = {
            "agent_id": record.get("agent_id") or "",
            "plan_hash": record.get("plan_hash") or "",
            "ts": record.get("ts"),
        }
    if kind == "invalidate":
        index.setdefault("invalidated", {})[key] = record.get("ts")
        receipts.pop(key, None)
        # A changed tree invalidates who reviewed it, not just the receipts.
        index.setdefault("critics", {}).pop(key, None)
    if kind == "session_cursor":
        sessions = index.setdefault("sessions", {})
        session_key = "%s:%s" % (record.get("worktree_id"), record.get("session_id"))
        sessions[session_key] = {
            "stop_loops": record.get("exit_status") or 0,
            "ts": record.get("ts"),
        }


def validate_segments(base: Optional[str] = None) -> None:
    runtime = base or runtime_dir()
    for path in _segment_paths(runtime):
        recover_segment(path)


def current_state(base: Optional[str] = None, validate: bool = False) -> Dict[str, Any]:
    runtime = base or runtime_dir()
    lock = acquire_lock(runtime)
    try:
        if validate:
            validate_segments(runtime)
        return _load_index(runtime)
    finally:
        release_lock(lock)


def gc_segments(base: Optional[str] = None, now: Optional[float] = None) -> None:
    runtime = base or runtime_dir()
    stamp = now if now is not None else time.time()
    lock = acquire_lock(runtime)
    try:
        index = _load_index(runtime)
        active = set()
        for entries in (index.get("receipts") or {}).values():
            for entry in entries:
                if entry.get("evidence_pointer"):
                    active.add(entry["evidence_pointer"])
        for evidence in (index.get("evidence") or {}).values():
            pointer = evidence.get("evidence_pointer")
            if pointer:
                active.add(pointer)
        for path in _segment_paths(runtime):
            age = stamp - os.path.getmtime(path)
            if age > RETENTION_S and os.path.basename(path) not in active:
                os.remove(path)
        from .sessions import compact_runtime_state

        _write_index(runtime, compact_runtime_state(index))
    finally:
        release_lock(lock)


def fail_closed_status() -> str:
    return STATUS_BLOCKED
