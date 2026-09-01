# Prepared911 Docs Benchmark

Required for design-system and frontend-architecture critics.

The primary benchmark is axon911-frontend's docs app, which documents the
packages axon911-frontend owns post CORE-754. prepared911's `turbo/apps/docs`
is secondary until its removal lands. Where the two disagree about
`@prepared/ui-*`, axon911-frontend is correct and the divergence is a
`DOCS-DRIFT-###` finding, not a judgment call.

## Route to the smallest relevant docs slice

- Design foundations: `axon911-frontend/apps/docs/mdx/design/foundations`
- Primitives: `axon911-frontend/apps/docs/mdx/design/primitives`
- Components: `axon911-frontend/apps/docs/mdx/design/components`
- Blocks: `axon911-frontend/apps/docs/mdx/design/blocks`
- Calendar and other domain catalogs: matching `mdx/design/*`
- Architecture and data: `axon911-frontend/apps/docs/mdx/engineering/architecture` and
  `working-with-data`
- Performance: `axon911-frontend/apps/docs/mdx/engineering/performance`
- Testing: `axon911-frontend/apps/docs/mdx/engineering/testing-strategy`
- Feature workflow: `axon911-frontend/apps/docs/mdx/engineering/working-on-features`
- Generated public surface:
  `axon911-frontend/apps/docs/generated/component-api-registry.json`
- Concrete docs consumer: relevant files under `app`, `features`, and `common`
- Secondary prepared911 slice (only when relevant): `turbo/apps/docs/...`

For a documented component, inspect `usage.mdx`, `api-dev.mdx`, and
`accessibility.mdx` when present. Then compare those claims with package
exports, source, tests, stories, and rendered examples.

## Runtime labels

Label relevant architecture guidance:

- `[universal]`: applies across React runtimes
- `[next]`: Next.js/App Router/RSC only
- `[vite]`: Vite SPA behavior

The docs app is a Next.js reference and a consumer of shared packages. It is
not a runtime template for Dispatch, Responder, Caller, or Axon.

## Drift handling

When docs conflict with API, tests, or behavior:

1. Preserve the stronger source as the review baseline.
2. Report the exact conflict as `DOCS-DRIFT`.
3. State whether generated API, prose, example, migration, or rendered
   verification needs updating.

Complete the `Docs Benchmark` template in `docs/review-contract.md` even when
the docs do not cover the target.
