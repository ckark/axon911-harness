"""Best-effort Agent-shell mutation classification.

Quoted-string content is stripped before the compound-mutation substring check,
so a script that merely mentions a commit command inside test data, JSON, or a
quoted example does not read as an attempt to chain one. Backtick spans are
deliberately left intact: a backtick is genuine shell command substitution, and
there is no reliable way to tell that usage apart from a backtick used as
markdown-style emphasis in a comment without real shell parsing. Avoid writing
the literal mutation phrases inside backticks in this codebase's own comments;
quote them instead.
"""

from __future__ import annotations

import os
import re
from typing import Dict, Optional, Sequence

COMPOUND_RE = re.compile(r"(&&|\|\||;|\n|`|\$\()")
# A single- or double-quoted span, respecting backslash escapes. Stripped
# before the substring check below so quoted example text in a script is not
# misread as an attempt to chain a mutation.
QUOTED_SPAN_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
FORCE_RE = re.compile(r"(^|\s)--force($|\s)|(^|\s)-f($|\s)")
ALL_RE = re.compile(r"(^|\s)--all($|\s)")
MIRROR_RE = re.compile(r"(^|\s)--mirror($|\s)")
DELETE_RE = re.compile(r"(^|\s)--delete($|\s)|(^|\s):[\w./-]+")
TAG_RE = re.compile(r"(^|\s)--tags($|\s)|(^|\s)refs/tags/")


def _strip_wrappers(command: str) -> str:
    text = command.strip()
    if text.startswith("rtk "):
        rest = text[4:].lstrip()
        # RTK's own hook invocation for either host, observed as a plain bash
        # command rather than unwrapped as a user command underneath it.
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
    if " git " in " %s " % text and text.split()[0:2] == ["env"]:
        return None
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
    """Best-effort working directory for a supported mutation command.

    `payload_cwd` is the session's directory, not the command's. A tool that
    resolves the root from it alone attributes work in a linked worktree to
    whichever root the session happens to sit in -- which is how a `gt submit`
    against axon911-frontend came back gated on prepared911's obligations.
    Directory-bearing forms are read off the command itself.
    """
    text = _strip_wrappers(command or "")
    tokens = text.split()

    # `gt` takes `--cwd`; it is the only way to target a worktree without a
    # `cd ... &&` prefix, which the compound rule denies for mutations.
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


def classify(command: str) -> Dict[str, str]:
    """Return permission, family, and reason. Never executes the command."""
    raw = command or ""
    if COMPOUND_RE.search(raw):
        lowered = QUOTED_SPAN_RE.sub(" ", raw).lower()
        if any(token in lowered for token in ("git commit", "git push", "gt create", "gt submit", "rtk git")):
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
    # git -C <path> <verb>
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
            # refspec other than implicit HEAD
            after = rest.split("push", 1)[1]
            if ":" in after and "--" not in after.split(":", 1)[0]:
                return {"permission": "deny", "family": "git-push", "reason": "unattested-refspec"}
        return {"permission": "ask", "family": "git-push", "reason": "supported-push"}
    return {"permission": "allow", "family": "other", "reason": "not-mutation"}
