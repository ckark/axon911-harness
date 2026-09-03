---
name: plan-check
description: Cheap plan gate that verifies a plan against the personal plan contract — ref manifest and claim ledger only, no critics or adjudicator. Use before implementing or before /adversarial-review mode=plan for T2 plans.
---

# Axon 911 Plan Check

This skill is read-only. It never applies fixes and never launches critics.

Use for ordinary plan quality gates. Before `/adversarial-review`, confirm
scope is frozen; unfrozen plans must not be paneled.

Do not invoke `/adversarial-review mode=plan` until plan-check passes and the
user confirms scope will not change.

## Context loading

Use progressive disclosure. Do not preload every repository skill or docs page.

1. Resolve the personal harness using `docs/review-contract.md` and
   `.cursor/skills/adversarial-review/SKILL.md`.
2. Read `docs/plan-contract.md` completely.
3. Resolve the target with
   [repository-router.md](../adversarial-review/references/repository-router.md).
4. Read
   [evidence-capture.md](../adversarial-review/references/evidence-capture.md)
   before pinning revisions or verifying claims.
5. Read `docs/routing-matrix.md` only for the tier definitions needed to score
   the plan's stated blast radius.

Do not copy recipes from those references into this skill. Cite and follow them.

## Inputs

- `target`: Plan file or pasted plan text
- `scope`: Optional constraints

## Phase 1: Contract completeness

Check that the plan contains every required section from `docs/plan-contract.md`:

- Target roots
- Ref manifest
- Self-authored claim ledger
- Blast radius and tier
- Affected consumers
- Verification plan
- Generated-artifact and docs obligations
- Deferred and out-of-scope

Missing sections are plan-contract defects. Record each one.

## Phase 2: Pin the revision set

Follow evidence-capture Phase 2a rules:

1. Build or verify the **ref manifest** for every PR, branch, or label the plan
   names.
2. Capture the **working-tree snapshot**.
3. State one scope decision: `committed-only` or `committed-plus-delta`.

## Phase 3: Verify the self-authored claim ledger

Do **not** rebuild the ledger from scratch when the plan already carries one.

For each row:

1. Re-run the stated command against the pinned ref.
2. Compare the raw result to the plan's recorded result.
3. Emit a verified verdict: `confirmed`, `refuted`, or `unverifiable`.

Additional rules:

- A plan that ships a `refuted` row fails plan-check. Report it as a
  plan-contract defect before any other work.
- Claims present in the plan prose but absent from the ledger are defects;
  extract them and verify them.
- Claims missing a command are `unverifiable` until the author supplies one.

Use the claim recipes in `evidence-capture.md`. Prefer verifying the author's
commands over inventing new ones.

## Phase 4: Score blast radius and tier

Tier is **computed**, not argued. Run the following from the harness checkout
root, since the script path is relative:

```bash
python3 harness/cli.py tier \
  --root <root> --base-ref <merge-base> --stated <plan tier> --json
```

The command reports the tier, the single predicate that produced it, and the
evidence for that predicate. Exit status is non-zero when the plan's stated tier
disagrees with the computed one in **either** direction.

Report all of:

1. Computed tier and its named predicate.
2. The plan's stated tier and the reconciliation verdict: `match`,
   `understated`, `overstated`, or `unstated`.
3. The surface delta (`none` / `additive` / `breaking`) and the call-site counts.

Both directions are plan-contract defects:

- **Understated** — the plan claims a narrower tier than the evidence supports.
  The review runs at the computed tier regardless.
- **Overstated** — the plan claims a broader tier than the evidence supports.
  This is not a harmless safety margin: it burns a full panel on a leaf change,
  and a tier that is always `T2` carries no information, which is how the
  hierarchy stopped meaning anything in the first place.

A `T0` claim is incomplete without the printed call-site count. A `T2` claim is
incomplete without a named predicate — one of `surface-breaking`,
`risk:<label>`, `cross-root`, `unmeasurable`, or `many-symbols`. If no predicate
can be cited, the tier drops to what the evidence supports.

`unmeasurable` is a verdict about the tree, not the change: the root is a
shallow clone, has unresolved conflicts, or has an interrupted rebase, merge,
cherry-pick, or bisect. Remediate it (`git fetch --unshallow`, resolve the
conflict, finish the rebase) rather than accepting a defensive `T2`.

## Final response

Return:

1. Plan-contract verdict: `PASS`, `PASS WITH CONCERNS`, or `CHANGES REQUIRED`
2. Missing required sections
3. Claim-ledger verification table (claim, command, result, verdict)
4. Refuted or unverifiable claims
5. Stated tier versus measured blast radius
6. Recommended next action:
   - Fix the plan and re-run `/plan-check`, or
   - Proceed to implementation under `docs/implementation-contract.md`, or
   - Escalate to `/adversarial-review mode=plan` when the measured tier is `T2`

Do not implement corrections. Do not launch critics.
