# Axon 911 Review Routing Matrix

## Blast-radius tiers

Tier sets **how deep** a review goes. It applies only after a trigger in
`docs/workspace-rule.md` has turned the panel on; the default is panel off.
The change-signal table below sets **which concerns** the review covers.

Tier is **computed, not asserted**:

```bash
python3 harness/cli.py tier --root <root> --stated <tier> --json
```

Under Cursor, run it from the harness root as
`python3 harness/cli.py tier --root <root> --stated <tier> --json`. Add
`--against <ref>` to score a full branch before a PR; live gating never passes
it, because a hook must score the current edit.

### Why this replaced a prose table

The previous criteria listed "public `ui-*` export" as a `T2` trigger. All 14
`@prepared/ui-*` packages expose exactly one public entry
(`"." -> "./src/index.ts"`), so that predicate was true by construction for any
change to any of them. Two more triggers were unbounded ("cross-root contract",
"a diff too large to hold in one head"), and the matrix allowed escalation but
never de-escalation. An always-true predicate under a one-way ratchet can only
land on the maximum, so effectively every change scored `T2` and the hierarchy
carried no information.

### Inputs

| Input | How it is measured |
|---|---|
| Surface delta | Diff of the hand-maintained surfaces: `packages/ui-*/src/index.ts`, each `package.json` `exports` map, `packages/ui-*/src/models/**`, `packages/ui-core/src/styles/**`. Classified `none` / `additive` / `breaking`. |
| Call sites | Files that **import** a changed symbol, per symbol. Excludes the changed files, package barrels, stories and tests, and prepared911's `turbo/packages/ui-*` mirror — that tree is a byte-copy of axon's packages, not a consumer of them. |
| Risk signals | RBAC/auth/PII, realtime lifecycle, media lifecycle. |
| Measurability | Shallow clone, unresolved conflicts, or an interrupted rebase/merge. |

The docs component registry is deliberately **not** an input. It covers 9 of 14
packages, gates discovery on a stories file rather than on exports, and records
only the *name* of an enum-typed prop — so it cannot see an enum member being
added or removed, the most common real API change in this design system.

### Tiers

| Tier | Predicate | Depth, once the panel is on |
|---|---|---|
| `T0` | `surface_delta == none` and at most 3 call sites per changed symbol, no risk signal | Diff-scoped: `design-system-critic` only |
| `T1` | `surface_delta == none` with broader reuse, **or** `additive`, **or** more distinct changed symbols than the scoring cap | `design-system-critic` plus Cursor `bugbot` |
| `T2` | `surface_delta == breaking`, **or** a risk signal, **or** cross-root, **or** unmeasurable | The concerns the change signal names, mapped to the real panel below |

### Both directions are defects

- **Understated** — the plan claims narrower than the evidence. The review runs
  at the computed tier regardless.
- **Overstated** — the plan claims broader than the evidence. Not a harmless
  safety margin: it burns a full panel on a leaf change, and a tier that is
  always `T2` trains you to ignore the number.

A `T0` claim is incomplete without its call-site count. A `T2` claim is
incomplete without a named predicate — one of `surface-breaking`, `risk:<label>`,
`cross-root`, `unmeasurable`, `many-symbols`. **If no predicate can be cited, the
tier drops** to what the evidence supports. Critics may still escalate on
material risk found during review, but escalation now has to name what it found.

`unmeasurable` is not a verdict about the change; it is a verdict about the tree.
Remediate it (`git fetch --unshallow`, resolve the conflict, finish the rebase)
rather than accepting a defensive `T2`.

Surface scoring reads the hand-maintained `ui-*` surfaces: package barrels
(`src/index.ts`), `package.json`, `src/models/`, and `ui-core` styles. Symbols
come from TypeScript `export` lines. `personal-harness` declares no scored
surface at all, so a harness change reports `symbols: []` and
`surface_delta: none` whatever it adds. Read that `0 call site(s)` as **not
measured** rather than as a measured leaf, and tier harness work from risk,
cross-root reach, and judgment. `additive` implies `T1` for those `ui-*`
surfaces, not for a new Python helper.

## Change signals

The real panel is small. The harness has one bespoke critic,
`design-system-critic`. Everything else is an existing tool:

- Cursor `bugbot` covers general code review, including architecture and
  performance concerns.
- Cursor `security-review` covers security and privacy, and only when injection,
  auth, or trust boundaries were an explicit requirement.
- Storybook MCP `run-story-tests` covers interaction and accessibility.
- `ponytail-review` is optional and advisory, and only when the diff adds files,
  dependencies, or abstractions.

There is no adjudicator. The human PR reviewer arbitrates. For a narrower
review, omit a concern that clearly does not apply and say why.

