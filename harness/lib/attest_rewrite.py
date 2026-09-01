"""Transparently route recognized verification commands through the attesting
wrapper, so a forgotten `cli.py attest` cannot produce an unrecorded PASS.

Scoped narrowly on purpose: only obligations that declare an exact `check`
command in `obligations.py` are eligible. That is six obligations today, all on
axon911-frontend (ui-allowlist, docs-registry, rendered-evidence, mf-types,
flag-manifest -- docs-page has no shell check, it is asserted by a human).
Matching is exact-string, not prefix or substring, because a near-miss like
`pnpm test:storybook:ci -- --shard=1/4` is a different invocation than the
plain form and attesting it under the same obligation id would be wrong.

This is the highest-risk piece of the port: `~/.claude/settings.json` already
binds PreToolUse/Bash to RTK's own hook, and the Vercel plugin binds PreToolUse
on Bash too, so three hooks can see the same command. The mitigations here are
idempotence (never re-wrap a command that already contains the wrapper) and a
`userConfig` kill switch (`attest_rewrite`, default true) -- see
`_maybe_attest_rewrite` in `dispatch/claude.py`. Live, multi-hook ordering
against the real RTK binary has not been exercised; this module's own behavior
is what the test suite covers.
"""

from __future__ import annotations

import os
import re
import shlex
from typing import Optional

from .fingerprint import snapshot
from .ledger import current_state
from .obligations import obligations_for
from .receipts import active_plan

# `rewrite()` shell-quotes the harness path with `shlex.quote()`, which adds a
# closing quote right after the filename when the path needs one (e.g. it
# contains a space) -- so the marker check allows an optional quote character
# between the filename and "attest" rather than requiring them adjacent.
ATTEST_MARKER_RE = re.compile(r"(cli\.py|runtime_gate\.py)[\"']?\s+attest\b")


def already_wrapped(command: str) -> bool:
    """True when the command already routes through the attesting wrapper."""
    return bool(ATTEST_MARKER_RE.search(command))


def _normalize(command: str) -> str:
    """Collapse whitespace and peel a bare `rtk ` prefix before matching.

    `rtk hook ...` is RTK's own hook invocation, not a user command, and is
    left untouched -- mirrors the same case in `shell_gate._strip_wrappers`.
    """
    text = " ".join(command.split())
    if text.startswith("rtk ") and not text.startswith(("rtk hook cursor", "rtk hook claude")):
        text = text[len("rtk ") :].lstrip()
    return text


def matching_obligation(root_id: str, command: str) -> Optional[str]:
    """The obligation id this exact command satisfies, if any."""
    normalized = _normalize(command)
    for obligation in obligations_for(root_id):
        check = obligation.get("check")
        if check and normalized == " ".join(check.split()):
            return str(obligation["id"])
    return None


def _active_plan_hash(root_id: str, root_path: str) -> str:
    try:
        current = snapshot(root_id, root_path, plan_hash="")
        registered = active_plan(current_state(), root_id, current["worktree_id"])
        return str(registered.get("plan_hash") or "")
    except Exception:
        return ""


def rewrite(root_id: str, root_path: str, command: str, harness_cli: str) -> Optional[str]:
    """The attest-wrapped form of `command`, or None if no rewrite applies.

    The original command is appended verbatim after `--`: the outer shell that
    ultimately runs this string tokenizes it into argv for `cli.py`, and
    `argparse.REMAINDER` hands that same tokenization to `subprocess.run`
    unmodified, so the command's own quoting is preserved without this
    function needing to re-parse it.
    """
    if already_wrapped(command):
        return None
    obligation_id = matching_obligation(root_id, command)
    if not obligation_id:
        return None
    plan_hash = _active_plan_hash(root_id, root_path)
    parts = [
        "python3",
        shlex.quote(harness_cli),
        "attest",
        "--root",
        root_id,
        "--obligation-id",
        obligation_id,
    ]
    if plan_hash:
        parts += ["--plan-hash", shlex.quote(plan_hash)]
    parts += ["--", command]
    return " ".join(parts)
