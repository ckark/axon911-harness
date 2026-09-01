#!/usr/bin/env python3
"""Cursor's entry point. Thin shim over `harness/cli.py`.

Kept at this path because `.cursor/hooks.json`, `docs/runtime-contract.md`, and
the implementation-check skill all name it. The logic lives in `harness/`, which
the Claude Code dispatcher shares.
"""

from __future__ import annotations

import os
import sys

HARNESS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "harness",
)
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
