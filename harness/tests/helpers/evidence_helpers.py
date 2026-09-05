"""Shared helpers for evidence unit tests."""

from __future__ import annotations

import json
import os
import struct
import uuid
import zlib
from typing import Any, Dict, Mapping, Optional

from lib.capture_receipt import CAPTURE_PRODUCER, CAPTURE_RECEIPT_VERSION


def write_min_png(path: str, width: int = 128, height: int = 128) -> None:
    """Write a valid minimal PNG without third-party libraries."""
    import binascii

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = binascii.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\xff\xff\xff" * width)
    raw = row * height
    compressed = zlib.compress(raw, 9)
    payload = signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(payload)


def write_capture_receipt(
    path: str,
    artifact_path: str,
    *,
    capture: Mapping[str, str],
    source_sha: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    role: str = "before",
) -> Dict[str, Any]:
    import hashlib

    from lib.media_validation import validate_image_artifact

    mime, width, height = validate_image_artifact(artifact_path)
    digest = hashlib.sha256()
    with open(artifact_path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    receipt: Dict[str, Any] = {
        "version": CAPTURE_RECEIPT_VERSION,
        "capture_id": str(uuid.uuid4()),
        "producer": CAPTURE_PRODUCER,
        "source_sha": source_sha,
        "source_tree": "dddddddddddddddddddddddddddddddddddddddd",
        "source_clean": True,
        "manifest_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "change_id": capture.get("change_id", "demo-change"),
        "content_origin": capture.get("content_origin", "product"),
        "capture_scope": capture.get("capture_scope", "contextual"),
        "role": role,
        "artifact_path": artifact_path,
        "artifact_hash": digest.hexdigest(),
        "story_id": capture.get("story_id", ""),
        "story_url": "http://127.0.0.1:3005/iframe.html",
        "theme": capture.get("theme", "dark"),
        "brand": capture.get("brand", "prepared"),
        "viewport": capture.get("viewport", "1280x720"),
        "state": capture.get("state", "default"),
        "target_selector": "#storybook-root",
        "clip_selector": "#storybook-root",
        "clip_bounds": {"x": 0, "y": 0, "width": width, "height": height},
        "dom_assertions": [],
        "mime": mime,
        "width": width,
        "height": height,
        "timestamp": "2026-09-03T00:00:00Z",
        "health": {
            "storybook_ready": True,
            "fonts_ready": True,
            "css_tokens_ready": True,
            "theme_applied": True,
            "target_visible": True,
            "target_bounds_nonzero": True,
            "stylesheets_present": True,
            "console_errors": [],
            "failed_requests": [],
            "dom_assertions_passed": True,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle)
    return receipt
