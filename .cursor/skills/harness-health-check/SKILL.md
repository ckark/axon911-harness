---
name: harness-health-check
description: Verifies that the Axon 911 personal multi-root Cursor workspace, repository instructions, project skills, docs benchmark, personal critics, and formal review skill are discoverable. Always read-only.
---

# Axon 911 Harness Health Check

Do not modify files or run mutating commands.

## Checks

1. List the workspace roots and confirm:
   - `prepared911`
   - `axon911-frontend`
   - `vault-core-ux`
   - `personal-harness`
2. Resolve and read:
   - `prepared911/AGENTS.md`
   - `prepared911/turbo/AGENTS.md`
   - `axon911-frontend/AGENTS.md`
   - `docs/workspace-rule.md` in the personal harness
3. Confirm these axon911-frontend (primary) and Prepared911 paths exist:
   - `axon911-frontend/apps/docs/mdx/design`
   - `axon911-frontend/apps/docs/mdx/engineering`
   - `axon911-frontend/apps/docs/generated/component-api-registry.json`
   - `prepared911/.agent/skills/planning-workflow/SKILL.md`
   - `prepared911/.agent/skills/react-ui-implementation/SKILL.md`
   - `prepared911/turbo/apps/docs/mdx/design` (secondary docs benchmark)
4. Confirm the personal harness contains:
   - `docs/review-contract.md`
   - `docs/routing-matrix.md`
   - `docs/plan-contract.md`
   - `docs/implementation-contract.md`
   - `docs/workspace-rule.md`
   - `docs/cursor-onboarding.md`
   - `docs/axon911-agents.md` (deferred; not a live workspace root)
   - `.cursor/skills/adversarial-review/SKILL.md`
   - `.cursor/skills/plan-check/SKILL.md`
   - `.cursor/skills/implementation-check/SKILL.md`
   - All files linked from the adversarial-review skill under `references/`
   - `.cursor/skills/adversarial-review/references/evidence-capture.md`
   - Seeded maintenance cases under
     `.cursor/skills/adversarial-review/evals/`
4a. Confirm `docs/review-contract.md` requires these evidence fields:
   - `Ref manifest` under Scope reviewed
   - `Working tree state` under Scope reviewed
   - `State` per finding (`committed` / `uncommitted` / `both`)
   - `Target layer` per finding (`plan-text` / `mid-stack-head` /
     `tip-residual` / `process`)
   - `Verification command` per provenance or numeric finding
   - Optional per-finding `Escalation` field
4b. Confirm adversarial-review `SKILL.md` includes:
   - Claim ledger plan disposition (`open` / `remediated-by-plan` /
     `out-of-scope`)
   - Phase 4 critic states (`returned-valid` / `returned-invalid` /
     `not-yet-returned`)
   - Phase 0 blast-radius tier resolution
   - Escalations raised and actioned in the final response
4c. Confirm `evidence-capture.md` includes the acceptance-criterion recipe and
   the blast-radius section.
4d. Confirm
    `.cursor/skills/adversarial-review/evals/adjudication-cases.md`
    includes `ADJ-9` through `ADJ-15`.
4e. Confirm `docs/routing-matrix.md` defines blast-radius tiers `T0`, `T1`,
   and `T2`.
4f. Confirm the workspace rule binds `docs/plan-contract.md` and
   `docs/implementation-contract.md`.
4g. Confirm runtime verification assets:
   - `docs/runtime-contract.md` (cooperative assurance, not tamper-proof)
   - `.cursor/hooks.json` (7 events bound to `.cursor/hooks/runtime_gate.py`)
   - `.cursor/hooks/runtime_gate.py`
   - `harness/cli.py`
   - `harness/scope_probe.py`
   - `.cursor/skills/implementation-check/SKILL.md`
   - `.cursor/agents/implementation-verifier.md`
   - `automations/pr-verification/config.json` with `status: dormant`
   - `.gitignore` ignores `.harness/runtime/`
4h. Absence of `.harness/runtime/scope-probe.json` is not a fail; skip
    verification and do not treat missing sibling-root fires as a pass. If
    that report exists, verify it as its own command (do not chain `git
    status`) and report `enforcement_scope`:

    ```bash
    python3 harness/scope_probe.py verify-report \
      .harness/runtime/scope-probe.json \
      --attempted-root personal-harness \
      --attempted-root prepared911 \
      --attempted-root axon911-frontend \
      --attempted-root vault-core-ux
    ```

    `verify-report` requires the positional report path and at least one
    `--attempted-root`. Missing sibling-root fires after a bounded window are
    a documented limitation, not a pass.
4i. Confirm Cursor exposes `implementation-check` and
    `implementation-verifier` in addition to the review panel.
4j. Confirm Cursor wiring from `docs/cursor-onboarding.md`:
    `python3 .cursor/hooks/runtime_gate.py benchmark --json` reports
    `history_independent: true`. Do not use `--help` as a probe. Do not chain
    this with `git status`; check 7 is a separate single command.
5. Report whether Cursor exposes:
   - `adversarial-review`
   - `plan-check`
   - `design-system-critic`
   - `frontend-architecture-critic`
   - `performance-reliability-critic`
   - `security-privacy-critic`
   - `quality-accessibility-critic`
   - `review-adjudicator`
6. Inspect Prepared911 `.cursor/mcp.json` and report the configured MCP server
   names without printing credentials or environment values.
7. Run only `git status --short --branch` in each repository root. One
    repository per command; never combine roots or chain with check 4j.
8. Report pre-existing dirty working trees without printing unnecessarily large
   diffs.
9. Confirm that no files changed during the health check.
10. Confirm invocation behavior:
    - The workspace rule is always-on.
    - Skills are dynamically discoverable.
    - `/plan-check` is the cheap plan gate (no critics).
    - `/implementation-check` attests verification and issues review receipts.
    - `/adversarial-review` explicitly requests the formal critic panel.
    - Critics do not run on every ordinary coding request.
    - Ordinary work still requires a fresh-context pass at the resolved tier.

## Output

Return:

- Overall: `PASS`, `PASS WITH WARNINGS`, or `FAIL`
- Workspace roots
- Prepared911 instruction discovery
- Skills and subagent discovery
- Docs benchmark availability
- MCP configuration availability
- Working-tree status
- Exact remediation for every warning or failure
