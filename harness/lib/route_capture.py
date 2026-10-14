"""Product-route Playwright capture orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .capture_provenance import resolve_capture_provenance
from .capture_receipt import CAPTURE_PRODUCER, CAPTURE_RECEIPT_VERSION, write_capture_receipt
from .media_validation import image_metadata
from .paths import harness_root


class RouteCaptureError(RuntimeError):
    """Raised when product-route capture fails."""


def _find_playwright_root(product_root: str) -> str:
    candidates = [
        os.path.join(product_root, "turbo", "apps", "automation"),
        os.path.join(product_root, "apps", "automation"),
    ]
    for candidate in candidates:
        if os.path.exists(os.path.join(candidate, "node_modules", "playwright", "package.json")):
            return candidate
        if os.path.exists(os.path.join(candidate, "node_modules", "@playwright", "test", "package.json")):
            return candidate
    raise RouteCaptureError("playwright not found under product root")


def capture_route(
    product_root: str,
    scenario: Mapping[str, Any],
    *,
    output_path: str,
    receipt_path: str,
    role: str,
    source_sha: str,
    manifest_hash: str = "",
    change_id: str = "",
    port: int = 3002,
    base_url: str = "",
) -> Dict[str, Any]:
    """Capture one product route using a harness-owned scenario spec."""
    provenance = resolve_capture_provenance(product_root, expected_commit=source_sha, role=role)
    script_path = os.path.join(harness_root(), "harness", "scripts", "route-capture.mjs")
    if not os.path.isfile(script_path):
        raise RouteCaptureError("route-capture.mjs missing")
    resolved_base = base_url.strip() or "http://127.0.0.1:%s" % port
    spec = {
        "baseUrl": resolved_base,
        "playwrightModuleRoot": _find_playwright_root(product_root),
        "scenario": dict(scenario),
        "outputPath": os.path.abspath(output_path),
        "role": role,
        "captureRunId": str(scenario.get("capture_run_id") or uuid.uuid4()),
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(spec, handle)
        spec_path = handle.name
    try:
        result = subprocess.run(
            ["node", script_path, spec_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            raise RouteCaptureError(result.stderr.strip() or result.stdout.strip() or "route capture failed")
        payload = json.loads(result.stdout.strip() or "{}")
        if not payload.get("ok"):
            raise RouteCaptureError(str(payload.get("error") or "route capture failed"))
    finally:
        os.unlink(spec_path)
    mime, width, height = image_metadata(output_path)
    digest = hashlib.sha256()
    with open(output_path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    capture_kind = "product-route"
    receipt = {
        "version": CAPTURE_RECEIPT_VERSION,
        "capture_id": str(scenario.get("capture_id") or uuid.uuid4()),
        "producer": CAPTURE_PRODUCER,
        "capture_kind": capture_kind,
        "source_sha": provenance["source_sha"],
        "source_tree": provenance["source_tree"],
        "source_clean": provenance["source_clean"],
        "manifest_hash": manifest_hash,
        "change_id": change_id,
        "content_origin": "product",
        "capture_scope": "contextual",
        "role": role,
        "artifact_path": os.path.abspath(output_path),
        "artifact_hash": digest.hexdigest(),
        "route": str(scenario.get("route") or ""),
        "entrypoint": str(scenario.get("entrypoint") or "dispatch"),
        "scenario_id": str(scenario.get("scenario_id") or ""),
        "theme": str(scenario.get("theme") or "dark"),
        "brand": str(scenario.get("brand") or "prepared"),
        "viewport": str(scenario.get("viewport") or "1280x720"),
        "state": str(scenario.get("state") or "default"),
        "target_selector": str(payload.get("target_selector") or ""),
        "clip_selector": str(payload.get("clip_selector") or ""),
        "clip_bounds": payload.get("clip_bounds") or {},
        "dom_assertions": payload.get("dom_assertions") or [],
        "changed_path_proof": payload.get("changed_path_proof") or [],
        "mime": mime,
        "width": width,
        "height": height,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "health": payload.get("health") or {},
        "server_port": port,
    }
    write_capture_receipt(receipt_path, receipt)
    return {"artifact_path": output_path, "receipt_path": receipt_path, "receipt": receipt}


def capture_route_batch(
    product_root: str,
    captures: Sequence[Mapping[str, Any]],
    *,
    role: str,
    source_sha: str,
    port: int = 3002,
    base_url: str = "",
    manifest_hash: str = "",
) -> List[Dict[str, Any]]:
    """Capture multiple product routes sequentially."""
    receipts: List[Dict[str, Any]] = []
    for item in captures:
        receipts.append(
            capture_route(
                product_root,
                item.get("scenario") or item,
                output_path=str(item["output_path"]),
                receipt_path=str(item.get("receipt_path") or str(item["output_path"]) + ".receipt.json"),
                role=role,
                source_sha=source_sha,
                manifest_hash=manifest_hash,
                change_id=str(item.get("change_id") or ""),
                port=port,
                base_url=base_url,
            )
        )
    return receipts
