# Axon 911 Runtime Contract

Cursor project hooks — `.cursor/hooks.json` over the shared dispatcher in
`harness/` — provide cooperative assurance against accidental early completion
and stale evidence. The agent and repository commands run as the same user.
The ledger is not tamper-proof, not atomic Git enforcement, and not a security
boundary against a hostile local process.

## Roots

Configured consumers, in precedence order:

- `axon911-frontend` — owns `@prepared/ui-*` post CORE-754; architectural authority
- `prepared911` — consumes the published artifacts; its `turbo/packages/ui-*` is a deprecating mirror
- `vault-core-ux`
- `chroma` — colour and token generator; no product-UI obligations
- `axon911-design` — hand-rolled `@axon911/design` package and its Storybook
- `personal-harness`

Root paths resolve from `HARNESS_ROOTS_JSON`, then `HARNESS_*_ROOT` environment
variables, then on-disk defaults. The harness checkout is located from an
explicit anchor rather than the working directory.

### Concurrent worktrees

A configured path names one root's default worktree, not the only one that
counts as that root. `identify_root` recognizes linked worktrees via shared
`git rev-parse --git-common-dir` and keeps each worktree's own path for
fingerprinting, diffs, and obligation checks.

CLI subcommands take `--root <id>` and prefer the process `cwd` when it names
the same root.

Sibling product roots use explicit `/implementation-check` plus optional PR
Automations unless hooks are configured there separately. See
`docs/workspace-rule.md` for the stable hook-scope answer.

## Status values

Exactly one of:

- `PASS`
- `BLOCKED`
- `INCONCLUSIVE`

`BLOCKED`, `INCONCLUSIVE`, malformed, stale, wrong-root, wrong-worktree,
wrong-tier, or pre-command receipts never satisfy a gate.

## Fingerprint

Versioned canonical snapshot shared by every producer and gate. Records are
sorted and length-prefixed before SHA-256:

- configured root identity
- canonical real path and Git worktree identity
- `HEAD`
- index tree
- tracked worktree bytes and modes
- relevant untracked files
- deletions and renames
- symlink targets
- submodule OIDs
- active plan hash
- plan context hash (scope, base, mirror intent, path surfaces)
- obligation-schema version
- command-spec version
- verifier version

Capture pre-command and post-command fingerprints. A command that mutates
state cannot issue `PASS`. It returns `INCONCLUSIVE` and must be rerun
against the post-command state.

## Receipts

- Event hooks record observations only.
- The dispatcher is the only ledger writer.
- The attesting wrapper is the only verification-receipt issuer.
- `/implementation-check` is the only review-receipt issuer after validating
  critic identity, on-disk report schema, tier, verdict, plan hash, report
  hash, and final fingerprint via `issue-review-receipt --report`.
- A `register-plan` record selects the active plan hash, tier, and optional
  atomic plan profile (scope, `base_oid`, Prepared mirror intent, per-path
  surface class). The profile's canonical hash binds fingerprints and receipts;
  changing scope or predicates invalidates prior proof even when the Markdown
  plan hash is unchanged.
- Shareable receipts are content-addressed. Session-local event cursors and
  stop-loop counters are namespaced by worktree and session.

## Review mode

Default: **`HARNESS_REVIEW_MODE=off`**. Mutation gates do not require a review
receipt unless review mode is raised:

- `off` — no gate demands a review receipt; `/adversarial-review` still runs
  on demand and may issue one
- `on-request` — requires a receipt when `HARNESS_REVIEW_REQUESTED=1`
- `always` — requires a receipt at the registered tier

Mechanical obligations (generated files, rendered evidence, conformance) stay
mandatory in all modes.

## Review cardinality

When review is required, **one critic** satisfies the gate at the **registered
tier or higher**. A lower-tier review receipt does not satisfy a higher-tier
gate.

Tier is computed for blast-radius signaling and panel trigger decisions — see
`docs/routing-matrix.md` — not for panel size.

### Confined re-verification

When a fix applies only paths named in a prior critic report, a review receipt
may survive a fingerprint change if marked `confined` with `confined_paths`.
Mechanical obligations must still pass.

Use `python3 harness/cli.py verify` for deterministic obligation coverage.

## Plan conformance

`register-plan` records the plan's declared scope alongside its hash and tier.
Changed paths are then classified against it:

- `in-scope` — declared, or a test, story, or docs file, which are never scope creep
- `undeclared` — changed but never named by the plan; silent scope creep
- `unimplemented` — named by the plan but never touched; work claimed but absent

`undeclared` blocks at commit/push mutation gates. `unimplemented` blocks at
stop. With no registered scope every path is in scope. When `base_oid` is set,
conformance compares the full branch delta against that ref plus uncommitted
worktree paths.

