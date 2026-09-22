# Axon 911 Implementation Contract

Personal definition of done for work across the multi-root workspace. This
contract does not redefine repository coding standards. Resolve the target root
first, then use that root's own instructions and verification commands.

## Resolve the root first

Identify which of `axon911-frontend`, `prepared911`, `vault-core-ux`, or
`personal-harness` owns the change.

When implementing (not reviewing only), apply the minimum-code ladder in
[docs/ponytail.md](ponytail.md) after this contract and the target root's
`AGENTS.md`. Harness and repository rules override ponytail.

axon911-frontend owns every
`@prepared/ui-*` package post CORE-754 (`AGENTS.md:121`, `docs/VENDORING.md`) and
is the architectural authority for the Axon 911 ecosystem; a ui-* bug fix belongs
there, not in prepared911's `turbo/packages/ui-*` mirror. axon911-frontend is
flat; prepared911 nests under `turbo/`. Read that root's `AGENTS.md` (vault
`.cursorrules`, or harness contracts) before editing. Do not transfer
Prepared911 commands or conventions to another root.

## Per-root verification

Run only the checks that cover what changed, judged by callers rather than
file count. Paste command output into the task summary.

### prepared911

From `turbo/` (or with the appropriate filter):

```bash
pnpm biome ci --changed --no-errors-on-unmatched .
pnpm turbo run lint typecheck --filter=<app>
pnpm turbo run test:unit --filter=<app> -- --run <changed-test-paths>
```

For Ruby under `apps/ruby/api/`:

```bash
rubocop -A <changed-files>
bundle exec rspec <changed-specs>
```

Follow the repository's pre-commit and branch policy in `AGENTS.md`.

### axon911-frontend

**`pnpm check` reports nothing on `packages/ui-*` or `apps/docs`.** oxlint
ignores both trees (`packages/tooling-config/src/oxlint/config.ts:37-58`,
CORE-754 debt, `docs/LINT-POLICY.md:53-55`). A green `pnpm check` is not evidence
for those paths, and neither is a green CI `lint` job.

```bash
pnpm check                 # ultracite check + feature-flags:check + intent:check (root-level)
pnpm turbo run typecheck   # also runs generate-ui-components.mjs --check
pnpm test:unit:run
pnpm test:storybook:ci     # Vitest browser mode: a11y + interaction
```

`pnpm check` is **not** the same gate as `pnpm lint` / `pnpm format`, which fan
out per package through turbo.

| Path | What actually covers it |
|---|---|
| `packages/ui-*` | typecheck, unit tests, Storybook build and test, the `apps/auth` webpack build (ui-core only) |
| `apps/**`, `remotes/**` | Playwright from `apps/automation` after `pnpm build:mf`; `apps/storybook` globs `packages/*/src` only, so these have no Storybook coverage |
| `remotes/**`, `mfe-core` | `pnpm mf:types:check` |
| `packages/feature-flags` | `pnpm feature-flags:check` |

Formatter is Ultracite 7 over oxlint and oxfmt. There is no Biome — that applies
only to prepared911. Prefer `pnpm fix` before claiming lint/format done.

`pnpm check` also runs `intent:check`, which is
`intent install && oxfmt AGENTS.md && git diff --exit-code -- AGENTS.md`. Never
hand-edit the `<!-- intent-skills:start/end -->` block in `AGENTS.md`; run
`pnpm intent:sync` after any `AGENTS.md` change.

The harness additionally runs the rules the repo switched off, scoped to the
lines this change touched:

```bash
python3 harness/cli.py ui-principles --root axon911-frontend
```

Under Cursor the harness is a workspace root rather than a plugin, so the same
command is `python3 harness/cli.py ui-principles --root axon911-frontend` from
the harness root.

### vault-core-ux

- Required frontmatter present and valid
- Outgoing `[[wikilinks]]` resolve
- Note lives under the correct top-level folder
- No proprietary HTML or generated cache files

### personal-harness

