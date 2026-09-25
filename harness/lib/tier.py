"""Computed blast-radius tier.

Replaces the prose predicate table that made every change land on T2. That table
listed "public `ui-*` export" as a T2 trigger, and every one of the 14 packages
exposes exactly one public entry (`"." -> "./src/index.ts"`), so the predicate
was true by construction for any change to any of them. Combined with "tier is a
floor" -- escalation allowed, de-escalation not -- the result could only ever be
the maximum.

Two rules make the hierarchy hold again:

* Tier follows a measured **surface delta** plus **per-symbol** importer counts,
  not the directory a file happens to live in.
* T2 must name the predicate that fired and the evidence for it, symmetrically
  with T0 already requiring an importer count. A T2 that cannot cite a predicate
  is dropped rather than accepted.

The routing matrix still selects *which* critics apply by change signal. It no
longer decides *how many*.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

GitRunner = Callable[[Sequence[str], str], str]

TIERS = ("T0", "T1", "T2")
TIER_RANK = {"T0": 0, "T1": 1, "T2": 2}

DELTA_NONE = "none"
DELTA_ADDITIVE = "additive"
DELTA_BREAKING = "breaking"

# A T0 claim needs the call-site count; this is what it must come in under.
#
# The count is "files referencing a changed symbol, excluding the changed files
# themselves" -- i.e. how many places a reviewer would have to check. Two
# tempting alternatives are both wrong here:
#
#   * "no importers outside the owning package" would make a design-system
#     component change impossible to score T0, since components exist to be
#     consumed -- recreating the always-maximum bug one tier down.
#   * "no importers at all" would ignore reuse that is entirely internal to
#     ui-core, where a shared helper can have dozens of call sites.
T0_MAX_CALL_SITES = 3

# Public-surface sources per root. Deliberately not the docs component registry:
# that covers 9 of 14 packages, gates discovery on a stories file rather than on
# exports, and records only the *name* of an enum-typed prop -- so it cannot see
# an enum member being added or removed, which is the most common real API change
# in this design system. These files are hand-maintained, so a diff in one is a
# real surface change.
SURFACE_PATTERNS = {
    "axon911-frontend": (
        r"^packages/ui-[^/]+/src/index\.ts$",
        r"^packages/ui-[^/]+/package\.json$",
        r"^packages/ui-[^/]+/src/models/",
        r"^packages/ui-core/src/styles/",
    ),
    "prepared911": (
        r"^turbo/packages/ui-[^/]+/src/index\.ts$",
        r"^turbo/packages/ui-[^/]+/package\.json$",
        r"^turbo/packages/ui-[^/]+/src/models/",
        r"^turbo/packages/ui-core/src/styles/",
    ),
    "vault-core-ux": (),
    "chroma": (),
    "axon911-design": (r"^src/index\.ts$",),
    "personal-harness": (),
}

# Risk signals force T2 regardless of surface delta, because the failure mode is
# not "a caller breaks" -- it is an outage, a privacy incident, or a leak.
RISK_PATTERNS = (
    (r"(rbac|permission|authoriz|authent)", "auth-or-rbac"),
    (r"(^|/)util-permissions/", "auth-or-rbac"),
    (r"(^|/)feature-auth/", "auth-or-rbac"),
    (r"(pii|redact|telemetry)", "privacy-or-telemetry"),
    (r"(subscription|websocket|livestream)", "realtime-lifecycle"),
    (r"(ui-audio-player|ui-video-player)", "media-lifecycle"),
)

EXPORT_RE = re.compile(r"^[+-]\s*export\b")
NON_API_FILE_RE = re.compile(r"\.(stories|test|spec)\.[jt]sx?$|(^|/)__(tests|mocks)__/")
# Named bindings inside an import statement, single- or multi-line.
IMPORT_BLOCK_RE = re.compile(r"\bimport\s+(?:type\s+)?\{([^}]*)\}\s*from\b", re.DOTALL)
IMPORT_DEFAULT_RE = re.compile(r"\bimport\s+(?:type\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:,|from)\b")

# Reporting cap. The tier only needs to know whether the count is at or under
# T0_MAX_CALL_SITES, so counting stops here and reports a floor. Without this a
# symbol like `formatMessage` would mean opening two thousand files.
CALL_SITE_REPORT_CAP = 25

# Importer counting costs a `git grep` plus file reads per symbol, and this runs
# inside a hook timeout. A change touching more distinct exported symbols than
# this is broad by inspection, so counting them adds cost without changing the
# answer.
MAX_SYMBOLS_SCORED = 40
IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
ENUM_MEMBER_RE = re.compile(r"^[+-]\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=")
# `foo?: T` becoming `foo: T` is a break for every existing caller.
OPTIONAL_PROP_RE = re.compile(r"^[+-]\s*(?:readonly\s+)?([A-Za-z_$][A-Za-z0-9_$]*)(\??):")

RESERVED = {
    "export",
    "default",
    "from",
    "type",
    "interface",
    "enum",
    "const",
    "function",
    "class",
    "as",
    "declare",
    "readonly",
    "true",
    "false",
    "null",
    "undefined",
    "string",
    "number",
    "boolean",
}


def _default_git(args: Sequence[str], cwd: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout
    except OSError:
        return ""


def is_shallow(root_path: str, git: Optional[GitRunner] = None) -> bool:
    """A shallow clone has no merge base, so nothing here can be measured."""
    runner = git or _default_git
    return runner(["rev-parse", "--is-shallow-repository"], root_path).strip() == "true"


def unmerged_paths(root_path: str, git: Optional[GitRunner] = None) -> List[str]:
    """Paths with unresolved conflicts.

    A conflicted tree contains conflict markers, so its fingerprint, its diff,
    and any evidence captured from it describe a state that was never intended.
    Scoring it would produce a confident answer about a file nobody wrote.
    """
    runner = git or _default_git
    raw = runner(["diff", "--name-only", "--diff-filter=U"], root_path)
    return sorted(line.strip() for line in raw.splitlines() if line.strip())


def interrupted_operation(root_path: str, git: Optional[GitRunner] = None) -> str:
    """Name of an in-progress rebase/merge/cherry-pick, or an empty string."""
    git_dir = (git or _default_git)(["rev-parse", "--git-dir"], root_path).strip()
    if not git_dir:
        return ""
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(root_path, git_dir)
    for marker, label in (
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
        ("MERGE_HEAD", "merge"),
        ("CHERRY_PICK_HEAD", "cherry-pick"),
        ("BISECT_LOG", "bisect"),
    ):
        if os.path.exists(os.path.join(git_dir, marker)):
            return label
    return ""


WILDCARD_REEXPORT_RE = re.compile(r'export\s+\*\s+from\s+["\']([^"\']+)["\']')

# packages/<pkg>/src/index.ts wildcard re-exports several `<family>-exports.ts`
# barrels (menu, context-menu, ...) instead of naming every export directly.
# Adding or removing a name inside one of those barrels is a real surface
# change, but it never touches index.ts itself -- the `export * from "./x"`
# line is written once when the family is created, not per member. Detected
# by parsing index.ts rather than hardcoding barrel filenames, since the
# convention is not limited to files literally named `*-exports.ts`.
_WILDCARD_TARGET_CACHE: Dict[str, List[str]] = {}


def _package_index_path(root_id: str, path: str) -> str:
    """The owning package's own `src/index.ts`, relative to the root, or ''."""
    marker = "turbo/packages/" if root_id == "prepared911" else "packages/"
    if marker not in path:
        return ""
    prefix = path[: path.index(marker) + len(marker)]
    package = path[len(prefix) :].split("/", 1)[0]
    return "%s%s/src/index.ts" % (prefix, package)


