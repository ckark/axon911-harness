---
name: harness-mode
description: Route Axon 911 frontend work through the right repository, contract, and review tier. Use when starting any implementation or plan touching axon911-frontend, prepared911, @prepared/ui-*, or vault-core-ux — including bug fixes, component changes, design-system work, and Module Federation changes. Resolves which root owns the change before any edit.
argument-hint: [optional description of the work]
allowed-tools: Read Grep Glob Bash(python3 ${CLAUDE_PLUGIN_ROOT}/harness/*) Bash(git *)
---

# Axon 911 Harness Mode

The entry point. It resolves ownership, loads the right repository's own rules,
scores the tier, and hands off to a contract. It does not restate coding
standards: each repository's own instructions outrank this harness.

## 1. Resolve the owning root before editing

| Change | Root |
|---|---|
| `@prepared/ui-*`, design tokens, shared frontend architecture | `axon911-frontend` |
| Shells, remotes, `mfe-core`, `tooling-config` | `axon911-frontend` |
| Dispatch, beacon, Ruby or Go services | `prepared911` |
| Core UX decisions, standards, history | `vault-core-ux` |
| Critics, contracts, gates | `personal-harness` (only when asked) |

axon911-frontend owns every `@prepared/ui-*` package post CORE-754
(`AGENTS.md:121`, `docs/VENDORING.md`) and publishes them as
`@prepared911/ui-*`. prepared911 consumes those artifacts, and its
`turbo/packages/ui-*` copies are slated for removal — **a ui-* bug fix belongs
in axon911-frontend**, not in the prepared911 copy. Fix bugs there; never
re-sync from prepared911; never restore `SOURCE.md`.

axon911-frontend is flat (`packages/ui-*`, `apps/docs`, `apps/storybook`);
prepared911 nests under `turbo/`. Paths and commands do not transfer.

## 2. Read the owning root's own instructions

Read that root's `AGENTS.md` first. For axon911-frontend also run, per the
generated block at the top of its `AGENTS.md`:

```bash
pnpm dlx @tanstack/intent@latest list
```

Never hand-edit the `<!-- intent-skills:start/end -->` block — `pnpm check`
runs `intent:check`, which fails on any drift. After any `AGENTS.md` change run
`pnpm intent:sync`.

## 3. Score the tier

```bash
python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py tier --root <root> --json
```

The tier is computed from a measured public-surface delta plus per-symbol
call-site counts, and it names the one predicate that produced it. Do not assert
a tier; read it. `T0` is one critic, `T1` two, `T2` the signal-selected panel
plus adjudication (`${CLAUDE_PLUGIN_ROOT}/docs/routing-matrix.md`).

If the tier comes back `unmeasurable`, the root is a shallow clone: run
`git fetch --unshallow` rather than accepting a defensive `T2`.

## 4. Know what your verification actually covers

**`pnpm check` and `pnpm lint` report nothing on `packages/ui-*` or
`apps/docs`.** oxlint ignores both trees (CORE-754 debt,
`docs/LINT-POLICY.md:53-55`), so in those paths a green `pnpm check` is not
evidence. Real coverage:

| Path | Evidence |
|---|---|
| `packages/ui-*` | `pnpm turbo run typecheck`, `pnpm test:unit:run`, `pnpm test:storybook:ci` |
| `apps/**`, `remotes/**` | Playwright from `apps/automation` after `pnpm build:mf` — `apps/storybook` globs `packages/*/src` only, so these have no Storybook coverage |
| `remotes/**`, `mfe-core` | `pnpm mf:types:check` |
| `packages/feature-flags` | `pnpm feature-flags:check` |

## 5. Hand off

- Writing a plan → `${CLAUDE_PLUGIN_ROOT}/docs/plan-contract.md`, then `/a911-harness:plan-check`.
- Implementing → `${CLAUDE_PLUGIN_ROOT}/docs/implementation-contract.md`, then `/a911-harness:implementation-check` before committing.
- Formal review gate → `/a911-harness:adversarial-review`.
- Rendered evidence → `/a911-harness:capture-evidence`.

Ordinary work still needs a fresh-context review at its tier. Reviewing your own
work in the context that wrote it does not count.
