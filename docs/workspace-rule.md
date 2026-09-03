# Axon 911 Workspace Rule

Always-on guidance for work across the four roots. Cursor loads this through
`.cursor/rules/prepared911-workspace.mdc` at session start.

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

prepared911 remains authoritative for its own application code.

Each repository's own instructions take precedence for work in that repository.
The harness coordinates; it does not redefine project coding standards.

## Before editing

Identify the target root, then read that root's own `AGENTS.md`. axon911-frontend
is flat (`packages/ui-*`, `apps/docs`, `apps/storybook`); prepared911 nests under
`turbo/`. Never transfer one root's paths, commands, or conventions to another.

In axon911-frontend, run `pnpm dlx @tanstack/intent@latest list` before a
substantial change, per the generated block at the top of its `AGENTS.md`.

## Verification blind spot

`pnpm check` and `pnpm lint` give **no signal** on `packages/ui-*` or
`apps/docs`. In those paths evidence means `pnpm turbo run typecheck`,
`pnpm test:unit:run`, and `pnpm test:storybook:ci`.

## Default posture: mechanical on, panel off

The harness mechanical half (Python hooks, fingerprint-bound receipts,
conformance, mirror warnings) runs by default at near-zero token cost.

The LLM review panel is **off by default** (`HARNESS_REVIEW_MODE=off`). Code
review comes from Cursor `bugbot` plus the human PR reviewer.

Run `/adversarial-review` only when one of these is true:

- breaking change to a published `@prepared911/ui-*` API that prepared911 consumes
- blast radius beyond one reviewer's head (`T2`, or `pr-blast-radius` finds
  consumers in both roots)
- no human reviewer will have CORE-754 authority context
- expensive to reverse (package publish or downstream migration)
- you ask for it explicitly

Keep the panel off during exploration, prototyping, `vault-core-ux`, and
`personal-harness` work unless asked.

Raise review gating temporarily with `HARNESS_REVIEW_MODE=on-request` and
`HARNESS_REVIEW_REQUESTED=1`, or `HARNESS_REVIEW_MODE=always`.

## Session budget

Read `docs/session-budget.md`. Stop at ~60 assistant turns or ~80k context.
Write `.harness/runtime/handoff/<plan-hash>.md` before starting a fresh session.

The orchestrator delegates exploration to subagents and does not re-read what a
subagent already reported.

## Reuse before rebuild

Prefer existing tooling over bespoke harness critics:

- General review: Cursor `bugbot` and `security-review`
- Docs baseline: `prepared-docs` MCP when ui-* or docs paths changed
- Blast radius: team `pr-blast-radius` skill
- Rendered evidence: Storybook MCP `run-story-tests`, `/capture-evidence`
- Mechanical checks: team `pre-summary-checks`
- PR body: `pr-context-generator`, `pull-request-standards`
- Branches: Graphite / Cursor Review

## Contracts

- Plans: `docs/plan-contract.md`; prefer `/plan-check` before implementing.
- Implementation: `docs/implementation-contract.md`; `/implementation-check`
  before committing.
- Blast-radius tiers: computed via `python3 harness/cli.py tier --json`.
- Runtime gating: `docs/runtime-contract.md`.

## Safety

- Do not modify `personal-harness` during a product task unless asked.
- Do not modify any product root during a review-only task.
- Preserve pre-existing dirty working trees in every root.
- Report the root containing every modified file.

## Hook scope (sibling roots)

Cursor project hooks in this harness checkout apply when the workspace includes
this repository. Product roots use explicit `/implementation-check` plus optional
PR Automations; hooks are not assumed active in sibling roots until configured.
