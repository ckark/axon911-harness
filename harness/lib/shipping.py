"""Read-only push readiness evaluation without mutating git or runtime state."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .conformance import evaluate_against_base, summarize
from .constants import STATUS_BLOCKED, STATUS_PASS
from .command_specs import obligation_spec, validate_attestation_command
from .evidence import revalidate_evidence
from .ledger import current_state
from .path_selector import select_obligations
from .plan_profile import active_profile
from .receipts import build_recovery, evaluate_gate


def _branch_paths(root_path: str, base_oid: str) -> List[str]:
    from .conformance import branch_changed_paths

    if base_oid:
        return branch_changed_paths(root_path, base_oid)
    from .fingerprint import changed_paths

    return changed_paths(root_path)


def _hook_prerequisites(root_path: str) -> List[str]:
    notes: List[str] = []
    hook = os.path.join(root_path, ".git-hooks", "pre-push")
    if os.path.isfile(hook):
        notes.append("repository pre-push hook present at .git-hooks/pre-push")
    git_hook = os.path.join(root_path, ".git", "hooks", "pre-push")
    if os.path.isfile(git_hook):
        notes.append("local .git/hooks/pre-push present")
    if not os.environ.get("NODE_AUTH_TOKEN"):
        notes.append("NODE_AUTH_TOKEN unset; prepared911 pre-push may fail on private packages")
    return notes


def evaluate_ship_plan(
    root_id: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    family: str = "git-push",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate push gate readiness without writing ledger records."""
    try:
        state = current_state(base=base, validate=False)
    except Exception:
        state = {}
    profile = active_profile(state, root_id, worktree_id)
    changed = _branch_paths(root_path, str(profile.get("base_oid") or ""))
    selection = select_obligations(
        root_id,
        changed,
        profile,
        profile.get("tier") or "T0",
        family=family,
    )
    conformance = evaluate_against_base(
        root_id,
        worktree_id,
        changed,
        profile,
        root_path=root_path,
        base=base,
    )
    gate = evaluate_gate(
        root_id,
        worktree_id,
        fingerprint,
        selection["required_obligation_ids"],
        profile.get("plan_hash") or "",
        profile.get("tier") or "T0",
        changed_paths=changed,
        root_path=root_path,
        base=base,
        selection=selection,
        conformance=conformance,
        mutation_family=family,
    )
    recovery = gate.get("recovery") or build_recovery([], profile.get("plan_hash") or "")
    attestable = []
    skill_actions = []
    for obligation_id in selection["required_obligation_ids"]:
        if obligation_id.startswith("review."):
            skill_actions.append(
                {"action": "adversarial-review", "obligation_id": obligation_id}
            )
            continue
        if obligation_id.endswith(".rendered-evidence") or obligation_id.endswith(".before-after"):
            skill_actions.append(
                {"action": "capture-evidence", "obligation_id": obligation_id}
            )
            continue
        spec = obligation_spec(obligation_id)
        check = spec.get("check") or spec.get("regenerate")
        if check:
            attestable.append(
                {
                    "obligation_id": obligation_id,
                    "argv": [
                        "python3",
                        "harness/cli.py",
                        "attest",
                        "--root",
                        root_id,
                        "--obligation-id",
                        obligation_id,
                        "--",
                        *check.split(),
                    ],
                }
            )
    return {
        "root": root_id,
        "head": _git_head(root_path),
        "fingerprint": fingerprint,
        "plan_hash": profile.get("plan_hash") or "",
        "plan_context_hash": profile.get("plan_context_hash") or "",
        "tier": profile.get("tier") or "T0",
        "changed_paths": changed,
        "required_obligation_ids": selection["required_obligation_ids"],
        "classification_errors": selection["classification_errors"],
        "conformance": conformance,
        "conformance_message": summarize(conformance),
        "gate": gate,
        "recovery": recovery,
        "attestable": attestable,
        "skill_actions": skill_actions,
        "hook_prerequisites": _hook_prerequisites(root_path),
        "ready": gate.get("permission") == "allow" and not selection["classification_errors"],
    }


def _git_head(root_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""
