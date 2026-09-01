---
name: harness-health-check
description: Verifies that the Axon 911 personal multi-root Cursor workspace, repository instructions, project skills, docs benchmark, personal critics, and formal review skill are discoverable. Always read-only.
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash(python3 ${CLAUDE_PLUGIN_ROOT}/harness/*) Bash(git *) Bash(claude plugin *)
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
   - `${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/SKILL.md`
   - `${CLAUDE_PLUGIN_ROOT}/skills/plan-check/SKILL.md`
   - All files linked from the adversarial-review skill under `references/`
   - `${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/references/evidence-capture.md`
   - Seeded maintenance cases under
     `${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/evals/`
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
    `${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/evals/adjudication-cases.md`
    includes `ADJ-9` through `ADJ-15`.
4e. Confirm `docs/routing-matrix.md` defines blast-radius tiers `T0`, `T1`,
   and `T2`.
4f. Confirm the workspace rule binds `docs/plan-contract.md` and
   `docs/implementation-contract.md`.
4g. Confirm runtime verification assets:
   - `docs/runtime-contract.md` (cooperative assurance, not tamper-proof)
   - `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json`
   - `"${CLAUDE_PLUGIN_ROOT}"/harness/cli.py`
   - `"${CLAUDE_PLUGIN_ROOT}"/harness/scope_probe.py`
   - `${CLAUDE_PLUGIN_ROOT}/skills/implementation-check/SKILL.md`
   - `.cursor/agents/implementation-verifier.md`
   - `automations/pr-verification/config.json` with `status: dormant`
   - `.gitignore` ignores `.harness/runtime/`
4h. If `.harness/runtime/scope-probe.json` exists, verify it with
    `python3 "${CLAUDE_PLUGIN_ROOT}"/harness/scope_probe.py verify-report` and report the
    measured `enforcement_scope`. Missing sibling-root fires are a documented
    limitation, not a pass.
4i. Confirm Cursor exposes `implementation-check` and
    `implementation-verifier` in addition to the review panel.
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
    - `/a911-harness:plan-check` is the cheap plan gate (no critics).
    - `/a911-harness:implementation-check` attests verification and issues review receipts.
    - `/a911-harness:adversarial-review` explicitly requests the formal critic panel.
    - Critics do not run on every ordinary coding request.
    - Ordinary work still requires a fresh-context pass at the resolved tier.

## Claude Code checks

11. Plugin resolution and inventory:

    ```bash
    claude plugin validate "${CLAUDE_PLUGIN_ROOT}"
    claude plugin details a911-harness@a911-harness
    ```

    Confirm 8 agents and 6 skills are listed, and report the projected token
    cost. The agents are the 7 critics plus `evidence-verifier`; the skills are
    `harness-mode`, `plan-check`, `adversarial-review`, `implementation-check`,
    `capture-evidence`, `harness-health-check`.

12. Every event in `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json` is bound:
    `SessionStart`, `PreToolUse` (Bash), `PostToolUse`
    (Edit|Write|NotebookEdit|Bash), `SubagentStart`, `SubagentStop`,
    `PreCompact`, `TaskCreated`, `TaskCompleted`, `Stop`.

13. The shared runtime layer passes on both hosts:

    ```bash
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
      -s "${CLAUDE_PLUGIN_ROOT}/harness/tests" -p 'test_*.py'
    ```

    Both `test_cursor_event_contract.py` and `test_claude_event_contract.py`
    must pass: one harness, two hosts.

14. Ledger hygiene: `.harness/runtime/` exists with `0700` directories and
    `0600` files, and is gitignored.

15. **Shallow-clone check, per root.** For each of `axon911-frontend`,
    `prepared911`, `vault-core-ux`:

    ```bash
    git -C <root> rev-parse --is-shallow-repository
    ```

    A `true` is a **FAIL**, not a warning: ref manifests, call-site counts, and
    tier scoring all have nothing to measure against. Remediation is
    `git -C <root> fetch --unshallow`.

16. Tier scoring is live and discriminating — not stuck at `T2`:

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py tier --root axon911-frontend --json
    ```

    Report the tier and its predicate. A `T2` with predicate `unmeasurable`
    means check 15 failed.

17. axon911-frontend benchmark paths exist:
    - `apps/docs/mdx/design`
    - `apps/docs/mdx/engineering`
    - `apps/docs/generated/component-api-registry.json`
    - `packages/feature-staff-panel/src/components/annotation/utils/ui-components.generated.ts`
    - `apps/storybook/.storybook/main.ts`

18. Sibling roots are reachable in this session. This needs `--add-dir` (use
    `bin/a911`); `permissions.additionalDirectories` grants file access but
    loads no skills or commands.

19. Report, without failing, the known upstream gaps the harness works around:
    oxlint ignores `packages/ui-*` and `apps/docs`; no CI job drift-checks
    `apps/docs/generated/component-api-registry.json`.

## Output

Return:

- Overall: `PASS`, `PASS WITH WARNINGS`, or `FAIL`
- Workspace roots
- Prepared911 instruction discovery
- Skills and subagent discovery
- Docs benchmark availability
- MCP configuration availability
- Working-tree status
- Claude Code plugin, agent, skill, and hook inventory
- Per-root shallow-clone status
- Computed tier and predicate for the current working tree
- Exact remediation for every warning or failure
