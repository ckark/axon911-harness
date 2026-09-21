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

## Jev routing (before dispatch)

Run batched Jev review routing on trigger facts only (changed-path summary,
tier predicate, auth/privacy flags). Do not send full diffs or secrets.

```bash
python3 harness/cli.py jev route-review \
  --fact tier=T2 --fact ui_packages_changed=true --json
```

When Jev returns `policy_action=fallback`, dispatch the full default panel below.
Screen context passages before critic dispatch:

```bash
python3 harness/cli.py jev rank-context --purpose review --passage "id=text" --json
```

After critics return findings, classify each finding:

```bash
python3 harness/cli.py jev check-findings --file .harness/runtime/reports/<critic>-<fingerprint>.md --json
```

Uncertain classifications stay with the human reviewer.

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
still recorded when this skill completes. Receipts require a validated on-disk
report via `issue-review-receipt --report`.

Do not implement corrections in this skill.
