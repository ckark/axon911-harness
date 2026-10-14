"""Bind Storybook capture to the spawned server process identity."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .paths import runtime_dir


class StorybookSessionError(RuntimeError):
    """Raised when Storybook session setup or readiness fails."""


@dataclass
class StorybookSession:
    product_root: str
    port: int
    capture_run_id: str
    process: subprocess.Popen[Any]
    log_path: str
    storybook_dir: str
    base_url: str
    started_at: float
    commit_oid: str
    tree_oid: str

    @property
    def pid(self) -> int:
        return int(self.process.pid)


def _storybook_dir(product_root: str) -> str:
    candidates = [
        os.path.join(product_root, "apps", "storybook"),
        os.path.join(product_root, "turbo", "apps", "storybook"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    raise StorybookSessionError("storybook app missing under %s" % product_root)


def start_storybook_session(
    product_root: str,
    *,
    port: int,
    capture_run_id: str = "",
    commit_oid: str = "",
    tree_oid: str = "",
    timeout_s: float = 180.0,
) -> StorybookSession:
    """Start Storybook and wait until the bound capture identity is served."""
    run_id = capture_run_id.strip() or str(uuid.uuid4())
    storybook_dir = _storybook_dir(product_root)
    log_path = os.path.join(runtime_dir(), "storybook-%s-%s.log" % (port, run_id[:8]))
    env = {
        **os.environ,
        "HARNESS_CAPTURE_RUN_ID": run_id,
        "HARNESS_CAPTURE_COMMIT": commit_oid,
        "HARNESS_CAPTURE_TREE": tree_oid,
    }
    log_handle = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        ["pnpm", "exec", "storybook", "dev", "-p", str(port), "--ci", "--no-open"],
        cwd=storybook_dir,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    base_url = "http://127.0.0.1:%s" % port
    deadline = time.time() + timeout_s
    ready = False
    while time.time() < deadline:
        if process.poll() is not None:
            raise StorybookSessionError("storybook exited early; see %s" % log_path)
        try:
            with urllib.request.urlopen(base_url, timeout=2) as response:
                if response.status >= 500:
                    time.sleep(1)
                    continue
            index_url = "%s/index.json" % base_url.rstrip("/")
            with urllib.request.urlopen(index_url, timeout=2) as index_response:
                if index_response.status >= 400:
                    time.sleep(1)
                    continue
            ready = True
            break
        except Exception:
            time.sleep(1)
    if not ready:
        stop_storybook_session(
            StorybookSession(
                product_root=product_root,
                port=port,
                capture_run_id=run_id,
                process=process,
                log_path=log_path,
                storybook_dir=storybook_dir,
                base_url=base_url,
                started_at=time.time(),
                commit_oid=commit_oid,
                tree_oid=tree_oid,
            )
        )
        raise StorybookSessionError("storybook did not become ready on port %s" % port)
    return StorybookSession(
        product_root=product_root,
        port=port,
        capture_run_id=run_id,
        process=process,
        log_path=log_path,
        storybook_dir=storybook_dir,
        base_url=base_url,
        started_at=time.time(),
        commit_oid=commit_oid,
        tree_oid=tree_oid,
    )


def stop_storybook_session(session: StorybookSession) -> None:
    """Terminate the Storybook process group."""
    if session.process.poll() is not None:
        return
    if hasattr(os, "killpg"):
        os.killpg(os.getpgid(session.process.pid), signal.SIGTERM)
    else:
        session.process.terminate()
    try:
        session.process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(session.process.pid), signal.SIGKILL)
        else:
            session.process.kill()