| Change signal | Concerns | Real panel | Required evidence |
|---|---|---|---|
| `axon911-frontend/packages/ui/**` (the design system), tokens, themes, icons, public UI API | Design system, architecture, performance, accessibility | `design-system-critic`, `bugbot`, `run-story-tests` | `pnpm --filter ./packages/ui check`, generated API registry, docs design MDX, the package's own Storybook, consumers |
| Legacy `axon911-frontend/packages/ui-core/**` until CORE-1276 deletes it | Design system, architecture, performance, accessibility | `design-system-critic`, `bugbot`, `run-story-tests` | Docs design MDX, generated API registry, Storybook, consumers |
| Other `axon911-frontend/packages/ui-*/**` | Design system, architecture, accessibility | `design-system-critic`, `bugbot`, `run-story-tests` | Package exports, dependencies, docs coverage, stories, consumers |
| Dispatch/Responder/Caller React change | Architecture; add others by risk | `bugbot`; `design-system-critic` when shared UI changed | Vite rules, Apollo/state evidence, affected consumers |
| Beacon or Docs React change | Architecture; add others by risk | `bugbot`; `design-system-critic` when shared UI changed | Next.js/RSC rules, server/client boundaries |
| RBAC, authentication, roles, permissions, PII | Security/privacy and architecture | `security-review`, `bugbot` | RBAC skills, caller paths, tests, server enforcement |
| Lists, subscriptions, audio/video lifecycle, bundle or cache change | Performance and architecture | `bugbot`, with a measurement or an explicit measurement gap | Measurements or explicit measurement gap |
| Forms, modals, navigation, interactive components | Accessibility and design system | `design-system-critic`, `run-story-tests` | Accessibility MDX, stories, semantic tests |
| Plan affecting public contracts or multiple apps | Every concern the signals above name | The union of the panels those signals name | Plan references, package graph, migration/rollout strategy |
| Axon host, remote, federation, or shared-domain change | Architecture; add performance, security, and accessibility by risk | `bugbot`; `security-review` and `run-story-tests` when the risk applies | Axon `AGENTS.md`, triggered MFE/Vite/router skills, shell/remote contract and failure UI |
| prepared911 consumption of published `@prepared911/ui-*` (the `turbo/packages/ui-*` mirror routes below, not here) | Design system, architecture, accessibility | `design-system-critic`, `bugbot`, `run-story-tests` | Package provenance, exports, axon911-frontend `apps/docs` benchmark (prepared911 `turbo/apps/docs` only as secondary), prepared911 consumers |
| Vault architecture or standard update | The domain the note covers | `design-system-critic` when the note touches shared UI; otherwise `bugbot` | Note frontmatter, linked architecture index, runtime sources supporting any implementation claim |
| `chroma` generator, token emitters, or Figma sync (`lib/color/**`, `lib/tokens/**`, `tokens/**`, `figma-plugin/**`, `scripts/figma-push.ts`) | Design system and architecture | `design-system-critic`, `bugbot` | `pnpm check:generator`, `pnpm tokens:figma` validation, and a live Figma resolve check when the sync changes |
| `axon911-design` components, tokens, or Storybook (`src/**`, `.storybook/**`) | Design system, architecture, accessibility | `design-system-critic`, `bugbot`, `run-story-tests` | `pnpm check`, `pnpm typecheck`, `pnpm test:unit --run`, `pnpm test:storybook --run` |
| Contract spanning Prepared911 and Axon | Every concern the signals above name | The union of the panels those signals name | Separate evidence per root, ownership, versions/exports, producer/consumers, rollout and rollback |
| Harness runtime, Cursor hooks, review contracts, or always-on workspace rules | Architecture, security/privacy, accessibility; add performance when hooks or ledgers are on a hot path | `bugbot`, `security-review`; `run-story-tests` when a user-visible surface changed | Runtime contract, event schemas, receipt fingerprints, and measured cross-root scope |

Next.js-only patterns from `axon911-frontend/apps/docs` must never be imposed on
Vite apps. axon911-frontend runs three Vite 8 + TanStack Router + Module
Federation shells and eight remotes alongside two Next.js apps (`apps/docs`,
`apps/auth`); classify guidance as `[universal]`, `[next]`, or `[vite]` before
applying it.

Two further rows for the flat axon layout:

| Change signal | Concerns | Real panel | Required evidence |
|---|---|---|---|
| `packages/mfe-core/**`, `packages/tooling-config/**` | Architecture, performance | `bugbot` | Contract and build-factory surface for 3 shells and 8 remotes; `pnpm mf:types:check` |
| `prepared911/turbo/packages/ui-*/**` | Design system, architecture | `design-system-critic`, `bugbot` | Deprecating mirror: state whether the change belongs in axon911-frontend instead |