def _wildcard_reexport_targets(root_path: str, index_rel: str) -> List[str]:
    cache_key = "%s\0%s" % (root_path, index_rel)
    if cache_key in _WILDCARD_TARGET_CACHE:
        return _WILDCARD_TARGET_CACHE[cache_key]
    targets: List[str] = []
    try:
        with open(os.path.join(root_path, index_rel), "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError:
        _WILDCARD_TARGET_CACHE[cache_key] = targets
        return targets
    base = os.path.dirname(index_rel)
    for match in WILDCARD_REEXPORT_RE.finditer(content):
        spec = match.group(1)
        if not spec.startswith("."):
            continue
        resolved = os.path.normpath(os.path.join(base, spec))
        for suffix in (".ts", ".tsx", "/index.ts", "/index.tsx"):
            candidate = (resolved + suffix).replace(os.sep, "/")
            if os.path.isfile(os.path.join(root_path, candidate)):
                targets.append(candidate)
                break
    _WILDCARD_TARGET_CACHE[cache_key] = targets
    return targets


def _is_wildcard_reexported(root_id: str, root_path: str, path: str) -> bool:
    index_rel = _package_index_path(root_id, path)
    if not index_rel or path == index_rel:
        return False
    return path in _wildcard_reexport_targets(root_path, index_rel)


def surface_paths(
    root_id: str, changed: Iterable[str], root_path: Optional[str] = None
) -> List[str]:
    patterns = [re.compile(p) for p in SURFACE_PATTERNS.get(root_id, ())]
    changed = list(changed)
    direct = {path for path in changed if any(pattern.search(path) for pattern in patterns)}
    if root_path:
        direct.update(
            path for path in changed if _is_wildcard_reexported(root_id, root_path, path)
        )
    return sorted(direct)


def risk_signals(changed: Iterable[str]) -> List[str]:
    found = []
    for path in changed:
        lowered = path.lower()
        for pattern, label in RISK_PATTERNS:
            if re.search(pattern, lowered) and label not in found:
                found.append(label)
    return sorted(found)


def _diff(root_path: str, base_ref: str, path: str, git: GitRunner) -> str:
    return git(["diff", "-U0", base_ref, "--", path], root_path)


DECLARED_EXPORT_RE = re.compile(
    r"^[+-]\s*export\s+(?:declare\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:const|let|var|function\*?|class|interface|type|enum)\s+"
    r"([A-Za-z_$][A-Za-z0-9_$]*)"
)
NAMED_EXPORT_RE = re.compile(r"^[+-]\s*export\s+(?:type\s+)?\{([^}]*)\}")
STAR_EXPORT_RE = re.compile(r"^[+-]\s*export\s+\*\s+(?:as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+)?from\s+['\"]([^'\"]+)['\"]")


def _export_names(line: str) -> List[str]:
    """Bindings an export line declares.

    Tokenizing the whole line was wrong in both directions: it read the path
    segments of `export * from "./components/navbar"` as exported names, and read
    a type annotation (`ReadonlyArray`) on an export line as an exported binding.
    """
    star = STAR_EXPORT_RE.match(line)
    if star:
        # `export * as ns from "m"` binds a namespace; a bare star re-exports a
        # module whose members are not named here, so there is nothing to count.
        return [star.group(1)] if star.group(1) else []

    declared = DECLARED_EXPORT_RE.match(line)
    if declared:
        return [declared.group(1)]

    named = NAMED_EXPORT_RE.match(line)
    if named:
        names = []
        for token in named.group(1).split(","):
            binding = token.strip()
            if not binding:
                continue
            binding = binding.split(" as ")[-1].strip()
            if binding.startswith("type "):
                binding = binding[len("type ") :].strip()
            if binding and binding not in RESERVED:
                names.append(binding)
        return names
    return []


def _star_module(line: str) -> str:
    star = STAR_EXPORT_RE.match(line)
    return star.group(2) if star else ""


def _classify_exports_json(root_path: str, base_ref: str, path: str, git: GitRunner) -> Tuple[str, List[str]]:
    """An `exports` map change is breaking unless it only adds subpaths."""
    before = git(["show", "%s:%s" % (base_ref, path)], root_path)
    try:
        old_map = json.loads(before).get("exports") or {}
    except (ValueError, AttributeError):
        return DELTA_NONE, []
    try:
        with open(os.path.join(root_path, path), "r", encoding="utf-8") as handle:
            new_map = json.load(handle).get("exports") or {}
    except (OSError, ValueError, AttributeError):
        return DELTA_NONE, []
    if old_map == new_map:
        return DELTA_NONE, []
    removed = sorted(set(old_map) - set(new_map))
    changed = sorted(key for key in set(old_map) & set(new_map) if old_map[key] != new_map[key])
    if removed or changed:
        return DELTA_BREAKING, ["exports:%s" % key for key in removed + changed]
    return DELTA_ADDITIVE, ["exports:%s" % key for key in sorted(set(new_map) - set(old_map))]


def classify_surface(
    root_id: str,
    root_path: str,
    changed: Sequence[str],
    base_ref: str = "HEAD",
    git: Optional[GitRunner] = None,
) -> Dict[str, object]:
    """Classify the public-surface delta as none, additive, or breaking."""
    runner = git or _default_git
    paths = surface_paths(root_id, changed, root_path)
    delta = DELTA_NONE
    evidence: List[str] = []
    symbols: List[str] = []

    for path in paths:
        if path.endswith("package.json"):
            path_delta, path_evidence = _classify_exports_json(root_path, base_ref, path, runner)
        else:
            path_delta, path_evidence, path_symbols = _classify_text_surface(
                root_path, base_ref, path, runner
            )
            symbols.extend(path_symbols)
        if path_evidence:
            evidence.extend("%s %s" % (path, item) for item in path_evidence)
        if path_delta == DELTA_BREAKING:
            delta = DELTA_BREAKING
        elif path_delta == DELTA_ADDITIVE and delta != DELTA_BREAKING:
            delta = DELTA_ADDITIVE

    return {
        "delta": delta,
        "surface_paths": paths,
        "evidence": evidence,
        "symbols": sorted(set(symbols)),
    }


def _classify_text_surface(
    root_path: str, base_ref: str, path: str, git: GitRunner
) -> Tuple[str, List[str], List[str]]:
    diff = _diff(root_path, base_ref, path, git)
    if not diff.strip():
        return DELTA_NONE, [], []

    removed_exports: List[str] = []
    added_exports: List[str] = []
    removed_members: List[str] = []
    added_members: List[str] = []
    tightened: List[str] = []
    optional_before: Dict[str, bool] = {}

    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if not line.startswith(("+", "-")):
            continue
        if EXPORT_RE.match(line):
            target = added_exports if line.startswith("+") else removed_exports
            names = _export_names(line)
            module = _star_module(line)
            if module:
                # A bare `export * from "./x"` names no bindings, so track the
                # module path itself: losing it is still a surface removal.
                target.append("*%s" % module)
            target.extend(names)
            continue
        member = ENUM_MEMBER_RE.match(line)
        if member:
            (added_members if line.startswith("+") else removed_members).append(member.group(1))
            continue
        prop = OPTIONAL_PROP_RE.match(line)
        if prop:
            name, optional = prop.group(1), bool(prop.group(2))
            if line.startswith("-"):
                optional_before[name] = optional
            elif optional_before.get(name) and not optional:
                tightened.append(name)

    lost_exports = sorted(set(removed_exports) - set(added_exports))
    lost_members = sorted(set(removed_members) - set(added_members))
    if lost_exports or lost_members or tightened:
        evidence = (
            ["removed export %s" % name for name in lost_exports]
            + ["removed enum member %s" % name for name in lost_members]
            + ["optional prop %s became required" % name for name in tightened]
        )
        return DELTA_BREAKING, evidence, lost_exports + added_exports

    gained_exports = sorted(set(added_exports) - set(removed_exports))
    gained_members = sorted(set(added_members) - set(removed_members))
    if gained_exports or gained_members:
        evidence = ["added export %s" % name for name in gained_exports] + [
            "added enum member %s" % name for name in gained_members
        ]
        return DELTA_ADDITIVE, evidence, gained_exports

    return DELTA_NONE, [], []


# prepared911's `turbo/packages/ui-*` tree is a byte-copy of axon's packages
# (CORE-754 made src/ identical at cutover), not a consumer of them. Counting it
# as a call site inflates the tier of every axon change by the size of the
# mirror. prepared911 *application* code referencing a symbol is a real consumer
# and still counts.
MIRROR_TREES = {
    "prepared911": r"^turbo/packages/ui-[^/]+/",
    "axon911-frontend": r"^packages/ui-[^/]+/",
}


def _is_mirror_of(owning_root: str, entry_root: str, path: str) -> bool:
    if entry_root == owning_root:
        return False
    pattern = MIRROR_TREES.get(entry_root)
    return bool(pattern and re.search(pattern, path))


def _is_surface_file(root_id: str, path: str, root_path: Optional[str] = None) -> bool:
    """True for export surfaces (barrels, export maps, models, published styles)."""
    return bool(surface_paths(root_id, [path], root_path))


def _owning_package(root_id: str, path: str) -> str:
    """The `ui-*` package a changed path belongs to, if any."""
    marker = "turbo/packages/" if root_id == "prepared911" else "packages/"
    if marker not in path:
        return ""
    tail = path.split(marker, 1)[1]
    package = tail.split("/", 1)[0]
    return package if package.startswith("ui-") else ""


def _imported_names(content: str) -> set:
    """Names a module actually imports, ignoring incidental mentions."""
    names = set()
    for block in IMPORT_BLOCK_RE.findall(content):
        for token in block.split(","):
            binding = token.strip()
            if not binding:
                continue
            binding = binding.split(" as ")[0].strip()
            if binding.startswith("type "):
                binding = binding[len("type ") :].strip()
            if binding:
                names.add(binding)
    names.update(IMPORT_DEFAULT_RE.findall(content))
    return names


def importer_counts(
    roots: Dict[str, str],
    symbols: Sequence[str],
    owning_root: str = "",
    owning_package: str = "",
    changed: Sequence[str] = (),
    git: Optional[GitRunner] = None,
) -> Dict[str, Dict[str, object]]:
    """Count call sites of each changed symbol, per symbol rather than per package.

    Package-level counting was the other reason everything read as broad: a change
    to one component in `ui-core` inherited the caller count of the whole package.

    Matching is whole-identifier (`git grep -w`), so `ButtonType` is not counted
    as a reference to `Button`.
    """
    runner = git or _default_git
    excluded = {"%s:%s" % (owning_root, path) for path in changed}
    counts: Dict[str, Dict[str, object]] = {}
    for symbol in symbols:
        files: List[str] = []
        for root_id, root_path in sorted(roots.items()):
            if root_id == "personal-harness":
                continue
            raw = runner(
                ["grep", "-l", "-w", "-e", symbol, "--", "*.ts", "*.tsx"],
                root_path,
            )
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    files.append("%s:%s" % (root_id, line))
        # Neither the files under edit nor a package barrel is a call site: the
        # first is the change, the second is the export surface, and the surface
        # is already measured by classify_surface. Counting a barrel as a
        # consumer inflates every count by one per re-exporting package.
        candidates = []
        for entry in files:
            entry_root, entry_path = entry.split(":", 1)
            if entry in excluded:
                continue
            if _is_surface_file(entry_root, entry_path, roots.get(entry_root)):
                continue
            if NON_API_FILE_RE.search(entry_path):
                continue
            if _is_mirror_of(owning_root, entry_root, entry_path):
                continue
            candidates.append(entry)
        # `git grep -w` finds mentions, not imports. A local variable named
        # `Error`, or a doc comment, is not a call site.
        call_sites = []
        truncated = False
        for entry in candidates:
            entry_root, entry_path = entry.split(":", 1)
            try:
                with open(os.path.join(roots[entry_root], entry_path), "r", encoding="utf-8") as handle:
                    content = handle.read()
            except (OSError, KeyError, UnicodeDecodeError):
                continue
            if symbol in _imported_names(content):
                call_sites.append(entry)
                if len(call_sites) >= CALL_SITE_REPORT_CAP:
                    truncated = True
                    break
        outside = [
            entry
            for entry in call_sites
            if not (
                owning_package
                and entry.startswith("%s:" % owning_root)
                and _owning_package(owning_root, entry.split(":", 1)[1]) == owning_package
            )
        ]
        counts[symbol] = {
            "call_sites": len(call_sites),
            "truncated": truncated,
            "outside_owning_package": len(outside),
            "roots": sorted({entry.split(":", 1)[0] for entry in call_sites}),
        }
    return counts


def local_exports(root_path: str, paths: Sequence[str]) -> List[str]:
    """Identifiers a changed file exports, for changes with no public surface delta.

    Without this, a behavior-only edit has no symbols to count and every such
    change looks equally narrow -- so a shared helper with thirty callers would
    score the same T0 as a leaf component with two.
    """
    names: List[str] = []
    for path in paths:
        if not path.endswith((".ts", ".tsx")):
            continue
        # Story and test exports are fixtures, not API. Counting them made a
        # Callout change look like it exported `AllColors` and `WithLoading`.
        if NON_API_FILE_RE.search(path):
            continue
        try:
            with open(os.path.join(root_path, path), "r", encoding="utf-8") as handle:
                content = handle.read()
        except OSError:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("export"):
                continue
            match = re.match(
                r"export\s+(?:default\s+)?(?:async\s+)?"
                r"(?:const|let|var|function|class|interface|type|enum)\s+"
                r"([A-Za-z_$][A-Za-z0-9_$]*)",
                stripped,
            )
            if match:
                names.append(match.group(1))
            elif stripped.startswith(("export {", "export type {")):
                inner = stripped[stripped.index("{") + 1 :].split("}")[0]
                for token in inner.split(","):
                    binding = token.strip()
                    if not binding:
                        continue
                    # `export { a as b }` exports b; `export type { T }` exports T.
                    binding = binding.split(" as ")[-1].strip()
                    if binding.startswith("type "):
                        binding = binding[len("type ") :].strip()
                    if binding:
                        names.append(binding)
    return sorted({name for name in names if name and name not in RESERVED})


def compute_tier(
    changes: Dict[str, Sequence[str]],
    roots: Dict[str, str],
    base_ref: str = "HEAD",
    stated: Optional[str] = None,
    git: Optional[GitRunner] = None,
) -> Dict[str, object]:
    """Compute the tier from measured evidence and name the predicate that fired.

    `changes` maps root id to that root's changed paths, so a change spanning
    roots is visible here rather than inferred.
    """
    runner = git or _default_git
    active = {root: list(paths) for root, paths in changes.items() if paths}

    unmeasurable: List[str] = []
    unmeasurable_reasons: List[str] = []
    for root in sorted(active):
        if root not in roots:
            continue
        if is_shallow(roots[root], git=runner):
            unmeasurable.append(root)
            unmeasurable_reasons.append(
                "%s is a shallow clone: no merge base, so surface delta and call "
                "sites cannot be measured (git fetch --unshallow)" % root
            )
            continue
        conflicts = unmerged_paths(roots[root], git=runner)
        if conflicts:
            unmeasurable.append(root)
            unmeasurable_reasons.append(
                "%s has %d unresolved conflict(s) (%s): the tree contains conflict "
                "markers, so its fingerprint and any evidence from it describe a "
                "state nobody authored -- resolve before scoring"
                % (root, len(conflicts), ", ".join(conflicts[:3]))
            )
            continue
        interrupted = interrupted_operation(roots[root], git=runner)
        if interrupted:
            unmeasurable.append(root)
            unmeasurable_reasons.append(
                "%s has an interrupted %s in progress: HEAD is not the intended "
                "commit, so a ref manifest built here is not reproducible"
                % (root, interrupted)
            )

    all_paths = [path for paths in active.values() for path in paths]
    risks = risk_signals(all_paths)

    surface: Dict[str, Dict[str, object]] = {}
    delta = DELTA_NONE
    evidence: List[str] = []
    for root_id, paths in sorted(active.items()):
        if root_id not in roots:
            continue
        result = classify_surface(root_id, roots[root_id], paths, base_ref=base_ref, git=runner)
        surface[root_id] = result
        root_delta = str(result["delta"])
        if root_delta == DELTA_BREAKING:
            delta = DELTA_BREAKING
        elif root_delta == DELTA_ADDITIVE and delta != DELTA_BREAKING:
            delta = DELTA_ADDITIVE
        evidence.extend("%s: %s" % (root_id, item) for item in result["evidence"])  # type: ignore[arg-type]

    symbols = sorted({s for r in surface.values() for s in r["symbols"]})  # type: ignore[index]
    owning_root = next(iter(sorted(active)), "")
    if not symbols and owning_root in roots:
        # No public surface delta: fall back to what the changed files export, so
        # internal reuse still separates a leaf change from a shared one.
        symbols = local_exports(roots[owning_root], active.get(owning_root, []))
    owning_package = ""
    for path in active.get(owning_root, []):
        owning_package = _owning_package(owning_root, path)
        if owning_package:
            break

    # Call-site counts only decide T0 vs T1. When a T2 predicate has already
    # fired the answer cannot change, so skip the work entirely -- it is the
    # expensive part and this runs inside a hook timeout.
    tier_already_broad = bool(unmeasurable) or len(active) > 1 or bool(risks) or delta == DELTA_BREAKING
    symbols_over_cap = len(symbols) > MAX_SYMBOLS_SCORED
    importers: Dict[str, Dict[str, object]] = {}
    if symbols and not tier_already_broad and not symbols_over_cap:
        importers = importer_counts(
            roots,
            symbols,
            owning_root,
            owning_package,
            changed=active.get(owning_root, []),
            git=runner,
        )
    max_outside = max(
        [int(meta["outside_owning_package"]) for meta in importers.values()] or [0]
    )
    max_call_sites = max([int(meta["call_sites"]) for meta in importers.values()] or [0])

    # Ordered by severity; the first match is the named predicate.
    if unmeasurable:
        tier, predicate = "T2", "unmeasurable"
        evidence.extend(unmeasurable_reasons)
    elif len(active) > 1:
        tier, predicate = "T2", "cross-root"
        evidence.append("changes span roots: %s" % ", ".join(sorted(active)))
    elif risks:
        tier, predicate = "T2", "risk:%s" % risks[0]
        evidence.append("risk signals: %s" % ", ".join(risks))
    elif delta == DELTA_BREAKING:
        tier, predicate = "T2", "surface-breaking"
    elif delta == DELTA_ADDITIVE:
        tier, predicate = "T1", "surface-additive"
    elif symbols_over_cap:
        tier, predicate = "T1", "many-symbols"
        evidence.append(
            "%d distinct exported symbols changed, over the %d scored for call "
            "sites: broad by inspection" % (len(symbols), MAX_SYMBOLS_SCORED)
        )
    elif max_call_sites <= T0_MAX_CALL_SITES:
        tier, predicate = "T0", "leaf"
        evidence.append(
            "no public surface delta; %d call site(s) of changed symbols "
            "(%d outside the owning package), at or under the T0 limit of %d"
            % (max_call_sites, max_outside, T0_MAX_CALL_SITES)
        )
    else:
        tier, predicate = "T1", "internal-reuse"
        evidence.append(
            "no public surface delta, but %d call site(s) of changed symbols "
            "(%d outside the owning package) exceeds the T0 limit of %d"
            % (max_call_sites, max_outside, T0_MAX_CALL_SITES)
        )

    return {
        "tier": tier,
        "predicate": predicate,
        "evidence": evidence,
        "surface_delta": delta,
        "surface": surface,
        "symbols": symbols,
        "importers": importers,
        "call_sites_scored": bool(importers),
        "risk_signals": risks,
        "unmeasurable_roots": unmeasurable,
        "measurable": not unmeasurable,
        "roots_touched": sorted(active),
    }


def reconcile(computed: Dict[str, object], stated: Optional[str]) -> Dict[str, object]:
    """Compare a plan's stated tier with the computed one, both directions.

    Understatement has always been a defect. Overstatement is one too: an
    inflated tier burns a full panel on a leaf change and teaches you to ignore
    the number, which is how the hierarchy stopped meaning anything.
    """
    tier = str(computed["tier"])
    if stated is None or stated not in TIER_RANK:
        return {"verdict": "unstated", "effective": tier, "stated": stated, "computed": tier}
    stated_rank, computed_rank = TIER_RANK[stated], TIER_RANK[tier]
    if stated_rank < computed_rank:
        verdict = "understated"
    elif stated_rank > computed_rank:
        verdict = "overstated"
    else:
        verdict = "match"
    return {
        "verdict": verdict,
        # A stated tier is a floor for panel size, so understatement still runs
        # the computed tier. Overstatement drops to what the evidence supports.
        "effective": tier,
        "stated": stated,
        "computed": tier,
        "predicate": computed["predicate"],
    }
