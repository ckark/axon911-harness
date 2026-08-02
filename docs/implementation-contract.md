# Prepared911 Implementation Contract

Personal definition of done for work across the multi-root workspace. This
contract does not redefine repository coding standards. Resolve the target root
first, then use that root's own instructions and verification commands.

## Resolve the root first

Identify which of `prepared911`, `axon911-frontend`, or `vault-core-ux` owns
the change. Read that root's `AGENTS.md` (or vault `.cursorrules`) before
editing. Do not transfer Prepared911 commands or conventions to another root.

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

```bash
pnpm check
pnpm turbo run typecheck
```

Run package-scoped tests when the change has dedicated coverage. Prefer
`pnpm fix` before claiming lint/format done.

### vault-core-ux

- Required frontmatter present and valid
- Outgoing `[[wikilinks]]` resolve
- Note lives under the correct top-level folder
- No proprietary HTML or generated cache files

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

## Rendered evidence for anything a user sees

Anything an operator or user sees rendered — UI components, docs pages, modal
flows, Storybook variants — ships with rendered evidence of the after state
(before-and-after when changing something that already exists):

- Storybook story
- Docs page
- Playwright screenshot or trace

If the surface cannot be reached live, render against realistic data and say
so. A green typecheck alone is not rendered evidence.

## Standing obligations

These are citable personal obligations for implementation work in this
workspace. Subagents and reviews may treat violations as contract defects.

- Keep `ui-components.generated.ts` (or the target root's equivalent
  generated registry) current when component APIs change.
- Update the corresponding docs-site page for any `ui-*` package change.
- Never use the `style` attribute on `Box` or `FlexBox`; use `className` with
  `bem` and `prefixClass`, and update or create the related SCSS file.
- Never use basic HTML elements (`button`, `div`, `span`, and peers) when a
  `@prepared/ui-core` primitive exists. Ask before using raw `div` or `span`.
- Do not add comments unless asked; always add tsdocs to new props, hooks,
  utils, and helper files.
- Check for linter and TypeScript errors before completing the answer.
- Prefer Graphite/Cursor Review for branch and PR management when available.
- If a Figma link is supplied, check that the Figma MCP is active; if not,
  ask to authenticate again.

## Done means

A task is done only when all of the following are true:

1. Per-root verification commands for affected callers have been run and their
   output pasted or summarized with exit status.
2. Rendered evidence is attached for any user-visible change.
3. Every instance of the changed pattern is fixed at the shared layer, or
   explicitly deferred with a reason.
4. Generated artifacts named by the plan or standing obligations are current.
5. A fresh-context review has been dispatched at the blast-radius tier the
   change requires (`T0`, `T1`, or `T2` per `docs/routing-matrix.md`).

Authoring-context self-review and a green CI run alone do not satisfy item 5.

## Constraints

- Do not skip repository hooks with `--no-verify` unless explicitly instructed.
- Do not amend commits or force-push to trunk.
- Do not modify `personal-harness` during an ordinary product implementation
  task unless the user asks to update the harness.
- Preserve pre-existing dirty working trees in every root.
