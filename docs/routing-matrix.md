# Axon 911 Review Routing Matrix

## Blast-radius tiers

Tier sets **how many critics** and **how deep** they go. The change-signal table
below still sets **which** critics apply.

Tier is **computed, not asserted**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py tier --root <root> --stated <tier> --json
```

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

| Tier | Predicate | Panel |
|---|---|---|
| `T0` | `surface_delta == none` and at most 3 call sites per changed symbol, no risk signal | One critic, diff-scoped |
| `T1` | `surface_delta == none` with broader reuse, **or** `additive`, **or** more distinct changed symbols than the scoring cap | Two critics |
| `T2` | `surface_delta == breaking`, **or** a risk signal, **or** cross-root, **or** unmeasurable | Signal-selected panel plus adjudication |

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

## Change signals

Use all five critics for substantial formal reviews (`T2` or broad change
signals). For narrower reviews, the coordinator may omit clearly irrelevant
critics but must say why. Tier still caps panel size: a `T0` review runs one
critic even when several change signals match; a `T1` review runs two.

| Change signal | Required critics | Required evidence |
|---|---|---|
| `axon911-frontend/packages/ui-core/**`, tokens, themes, icons, public UI API | Design system, frontend architecture, performance, quality/accessibility | Docs design MDX, generated API registry, Storybook, consumers |
| Other `axon911-frontend/packages/ui-*/**` | Design system, frontend architecture, quality/accessibility | Package exports, dependencies, docs coverage, stories, consumers |
| Dispatch/Responder/Caller React change | Frontend architecture; add other critics by risk | Vite rules, Apollo/state evidence, affected consumers |
| Beacon or Docs React change | Frontend architecture; add other critics by risk | Next.js/RSC rules, server/client boundaries |
| RBAC, authentication, roles, permissions, PII | Security/privacy and frontend architecture | RBAC skills, caller paths, tests, server enforcement |
| Lists, subscriptions, audio/video lifecycle, bundle or cache change | Performance/reliability and frontend architecture | Measurements or explicit measurement gap |
| Forms, modals, navigation, interactive components | Quality/accessibility and design system | Accessibility MDX, stories, semantic tests |
| Plan affecting public contracts or multiple apps | All critics | Plan references, package graph, migration/rollout strategy |
| Axon host, remote, federation, or shared-domain change | Frontend architecture; add performance, security, and quality by risk | Axon `AGENTS.md`, triggered MFE/Vite/router skills, shell/remote contract and failure UI |
| Axon vendored `@prepared/ui-*` change | Design system, frontend architecture, quality/accessibility | Package provenance, exports, Prepared911 docs benchmark, Axon consumers |
| Vault architecture or standard update | Relevant domain critic and adjudicator | Note frontmatter, linked architecture index, runtime sources supporting any implementation claim |
| Contract spanning Prepared911 and Axon | All critics | Separate evidence per root, ownership, versions/exports, producer/consumers, rollout and rollback |
| Harness runtime, Cursor hooks, review contracts, or always-on workspace rules | Frontend architecture, security/privacy, quality/accessibility; add performance when hooks or ledgers are on a hot path | Runtime contract, event schemas, receipt fingerprints, and measured cross-root scope |

Next.js-only patterns from `axon911-frontend/apps/docs` must never be imposed on
Vite apps. axon911-frontend runs three Vite 8 + TanStack Router + Module
Federation shells and eight remotes alongside two Next.js apps (`apps/docs`,
`apps/auth`); classify guidance as `[universal]`, `[next]`, or `[vite]` before
applying it.

Two further rows for the flat axon layout:

| Change signal | Required critics | Required evidence |
|---|---|---|
| `packages/mfe-core/**`, `packages/tooling-config/**` | Frontend architecture, performance | Contract and build-factory surface for 3 shells and 8 remotes; `pnpm mf:types:check` |
| `prepared911/turbo/packages/ui-*/**` | Design system, frontend architecture | Deprecating mirror: state whether the change belongs in axon911-frontend instead |
