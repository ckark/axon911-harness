"""Shared versions and limits for the runtime contract."""

from __future__ import annotations

FINGERPRINT_VERSION = "2"
OBLIGATION_SCHEMA_VERSION = "2"
COMMAND_SPEC_VERSION = "2"
VERIFIER_VERSION = "2"
LEDGER_VERSION = 1
MAX_EVENT_BYTES = 65536
LOCK_TIMEOUT_S = 2.0
SEGMENT_MAX_BYTES = 10 * 1024 * 1024
SEGMENT_MAX_AGE_S = 7 * 24 * 60 * 60
RETENTION_S = 30 * 24 * 60 * 60
STOP_LOOP_LIMIT = 3
# axon911-frontend first: it owns @prepared/ui-* post CORE-754 and is the
# architectural authority for the Axon 911 ecosystem. Membership is what the
# code checks; the order documents precedence for readers.
ROOT_IDS = (
    "axon911-frontend",
    "prepared911",
    "vault-core-ux",
    "personal-harness",
)
ALLOWED_PERSISTED_FIELDS = (
    "version",
    "kind",
    "event_id",
    "obligation_id",
    "root",
    "worktree_id",
    "session_id",
    "fingerprint",
    "plan_hash",
    "status",
    "exit_status",
    "duration_ms",
    "ts",
    "evidence_pointer",
    "tier",
    "critic_id",
    "confined",
    "confined_paths",
    # Root-relative path globs a plan declared as its scope. Metadata about the
    # plan, not content from it: no diffs, prose, or commands are persisted.
    "scope",
    "base_oid",
    "mirror_intent",
    "path_surfaces",
    "plan_context_hash",
    "evidence_kind",
    "change_id",
    "capture_story_id",
    "capture_theme",
    "capture_brand",
    "capture_viewport",
    "capture_state",
    "artifact_hash",
    "artifact_size",
    "phase",
    "handoff",
    "changed_paths",
    "obligation_statuses",
    "command_spec_version",
    "schema_version",
    "seq",
    "prev_hash",
    "receipt_id",
    "nonce",
)
STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"
STATUS_INCONCLUSIVE = "INCONCLUSIVE"
RECOVERY_COMMAND = "/implementation-check"
REVIEW_MODE_OFF = "off"
REVIEW_MODE_ON_REQUEST = "on-request"
REVIEW_MODE_ALWAYS = "always"
