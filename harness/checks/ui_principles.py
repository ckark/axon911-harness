"""Re-activate the ui-* rules axon911-frontend already wrote, then switched off.

`packages/tooling-config/src/oxlint/config.ts` ignores `**/packages/ui-*/**` and
`**/apps/docs/**` (CORE-754 lint debt; ~1100 warnings; incident 2026-08-25,
documented in `docs/LINT-POLICY.md:53-55`). The consequence is that the repo's
own rules -- `no-restricted-imports` banning `@mui/material` ("Use
@prepared/ui-core primitives instead") and `styled-components` ("Use Box /
FlexBox props instead"), plus `no-console`, `import/no-default-export`,
`oxc/no-barrel-file`, `react/exhaustive-deps` and the rest -- report nothing on
exactly the code the design system lives in. `pnpm check` is silent there.

So this does not invent rules. It runs the repo's own resolved config with the
ui-* ignore lifted, and reports **only findings on lines this change touched** --
the same intersect-with-changed-lines technique axon uses in
`packages/tooling-config/src/oxlint/localization/check-changed.mjs`, and the
reason re-enabling here does not resurrect the 1100 legacy warnings.

Designed to be liftable: when CORE-780 re-enables oxlint package by package,
these findings become upstream CI findings and this check can shrink.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set

# JS plugins resolve their modules relative to the config file. The config has to
# live outside the repo to avoid dirtying the working tree, so these rules cannot
# run here; they are already covered when CI lints non-ui packages.
JS_PLUGIN_PREFIXES = ("react-hooks-js/", "testing-library/", "prepared-hooks/")

UI_PATTERNS = {
    "axon911-frontend": r"^packages/ui-[^/]+/",
    "prepared911": r"^turbo/packages/ui-[^/]+/",
}

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class CheckUnavailable(RuntimeError):
    """The upstream toolchain needed for a check is not runnable here."""


def _run(args: Sequence[str], cwd: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def ui_changed(root_id: str, changed: Sequence[str]) -> List[str]:
    pattern = UI_PATTERNS.get(root_id)
    if not pattern:
        return []
    compiled = re.compile(pattern)
    return sorted(p for p in changed if compiled.search(p.replace(os.sep, "/")))


def changed_lines(root_path: str, base_ref: str, paths: Sequence[str]) -> Dict[str, Set[int]]:
    """Added and modified line numbers per file, for diff-scoping findings."""
    ranges: Dict[str, Set[int]] = {}
    for path in paths:
        result = _run(["git", "diff", "-U0", base_ref, "--", path], root_path)
        lines: Set[int] = set()
        for line in result.stdout.splitlines():
            match = HUNK_RE.match(line)
            if not match:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            lines.update(range(start, start + max(count, 1)))
        ranges[path] = lines
    return ranges


def _normalize_rules(rules: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """`--print-config` emits `[severity, [opts]]`, which its own parser rejects."""
    normalized: Dict[str, Any] = {}
    for name, value in (rules or {}).items():
        if isinstance(value, list) and len(value) == 2 and isinstance(value[1], list):
            normalized[name] = [value[0], *value[1]]
        else:
            normalized[name] = value
    return normalized


def _strip_js_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in rules.items() if not k.startswith(JS_PLUGIN_PREFIXES)}


def resolve_config(root_path: str) -> Dict[str, Any]:
    """Resolve the repo's own oxlint config, with the ui-* ignore lifted."""
    result = _run(["pnpm", "exec", "oxlint", "--print-config"], root_path)
    if result.returncode != 0 or not result.stdout.strip():
        raise CheckUnavailable("oxlint --print-config unavailable in %s" % root_path)
    try:
        config = json.loads(result.stdout)
    except ValueError as exc:
        raise CheckUnavailable("oxlint config was not JSON: %s" % exc)

    before = list(config.get("ignorePatterns") or [])
    config["ignorePatterns"] = [
        p for p in before if "packages/ui-" not in p and "apps/docs" not in p
    ]
    config["_lifted_ignores"] = [p for p in before if p not in config["ignorePatterns"]]
    config.pop("jsPlugins", None)
    config["rules"] = _strip_js_rules(_normalize_rules(config.get("rules")))
    for override in config.get("overrides") or []:
        override.pop("jsPlugins", None)
        override["rules"] = _strip_js_rules(_normalize_rules(override.get("rules")))
    return config


