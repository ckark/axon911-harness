# Repository Router

Resolve the target root before loading domain context.

| Root | Identity | Primary instructions | Typical role |
|---|---|---|---|
| `axon911-frontend` | Root `AGENTS.md`, `packages/ui`, `apps/docs`, `apps/storybook` | Root `AGENTS.md`, `.agents/skills/README.md`, `docs/VENDORING.md`, triggered `.agents/skills/*/SKILL.md` | Owns the design system `packages/ui` (`@prepared911/ui`, being renamed `@axon911/ui`) and the legacy `@prepared911/ui-*` packages post CORE-754; architectural and agentic authority for the Axon 911 ecosystem; three Vite 8 + Module Federation + TanStack Router shells and eight remotes, plus two Next.js apps (`apps/docs`, `apps/auth`) |
| `prepared911` | `AGENTS.md`, `turbo/AGENTS.md`, `turbo/packages/ui-core/package.json` | Layered `AGENTS.md`, referenced `.agent/skills`, source and tests | Application repository; consumes published `@prepared911/ui-*` artifacts; `turbo/packages/ui-*` is a deprecating mirror slated for removal, not a source of truth |
| `vault-core-ux` | Root `README.md`, `20-architecture`, `30-standards` | `README.md`, `.cursorrules`, note frontmatter and linked architecture index | Knowledge vault: decisions, proposals, standards, and historical context |
| `chroma` | Root `AGENTS.md`, `lib/color/`, `lib/tokens/`, `tokens/`, `figma-plugin/` | Root `AGENTS.md` (Next.js agent rules), `docs/token-spec.md`, `docs/figma-pipeline.md` | Colour-ramp and token generator; emits CSS tokens, `tokens/manifest.json`, and the Figma variables payload |
| `personal-harness` | `docs/review-contract.md`, `.cursor/skills/adversarial-review/SKILL.md` | Workspace rule, plan/implementation/runtime contracts, routing matrix, critic prompts | Review orchestration and explicit harness implementation, including runtime verification |

## Route by target

- If the target names one root, use that root's instructions and behavior as
  authoritative.
- If a target crosses roots, create a separate evidence section per root and
  identify the contract joining them.
- Treat similarly named packages as distinct until package name, version,
  exports, and ownership are compared.
- Treat Vault notes as context or intent, not proof of runtime behavior.
- Treat axon911-frontend's `packages/ui` as the design system's source of
  truth. CORE-1276 deletes its legacy `packages/ui-*`. Treat prepared911's `turbo/packages/ui-*` as the deprecating
  mirror unless the target explicitly names it as the fix location.

Use `cross-repo-source-priority.md` whenever sources disagree or code is
proposed to move between roots.
