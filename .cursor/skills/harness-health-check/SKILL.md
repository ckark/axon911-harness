---
name: harness-health-check
description: Verifies that the Axon 911 personal multi-root Cursor workspace, repository instructions, project skills, docs benchmark, and runtime hooks are discoverable. Always read-only.
---

# Axon 911 Harness Health Check

Do not modify files or run mutating commands.

## Checks

1. List the workspace roots and confirm all four roots resolve.
2. Resolve and read each root's `AGENTS.md` (or vault `.cursorrules`).
3. Confirm axon911-frontend docs benchmark paths exist.
4. Confirm the personal harness contains:
   - `docs/review-contract.md`, `docs/runtime-contract.md`, `docs/workspace-rule.md`
   - `docs/session-budget.md`
   - `.cursor/skills/adversarial-review/SKILL.md`
   - `.cursor/skills/plan-check/SKILL.md`
   - `.cursor/skills/implementation-check/SKILL.md`
   - `.cursor/skills/capture-evidence/SKILL.md`
   - `.cursor/agents/design-system-critic.md`
   - `.cursor/agents/evidence-verifier.md`
   - `.cursor/hooks.json` and `.cursor/hooks/runtime_gate.py`
   - `harness/cli.py` with `verify` and `cost` subcommands
5. Confirm deleted critics are absent:
   - no `review-adjudicator`, `implementation-verifier`, or multi-critic panel agents
6. Confirm `docs/workspace-rule.md` documents mechanical-on / panel-off posture.
7. Run `python3 harness/cli.py benchmark --json` (expect `history_independent: true`).
8. Run `git status --short --branch` in each repository root (one command each).
9. Confirm no files changed during the health check.

## Output

Return overall `PASS`, `PASS WITH WARNINGS`, or `FAIL` with exact remediation.