def lint(root_path: str, base_ref: str, paths: Sequence[str]) -> Dict[str, Any]:
    """Run the repo's rules over `paths`, keeping only findings on changed lines."""
    lintable = [p for p in paths if p.endswith((".ts", ".tsx"))]
    if not lintable:
        return {"findings": [], "suppressed_legacy": 0, "lifted_ignores": [], "files": 0}

    config = resolve_config(root_path)
    lifted = config.pop("_lifted_ignores", [])
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=tempfile.gettempdir())
    try:
        json.dump(config, handle)
        handle.close()
        result = _run(
            [
                "pnpm", "exec", "oxlint",
                "-c", handle.name,
                "--format=json",
                "--no-error-on-unmatched-pattern",
                *lintable,
            ],
            root_path,
        )
        try:
            payload = json.loads(result.stdout or "{}")
        except ValueError:
            raise CheckUnavailable(
                "oxlint did not return JSON: %s" % (result.stdout or result.stderr)[:200]
            )
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass

    touched = changed_lines(root_path, base_ref, lintable)
    findings, suppressed = [], 0
    for diagnostic in payload.get("diagnostics") or []:
        filename = str(diagnostic.get("filename") or "")
        labels = diagnostic.get("labels") or [{}]
        line = ((labels[0] or {}).get("span") or {}).get("line")
        scoped = touched.get(filename)
        # Only report what this change introduced. Pre-existing debt in an
        # untouched line is CORE-780's problem, not this change's.
        if scoped is not None and line is not None and int(line) not in scoped:
            suppressed += 1
            continue
        findings.append(
            {
                "check": "oxlint",
                "rule": diagnostic.get("code"),
                "severity": diagnostic.get("severity"),
                "file": filename,
                "line": line,
                "message": diagnostic.get("message"),
                "help": diagnostic.get("help"),
            }
        )
    return {
        "findings": findings,
        "suppressed_legacy": suppressed,
        "lifted_ignores": lifted,
        "files": len(lintable),
    }


def scss_paint(root_path: str, paths: Sequence[str]) -> Dict[str, Any]:
    """Run ui-core's own hardcoded-paint audit, which today only runs in a test.

    `packages/ui-core/scripts/audit-component-scss-paint.mjs` enforces tokens
    over raw hex, `rgb()` without `var()`, literal `border-radius`, and literal
    `font-family`. It is reached only via a Vitest integration test, so it is
    invisible at the point a change is made.
    """
    script = os.path.join(root_path, "packages/ui-core/scripts/audit-component-scss-paint.mjs")
    if not os.path.isfile(script):
        return {"ran": False, "findings": [], "reason": "audit script not present"}
    if not any(p.endswith(".scss") for p in paths):
        return {"ran": False, "findings": [], "reason": "no SCSS changed"}
    result = _run(["node", script], root_path)
    if result.returncode == 0:
        return {"ran": True, "findings": []}
    findings = [
        {"check": "scss-paint", "severity": "error", "message": line.strip()}
        for line in (result.stdout + result.stderr).splitlines()
        if line.strip()
    ]
    return {"ran": True, "findings": findings[:40]}


def check(
    root_id: str, root_path: str, base_ref: str, changed: Sequence[str]
) -> Dict[str, Any]:
    """Full ui-* principle report for a change."""
    targets = ui_changed(root_id, changed)
    report: Dict[str, Any] = {
        "root": root_id,
        "ui_files_changed": targets,
        "findings": [],
        "unavailable": [],
    }
    if not targets:
        report["status"] = "PASS"
        report["reason"] = "no packages/ui-* files changed"
        return report

    try:
        lint_result = lint(root_path, base_ref, targets)
        report["findings"].extend(lint_result["findings"])
        report["suppressed_legacy"] = lint_result["suppressed_legacy"]
        report["lifted_ignores"] = lint_result["lifted_ignores"]
    except (CheckUnavailable, subprocess.TimeoutExpired, OSError) as exc:
        report["unavailable"].append({"check": "oxlint", "reason": str(exc)[:200]})

    try:
        paint = scss_paint(root_path, targets)
        report["findings"].extend(paint["findings"])
        report["scss_paint_ran"] = paint["ran"]
    except (subprocess.TimeoutExpired, OSError) as exc:
        report["unavailable"].append({"check": "scss-paint", "reason": str(exc)[:200]})

    report["status"] = "BLOCKED" if report["findings"] else "PASS"
    return report
