# Axon 911 Personal Cursor Harness

This private workspace overlays personal review orchestration on Prepared911
and makes related frontend repositories available for cross-repository
inspection without adding personal agent files to any repository.

## Workspace roots

- `prepared911`: application source, repository instructions, project skills,
  documentation, tests, and verification commands.
- `axon911-frontend`: related frontend source and package history. It is an
  eligible read/write implementation root.
- `vault-core-ux`: Core UX decisions, standards, proposals, and history. It is
  an eligible read/write knowledge root.
- `personal-harness`: private critics, review contracts, and orchestration.

`axon911-agents` is cloned nearby and is not a live workspace root. See
`docs/axon911-agents.md` for how to use it as a local overlay and what not to
merge into Eve.

Each repository's own instructions and behavior take precedence for work in
that repository. An implementation task must identify its target root or roots
before editing. For anything `@prepared/ui-*`, design-token, or
shared-frontend-architecture shaped, axon911-frontend is authoritative; see
`docs/workspace-rule.md` and `docs/cursor-onboarding.md`.

## Open

```shell
open -a Cursor "/Users/ckark/Documents/CursorWorkspaces/prepared911-harness/prepared911-personal.code-workspace"
```

On this machine, `~/.local/bin/cursor` is the standalone Cursor Agent CLI and
does not launch the macOS IDE. To invoke the IDE's bundled command directly,
use:

```shell
"/Applications/Cursor.app/Contents/Resources/app/bin/cursor" \
  "/Users/ckark/Documents/CursorWorkspaces/prepared911-harness/prepared911-personal.code-workspace"
```

After opening, start a fresh Cursor Agent conversation and run:

```text
/harness-health-check

Verify this Prepared911 personal workspace. Do not modify anything.
```

## Everyday use

There is no harness process to start. Open the `.code-workspace` file and use
Cursor Agent normally.

- The workspace rule is always-on. It resolves the four roots, preserves
  repository boundaries, and routes normal implementation work to the target
  repository's own instructions.
- Plans follow `docs/plan-contract.md`. Implementation follows
  `docs/implementation-contract.md`.
- Default posture is **mechanical on, panel off** — see `docs/workspace-rule.md`.
- Use `/plan-check` as the cheap plan gate before implementing.
- Use `/adversarial-review` only when the panel trigger list applies or you
  explicitly want formal review. One bespoke critic (`design-system-critic`)
  plus Cursor `bugbot` / `security-review`; no adjudicator.
- Blast-radius tier (`python3 harness/cli.py tier --json`) informs trigger
  decisions; it no longer selects panel size.
- Use `/implementation-check` to attest repository-owned commands before commit
  or push. Use `python3 harness/cli.py verify` for mechanical coverage.
- Read `docs/session-budget.md` — stop long sessions at ~60 turns.
- Use `python3 harness/cli.py cost <transcript.jsonl>` to estimate session cost.
- Use `/harness-health-check` after setup changes or a Cursor update, not before
  every task.
- Cursor wiring, CLI commands, and gate surprises are in
  `docs/cursor-onboarding.md`. Confirm the shim with
  `python3 .cursor/hooks/runtime_gate.py benchmark --json` (do not use
  `--help`).

## Runtime verification

Local Cursor project hooks in this harness provide cooperative assurance
against accidental early completion and stale evidence. They are not
tamper-proof, not atomic Git enforcement, and not a security boundary.

- Event ledger and mutation preflight live under `.cursor/hooks/` with
  registration in `.cursor/hooks.json`.
- Use `/implementation-check` to attest repository-owned commands and issue
  review receipts before an Agent-shell commit or push.
- The recovery command printed by a denied gate is `/implementation-check`.
- Automatic enforcement is harness-local unless a live four-root scope probe
  proves otherwise. Product roots still need explicit `/implementation-check`
  plus optional later PR Automations.
- Dormant Automation templates live under `automations/pr-verification/`. Do
  not create live Automations from them until the activation checklist is
  complete.
