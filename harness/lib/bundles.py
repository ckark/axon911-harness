"""Content-addressed cross-root publication bundles."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .constants import STATUS_BLOCKED, STATUS_PASS
from .paths import runtime_dir
from .plan_profile import plan_context_hash
from .shipping import evaluate_ship_plan


STAGE_CANDIDATE = "publication-candidate"
STAGE_SHIP_READY = "ship-ready"
BUNDLE_STAGES = (STAGE_CANDIDATE, STAGE_SHIP_READY)


def bundle_manifest(
    plan_hash: str,
    tier: str,
    stage: str,
    roots: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "version": 1,
        "stage": stage,
        "plan_hash": plan_hash,
        "tier": tier,
        "roots": roots,
        "created_at": time.time(),
    }


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_bundle(manifest: Mapping[str, Any], base: Optional[str] = None) -> str:
    runtime = base or runtime_dir()
    bundles_dir = os.path.join(runtime, "bundles")
    os.makedirs(bundles_dir, mode=0o700, exist_ok=True)
    digest = manifest_digest(manifest)
    path = os.path.join(bundles_dir, "%s.json" % digest)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, indent=2)
            handle.write("\n")
        os.chmod(path, 0o600)
    return path


def load_bundle(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_bundle_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    if manifest.get("stage") not in BUNDLE_STAGES:
        errors.append("invalid-stage")
    roots = manifest.get("roots") or {}
    if not roots:
        errors.append("missing-roots")
    for root_id, entry in roots.items():
        if not entry.get("fingerprint"):
            errors.append("%s:missing-fingerprint" % root_id)
        if not entry.get("plan_hash"):
            errors.append("%s:missing-plan-hash" % root_id)
    status = STATUS_PASS if not errors else STATUS_BLOCKED
    return {"status": status, "errors": errors, "digest": manifest_digest(manifest)}


def build_root_entry(
    root_id: str,
    root_path: str,
    worktree_id: str,
    fingerprint: str,
    family: str = "git-push",
    base: Optional[str] = None,
) -> Dict[str, Any]:
    ship = evaluate_ship_plan(
        root_id,
        root_path,
        worktree_id,
        fingerprint,
        family=family,
        base=base,
    )
    return {
        "branch": _git_branch(root_path),
        "head": ship.get("head") or "",
        "fingerprint": fingerprint,
        "plan_hash": ship.get("plan_hash") or "",
        "plan_context_hash": ship.get("plan_context_hash") or "",
        "tier": ship.get("tier") or "T0",
        "required_obligation_ids": ship.get("required_obligation_ids") or [],
        "ready": ship.get("ready"),
        "gate": ship.get("gate") or {},
        "recovery": ship.get("recovery") or {},
    }


def _git_branch(root_path: str) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""
