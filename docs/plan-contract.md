# Axon 911 Plan Contract

Every implementation plan authored in this workspace must satisfy the structure
below. Fields exist because adversarial-review Phases 2a/2b already consume
them. A plan that omits them forces the review harness to
reconstruct evidence the author could have provided.

## Required sections

### Target roots

List every root the plan will modify:

- `prepared911`
- `axon911-frontend`
- `vault-core-ux`
- `chroma`
- `personal-harness`

Do not claim a root is in scope without identifying at least one path under it.
Plans that change runtime verification, Cursor hooks, review contracts, or
harness skills must name `personal-harness` and at least one path under it.

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

- Name the specific docs page for every `ui-*` package change: `apps/docs` in
  axon911-frontend, `turbo/apps/docs` in prepared911.
- State whether `ui-components.generated.ts` (or the equivalent generated
  registry for the target root) needs regeneration.
- State "none" explicitly when neither applies.

### PR body fields, for axon911-frontend targets

`.github/workflows/package-pr-check.yaml` enforces the
`prBodyRequiredFields` declared in `.changeset/package-release.config.json`
under a `### Package Release` heading. A plan that already satisfies this
contract carries every one of them; `/implementation-check` emits the section
rather than asking for it again:

| PR body field | Plan section it comes from |
|---|---|
| Affected packages | Affected consumers |
| Bump severity | Lockstep decision in the changeset, cross-checked against blast radius and tier |
| Public API / behavior summary | Changed exports named in the blast-radius section |
| Migration notes | Deferred and out-of-scope |
| Cutover impact | Blast radius and tier |
| Test evidence | Self-authored claim ledger plus attested verification commands |

A plan that cannot fill a field has not established the corresponding section.
Do not paper over the gap in the PR body.

### Design intent

Required only when the plan changes behavior a user can see or operate. A plan
that changes no user-visible behavior states "none" here. Cite principle ids
from `docs/design-principles.md`.

- **User and situation:** who is doing what, under which conditions.
- **Desired outcome:** what should become easier, clearer, or more dependable.
- **Applicable principles:** the specific `DP-*` or `DSP-*` ids that influence
  the decision, each with the clause that applies.
- **Observable acceptance:** the behavior that demonstrates success, written as
  interaction scenarios an implementer can run and a reviewer can watch.
- **Uncertainty:** what requires operator observation or further research. An
  agent's own walkthrough does not answer this.

"Aligns with our design principles" is not acceptance. Name the scenario:

> When an operator switches incidents while an update is pending, the interface
> preserves the pending state and makes its incident association clear.

### Deferred and out-of-scope

List every known related concern the plan deliberately does not address.
Without this section, review-contract downgrades for `out-of-scope` and
`remediated-by-plan` cannot apply.

## Execution manifest (strict plans)

For user-visible migrations, compile the accepted plan into a canonical execution
manifest JSON before implementation:

| Field | Purpose |
|---|---|
| `plan_hash` | Immutable plan identity |
| `tier` | `T0` / `T1` / `T2` blast radius |
| `target_roots.<root>.base_oid` | Pinned baseline commit |
| `target_roots.<root>.allowed_paths` | Declared scope globs |
| `target_roots.<root>.required_paths` | Paths that must change |
| `target_roots.<root>.evidence_states` | Per-glob evidence mode: `none` (visual parity; default for token swaps), `after`, `before-after` |
| `budgets` | Session turn and context limits |

Register with:

```bash
python3 harness/cli.py register-plan --root <root> \
  --manifest execution-manifest.json \
  --evidence-manifest .harness/runtime/evidence/<plan>/manifest.json
```

Changing scope, evidence mode, sequencing, or budgets requires a new manifest
version; prior receipts bind to the previous `execution_manifest_hash`.

### Definitive evidence manifests

Schema v4 execution plans pair the execution manifest with a checksummed
migration-evidence manifest. Each row declares one capture kind:
`storybook`, `product-route`, or `not-applicable`. Each row also declares one
evidence state: `changed`, `expected_unchanged`, `new_visible`, or
`static_only`.

- `changed` requires distinct Before and After capture identities.
- `expected_unchanged` is visual parity (token swap, architecture-only). It
  creates no screenshot obligation. Optional captures, if present, must match.
- `new_visible` requires machine-checked absence on the baseline and an After.
- `static_only` uses `not-applicable` and names its verification command.

Every phase declares a positive `max_attempts`. Ref, scope, state, capture-mode,
required-path, sequence, or budget changes require a superseding manifest.

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
