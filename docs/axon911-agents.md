# Axon911 Agents (deferred workspace root)

`prepared911/axon911-agents` is the Eve production monorepo for independently
deployable agents. It is cloned at
`/Users/ckark/Documents/GitHub/axon911-agents` and is **not** a live workspace
root yet. Do not add it to `axon911-harness.code-workspace`, the
repository router, or the always-on workspace rule until that wiring is
explicitly requested.

This note is harness overlay only. It does not change Eve runtime law.

## What it is

Private Eve-native monorepo. Default branch `main`. Agents include:

- Software Factory: `intake-agent`, `classifier-agent`, `build-agent`
- `core-ux-agent` (Ally Gorethm; Slack + GitHub Core UX teammate/reviewer)
- `triage-bot`

Identity markers for a future router row:

- Root `AGENTS.md`
- `agents/`
- `packages/agent-governance/`

Primary instructions: root `AGENTS.md` and
`.agents/skills/axon911-agent-development/SKILL.md`.

## How to use it with this harness today

Open or edit that clone as its own Cursor window when the task targets an
Eve agent. Follow its instructions. Use this harness only as a local overlay:

| Job | Use |
|---|---|
| Change an agent, eval, or policy | Target `axon911-agents`. Follow its `AGENTS.md`. |
| Local plan/review overlay | `/plan-check` and `/adversarial-review` in this harness |
| PR teammate on GitHub/Slack | `core-ux-agent` (Ally). Loads Prepared skills from `prepared911` at a pinned SHA. Does not load private critics. |
| Staff request to Cursor Cloud | `classifier-agent`. Cloud sessions do not see harness project hooks. |

Local T2 review and Core UX PR review can stack. They are not substitutes.

Verification in that repo (from its `AGENTS.md`):

```bash
pnpm install
pnpm typecheck
pnpm test
pnpm build
pnpm eval
```

Prefer `pnpm --filter <agent>` plus `eve info` after authored Eve filesystem
changes.

## Source priority

When a task names `axon911-agents`, that repository's instructions win. Do
not apply Prepared911 `turbo/` commands, Axon MFE rules, or harness critic
prompts as Eve runtime law.

Keep agent contracts harness-neutral: Cursor, Claude SDK, or pi.dev may
develop and evaluate. They must not gain production authority or skip Eve
policy, redaction, evals, or approvals.

`core-ux-agent` loads Prepared skills read-only from `prepared911/prepared911`
at `PREPARED911_SKILLS_REF` / registry `reviewRef`, not from this harness.

## Do not

- Merge Eve agents into this harness or copy harness critics into Eve
  production
- Copy `.cursor/hooks` or personal critics into `axon911-agents`
- Put harness receipts in place of Eve policy
- Point Core UX at harness skills instead of pinned `prepared911` skills
- Expect local mutation preflight to constrain classifier-launched Cloud
  Agents
- Treat Vault notes as proof of Eve runtime
- Copy secrets, Connect, Vercel projects, or CODEOWNERS into this harness

## Future wiring (not done)

When explicitly requested, land these in the same change:

1. Add a fifth workspace folder named `axon911-agents` pointing at
   `../../GitHub/axon911-agents` (same relative style as `axon911-frontend`).
2. Teach the repository router the identity markers above.
3. List the root in the workspace rule, plan contract, implementation
   contract, health check, and README.
4. Add a routing-matrix signal for Eve agent, policy, eval, or governance
   changes: security/privacy plus the relevant domain critic. Do not treat
   this as an Axon MFE or `ui-*` change.
5. If runtime verification is active, add `axon911-agents` to configured
   roots with empty product UI obligations (same class as vault). Prove
   `git -C …/axon911-agents commit` denies as `root=axon911-agents`.

Until then, health check must still pass with the four live roots only.
