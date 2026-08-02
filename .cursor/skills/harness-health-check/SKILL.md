---
name: harness-health-check
description: Verifies that the Prepared911 personal multi-root Cursor workspace, repository instructions, project skills, docs benchmark, personal critics, and formal review skill are discoverable. Always read-only.
---

# Prepared911 Harness Health Check

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
   - `prepared911/turbo/apps/docs/AGENTS.md`
3. Confirm these Prepared911 paths exist:
   - `.agent/skills/planning-workflow/SKILL.md`
   - `.agent/skills/react-ui-implementation/SKILL.md`
   - `turbo/apps/docs/mdx/design`
   - `turbo/apps/docs/mdx/engineering`
   - `turbo/apps/docs/generated/component-api-registry.json`
4. Confirm the personal harness contains:
   - `docs/review-contract.md`
   - `docs/routing-matrix.md`
   - `docs/plan-contract.md`
   - `docs/implementation-contract.md`
   - `.cursor/skills/adversarial-review/SKILL.md`
   - `.cursor/skills/plan-check/SKILL.md`
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
7. Run only `git status --short --branch` in each repository root.
8. Report pre-existing dirty working trees without printing unnecessarily large
   diffs.
9. Confirm that no files changed during the health check.
10. Confirm invocation behavior:
    - The workspace rule is always-on.
    - Skills are dynamically discoverable.
    - `/plan-check` is the cheap plan gate (no critics).
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
