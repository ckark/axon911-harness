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
   - `.cursor/skills/ponytail-review/SKILL.md`
   - `docs/ponytail.md` and `third_party/ponytail/LICENSE`
   - `.cursor/agents/design-system-critic.md`
   - `.cursor/hooks.json` and `.cursor/hooks/runtime_gate.py`
   - `harness/cli.py` with `verify`, `cost`, and `jev` subcommands
5. Confirm deleted critics are absent:
   - no `review-adjudicator`, `implementation-verifier`, or multi-critic panel agents
6. Confirm ponytail is **vendored text only** (FAIL if any apply):
   - `.cursor/hooks.json` or `~/.cursor/hooks.json` contains `hooks/ponytail-`
   - `.cursor/rules/ponytail.mdc` exists in the harness or first workspace root
   - `~/.cursor/.ponytail-active` exists
7. Confirm `docs/workspace-rule.md` documents mechanical-on / panel-off posture.
8. Run `python3 harness/cli.py benchmark --json` (expect `history_independent: true`).
9. Run `python3 harness/cli.py jev smoke --json` when `TYPESAFE_API_KEY` is configured (expect `policy_action=pass` or document fallback).
10. Verify hook-delivered routing:
   - `~/.cursor/hooks.json` contains `harness/dispatch/jev_hooks.py` for
     `beforeSubmitPrompt`, an unmatched `postToolUse`, and a `postToolUse`
     matcher `CreatePlan`. A missing entry is a **FAIL**.
   - `python3 harness/cli.py jev list-skills --json` resolves skills from more
     than one root; a single-root roster means root paths are misconfigured.
   - `python3 harness/cli.py jev routing-status --json` reports
     `eligible_turns`, `routed_turns`, `delivered_turns`, and `jev_failures`.
     `policy_action=flag` (delivered turns below 90% of eligible turns) is a
     **warning**, not a failure. `routing-idle` (no eligible turns) is not a
     failure.
   - `docs_rank=absent` is a **warning** only. Do not FAIL the health check
     for a missing doc rank.
11. Run `git status --short --branch` in each repository root (one command each).
12. Confirm no files changed during the health check.

## Output

Return overall `PASS`, `PASS WITH WARNINGS`, or `FAIL` with exact remediation.
