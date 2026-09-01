# Axon 911 Runtime Contract

Local project hooks — Cursor's `.cursor/hooks.json` and Claude Code's
`hooks/hooks.json`, both over the shared dispatcher in `harness/` — provide
cooperative assurance against accidental early completion and stale evidence. The Agent and repository commands run as the
same user. The ledger is not tamper-proof, not atomic Git enforcement, and
not a security boundary against a hostile local process.

## Roots

Configured consumers, in precedence order:

- `axon911-frontend` — owns `@prepared/ui-*` post CORE-754; architectural authority
- `prepared911` — consumes the published artifacts; its `turbo/packages/ui-*` is a deprecating mirror
- `vault-core-ux`
- `personal-harness`

Root paths resolve from `HARNESS_ROOTS_JSON`, then the plugin `userConfig`
environment variables, then on-disk defaults. The harness checkout itself is
located from an explicit anchor rather than the working directory: under Claude
Code the hooks run with the *product* repo as cwd, where an upward walk finds
nothing and every root would otherwise collapse to `personal-harness`.

### Concurrent worktrees

A configured path names one root's default worktree, not the only one that
counts as that root. Working across several worktrees of the same repository
at once — one per branch or task — is routine, and every one of them is
recognized: `identify_root` falls back from a plain path-prefix match to
comparing each side's `git rev-parse --git-common-dir`, which is identical
across every worktree of one repository even though each has its own toplevel
path, HEAD, and index. A worktree recognized this way resolves to the
configured `root_id` but keeps *its own* path for every operation that
follows — fingerprinting, `changed_paths`, tier scoring, obligation checks —
never the configured default's. Getting this wrong would mean every worktree
but the first is silently treated as outside the harness altogether: a commit
denied with `root-identity`, or a session nagged or gated against the wrong
tree's diff.

CLI subcommands (`attest`, `register-plan`, `issue-review-receipt`, `tier`,
`ui-principles`, `conformance`) take `--root <id>` rather than a live event
payload, so they resolve the matching worktree from their own process `cwd`
when it names the same root, and fall back to the configured default only when
invoked from somewhere unrelated to any worktree of it.

Automatic project-hook enforcement is harness-local until a live four-root
scope probe records otherwise. Sibling roots still use explicit
`/implementation-check` plus optional PR Automations.

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
  critic identity, report contract, tier, verdict, plan hash, and final
  fingerprint.
- A `register-plan` record selects the active plan hash and obligation-schema
  version.
- Shareable receipts are content-addressed. Session-local event cursors and
  stop-loop counters are namespaced by worktree and session.

## Review cardinality

- `T0`: one fresh applicable critic
- `T1`: two independent applicable critics
- `T2`: signal-selected panel plus adjudication

Tier is computed, not asserted — see `docs/routing-matrix.md`.

### Identity-bound counting

A review receipt is issued by the orchestrator, so on its own it is
self-attested. Claude Code's `SubagentStart` and `SubagentStop` carry
`agent_type` and `agent_id`, so the harness records **who actually returned**
from the host's own events rather than from the agent's prose. Where those
records exist for the active plan hash and fingerprint, the gate also requires
the tier's cardinality against them: `T0` one distinct critic, `T1` two, `T2`
three including `review-adjudicator`.

Hosts that expose no subagent identity keep the receipt-only behavior. This
supplements review receipts; it never replaces them. Under Claude Code the
earlier blanket rule softens: unvalidated *content* is still not proof, but
identity is bound.

Editing a file invalidates the critic records for that fingerprint along with
the receipts — a changed tree invalidates who reviewed it.

The mechanical implementation verifier supplements these receipts. It never
replaces them.

## Plan conformance

`register-plan` records the plan's declared scope alongside its hash and tier.
Changed paths are then classified against it:

- `in-scope` — declared, or a test, story, or docs file, which are never scope creep
- `undeclared` — changed but never named by the plan; silent scope creep
- `unimplemented` — named by the plan but never touched; work claimed but absent

`undeclared` warns while editing and blocks at a mutation gate.
`unimplemented` blocks the turn from ending. With no registered scope every path
is in scope: an unregistered plan promised nothing, which is not the same as a
promise broken.

## Unmeasurable trees

A root is unmeasurable when it is a shallow clone, has unresolved conflicts, or
has an interrupted rebase, merge, cherry-pick, or bisect. Such a tree contains
content nobody authored, or a HEAD that is not the intended commit, so its
fingerprint, its diff, and any evidence captured from it are not reproducible.
Tier resolves to `T2` with predicate `unmeasurable` and the specific reason.
Remediate the tree rather than accepting the tier.

## Obligation adapters

Prepared911 and Axon each have independent IDs:

- `ui-components.generated.ts` currency
- docs API-registry currency
- corresponding `ui-*` docs-page updates
- rendered evidence

Use each root's actual paths. Vault and personal-harness disable product UI
obligations. New visible surfaces require after-state evidence. Changed
existing surfaces require before-and-after evidence. Missing, stale,
incomplete, or cross-root evidence blocks. Non-user-visible changes are
exempt.

## Event handling

Strict per-event schemas, a 64 KiB input limit, canonical root containment,
symlink and special-file rejection, argument-array subprocesses, and static
sanitized hook responses.

### Cursor