- Runtime state is gitignored under `.harness/runtime/`. Legacy
  `.cursor/runtime/` stays ignored so older checkouts stay clean.

Examples:

```text
Implement the caller-toolbar change in prepared911 and run the relevant tests.
```

This uses the baseline workspace, plan/implementation contracts, and
repository guidance without the full critic panel. Still dispatch a tiered
fresh-context review before merge.

```text
/plan-check
target=<plan file>
```

Verifies plan-contract completeness, the self-authored claim ledger, and the
stated blast-radius tier. No critics.

```text
/adversarial-review
mode=implementation
target=origin/trunk...HEAD
scope=caller toolbar and shared UI impact
```

This runs the formal specialist and adjudication workflow without applying
fixes.

## Formal review

```text
/adversarial-review
mode=plan
target=<plan file>
scope=<optional constraints>
```

Prefer `/plan-check` first. Use `mode=plan` for `T2` plans that need the
specialist panel.

or:

```text
/adversarial-review
mode=implementation
target=origin/trunk...HEAD
scope=<optional constraints>
```

Formal review is read-only. Applying adjudicated fixes is a separate task and
must satisfy `docs/implementation-contract.md`.

## TypeSafe Jev (bounded judgments)

The harness calls TypeSafe Jev over `POST https://api.typesafe.ai/v1/systemone`
using Python 3.9 stdlib HTTP. Configure `TYPESAFE_API_KEY` (or the macOS Keychain
item `typesafe-ai-api-key`). The key is never printed or persisted in ledgers.

```bash
python3 harness/cli.py jev smoke --json
python3 harness/cli.py jev route-task --request "add a remote module" --json
```

Subcommands: `route-task`, `list-skills`, `routing-status`, `assess-plan`,
`check-claim`, `assess-change`, `rank-context`, `route-review`, `check-findings`,
`assess-command`, and `eval`.

**Task routing is required**, not advisory: run `route-task` before loading a
skill body for any non-exempt action request. The roster spans all four roots
(`<root>#<skill>`); `list-skills` prints it. `/harness-health-check` fails when
`routing-status` reports `routing-absent`. See `docs/workspace-rule.md` for the
exemptions.

Deterministic proof (hashes, Git state, schemas, receipts, tests) stays
authoritative. Jev runs in **shadow mode** for semantic tier risk, visibility, and
unknown shell commands until labeled evals promote a question set; on API failure
or low confidence the harness falls back to the existing LLM or human path.

Observations append to `.harness/runtime/jev-observations.jsonl` only (not indexed
gate state). Disable with `HARNESS_JEV_RECORD=0`.

## Ponytail (minimum-code ladder)

Vendored from [ponytail](https://github.com/DietrichGebert/ponytail) as adapted
text in [docs/ponytail.md](docs/ponytail.md) and an optional complexity review
skill (`ponytail-review`). Upstream Cursor hooks and global mode switching are
**not** installed. Read the ladder before code authoring; repository `AGENTS.md`
and harness contracts override it.

## Maintenance

- Keep Prepared911-specific coding conventions in the Prepared911 repository.
- Keep only personal orchestration and reviewer prompts in this harness.
- Update `docs/review-contract.md` before changing report fields or verdicts.
- Update `docs/plan-contract.md` or `docs/implementation-contract.md` when
  plan or done definitions change.
- Keep `docs/axon911-agents.md` current if the Eve agents clone or overlay
  rules change. Do not mount that repo until wiring is explicitly requested.
- Keep contextual repository facts in
  `.cursor/skills/adversarial-review/references/`; do not create a registered
  skill for every topic.
- Use the seeded cases under `.cursor/skills/adversarial-review/evals/` when
  changing review behavior.
- Run `/harness-health-check` after Cursor upgrades or agent-schema changes.
- Keep `docs/cursor-onboarding.md` current when Cursor wiring, hook paths, or
  CLI commands change.