## Unmeasurable trees

A root is unmeasurable when it is a shallow clone, has unresolved conflicts, or
has an interrupted rebase, merge, cherry-pick, or bisect. Tier resolves to `T2`
with predicate `unmeasurable`. Remediate the tree rather than accepting the tier.

## Obligation adapters

Prepared911 and Axon each have independent IDs:

- `ui-components.generated.ts` currency
- docs API-registry currency
- corresponding `ui-*` docs-page updates
- rendered evidence, only when the plan declares a visual delta

Prepared911 `consumer-only` mirror intent suppresses Prepared docs-registry and
docs-page obligations while retaining allowlist and surface-declared evidence.
Axon `packages/ui-*` remains authoritative. Screenshot gates follow declared
evidence mode (`none` / `after` / `before-after`), not inferred visibility.
Token swaps use `none` or migration `expected_unchanged`.

## Event handling

Strict per-event schemas, a 64 KiB input limit, canonical root containment,
symlink and special-file rejection, argument-array subprocesses, and static
sanitized hook responses.

| Event | Role |
|---|---|
| `sessionStart` | Observational; may announce a compatible handoff state |
| `preCompact` | Observational; safe session scaffold |
| `afterFileEdit` | Invalidate receipts; cannot issue receipts |
| `postToolUse` | Observe; cannot issue receipts |
| `subagentStop` | Follow up only; unvalidated reports are not proof |
| `beforeShellExecution` | Mutation preflight |
| `stop` | Bounded follow-up when proof is missing or stale; does not invoke an LLM evidence verifier |

Observational failures fail open with generic diagnostics. Gate failures deny
with root, structured recovery categories, and `/implementation-check`.

## Persistence

Gitignored `.harness/runtime/` (legacy `.cursor/runtime/` remains ignored):

- owner-only `0700` directories and `0600` files
- bounded lock acquisition and atomic appends
- segment at 10 MiB or seven days; retain at most 30 days

Never persist raw commands, prompts, environment, diffs, PR text, summaries,
tool output, transcripts, customer data, or secrets.

## Agent-shell mutation preflight

Best-effort classification of `git commit`, `git push`, `git -C`, absolute Git
paths, RTK forms, `gt create`, and `gt submit`. Deny compound mutation commands.
Read-only Git chains (`git log && git status`, etc.) are allowed when every
stage uses a recognized read-only verb. Commits and pushes must be separate
commands.

For strict migrations, commit preflight requires plan conformance and
nonvisual obligations but defers rendered-evidence and visual-acceptance
obligations. Push preflight requires those receipts only when the plan
declares a visual delta (`after`, `before-after`, or migration `changed` /
`new_visible`). Token-swap and `expected_unchanged` rows do not gate push.

## Recovery command

```text
/implementation-check
```

Also: `python3 harness/cli.py verify --explain`, `python3 harness/cli.py ship-plan`,
`python3 harness/cli.py preview-obligations`, `python3 harness/cli.py record-evidence`,
`python3 harness/cli.py capture-ready`, `python3 harness/cli.py execution-preflight`,
`python3 harness/cli.py issue-visual-acceptance-receipt`,
`python3 harness/cli.py session-status`, `python3 harness/cli.py handoff`,
`python3 harness/cli.py bundle verify`, `python3 harness/cli.py cost <transcript>`.

## Capture preflight and visual acceptance

Before a screenshot campaign, `capture-ready` (alias `execution-preflight`) checks
the strict execution manifest, scope conformance, nonvisual verification receipts,
final staged subject tree, migration manifest coverage, and session budget.

Capture receipts (v4) are a strict union of `storybook`, `product-route`, and
`not-applicable`. Executable receipts bind artifact bytes to `source_sha`,
`source_tree`, `manifest_hash`, `change_id`, `content_origin`, `capture_scope`,
clip bounds, DOM assertion results, role-exclusive process identity, and the
exact story or route scenario. Versions 2 and 3 fail closed. Capture health
receipts prove render readiness only; they do not substitute for visual
acceptance.

The verifier rederives commit and tree OIDs from Git and recomputes receipt and
artifact hashes. A Before must match the execution-pinned trunk; an After must
match the exact PR head and prove that a changed production path produced the
asserted migration state.

Declared visual-delta migration work requires one fresh-context visual
acceptance receipt (`visual.acceptance`) issued by a reviewer session distinct
from the authoring session. The report must pass every visual-delta
`change_id`; per-change `FAIL` verdicts block ship even when the overall
verdict is `PASS`. Parity rows do not require this receipt.
