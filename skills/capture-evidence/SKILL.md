---
name: capture-evidence
description: Capture rendered evidence for a user-visible change and bind it to the current fingerprint, so the rendered-evidence obligation is satisfied by an artifact rather than an assertion. Use before claiming a UI change done.
disable-model-invocation: true
argument-hint: [root=<root id>] [component=<name>] [story=<story id>]
allowed-tools: Read Grep Glob Bash(python3 ${CLAUDE_PLUGIN_ROOT}/harness/*) Bash(pnpm *) Bash(git *)
---

# Capture Rendered Evidence

`${CLAUDE_PLUGIN_ROOT}/docs/implementation-contract.md` requires rendered
evidence for anything a user sees. A green typecheck is not rendered evidence.
This skill produces the artifact and binds it to the fingerprint of the tree it
was captured from, so it cannot silently go stale.

## Pick the route by what changed

`apps/storybook` is the only Storybook in axon911-frontend, and its stories glob
is `../../../packages/*/src/**/*.stories.@(ts|tsx)`. Stories under `apps/` or
`remotes/` are **never discovered**, so those changes cannot use it.

| Changed | Route |
|---|---|
| `packages/ui-*` | Storybook — `pnpm storybook` (port 5203) |
| `apps/**`, `remotes/**` | Playwright — `pnpm build:mf` then `apps/automation` |

There is no Chromatic in this repo. Visual coverage is Storybook plus Vitest
browser-mode a11y and interaction tests.

## Procedure

1. Identify the changed component and confirm it has a story. `ui-takeover-page`
   has one story and no tests, so a change there usually means writing the story
   first.
2. Start the surface:

   ```bash
   pnpm storybook            # packages/ui-*
   pnpm build:mf             # apps/** and remotes/** first
   ```

3. Open the story or route in the browser and capture the **after** state. When
   changing something that already exists, capture **before and after** — the
   contract requires both.
4. Write artifacts under `.harness/runtime/evidence/<fingerprint>/`, named by
   obligation id. Get the current fingerprint from the harness rather than
   guessing it.
5. Re-run `/a911-harness:implementation-check` so the obligation resolves
   against the artifact.

## Rules

- New visible surface → after-state evidence. Changed existing surface →
  before-and-after.
- Evidence captured against a different fingerprint is stale and does not count;
  editing a file invalidates it, by design.
- Cross-root evidence does not transfer: an axon screenshot does not satisfy a
  prepared911 obligation.
- If the surface genuinely cannot be reached live, render against realistic data
  and say so explicitly in the summary.
- Non-visible changes are exempt. Do not manufacture a screenshot for a type
  change.
