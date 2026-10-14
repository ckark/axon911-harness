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

## Envelope (orchestrator context)

Critics write the full report to
`.harness/runtime/reports/<critic>-<fingerprint>.md`. The orchestrator receives
only:

- Verdict
- Finding IDs with severity
- Report path
- Fingerprint and plan hash

Full report text must not enter the orchestrator context.

## Findings

For every finding provide:

- **ID:** Domain-prefixed identifier (`DS-###`, `FA-###`, `DOCS-DRIFT-###`,
  `INTENT-###`, …). An `INTENT-###` finding names the principle id, the
  observed behavior, the user consequence, and the smallest correction. Use
  full severity when citing DP-* or DSP-* ids from
  [design-principles.md](design-principles.md) (authoritative for review).
- **Severity:** `critical`, `high`, `medium`, `low`, or `informational`
- **Location:** Exact `<ref>:<path>:<line>`, plan section, public API, or command output
- **Evidence:** What was directly observed
- **Recommendation:** The smallest correction at the shared layer
- **Verification command:** Required for provenance or numeric claims

T0 short form: verdict, findings, one verification command, HEAD SHA only in
scope reviewed (no four-ref manifest).

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
- The docs app is a required benchmark when `packages/ui`, `packages/ui-*`, or
  `apps/docs` changed; stale docs must be reported as `DOCS-DRIFT`. Prefer the
  `prepared-docs` MCP over hand-read MDX.

## Docs benchmark

Required only when changed paths touch `packages/ui`, `packages/ui-*`, `apps/docs`, or the
prepared911 mirror. Source from the `prepared-docs` MCP when available.

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

Missing this section when ui-* or docs paths changed invalidates the report.

## Definitive visual acceptance

The visual verifier must be distinct from the authoring session. It receives
the expected outcomes, changed-path summary, full-resolution images, contact
sheet, and v4 health receipts. Its report records PASS or FAIL for every
`change_id` and binds the product trees, staged harness tree, evidence-manifest
hash, artifact hashes, and reviewer identity.

Visual acceptance does not replace deterministic provenance checks, Bugbot, or
the T2 architecture and security review. A `not-applicable` row is reviewed
through its machine-checked absence or static verification result and has no
image verdict.

## Source priority

For anything `@prepared/ui-*`, design-token, or shared-frontend-architecture
shaped, axon911-frontend is authoritative regardless of which root the target
lives in. Post CORE-754 it owns all 14 `@prepared/ui-*` packages and publishes
them as `@prepared911/ui-*`; prepared911 consumes the published artifacts and
its own `turbo/packages/ui-*` copies are slated for removal.
`axon911-frontend/AGENTS.md:121` and `axon911-frontend/docs/VENDORING.md` state
this, and both are required reading for the design-system critic — including VENDORING's three authoring rules:
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
