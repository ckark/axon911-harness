"""Best-effort Agent-shell mutation classification.

Quoted-string content is stripped before compound checks. Read-only Git chains
using `&&`, `||`, or `;` are allowed when every stage is a recognized
read-only Git invocation.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Sequence

COMPOUND_SPLIT_RE = re.compile(r"(\&\&|\|\||;|\n)")
FORBIDDEN_SHELL_RE = re.compile(r"(`|\$\(|<<|>>|<\(|>\(|>\(|&\s*$|\|\s*$)")
FORCE_RE = re.compile(r"(^|\s)--force($|\s)|(^|\s)-f($|\s)")
ALL_RE = re.compile(r"(^|\s)--all($|\s)")
MIRROR_RE = re.compile(r"(^|\s)--mirror($|\s)")
DELETE_RE = re.compile(r"(^|\s)--delete($|\s)|(^|\s):[\w./-]+")
TAG_RE = re.compile(r"(^|\s)--tags($|\s)|(^|\s)refs/tags/")
QUOTED_SPAN_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
READONLY_GIT_VERBS = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "merge-base",
        "ls-files",
        "ls-tree",
        "cat-file",
        "grep",
        "blame",
        "shortlog",
        "for-each-ref",
        "fetch",
        "branch",
        "remote",
        "config",
    }
)
MUTATING_GIT_VERBS = frozenset(
    {
        "commit",
        "push",
        "add",
        "rm",
        "mv",
        "reset",
        "checkout",
        "switch",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "stash",
        "clean",
        "tag",
        "am",
        "apply",
        "pull",
    }
)


def _strip_wrappers(command: str) -> str:
    text = command.strip()
    if text.startswith("rtk "):
        rest = text[4:].lstrip()
        if rest.startswith("hook cursor") or rest.startswith("hook claude"):
            return text
        if rest.startswith("git "):
            return rest
        if rest.startswith("rewrite "):
            inner = rest[8:].strip().strip('"').strip("'")
            return _strip_wrappers(inner)
    return text


def _git_invocation(command: str) -> Optional[str]:
    text = _strip_wrappers(command)
    if text.startswith("git "):
        return text
    if text.startswith("/"):
        parts = text.split()
        if parts and os.path.basename(parts[0]) == "git":
            return "git " + " ".join(parts[1:])
    tokens = text.split()
    if len(tokens) >= 3 and tokens[0] == "git" and tokens[1] == "-C":
        return text
    return text if text.startswith("git") else None


def _explicit_directory(tokens: Sequence[str], flag: str) -> str:
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens):
            return tokens[index + 1].strip("'\"")
    return ""


def mutation_cwd(command: str, payload_cwd: str) -> str:
    """Best-effort working directory for a supported mutation command."""
    text = _strip_wrappers(command or "")
    tokens = text.split()
    if tokens[:1] == ["gt"]:
        explicit = _explicit_directory(tokens, "--cwd")
        if explicit:
            return explicit
        return payload_cwd
    git = _git_invocation(text)
    if not git:
        return payload_cwd
    explicit = _explicit_directory(git.split(), "-C")
    return explicit or payload_cwd


def _git_verb(git_command: str) -> str:
    tokens = git_command.split()
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in ("git", "-C", "--git-dir", "--work-tree"):
            if token in ("-C", "--git-dir", "--work-tree") and index + 1 < len(tokens):
                skip_next = True
            continue
        if token.startswith("-"):
            continue
        return token
    return ""


def _is_readonly_git_stage(stage: str) -> bool:
    git = _git_invocation(stage.strip())
    if not git:
        return False
    verb = _git_verb(git)
    if not verb:
        return False
    if verb in MUTATING_GIT_VERBS:
        return False
    return verb in READONLY_GIT_VERBS


def _split_compound(command: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    for piece in COMPOUND_SPLIT_RE.split(command):
        if piece in ("&&", "||", ";", "\n"):
            if current:
                parts.append("".join(current).strip())
                current = []
            continue
        current.append(piece)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def _compound_has_mutation_phrase(command: str) -> bool:
    lowered = QUOTED_SPAN_RE.sub(" ", command).lower()
    return any(
        token in lowered
        for token in ("git commit", "git push", "gt create", "gt submit", "rtk git")
    )


def _readonly_git_chain(command: str) -> bool:
    stages = _split_compound(command)
    if len(stages) <= 1:
        return False
    for stage in stages:
        if not _is_readonly_git_stage(stage):
            return False
    return True


def classify(command: str) -> Dict[str, str]:
    """Return permission, family, and reason. Never executes the command."""
    raw = command or ""
    if FORBIDDEN_SHELL_RE.search(raw):
        return {
            "permission": "deny",
            "family": "compound",
            "reason": "compound-or-ambiguous-mutation",
        }
    if _readonly_git_chain(raw):
        return {"permission": "allow", "family": "git-readonly", "reason": "readonly-git-chain"}
    if COMPOUND_SPLIT_RE.search(raw):
        if _compound_has_mutation_phrase(raw):
            return {
                "permission": "deny",
                "family": "compound",
                "reason": "compound-or-ambiguous-mutation",
            }
    text = _strip_wrappers(raw)
    if text.startswith("gt create"):
        return {"permission": "ask", "family": "gt-create", "reason": "supported-commit"}
    if text.startswith("gt submit"):
        return {"permission": "ask", "family": "gt-submit", "reason": "supported-push"}
    git = _git_invocation(text)
    if git is None:
        return {"permission": "allow", "family": "other", "reason": "not-mutation"}
    tokens = git.split()
    verb = ""
    for index, token in enumerate(tokens):
        if token in ("commit", "push"):
            verb = token
            break
        if token == "-C" and index + 1 < len(tokens):
            continue
    rest = git
    if verb == "commit":
        if " && " in raw or "push" in raw.split("commit", 1)[-1]:
            return {"permission": "deny", "family": "compound", "reason": "commit-and-push-together"}
        return {"permission": "ask", "family": "git-commit", "reason": "supported-commit"}
    if verb == "push":
        if FORCE_RE.search(rest):
            return {"permission": "deny", "family": "git-push", "reason": "force-push"}
        if ALL_RE.search(rest):
            return {"permission": "deny", "family": "git-push", "reason": "push-all"}
        if MIRROR_RE.search(rest):
            return {"permission": "deny", "family": "git-push", "reason": "push-mirror"}
        if DELETE_RE.search(rest):
            return {"permission": "deny", "family": "git-push", "reason": "push-delete"}
        if TAG_RE.search(rest):
            return {"permission": "deny", "family": "git-push", "reason": "unattested-tags"}
        if ":" in rest and "git push" in rest:
            after = rest.split("push", 1)[1]
            if ":" in after and "--" not in after.split(":", 1)[0]:
                return {"permission": "deny", "family": "git-push", "reason": "unattested-refspec"}
        return {"permission": "ask", "family": "git-push", "reason": "supported-push"}
    return {"permission": "allow", "family": "other", "reason": "not-mutation"}
