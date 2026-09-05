"""Harness-owned Storybook capture orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .capture_receipt import (
    CAPTURE_PRODUCER,
    CAPTURE_RECEIPT_VERSION,
    capture_source_provenance,
    write_capture_receipt,
)
from .media_validation import image_metadata
from .paths import harness_root, runtime_dir

DEFAULT_STORYBOOK_PORT = 3005
DEFAULT_TARGET_SELECTOR = "#storybook-root"


class StorybookCaptureError(RuntimeError):
    """Raised when Storybook capture fails."""


def _find_playwright_root(product_root: str) -> str:
    candidates = [
        os.path.join(product_root, "apps", "storybook"),
        os.path.join(product_root, "turbo", "apps", "storybook"),
        os.path.join(product_root, "turbo", "apps", "automation"),
    ]
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "node_modules", "playwright")):
            return candidate
    raise StorybookCaptureError("playwright not found under product root")


def _storybook_script(product_root: str) -> str:
    for candidate in (
        os.path.join(product_root, "apps", "storybook", "package.json"),
        os.path.join(product_root, "turbo", "apps", "storybook", "package.json"),
    ):
        if os.path.isfile(candidate):
            return candidate
    raise StorybookCaptureError("storybook app missing under product root")


def start_storybook(product_root: str, port: int = DEFAULT_STORYBOOK_PORT) -> subprocess.Popen[Any]:
    storybook_dir = os.path.dirname(_storybook_script(product_root))
    if not os.path.isdir(storybook_dir):
        raise StorybookCaptureError("storybook app missing: %s" % storybook_dir)
    log_path = os.path.join(runtime_dir(), "storybook-%s.log" % port)
    log_handle = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        ["pnpm", "exec", "storybook", "dev", "-p", str(port), "--ci", "--no-open"],
        cwd=storybook_dir,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    deadline = time.time() + 180
    base_url = "http://127.0.0.1:%s" % port
    while time.time() < deadline:
        if process.poll() is not None:
            raise StorybookCaptureError("storybook exited early; see %s" % log_path)
        try:
            import urllib.request

            with urllib.request.urlopen(base_url, timeout=2) as response:
                if response.status < 500:
                    return process
        except Exception:
            time.sleep(2)
    raise StorybookCaptureError("storybook did not become ready on port %s" % port)


def stop_storybook(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if hasattr(os, "killpg"):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()


def capture_batch(
    product_root: str,
    captures: Sequence[Mapping[str, Any]],
    *,
    source_sha: str,
    role: str,
    port: int = DEFAULT_STORYBOOK_PORT,
    storybook_process: Optional[subprocess.Popen[Any]] = None,
    manage_storybook: bool = True,
    manifest_hash: str = "",
    content_origin: str = "product",
    capture_scope: str = "contextual",
    staged_subject: bool = False,
) -> List[Dict[str, Any]]:
    """Capture a batch of stories and write PNG + receipt pairs."""
    owned_process = manage_storybook and storybook_process is None
    process = storybook_process
    if manage_storybook and process is None:
        process = start_storybook(product_root, port=port)
    provenance = capture_source_provenance(
        product_root,
        source_sha=source_sha,
        staged=staged_subject or role == "after",
    )
    script_path = os.path.join(harness_root(), "harness", "scripts", "storybook-capture.mjs")
    playwright_root = _find_playwright_root(product_root)
    spec = {
        "baseUrl": "http://127.0.0.1:%s" % port,
        "playwrightModuleRoot": playwright_root,
        "captures": [
            {
                "story_id": item["story_id"],
                "theme": item.get("theme", "dark"),
                "brand": item.get("brand", "prepared"),
                "viewport": item.get("viewport", "1280x720"),
                "state": item.get("state", "default"),
                "target_selector": item.get("target_selector", DEFAULT_TARGET_SELECTOR),
                "output_path": os.path.abspath(item["output_path"]),
                "actions": list(item.get("actions") or []),
                "dom_assertions": list(item.get("dom_assertions") or []),
            }
            for item in captures
        ],
    }
    receipts: List[Dict[str, Any]] = []
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
            raise StorybookCaptureError(result.stderr.strip() or result.stdout.strip())
        payload = json.loads(result.stdout.strip() or "{}")
        if not payload.get("ok"):
            raise StorybookCaptureError("capture script failed")
        outcomes = payload.get("results") or []
        if len(outcomes) != len(captures):
            raise StorybookCaptureError(
                "capture result count mismatch: expected %d got %d" % (len(captures), len(outcomes))
            )
        for capture, outcome in zip(captures, outcomes):
            if str(outcome.get("story_id") or "") != str(capture.get("story_id") or ""):
                raise StorybookCaptureError(
                    "capture story_id mismatch: expected %s got %s"
                    % (capture.get("story_id"), outcome.get("story_id"))
                )
            output_path = os.path.abspath(str(capture["output_path"]))
            mime, width, height = image_metadata(output_path)
            digest = hashlib.sha256()
            with open(output_path, "rb") as handle:
                while True:
                    chunk = handle.read(1024 * 64)
                    if not chunk:
                        break
                    digest.update(chunk)
            change_id = str(capture.get("change_id") or "")
            receipt = {
                "version": CAPTURE_RECEIPT_VERSION,
                "capture_id": str(capture.get("capture_id") or uuid.uuid4()),
                "producer": CAPTURE_PRODUCER,
                "capture_kind": "storybook",
                "source_sha": provenance["source_sha"],
                "source_tree": provenance["source_tree"],
                "source_clean": provenance["source_clean"],
                "manifest_hash": manifest_hash,
                "change_id": change_id,
                "content_origin": str(capture.get("content_origin") or content_origin),
                "capture_scope": str(capture.get("capture_scope") or capture_scope),
                "role": role,
                "server_port": port,
                "artifact_path": output_path,
                "artifact_hash": digest.hexdigest(),
                "story_id": str(capture.get("story_id") or ""),
                "story_url": str(outcome.get("story_url") or ""),
                "theme": str(capture.get("theme") or ""),
                "brand": str(capture.get("brand") or ""),
                "viewport": str(capture.get("viewport") or ""),
                "state": str(capture.get("state") or ""),
                "target_selector": str(outcome.get("target_selector") or DEFAULT_TARGET_SELECTOR),
                "clip_selector": str(outcome.get("clip_selector") or DEFAULT_TARGET_SELECTOR),
                "clip_bounds": outcome.get("clip_bounds") or {},
                "dom_assertions": outcome.get("dom_assertions") or [],
                "mime": mime,
                "width": width,
                "height": height,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "health": outcome.get("health") or {},
            }
            receipt_path = str(capture.get("receipt_path") or output_path + ".receipt.json")
            write_capture_receipt(receipt_path, receipt)
            receipts.append({"artifact_path": output_path, "receipt_path": receipt_path, "receipt": receipt})
    finally:
        os.unlink(spec_path)
        if owned_process and process is not None:
            stop_storybook(process)
    return receipts
