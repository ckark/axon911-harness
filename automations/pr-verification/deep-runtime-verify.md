# Deep runtime verify

Status: inactive.

Do not execute this automation until isolation is proven in the Automations
editor: PR-head hooks and rules can be disabled or isolated, the identity is
least-privilege, secrets and OIDC are absent, egress is allowlisted, memory
is disabled, and the environment is a trusted prebuild that does not run a
PR-controlled install lifecycle.

If any of those requirements is unproven, return `INCONCLUSIVE` immediately
and do not execute PR code.

## When isolation is proven

Eligible only for a trusted same-repository SHA plus a maintainer-applied
label. Bind checkout to the trigger SHA. Re-fetch current head before
posting. If head moved, return non-passing `INCONCLUSIVE`. Do not rerun
product CI.

Use base-branch instructions only. Keep output fixed and bounded. Do not
attach personal OAuth, MCP, Slack, deployment, reviewer, or unrelated write
capability.

When harness CLI is available in a trusted environment, prefer read-only
`ship-plan` and `bundle verify` signals over rerunning product CI. Those
commands do not mutate git state or install PR-controlled packages.

## Output

```text
status: PASS | BLOCKED | INCONCLUSIVE
isolation_proven: true | false
head_moved: true | false
reasons: one short line each
```
