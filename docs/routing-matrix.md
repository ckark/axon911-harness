# Prepared911 Review Routing Matrix

## Blast-radius tiers

Tier sets **how many critics** and **how deep** they go. The change-signal
table below still sets **which** critics apply. Judge tier by callers, not by
file count. A one-line edit to a helper with many importers is not a small
change. Use the blast-radius recipe in
`.cursor/skills/adversarial-review/references/evidence-capture.md`.

A stated tier is a **floor**, not a ceiling. Critics may escalate when they
spot material risk outside a narrow scope.

| Tier | When | Panel depth |
|---|---|---|
| `T0` narrow | Leaf change, no exported surface, few callers (importer count required) | One critic, diff-scoped, modest effort |
| `T1` moderate | App-shared component or package-internal contract | Two critics |
| `T2` broad | Public `ui-*` export, token or theme, RBAC/auth/PII, subscription or audio/video lifecycle, cross-root contract, or a diff too large to hold in one head | Full panel selected by change signal, high effort |

For ordinary work, `/plan-check` scores the plan's tier. Formal
`/adversarial-review` resolves the tier in Phase 0 before selecting the
panel. Never skip a fresh-context pass solely because the change looks small
by file count.

## Change signals

Use all five critics for substantial formal reviews (`T2` or broad change
signals). For narrower reviews, the coordinator may omit clearly irrelevant
critics but must say why. Tier still caps panel size: a `T0` review runs one
critic even when several change signals match; a `T1` review runs two.

| Change signal | Required critics | Required evidence |
|---|---|---|
| `turbo/packages/ui-core/**`, tokens, themes, icons, public UI API | Design system, frontend architecture, performance, quality/accessibility | Docs design MDX, generated API registry, Storybook, consumers |
| Other `turbo/packages/ui-*/**` | Design system, frontend architecture, quality/accessibility | Package exports, dependencies, docs coverage, stories, consumers |
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

Next.js-only patterns from `turbo/apps/docs` must never be imposed on Vite apps.
The docs app is a benchmark for shared principles and a concrete Next.js
consumer, not a universal runtime template.
