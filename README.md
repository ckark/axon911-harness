# Prepared911 Personal Cursor Harness

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

Each repository's own instructions and behavior take precedence for work in
that repository. An implementation task must identify its target root or roots
before editing.

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
- Cursor discovers skills dynamically. It may select `adversarial-review` when
  a request clearly asks for a formal review, but ordinary coding does not run
  all critics.
- Custom critics are workers for the formal review workflow. They do not run
  independently on every prompt.
- Use `/plan-check` as the cheap plan gate (ref manifest + claim ledger, no
  critics) before implementing.
- Use `/adversarial-review` when you require the formal, read-only review
  gate. Explicit invocation is the reliable choice for an approval decision.
- Blast-radius tiers in `docs/routing-matrix.md` set panel depth:
  - `T0` — one critic, narrow leaf change (importer count required)
  - `T1` — two critics
  - `T2` — full panel for public contracts, auth/PII, realtime, or cross-root
- Ordinary changes still need a fresh-context pass at their tier. Authoring-
  context self-review is not enough.
- Use `/harness-health-check` after setup changes or a Cursor update, not before
  every task.

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

## Maintenance

- Keep Prepared911-specific coding conventions in the Prepared911 repository.
- Keep only personal orchestration and reviewer prompts in this harness.
- Update `docs/review-contract.md` before changing report fields or verdicts.
- Update `docs/plan-contract.md` or `docs/implementation-contract.md` when
  plan or done definitions change.
- Keep contextual repository facts in
  `.cursor/skills/adversarial-review/references/`; do not create a registered
  skill for every topic.
- Use the seeded cases under `.cursor/skills/adversarial-review/evals/` when
  changing review behavior.
- Run `/harness-health-check` after Cursor upgrades or agent-schema changes.
