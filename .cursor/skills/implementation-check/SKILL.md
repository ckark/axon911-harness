---
name: implementation-check
description: Attest root-owned verification, gather fingerprint-bound evidence, optionally validate critic reports, and issue review receipts. Use before commits or pushes, after a stop follow-up, or when claiming implementation done.
---

# Implementation Check

Local receipts are cooperative assurance, not tamper-proof enforcement.

## Context loading

1. Read `docs/runtime-contract.md` and `docs/implementation-contract.md`.
2. Default posture is mechanical-on, panel-off (`HARNESS_REVIEW_MODE=off`).

## Procedure

1. Identify changed paths in each affected root.
2. Register the plan when one exists:

   ```bash
   python3 harness/cli.py register-plan --root <root> --plan-hash <sha256> --tier <tier>
   ```

3. Run root-owned checks through the attesting wrapper:

   ```bash
   python3 harness/cli.py attest --root <root> --obligation-id <id> --plan-hash <sha256> -- <argv>
   ```

4. Capture rendered evidence via `/capture-evidence` when user-visible surfaces changed.
5. Mechanical verification:

   ```bash
   python3 harness/cli.py verify --root <root> --json
   ```

6. **Review receipt (optional by default):** only when `/adversarial-review` ran
   or `HARNESS_REVIEW_MODE` is raised. Validate the report file at
   `.harness/runtime/reports/design-system-critic-<fingerprint>.md`, not prose
   in context. Then:

   ```bash
   python3 harness/cli.py issue-review-receipt \
     --root <root> --tier <tier> --plan-hash <sha256> --status PASS \
     --critic design-system-critic
   ```

7. For push: attest `push.oid`. For `gt submit`: attest `stack-oid-set`.

## Recovery

If a gate denies, rerun this skill against the current fingerprint.
