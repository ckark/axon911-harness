"""Streaming image signature and dimension validation without full decode."""

from __future__ import annotations

import struct
from typing import Tuple

MIN_IMAGE_DIMENSION = 100
PLACEHOLDER_MAX_BYTES = 4096

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"
WEBP_WEBP = b"WEBP"


class MediaValidationError(ValueError):
    """Raised when an artifact is not a valid image."""


def _read_header(path: str, size: int = 64) -> bytes:
    with open(path, "rb") as handle:
        return handle.read(size)


def _png_dimensions(header: bytes) -> Tuple[int, int]:
    if len(header) < 24 or header[:8] != PNG_SIGNATURE:
        raise MediaValidationError("invalid PNG signature")
    if header[12:16] != b"IHDR":
        raise MediaValidationError("PNG missing IHDR chunk")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _jpeg_dimensions(path: str) -> Tuple[int, int]:
    with open(path, "rb") as handle:
        if handle.read(2) != JPEG_SIGNATURE[:2]:
            raise MediaValidationError("invalid JPEG signature")
        while True:
            marker_prefix = handle.read(1)
            if not marker_prefix:
                raise MediaValidationError("JPEG missing SOF segment")
            if marker_prefix != b"\xff":
                continue
            marker = handle.read(1)
            if not marker:
                raise MediaValidationError("JPEG truncated")
            if marker in (b"\xc0", b"\xc1", b"\xc2"):
                segment = handle.read(5)
                if len(segment) < 5:
                    raise MediaValidationError("JPEG SOF truncated")
                height, width = struct.unpack(">HH", segment[1:5])
                return int(width), int(height)
            if marker in (b"\xd8", b"\xd9"):
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) < 2:
                raise MediaValidationError("JPEG segment truncated")
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2:
                raise MediaValidationError("invalid JPEG segment length")
            handle.seek(length - 2, 1)


def _webp_dimensions(header: bytes) -> Tuple[int, int]:
    if len(header) < 30 or header[:4] != WEBP_RIFF or header[8:12] != WEBP_WEBP:
        raise MediaValidationError("invalid WebP signature")
    chunk = header[12:16]
    if chunk == b"VP8 ":
        if len(header) < 30:
            raise MediaValidationError("WebP VP8 truncated")
        width = struct.unpack("<H", header[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", header[28:30])[0] & 0x3FFF
        return int(width), int(height)
    if chunk == b"VP8L":
        if len(header) < 25:
            raise MediaValidationError("WebP VP8L truncated")
        bits = struct.unpack("<I", header[21:25])[0]
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return int(width), int(height)
    if chunk == b"VP8X":
        if len(header) < 30:
            raise MediaValidationError("WebP VP8X truncated")
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return int(width), int(height)
    raise MediaValidationError("unsupported WebP chunk")


def image_metadata(path: str) -> Tuple[str, int, int]:
    """Return `(mime, width, height)` for PNG, JPEG, or WebP."""
    header = _read_header(path, 64)
    if header.startswith(PNG_SIGNATURE):
        width, height = _png_dimensions(header)
        return "image/png", width, height
    if header.startswith(JPEG_SIGNATURE):
        width, height = _jpeg_dimensions(path)
        return "image/jpeg", width, height
    if header[:4] == WEBP_RIFF:
        width, height = _webp_dimensions(header)
        return "image/webp", width, height
    raise MediaValidationError("unsupported or malformed image")


def validate_image_artifact(
    path: str,
    *,
    min_width: int = MIN_IMAGE_DIMENSION,
    min_height: int = MIN_IMAGE_DIMENSION,
    reject_placeholder: bool = True,
) -> Tuple[str, int, int]:
    """Validate image signature, dimensions, and reject tiny placeholders."""
    file_size = 0
    with open(path, "rb") as handle:
        file_size = handle.seek(0, 2)
    mime, width, height = image_metadata(path)
    if width < min_width or height < min_height:
        raise MediaValidationError(
            "image too small: %dx%d (minimum %dx%d)" % (width, height, min_width, min_height)
        )
    if reject_placeholder and file_size <= PLACEHOLDER_MAX_BYTES and width <= 64 and height <= 64:
        raise MediaValidationError("placeholder image rejected")
    return mime, width, height
