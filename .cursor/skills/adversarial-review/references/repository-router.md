# Repository Router

Resolve the target root before loading domain context.

| Root | Identity | Primary instructions | Typical role |
|---|---|---|---|
| `prepared911` | `AGENTS.md`, `turbo/AGENTS.md`, `turbo/packages/ui-core/package.json` | Layered `AGENTS.md`, referenced `.agent/skills`, source and tests | Production monorepo and authoritative current behavior |
| `axon911-frontend` | Root `AGENTS.md`, `apps/responder`, `remotes`, `packages/tooling-config` | Root `AGENTS.md`, `.agents/skills/README.md`, triggered `.agents/skills/*/SKILL.md` | Vite 8, Module Federation, TanStack Router prototype and vendored UI consumers |
| `vault-core-ux` | Root `README.md`, `20-architecture`, `30-standards` | `README.md`, `.cursorrules`, note frontmatter and linked architecture index | Knowledge vault: decisions, proposals, standards, and historical context |
| `personal-harness` | `docs/review-contract.md`, `.cursor/skills/adversarial-review/SKILL.md` | Workspace rule, plan/implementation/runtime contracts, routing matrix, critic prompts | Review orchestration and explicit harness implementation, including runtime verification |

## Route by target

- If the target names one root, use that root's instructions and behavior as
  authoritative.
- If a target crosses roots, create a separate evidence section per root and
  identify the contract joining them.
- Treat similarly named packages as distinct until package name, version,
  exports, and ownership are compared.
- Treat Vault notes as context or intent, not proof of runtime behavior.
- Treat Axon's vendored packages as consumers or forks unless their provenance
  proves they are the current source of truth.

Use `cross-repo-source-priority.md` whenever sources disagree or code is
proposed to move between roots.
