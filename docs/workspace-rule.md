# Axon 911 Workspace Rule

Always-on guidance for work across the four roots. The Claude Code plugin
injects this at `SessionStart` when the working directory resolves inside a
configured root; the Cursor rule at `.cursor/rules/prepared911-workspace.mdc`
points here so the two hosts cannot drift.

## Roots

- `axon911-frontend` — owns `@prepared/ui-*` and the shared frontend
  architecture. Architectural authority for the Axon 911 ecosystem.
- `prepared911` — application repository. Consumes the published
  `@prepared911/ui-*` artifacts.
- `vault-core-ux` — Core UX decisions, standards, and history.
- `personal-harness` — private critics, contracts, and orchestration.

## Source priority

For anything `@prepared/ui-*`, design-token, or shared-frontend-architecture
shaped, axon911-frontend's public API, exports, tests, and actual behavior take
precedence. `axon911-frontend/AGENTS.md:121` and `docs/VENDORING.md` are
authoritative: fix bugs in axon911-frontend; prepared911 consumes the published
artifact. Do not re-sync ui-* from prepared911 and do not restore `SOURCE.md`.

prepared911 remains authoritative for its own application code — dispatch,
beacon, and the Ruby and Go services.

Each repository's own instructions take precedence for work in that repository.
The harness coordinates; it does not redefine project coding standards.

## Before editing

Identify the target root, then read that root's own `AGENTS.md`. axon911-frontend
is flat (`packages/ui-*`, `apps/docs`, `apps/storybook`); prepared911 nests under
`turbo/`. Never transfer one root's paths, commands, or conventions to another.

In axon911-frontend, run `pnpm dlx @tanstack/intent@latest list` before a
substantial change, per the generated block at the top of its `AGENTS.md`. Never
hand-edit the `<!-- intent-skills:start/end -->` block: `pnpm check` runs
`intent:check`, which fails on any drift.

## Verification has a blind spot

`pnpm check` and `pnpm lint` give **no signal** on `packages/ui-*` or
`apps/docs` — oxlint ignores both trees (CORE-754 debt, `docs/LINT-POLICY.md`).
In those paths evidence means `pnpm turbo run typecheck`, `pnpm test:unit:run`,
and `pnpm test:storybook:ci`. A green `pnpm check` is not evidence there.

## Contracts

- Plans follow `docs/plan-contract.md`; prefer `/plan-check` before implementing.
- Implementation follows `docs/implementation-contract.md`.
- Blast-radius tiers are computed, not asserted — see `docs/routing-matrix.md`.
- Runtime gating follows `docs/runtime-contract.md`. Local hooks are cooperative
  assurance, not a security boundary.

## Safety

- Do not modify `personal-harness` during a product task unless asked.
- Do not modify any product root during a review-only task.
- Preserve pre-existing dirty working trees in every root.
- Report the root containing every modified file.
