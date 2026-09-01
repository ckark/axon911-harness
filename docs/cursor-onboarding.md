# Using the harness from Cursor

Paste this to a Cursor agent, or point it at this file. It describes the harness
as it exists on `ckark/harness-attest-evals`, which both hosts share.

## Where the harness lives

This Cursor workspace uses the checkout at:

```
/Users/ckark/Documents/CursorWorkspaces/prepared911-harness
```

That checkout is `main` merged with `ckark/harness-attest-evals`. A sibling
worktree remains at `prepared911-harness-attest-evals` on the named branch.
One Python package, `harness/`, drives both hosts. Cursor enters through
`.cursor/`; Claude Code enters through the
`a911-harness` plugin. Neither host has logic of its own — a fix in `harness/`
lands in both.

```
.cursor/hooks.json            7 event bindings -> .cursor/hooks/runtime_gate.py
.cursor/hooks/runtime_gate.py thin shim; adds harness/ to sys.path, calls cli.main()
.cursor/agents/               7 read-only critics
.cursor/skills/               plan-check, adversarial-review, implementation-check,
                              harness-health-check
.cursor/rules/prepared911-workspace.mdc
                              pointer only -- the rule itself is docs/workspace-rule.md
docs/                         the contracts, shared by both hosts
harness/cli.py                the CLI, below
```

## Wiring it into a Cursor session

The hook commands in `.cursor/hooks.json` are **relative** (`.cursor/hooks/runtime_gate.py …`),
so Cursor must be running with this repository as a workspace root. Two options:

1. Open this repo as an additional root in a Cursor multi-root workspace, alongside
   the product repo you are editing.
2. Symlink `.cursor/` into the product repo's root.

Option 1 is preferred: the skills and `docs/` contracts resolve by relative path
from this repo, and option 2 leaves them dangling unless the whole repo is
reachable anyway.

Confirm the wiring before trusting it. The shim takes an event name or a CLI
subcommand, so `--help` is not a valid probe — it prints `unknown command` and
still exits 0. Use these instead:

```bash
# 1. The shim resolves harness/ and reaches the real CLI.
python3 .cursor/hooks/runtime_gate.py benchmark --json

# 2. The shared package is intact.
python3 -m unittest discover -s harness/tests -p 'test_*.py'   # 216 tests

# 3. Scoring works against a real checkout.
cd /path/to/axon911-frontend && \
  python3 <harness>/harness/cli.py tier --root axon911-frontend --json
```

`benchmark` should report `history_independent: true` with an append p95 well
under 100 ms. If step 1 raises `ModuleNotFoundError: cli`, the shim is not being
run from inside this repository.

## Pointing it at your checkouts

Defaults are hardcoded in `harness/lib/paths.py`:

| root | default |
|---|---|
| `axon911-frontend` | `/Users/ckark/Documents/GitHub/axon911-frontend` |
| `prepared911` | `/Users/ckark/Documents/GitHub/prepared911` |
| `vault-core-ux` | `/Users/ckark/Documents/GitHub/vault-core-ux` |

`personal-harness` always resolves to the checkout the running code belongs to.
Override with `HARNESS_ROOTS_JSON`, which wins over everything else:

```bash
export HARNESS_ROOTS_JSON='{"axon911-frontend":"/path/to/your/checkout"}'
```

You do **not** need an override per git worktree. The harness recognizes any
worktree of a configured root by its shared git common directory, so several
concurrent worktrees of `axon911-frontend` all resolve to that root id.

## The CLI

```bash
python3 harness/cli.py <command>
```

| command | what it does |
|---|---|
| `tier` | Score blast radius (T0/T1/T2) from measured evidence |
| `ui-principles` | Diff-scoped lint/SCSS checks on `packages/ui-*` |
| `conformance` | Compare a registered plan's declared scope against actual changes |
| `attest` | Run a verification command and bind its result to a fingerprint |
| `register-plan` | Persist a plan hash, tier, and declared scope |
| `issue-review-receipt` | Record a review at a tier |
| `benchmark` | Ledger/gate performance check |

Two flags matter in day-to-day use:

- `tier --against <ref>` scores the **full branch** diff rather than only the
  uncommitted worktree. Use it to audit a branch before a PR. Live gating never
  passes it, because a hook needs to score the current edit.
- Any `git` command may be written `git -C <path> …`, and any `gt` command
  `gt --cwd <path> …`. Both are read off the command to resolve the root. Without
  one, the root resolves from the session's directory, which is wrong whenever
  you are operating on a worktree other than the one Cursor opened.

## Rules the gate enforces that will surprise you

- **One mutation per command.** A `git commit`/`git push`/`gt submit` chained
  with `&&`, wrapped in a `for` loop, or piped is denied as
  `compound-or-ambiguous-mutation`. This is deliberate: a loop with N targets
  cannot be classified statically. Write one command per mutation.
- **Commits and pushes are separate commands.** Never chain them.
- **Receipts are fingerprint-bound.** Staging files changes the fingerprint, so
  issue the review receipt *after* `git add`, immediately before committing. If
  the gate says `review.T0` is missing right after you issued one, the tree moved
  underneath it — reissue.
- **`git push` additionally needs a `push.oid` receipt**; `gt submit` needs
  `stack-oid-set`. Attest them against the branch you are pushing:
  ```bash
  python3 harness/cli.py attest --root <root> --obligation-id push.oid -- git rev-parse HEAD
  ```
- **Editing `packages/ui-*` triggers axon obligations** — `ui-allowlist`,
  `docs-registry`, `docs-page`, `rendered-evidence`. Satisfy them by actually
  running the real check and attesting it, not by attesting something vacuous.

## Verification blind spots the harness exists to cover

- `pnpm check` and `pnpm lint` give **no signal** on `packages/ui-*` or
  `apps/docs` — oxlint ignores both trees (CORE-754 debt). A green `pnpm check`
  is not evidence there. Use `pnpm turbo run typecheck`, `pnpm test:unit:run`,
  and `pnpm test:storybook:ci`.
- `pnpm turbo run typecheck` can report all-green **from cache** while a
  generated file is stale, because `@prepared/feature-staff-panel`'s typecheck
  is what runs `generate-ui-components.mjs --check`. When a change adds or
  renames a `@prepared/ui-*` export, run `pnpm turbo run typecheck --force`.

## Authority model

axon911-frontend owns all `@prepared/ui-*` packages post CORE-754 and is
authoritative for anything ui-*, design-token, or shared-frontend-architecture
shaped — regardless of which root the task started in. prepared911 stays
authoritative for its own application code. `docs/review-contract.md` encodes
this; `apps/docs` in axon911-frontend is the primary docs benchmark and
`turbo/apps/docs` is secondary until its removal lands. Divergence is a
`DOCS-DRIFT-###` finding, not a judgment call.

## What Cursor does not have

`skills/` (Claude Code) has two skills `.cursor/skills/` does not:
`capture-evidence` and `harness-mode`. The four gate skills — `plan-check`,
`adversarial-review`, `implementation-check`, `harness-health-check` — exist on
both. Port the other two only if you want them; nothing depends on them.