| Event | Role |
|---|---|
| `sessionStart` | Observational; fire-and-forget; lazy init if absent |
| `preCompact` | Observational |
| `afterFileEdit` | Invalidate receipts; cannot issue receipts |
| `postToolUse` | Observe; cannot issue receipts |
| `subagentStop` | Follow up only; unvalidated reports are not proof |
| `beforeShellExecution` | Mutation preflight |
| `stop` | Bounded follow-up when proof is missing or stale |

### Claude Code

| Event | Role |
|---|---|
| `SessionStart` | Observational; injects the workspace rule inside a configured root |
| `PreCompact` | Observational |
| `PostToolUse` (`Edit`/`Write`/`NotebookEdit`) | Invalidate receipts; warn on plan drift and on edits to the deprecating mirror |
| `PostToolUse` (`Bash`) | Observe |
| `PreToolUse` (`Bash`) | Mutation preflight |
| `SubagentStart` / `SubagentStop` | Record critic dispatch and return with host-supplied identity |
| `TaskCompleted` | Roll back completion when a *concrete, path-triggered* obligation has no receipt |
| `Stop` | Same path-triggered check, then an agent verifier when that is `INCONCLUSIVE` |

Claude Code honors only `allow` and `deny` on `PreToolUse`, so the classifier's
`ask` continues to mean "evaluate the gate". Plan mode is never gated: it makes
no durable change, and a gate that fights it would only produce noise.

`TaskCompleted` and `Stop` deliberately do **not** carry the blanket
`review.<tier>` requirement that `PreToolUse`'s mutation preflight does.
`default_required()` (shared with Cursor) appends it on every call regardless
of whether anything relevant changed, and wiring that into events that fire on
every single turn meant every session touching a configured root demanded a
review receipt before it could finish a turn — nagging fired on ordinary
iteration with no commit anywhere in sight, not just when work was actually
about to ship. The commit itself is still fully gated at `PreToolUse`, which is
the point that actually matters; `TaskCompleted` and `Stop` only check the
specific, path-triggered obligations (stale generated files, missing rendered
evidence for a real UI change) that fire for a concrete, named reason. A
session with nothing relevant changed is never interrupted.

Observational failures fail open with generic diagnostics. Gate failures deny
with root, obligation IDs, and an exact recovery command.

## Persistence

Gitignored `.harness/runtime/` (legacy `.cursor/runtime/` remains ignored so
older checkouts stay clean):

- owner-only `0700` directories and `0600` files
- no-follow opens where supported
- bounded lock acquisition
- atomic locked appends
- completed-record durability
- recover a truncated final JSONL record
- fail closed on earlier corruption at mutation gates
- segment at 10 MiB or seven days
- retain at most 30 days
- compact current-state index so gates never scan full history

Allowlisted persisted fields: version, event or obligation ID,
root/worktree/session identifiers, hashes, status enum, exit status,
duration, bounded timestamps, and root-relative evidence pointers. Never
persist raw commands, prompts, environment, diffs, PR text, summaries, tool
output, transcripts, customer data, or secrets.

## Agent-shell mutation preflight

Best-effort classification of:

- `git commit` / `git push`
- `git -C`
- absolute Git paths
- RTK forms
- `gt create`
- `gt submit`

Deny compound or ambiguous mutation commands and unsupported high-risk push
forms (`--all`, `--mirror`, deletion, force, unattested tags or refspecs).
Commits and pushes must be separate commands. Commit preflight binds parent
plus index tree. Each supported push source ref binds to its resolved
attested OID. `gt submit` requires a stack-OID-set receipt.

Outside the guarantee: aliases, unknown wrappers, GUI source control, human
terminals, product Git hooks that mutate after preflight, and other
operation-boundary races.

## Transparent attest wrapping

Under Claude Code, `PreToolUse` recognizes a narrow set of exact-string
verification commands and rewrites them (`updatedInput.command`) to route
through the attesting wrapper, so running the plain command directly cannot
produce an unrecorded `PASS`. Scoped to obligations that declare a `check`
command in `harness/lib/obligations.py` — six today, all on
`axon911-frontend` (`ui-allowlist`, `docs-registry`, `rendered-evidence`,
`mf-types`, `flag-manifest`; `docs-page` has no shell check and is asserted by
a human). Matching is exact-string after whitespace normalization, not prefix
or substring: a sharded or flagged variant of a check command is a different
invocation and is not silently credited to the same obligation.

The rewrite is idempotent (a command already containing the wrapper is left
alone) and preserves the original command verbatim after `--`, including an
`rtk` prefix if the agent invoked the check through it — recognizing a command
under a wrapper must not silently drop that wrapper from what actually runs.
It is scoped to the four configured roots, same as every other Claude Code
gate. Disable it without uninstalling anything via the plugin's `userConfig`
(`attest_rewrite`, default `true`), surfaced as
`CLAUDE_PLUGIN_OPTION_ATTEST_REWRITE=false`.

This is the highest-risk piece of the port: `~/.claude/settings.json` already
binds `PreToolUse`/`Bash` to RTK's own hook, and the Vercel plugin binds
`PreToolUse` on `Bash` too, so three hooks can see and potentially rewrite the
same command. The mitigations above (idempotence, verbatim-append, the kill
switch) are what this module's own tests cover; live, multi-hook ordering
against the real RTK binary has not been exercised.

## Recovery command

```text
/a911-harness:implementation-check
```

Under Cursor the same command is `/implementation-check`.
