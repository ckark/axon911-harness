# Ponytail (vendored, adapted)

## Provenance

| Field | Value |
|-------|--------|
| Upstream | https://github.com/DietrichGebert/ponytail |
| Version | 4.10.0 |
| Pinned commit | `e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156` |
| Fetched | 2026-09-22 |
| License | MIT ([third_party/ponytail/LICENSE](../third_party/ponytail/LICENSE)) |

This file is adapted text only. The harness does **not** install upstream Cursor
hooks, global mode flags, or the ponytail MCP. See `docs/reuse-audit.md`.

## When this applies

Use the ladder below for **code authoring** in a product root after you have read
that root's `AGENTS.md` and any active plan. It does **not** apply to research,
Notion or PRD editing, docs-only work, or review-only tasks.

## Precedence

Repository `AGENTS.md`, harness contracts (`docs/plan-contract.md`,
`docs/implementation-contract.md`, `docs/review-contract.md`), project skills,
and explicit user rules **override** this ladder. Examples: BEM + SCSS per
component, TSDoc on new props, docs-page updates for `ui-*` changes, checked-in
generated files, `LocalizedMessage` on visible text, and Module Federation shared
deps in both remote and shell configs.

## Lazy senior dev ladder

Before writing code, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern
   that is already here; do not rewrite it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs **after** you understand the problem, not instead of it: read the
task and the code it touches, trace the real flow end to end, then climb.

**Bug fix = root cause, not symptom:** a report names a symptom. Grep every caller
of the function you touch and fix the shared function once. One guard there is a
smaller diff than one per caller; patching only the path the ticket names leaves
a sibling caller still broken.

## Rules

- No abstractions that were not explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem. The
  smallest change in the wrong place is not lazy; it is a second bug.
- Question complex requests before expanding scope: "Do you actually need X, or
  does Y cover it?" Do **not** reopen scope while executing an approved plan;
  scope questions belong in `/plan-check`.
- Pick the edge-case-correct option when two stdlib approaches are the same
  size; lazy means less code, not the flimsier algorithm.
- Deliberate simplifications with a known ceiling (global lock, O(n²) scan, naive
  heuristic): describe the ceiling and upgrade path in the **response and PR
  body**, not in code comments.

## Not lazy about

Understanding the problem (read fully and trace the real flow before picking a
rung), input validation at trust boundaries, error handling that prevents data
loss, security, accessibility, calibration real hardware needs, and anything
explicitly requested.

Non-trivial logic needs the **smallest test that fails if the logic breaks**,
written in the target repository's existing framework (Vitest, React Testing
Library, or Playwright per that repo's `docs/TESTING.md`). Trivial one-liners
need no test. Required plan obligations, generated files, TSDoc, and docs
updates are never optional cuts.

## Optional complexity review

For diffs that add new files, dependencies, or abstractions, run
`/ponytail-review` or load `.cursor/skills/ponytail-review/SKILL.md`. Findings
are advisory (`SIMPLIFY-###`, low or informational severity); they do not satisfy
`issue-review-receipt`.

## Local adaptations (from upstream AGENTS.md)

| Upstream | Harness |
|----------|---------|
| Inline shortcut comments in code for deferred work | Describe in response / PR only |
| Assert-only self-check without repo test stack | Smallest test in repo's Vitest/RTL/Playwright stack |
| Unqualified "question complex requests" | Scope questions only before plan lock; use `/plan-check` |
| Applies everywhere | Code authoring in product roots only |
| Self-referential ponytail-repo line | Removed |

## Updating the vendored copy

1. Choose a new upstream tag or commit on https://github.com/DietrichGebert/ponytail.
2. Diff `AGENTS.md` and `skills/ponytail-review/SKILL.md` against this file and
   `.cursor/skills/ponytail-review/SKILL.md`.
3. Reapply the **Local adaptations** table above.
4. Update the provenance header (version, SHA, fetch date).
5. Refresh `third_party/ponytail/LICENSE` if the upstream license changed.
6. Run `python3 -m unittest harness.tests.test_ponytail_vendor -v` and `pnpm`-free
   full harness tests per `AGENTS.md`.

No network access is required at runtime or in CI for ponytail; only this
maintainer refresh step may fetch upstream.
