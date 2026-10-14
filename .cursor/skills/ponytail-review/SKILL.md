---
name: ponytail-review
description: >
  Read-only complexity review for over-engineering. Finds what to delete:
  reinvented stdlib, unneeded dependencies, speculative abstractions. Outputs
  SIMPLIFY-### findings at low or informational severity only. Use when the
  user asks to review for over-engineering, simplify a diff, or what can be
  deleted. Does not replace Bugbot, security review, or design-system critic;
  does not issue review receipts.
---

# Ponytail complexity review (harness)

Read-only. Never modify files. Follow `docs/review-contract.md` for report
structure; this skill adds complexity-only scope and caps severity.

## Scope

Over-engineering and unnecessary complexity in the **current diff** only.
Correctness bugs, security holes, and performance regressions are out of scope;
route those to Bugbot or `security-review`.

Do **not** recommend deleting: required tests, TSDoc on new public APIs,
checked-in generated files, docs obligations for `ui-*` changes, BEM/SCSS
structure mandated by repo rules, or plan-declared verification commands.

## Output

Write the full report to
`.harness/runtime/reports/ponytail-review-<fingerprint>.md`.

Return only a short envelope to the orchestrator (verdict, finding IDs,
report path, fingerprint, plan hash). Do not issue `issue-review-receipt`; this
critic is not in the receipt gate.

## Verdict

Use review-contract verdicts. Prefer `PASS` or `PASS WITH CONCERNS`. Use
`CHANGES REQUIRED` only when deletion would materially reduce risk of ongoing
complexity (not for style preferences alone).

## Findings

For each item:

- **ID:** `SIMPLIFY-001`, `SIMPLIFY-002`, …
- **Severity:** `low` or `informational` only (never critical/high/medium for
  complexity-only notes).
- **Location:** `<ref>:<path>:<line>` or plan section.
- **Evidence:** What was observed in the diff.
- **Recommendation:** One line: what to cut and what replaces it (tag below).
- **Verification command:** Optional; required only if the finding cites numeric
  or provenance claims.

Tags (inline in recommendation):

- `delete:` dead code, unused flexibility, speculative feature. Replacement: nothing.
- `stdlib:` hand-rolled thing the standard library ships. Name the function.
- `native:` dependency or code doing what the platform already does.
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.

## Scoring

End the findings section with: `net: -N lines possible.` If nothing to cut,
state `Lean already. Ship.` and stop.

## After review

Optionally classify each finding:

```bash
python3 harness/cli.py jev check-findings --file .harness/runtime/reports/ponytail-review-<fingerprint>.md --json
```

Uncertain classifications stay with the human reviewer. Findings do not enter
the adversarial-review receipt path unless folded into the human PR test plan.

## Boundaries

Does not apply fixes. Does not duplicate design-system or security findings.
A single smoke test or minimal unit test required by the plan is not bloat.
