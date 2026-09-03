"""GitHub PR attachment helpers using official gh pr edit --attach."""

from __future__ import annotations

import re
import subprocess
from typing import List, Sequence, Tuple

from .constants import GH_ATTACH_MIN_VERSION

USER_ATTACHMENT_URL = re.compile(
    r"https://github\.com/user-attachments/assets/[0-9a-f-]{36}",
    re.IGNORECASE,
)


class GitHubAttachError(RuntimeError):
    """Raised when gh attachment workflow is unavailable or fails."""


def parse_gh_version(raw: str) -> Tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def require_gh_attach() -> str:
    try:
        result = subprocess.run(
            ["gh", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        raise GitHubAttachError("gh not available: %s" % exc) from exc
    version = parse_gh_version(result.stdout)
    if version < GH_ATTACH_MIN_VERSION:
        raise GitHubAttachError(
            "gh %s.%s.%s lacks --attach; require %s.%s.%s+"
            % (*version, *GH_ATTACH_MIN_VERSION)
        )
    return result.stdout.strip().splitlines()[0]


def attach_pr_files(
    repo: str,
    pr_number: int,
    files: Sequence[str],
    *,
    body_file: str = "",
) -> None:
    """Upload local files as permanent GitHub user attachments on a PR."""
    require_gh_attach()
    if not files:
        raise GitHubAttachError("no files to attach")
    command = ["gh", "pr", "edit", str(pr_number), "--repo", repo]
    if body_file:
        command.extend(["--body-file", body_file])
    for path in files:
        command.extend(["--attach", path])
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise GitHubAttachError(result.stderr.strip() or result.stdout.strip() or "gh attach failed")


def extract_attachment_urls(body: str) -> List[str]:
    return USER_ATTACHMENT_URL.findall(body or "")
