# Harness Reuse Audit

Post cost-reduction pass. Prefer existing Cursor and team tooling over bespoke
harness critics.

## Deleted (product substitutes)

| Harness artifact | Replaced by |
|---|---|
| `security-privacy-critic` | Cursor `security-review` subagent |
| `performance-reliability-critic` | Cursor `bugbot` + `react-best-practices` skill |
| `quality-accessibility-critic` | Storybook MCP `run-story-tests` + `bugbot` |
| `frontend-architecture-critic` | Merged into `design-system-critic` |
| `review-adjudicator` | Human PR reviewer |
| `implementation-verifier` (LLM) | `python3 harness/cli.py verify` |
| Claude Code plugin tree | Removed; Cursor-only |
| `harness/scope_probe.py` | Documented answer in `docs/workspace-rule.md` |
| Transparent attest rewrite | Removed with Claude Code |

## Kept (no product substitute)

| Artifact | Why |
|---|---|
| Fingerprint-bound receipts | Stale verification detection |
| Plan conformance | Silent scope drift |
| Mirror edit warnings | CORE-754 authority |
| `design-system-critic` | Cross-root blast radius + authority |
| `evidence-verifier` | INCONCLUSIVE stop gate judgment |
| `harness/cli.py tier` | Computed blast radius for trigger list |

## Delegated (use at runtime, not reimplemented)

- Docs baseline: `prepared-docs` MCP (verify serves axon911-frontend post CORE-754)
- Blast radius checklist: team `pr-blast-radius` skill
- Mechanical checks: team `pre-summary-checks`
- PR body: `pr-context-generator`, `pull-request-standards`
- Branch/PR: Graphite / Cursor Review

## Dormant (not activated in this pass)

- `automations/pr-verification/` — still dormant; activate separately for post-push verification off the interactive budget
