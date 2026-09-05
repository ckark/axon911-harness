#!/usr/bin/env python3
"""Atomic CORE-819 definitive evidence runner using normal checkout cycles."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from lib.capture_provenance import checkout_commit, resolve_capture_provenance  # noqa: E402
from lib.execution_state import begin_attempt, complete_attempt  # noqa: E402
from lib.migration_evidence import load_manifest, manifest_sha256  # noqa: E402
from dispatch.common import resolve_cli_root  # noqa: E402
from lib.paths import harness_root, runtime_dir  # noqa: E402
from lib.route_capture import RouteCaptureError, capture_route_batch  # noqa: E402
from lib.storybook_capture import capture_batch, stop_storybook  # noqa: E402
from lib.storybook_session import start_storybook_session, stop_storybook_session  # noqa: E402

EXECUTION_ID = "core819-definitive-v4"
EVIDENCE_ROOT = os.path.join(runtime_dir(), "evidence-quarantine-v2", EXECUTION_ID)


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _clear_capture_caches(product_root: str) -> None:
    for relative in (
        "turbo/node_modules/.vite",
        "turbo/apps/dispatch/node_modules/.vite",
        "apps/storybook/node_modules/.vite",
        "turbo/apps/storybook/node_modules/.vite",
    ):
        target = os.path.join(product_root, relative)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)


def _capture_storybook_items(
    product_root: str,
    items: list[dict],
    *,
    role: str,
    commit_oid: str,
    manifest_hash: str,
    port: int,
) -> None:
    provenance = resolve_capture_provenance(product_root, expected_commit=commit_oid, role=role)
    session = start_storybook_session(
        product_root,
        port=port,
        commit_oid=provenance["source_sha"],
        tree_oid=provenance["source_tree"],
    )
    try:
        captures = []
        for item in items:
            change_id = str(item["change_id"])
            capture = item.get("capture") or {}
            output_path = os.path.join(EVIDENCE_ROOT, "%s-%s.png" % (change_id, role))
            receipt_path = output_path + ".receipt.json"
            captures.append(
                {
                    "capture_id": "%s-%s-%s" % (EXECUTION_ID, change_id, role),
                    "change_id": change_id,
                    "story_id": capture.get("story_id", ""),
                    "theme": capture.get("theme", "dark"),
                    "brand": capture.get("brand", "prepared"),
                    "viewport": capture.get("viewport", "1280x720"),
                    "state": capture.get("state", "default"),
                    "output_path": output_path,
                    "receipt_path": receipt_path,
                    "dom_assertions": capture.get("dom_assertions") or [],
                }
            )
        capture_batch(
            product_root,
            captures,
            source_sha=commit_oid,
            role=role,
            port=port,
            storybook_process=session.process,
            manage_storybook=False,
            manifest_hash=manifest_hash,
        )
    finally:
        stop_storybook_session(session)


def _capture_route_items(
    product_root: str,
    items: list[dict],
    *,
    role: str,
    commit_oid: str,
    manifest_hash: str,
    port: int,
    base_url: str,
) -> None:
    captures = []
    for item in items:
        change_id = str(item["change_id"])
        capture = item.get("capture") or {}
        output_path = os.path.join(EVIDENCE_ROOT, "%s-%s.png" % (change_id, role))
        receipt_path = output_path + ".receipt.json"
        scenario = dict(capture)
        scenario["scenario_id"] = capture.get("scenario_id", change_id)
        scenario["capture_id"] = "%s-%s-%s" % (EXECUTION_ID, change_id, role)
        captures.append(
            {
                "change_id": change_id,
                "output_path": output_path,
                "receipt_path": receipt_path,
                "scenario": scenario,
            }
        )
    capture_route_batch(
        product_root,
        captures,
        role=role,
        source_sha=commit_oid,
        port=port,
        base_url=base_url,
        manifest_hash=manifest_hash,
    )


def _items_for_role(manifest: dict, role: str, refs: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {"prepared911": [], "axon911-frontend": []}
    for item in manifest.get("changes") or []:
        if not isinstance(item, dict):
            continue
        capture_kind = str(item.get("capture_kind") or "")
        evidence_state = str(item.get("evidence_state") or "changed")
        if capture_kind == "not-applicable" or evidence_state == "static_only":
            continue
        if role == "before" and evidence_state == "new_visible":
            continue
        if role == "after" and evidence_state not in ("changed", "expected_unchanged", "new_visible"):
            continue
        root_id = str(item.get("root") or "prepared911")
        grouped.setdefault(root_id, []).append(item)
    return grouped


def capture_role(
    manifest_path: str,
    *,
    role: str,
    trunk_refs: dict[str, str],
    head_refs: dict[str, str],
    dispatch_port: int = 3002,
    storybook_ports: dict[str, int] | None = None,
    dispatch_base_url: str = "",
) -> None:
    manifest = load_manifest(manifest_path)
    manifest_hash = manifest_sha256(manifest)
    refs = manifest.get("refs") or {}
    storybook_ports = storybook_ports or {"prepared911": 3005, "axon911-frontend": 5203}
    os.makedirs(EVIDENCE_ROOT, exist_ok=True)
    phase = "baseline-capture" if role == "before" else "after-capture"
    begin_attempt(EXECUTION_ID, phase, max_attempts=2, idempotency_key="%s:%s" % (role, manifest_hash))
    grouped = _items_for_role(manifest, role, refs)
    try:
        for root_id, items in grouped.items():
            if not items:
                continue
            product_root = resolve_cli_root(root_id)
            commit_oid = trunk_refs[root_id] if role == "before" else head_refs.get(root_id) or trunk_refs[root_id]
            _clear_capture_caches(product_root)
            checkout_commit(product_root, commit_oid)
            story_items = [item for item in items if str(item.get("capture_kind")) == "storybook"]
            route_items = [item for item in items if str(item.get("capture_kind")) == "product-route"]
            if story_items:
                _capture_storybook_items(
                    product_root,
                    story_items,
                    role=role,
                    commit_oid=commit_oid,
                    manifest_hash=manifest_hash,
                    port=storybook_ports.get(root_id, 3005),
                )
            if route_items:
                _capture_route_items(
                    product_root,
                    route_items,
                    role=role,
                    commit_oid=commit_oid,
                    manifest_hash=manifest_hash,
                    port=dispatch_port,
                    base_url=dispatch_base_url,
                )
        complete_attempt(EXECUTION_ID, phase, status="passed")
    except Exception as exc:
        complete_attempt(EXECUTION_ID, phase, status="failed", details={"error": str(exc)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=os.path.join(harness_root(), "harness", "manifests", "core819-definitive-v4.json"))
    parser.add_argument("--role", choices=("before", "after"), required=True)
    parser.add_argument("--dispatch-port", type=int, default=3002)
    parser.add_argument("--dispatch-base-url", default="")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    refs = manifest.get("refs") or {}
    trunk_refs = {
        "prepared911": str(refs.get("prepared911_trunk") or ""),
        "axon911-frontend": str(refs.get("axon_trunk") or ""),
    }
    head_refs = {
        "prepared911": str(refs.get("pr_26203") or ""),
        "axon911-frontend": str(refs.get("pr_541") or ""),
    }
    capture_role(
        args.manifest,
        role=args.role,
        trunk_refs=trunk_refs,
        head_refs=head_refs,
        dispatch_port=args.dispatch_port,
        dispatch_base_url=args.dispatch_base_url,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
