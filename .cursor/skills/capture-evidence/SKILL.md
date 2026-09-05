---
name: capture-evidence
description: Capture rendered evidence for a user-visible change and bind it to the current fingerprint, so the rendered-evidence obligation is satisfied by an artifact rather than an assertion. Use before claiming a UI change done.
---

# Capture Rendered Evidence

`docs/implementation-contract.md` requires rendered evidence for anything a user
sees. A green typecheck is not rendered evidence. This skill produces the
artifact and binds it to the fingerprint of the tree it was captured from, so
it cannot silently go stale.

## Pick the route by what changed

| Changed | Route |
|---|---|
| `packages/ui-*` in axon911-frontend | Storybook — `pnpm storybook` (port 5203) |
| `packages/ui-*` or Dispatch modules in prepared911 | Storybook — `just storybook run` (port 3005) |
| `apps/**`, `remotes/**` in axon911-frontend | Playwright — `pnpm build:mf` then `apps/automation` |

For **migration PRs**, use a per-change manifest and the migration evidence commands below. Do not add capture scripts or PNGs to the product branch.

## Migration PR procedure

0. Register the accepted plan and run preflight before any capture:

   ```bash
   python3 harness/cli.py register-plan --root <root> \
     --manifest execution-manifest.json \
     --evidence-manifest .harness/runtime/evidence/<plan-hash>/manifest.json
   python3 harness/cli.py capture-ready --root <root> --kind before|after
   ```

1. Author a manifest under `.harness/runtime/evidence/<plan-hash>/manifest.json` with one entry per visually changed consumer or state. Each entry needs `change_id`, `title`, `source_paths`, and `capture` metadata (`story_id`, `theme`, `brand`, `viewport`, `state`).
2. Capture **Before** on the baseline branch and **After** on the migration branch using the same capture metadata.
3. Register artifacts:

   ```bash
   python3 harness/cli.py record-evidence --root prepared911 \
     --change-id <change-id> --kind before|after \
     --story-id "<story>" --theme dark --brand prepared \
     --viewport 1280x720 --state <state> \
     --artifact .harness/runtime/evidence/<plan>/<file>.png
   ```

4. Verify completeness:

   ```bash
   python3 harness/cli.py migration-evidence verify \
     --root prepared911 --manifest .harness/runtime/evidence/<plan>/manifest.json
   ```

5. Render PR markdown:

   ```bash
   python3 harness/cli.py migration-evidence pr-body \
     --manifest .harness/runtime/evidence/<plan>/manifest.json
   ```

Embed hosted image URLs in the manifest (`before_url` / `after_url`) when Chromatic or GitHub user attachments are available. Never commit PNG binaries to the product branch.

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
4. Write artifacts under `.harness/runtime/evidence/` and register them:

   ```bash
   python3 harness/cli.py record-evidence --root <root> \
     --obligation-id <root>.rendered-evidence --kind before|after \
     --artifact <root-relative-png>
   ```

5. Re-run `/implementation-check` so the obligation resolves against the artifact.

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