From the harness root (or the isolated implementation worktree):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 -m json.tool .cursor/hooks.json >/dev/null
python3 .cursor/hooks/runtime_gate.py benchmark --json
```

The tests live in `harness/`, the package both hosts share, not under
`.cursor/`. `--help` is not a valid shim probe: it prints `unknown command` and
still exits 0. See `docs/cursor-onboarding.md`.

Follow `docs/runtime-contract.md` for obligation IDs, receipts, and Agent-shell
preflight. Dispatch a fresh-context review at the required tier; T2 harness
runtime changes still use `/adversarial-review`.

## Affected, not everything

Judge "affected" by callers, not by diff size. A one-line edit to a helper or
export with many importers is not a small change. Use the blast-radius recipe
in `.cursor/skills/adversarial-review/references/evidence-capture.md` before
deciding which tests and critics to run.

## Fix every instance at the shared layer

Before claiming a fix complete:

1. Grep every `ui-*` package, docs page, story, and both frontend roots for
   the same pattern.
2. Prefer the fix in the shared helper, `ui-core` primitive, or base module
   over a consumer-only patch.
3. List every instance touched or deliberately deferred. Deferred instances
   belong in the plan's out-of-scope section or the task summary.

Do not leave sibling call sites untouched after autocorrecting one.

## Lean execution sequence (user-visible migrations)

1. Freeze and register the accepted plan (`register-plan --manifest`).
2. Declare per-path evidence mode. Default is visual parity (`none` /
   `expected_unchanged`): token swaps and architecture-under-the-hood work
   that should look the same do not capture screenshots.
3. Capture baselines only for rows that declare a visual delta (`after`,
   `before-after`, or migration `changed` / `new_visible`).
4. Implement the shared contract plus one representative real consumer.
5. Run focused type, semantic DOM, and (when a delta is declared) rendered
   product checks for that sentinel.
6. Stop and correct the contract if the sentinel fails; do not begin the sweep.
7. Migrate remaining consumers and run affected checks.
8. When a visual delta is declared: stage final content, run `capture-ready`
   (alias `execution-preflight`), batch after captures once, and run one
   fresh-context visual acceptance pass. Then commit, push, and publish hosted
   evidence.

`capture-ready` blocks capture when the strict profile is missing, required paths
are untouched, nonvisual verification receipts are missing, the after subject
tree is not final, manifest coverage does not match the diff, or the session is
over budget.

Definitive captures use schema v4 receipts. Storybook receipts bind an exact
committed product story; product-route receipts bind an exact product
entrypoint, route, scenario adapter, and migration-state assertion.
`not-applicable` and parity rows produce no image or attachment slot. Both
executable capture kinds rederive the source commit and tree from Git, require a
clean normal checkout, and reject opposite-role cache, process, module,
stylesheet, or artifact reuse.

## Rendered evidence only when pixels should change

Treat screenshots like Chromatic: require them only when the change is expected
to yield a visual difference. Touching a user-visible surface is not enough.

- **Parity / token swap / architecture-only.** Declare `none` on the execution
  manifest glob, or `expected_unchanged` / `static_only` on the migration row.
  No before/after artifacts, hosted URLs, or `visual.acceptance` receipt.
  Optional captures, if present, must hash-match.
- **Visual delta.** Declare `after` (new surface) or `before-after` (changed
  existing surface), or a migration row with `changed` / `new_visible`. Those
  rows need Storybook, docs, or Playwright artifacts bound to the tree.

**Migration PRs** require a labeled before/after pair only for declared visual
deltas. Use `python3 harness/cli.py migration-evidence verify` against a
manifest under `.harness/runtime/evidence/`; embed hosted URLs in the PR body;
never commit evidence binaries to the product branch.

If a declared-delta surface cannot be reached live, render against realistic
data and say so. A green typecheck alone is not rendered evidence for a
declared visual delta.

## Standing obligations

These are citable personal obligations for implementation work in this
workspace. Subagents and reviews may treat violations as contract defects.

- Keep `ui-components.generated.ts` (or the target root's equivalent
  generated registry) current when component APIs change.
- Update the corresponding docs-site page for any `ui-*` package change.
- Style with `prefixClass` for the block and `bem` for elements and modifiers
  (`packages/ui-core/src/utils/{prefix-class,bem}.ts`, exported from `index.ts`),
  and update or create the related SCSS file.
- Prefer semantic tokens over raw values. Tokens are CSS custom properties
  (`var(--token)`), not SCSS variables. `apps/docs/mdx/design/foundations/`
  states the specific rules; `packages/ui-core/scripts/audit-component-scss-paint.mjs`
  mechanically enforces the paint subset.
- New visible-text props on owned components must be typed `LocalizedMessage`
  (`packages/mfe-core/src/contract/domains/localization/interface.ts:9`), which
  `pnpm typecheck` then enforces. Existing ui-core props are still plain
  `string` for historical reasons, so this binds new props only.
- Declare Module Federation shared dependencies in both the remote and
  `apps/responder/vite.config.mjs`.
- Feature flags require `TeamID`, `outagePolicy`, and `updatePolicy`.
- Generated files are checked in and CI rejects drift.
- Do not add comments unless asked.
- Check for linter and TypeScript errors before completing the answer.
- Prefer Graphite/Cursor Review for branch and PR management when available.
- If a Figma link is supplied, check that the Figma MCP is active; if not,
  ask to authenticate again.

## Done means

A task is done only when all of the following are true:

1. Per-root verification commands for affected callers have been run and their
   output pasted or summarized with exit status.
2. Rendered evidence is attached for every declared visual delta. Parity,
   token-swap, and architecture-only work must not be blocked on screenshots.
3. Every instance of the changed pattern is fixed at the shared layer, or
   explicitly deferred with a reason.
4. Generated artifacts named by the plan or standing obligations are current.
5. A fresh-context review has been dispatched at the **computed** blast-radius
   tier (`docs/routing-matrix.md`), not an asserted one, and the critic returns
   are identity-bound where the host supplies identity.
6. Changed paths conform to the plan's declared scope: nothing `undeclared` and
   nothing `unimplemented`, or each exception stated with a reason.

Authoring-context self-review and a green CI run alone do not satisfy item 5.

## Constraints

- Do not skip repository hooks with `--no-verify` unless explicitly instructed.
- Do not amend commits or force-push to trunk.
- Do not modify `personal-harness` during an ordinary product implementation
  task unless the user asks to update the harness. Explicit harness
  implementation is a first-class target when the user names it.
- Preserve pre-existing dirty working trees in every root.
