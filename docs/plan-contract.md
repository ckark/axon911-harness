# Prepared911 Plan Contract

Every implementation plan authored in this workspace must satisfy the structure
below. Fields exist because adversarial-review Phases 2a/2b and the adjudicator
already consume them. A plan that omits them forces the review harness to
reconstruct evidence the author could have provided.

## Required sections

### Target roots

List every root the plan will modify:

- `prepared911`
- `axon911-frontend`
- `vault-core-ux`

Do not claim a root is in scope without identifying at least one path under it.

### Ref manifest

For every PR, branch, or label the plan names, record:

| Field | Value |
|---|---|
| Branch name | |
| Head SHA | |
| Parent branch head SHA | |
| Merge-base with trunk | |

Build rows with the recipes in
`.cursor/skills/adversarial-review/references/evidence-capture.md`. Cite pinned
refs, not the working tree.

### Self-authored claim ledger

One row per falsifiable repository claim the plan makes (which PR adds a file,
which files a change touches, what a generated artifact contains, how large a
diff is, whether an export exists):

| Claim as written | Command | Raw result | Verdict |
|---|---|---|---|
| … | exact shell command | truncated raw output | `confirmed` / `refuted` / `unverifiable` |

A plan may not ship a `refuted` row. Resolve or remove the claim before
presenting the plan. Prefer the claim recipes in `evidence-capture.md`.

### Blast radius and tier

State exactly one of `T0`, `T1`, or `T2`, justified by caller counts rather
than file counts. Use the blast-radius recipe in `evidence-capture.md`. A `T0`
classification requires the importer count, not an assertion.

Tier definitions live in `docs/routing-matrix.md`.

### Affected consumers

List packages, apps, public exports, stories, and docs pages that import or
document anything the plan changes. Empty is valid only when the blast-radius
recipe returns zero importers outside the changed leaf.

### Verification plan

For each implementation task, state the exact command that proves it done, and
the rendered-evidence obligation for any change a user can see:

- Storybook story, docs page, or Playwright screenshot
- Before-and-after when changing something that already exists

Defer root-specific command catalogs to `docs/implementation-contract.md`.

### Generated-artifact and docs obligations

- Name the specific `turbo/apps/docs` page for every `ui-*` package change.
- State whether `ui-components.generated.ts` (or the equivalent generated
  registry for the target root) needs regeneration.
- State "none" explicitly when neither applies.

### Deferred and out-of-scope

List every known related concern the plan deliberately does not address.
Without this section, review-contract downgrades for `out-of-scope` and
`remediated-by-plan` cannot apply.

## Completeness verdict

A plan is contract-complete only when every required section is present and the
claim ledger contains no `refuted` rows. `/plan-check` reports this verdict
before any critic runs.

## Constraints

- Do not invent repository conventions.
- Do not treat the working tree as a revision.
- Prefer rules and documentation over tech-debt patterns in existing code.
- Resolve the target root before choosing commands or package conventions.
- Plans for ordinary work should still be reviewable by `/plan-check` even when
  `/adversarial-review mode=plan` is not requested.
