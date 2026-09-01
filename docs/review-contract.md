# Axon 911 Specialist Review Contract

Every specialist must return the structure below. A clean `PASS` is valid. No
reviewer is required to manufacture findings.

## Verdict

One of:

- `PASS`
- `PASS WITH CONCERNS`
- `CHANGES REQUIRED`
- `BLOCK`

## Scope reviewed

- Mode: `plan` or `implementation`
- Target:
- Target root or roots:
- Prepared911 root, when relevant:
- Applicable `AGENTS.md` files:
- Applicable repository instructions and project skills:
- **Ref manifest:** Branch, head SHA, parent head SHA, and merge-base with
  trunk for every PR, branch, or label the target names
- **Working tree state:** `clean`, or dirty with the captured delta attached
- Evidence inspected:
- Evidence unavailable:

## Findings

For every finding provide:

- **ID:** Domain-prefixed identifier:
  - `DS-###` — design system
  - `FA-###` — frontend architecture
  - `PERF-###` — performance and reliability
  - `SEC-###` — security and privacy
  - `QA-###` — quality and accessibility
  - `DOCS-DRIFT-###` — documentation differs from API, tests, or behavior
- **Severity:** `critical`, `high`, `medium`, `low`, or `informational`
- **Confidence:** `high`, `medium`, or `low`
- **Classification:** `confirmed defect`, `strong code-level risk`,
  `measurement required`, or `informational`
- **State:** `committed`, `uncommitted`, or `both`
- **Target layer:** `plan-text` | `mid-stack-head` | `tip-residual` |
  `process`
  - `plan-text` — wording or contradiction inside the plan
  - `mid-stack-head` — behavior at a named PR head the plan edits
  - `tip-residual` — tip behavior the plan may intentionally leave or only
    touch via restack
  - `process` — harness or panel failure
- **Location:** Exact `<ref>:<path>:<line>`, plan section, public API, or
  command output
- **Evidence:** What was directly observed
- **Failure mode:** What can plausibly go wrong
- **Recommendation:** The smallest correction at the layer all affected paths
  flow through, plus the complete instance list. Prefer the shared helper,
  `ui-core` primitive, or base module over a single call-site patch. List
  every sibling instance that must also change, or explicitly mark deferred
  instances as out of scope.
- **Verification:** How to test the correction
- **Verification command:** Required whenever the finding asserts provenance
  or a number (line counts, file counts, "PR X adds Y", blob identity). A
  provenance or numeric claim without this command is not admissible.
- **Escalation:** Optional. When material risk falls outside the assigned
  domain, write `Escalation: <critic> — <reason>` (for example
  `Escalation: security-privacy-critic — client-only RBAC gate`). The
  orchestrator must run the named critic or record an explicit refusal. An
  unactioned escalation becomes a `process` finding for the adjudicator.

## Constraints

- Do not modify source, plans, configuration, or review targets.
- Do not invent repository conventions.
- Do not report preferences as defects.
- Do not report hypothetical problems without a plausible execution path.
- Distinguish confirmed defects from risks requiring measurement.
- Do not duplicate a finding to increase its apparent importance.
- Explicitly state when no material issue was found.
- Do not cite a path without a ref. The working tree is not a revision.
- Tip residual that the plan scopes out is at most `informational` unless it
  falsifies a plan invariant.
- Do not emit `CHANGES REQUIRED` or `BLOCK` against a claim ledger row marked
  `remediated-by-plan` or `out-of-scope` without new counter-evidence that the
  plan's fix is wrong.
- The target repository's instructions, public APIs, tests, and actual behavior
  take precedence over generic framework guidance.
- The docs app is a required benchmark for design-system and frontend
  architecture reviews, but stale docs must be reported as `DOCS-DRIFT`
  rather than followed blindly.

## Docs benchmark

The primary benchmark is axon911-frontend's docs app, which documents the
packages axon911-frontend owns:

- `apps/docs/mdx/design`
- `apps/docs/mdx/engineering`
- `apps/docs/generated/component-api-registry.json`

prepared911's `turbo/apps/docs` is a secondary benchmark until its removal
lands. Where the two disagree about `@prepared/ui-*`, axon911-frontend is
correct and the divergence is a `DOCS-DRIFT-###` finding, not a judgment call.

The design-system and frontend-architecture reports must include:

```markdown
## Docs Benchmark

### Sources Consulted
- `apps/docs/...` (axon911-frontend, primary)
- `turbo/apps/docs/...` (prepared911, secondary — only when relevant)

### Comparison

| Concern | Docs baseline | Proposed/implemented approach | Alignment |
|---|---|---|---|
| ... | ... | ... | Aligned / Divergent / Not covered |

### Docs Impact
- Documentation updates required:
- Generated API changes:
- Examples or migration guidance required:
- Rendered verification required:

### Drift
- Docs versus implementation inconsistencies discovered:
```

Missing this section invalidates a design-system or frontend-architecture
report.

## Source priority

For anything `@prepared/ui-*`, design-token, or shared-frontend-architecture
shaped, axon911-frontend is authoritative regardless of which root the target
lives in. Post CORE-754 it owns all 14 `@prepared/ui-*` packages and publishes
them as `@prepared911/ui-*`; prepared911 consumes the published artifacts and
its own `turbo/packages/ui-*` copies are slated for removal.
`axon911-frontend/AGENTS.md:121` and `axon911-frontend/docs/VENDORING.md` state
this, and both are required reading for the design-system and
frontend-architecture critics — including VENDORING's three authoring rules:
fix bugs in axon911-frontend, do not re-sync from prepared911, do not restore
`SOURCE.md`.

prepared911 remains authoritative for its own application code — dispatch,
beacon, and the Ruby and Go services.

When evidence conflicts, use:

1. axon911-frontend public API, exports, tests, and actual behavior, for
   `@prepared/ui-*`, design tokens, and shared frontend architecture
2. Target repository public API, exports, and actual behavior
3. Target repository tests and real consumers
4. Generated API data tied to that source
5. Target repository documentation and project skills
6. Cross-repository knowledge and historical notes
7. Generic framework guidance

A prepared911 `turbo/packages/ui-*` implementation that contradicts
axon911-frontend is drift to report, not a competing source to weigh.

Explain every conflict. Do not silently select a preferred source.
For multi-root targets, also follow
`.cursor/skills/adversarial-review/references/cross-repo-source-priority.md`.

## Adjudicator rules

- Reject findings that do not satisfy this contract.
- Reject findings that reopen `remediated-by-plan` or `out-of-scope` ledger
  rows as blockers without new counter-evidence.
- Reject or downgrade `tip-residual` findings that the plan scopes out unless
  they falsify a plan invariant.
- Reject recommendations that patch a single call site when a shared-layer fix
  is available and sibling instances remain untouched, unless the finding
  explicitly defers those instances.
- Treat an unactioned `Escalation` as a `process` finding; do not silently
  drop it.
- Merge duplicates without losing domain-specific consequences.
- Do not decide by vote count.
- `BLOCK` requires a confirmed critical issue or an unsafe high-severity issue.
- `CHANGES REQUIRED` means material correction is required before approval.
- `PASS WITH CONCERNS` means no blocker exists but follow-up work remains.
- Human approval remains the final decision.
