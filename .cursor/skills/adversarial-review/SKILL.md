---
name: adversarial-review
description: Optional formal review gate. Dispatches the design-system critic plus Cursor bugbot/security-review when the panel trigger list applies. Use only after scope is frozen.
---

# Axon 911 Adversarial Review

Read-only. Never applies fixes. **Default posture is mechanical-on, panel-off.**
Run this skill only when a trigger from `docs/workspace-rule.md` applies or
the user explicitly requests it.

## Before starting

1. Confirm scope is **frozen**. If requirements are still changing, refuse and
   say why. Do not panel an unfrozen plan.
2. Read `docs/review-contract.md` and `docs/routing-matrix.md`.
3. Run `python3 harness/cli.py tier --root <root> --json` if tier is unknown.

## Panel (at most one bespoke critic)

Dispatch **in one foreground batch**, never backgrounded:

1. `design-system-critic` — always, for harness-specific authority and blast
   radius
2. Cursor `bugbot` — general code review
3. Cursor `security-review` — only when injection, auth, or trust boundaries
   were an explicit requirement

Do not dispatch performance-reliability or quality-accessibility critics.
Use Storybook MCP `run-story-tests` and Bugbot for those concerns.

There is no adjudicator. The human PR reviewer arbitrates.

## Evidence

Follow `.cursor/skills/adversarial-review/references/evidence-capture.md`.
Critics write full reports to `.harness/runtime/reports/` and return envelopes
only. Surviving findings go in the PR body test plan.

## After review

Run `/implementation-check` to issue a review receipt when `HARNESS_REVIEW_MODE`
is `on-request` or `always`. With default `off`, the receipt is optional but
still recorded when this skill completes.

Do not implement corrections in this skill.
