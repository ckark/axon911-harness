# Seeded Adjudication Cases

## ADJ-1: Preference-only performance claim

Seed: A critic rejects `useMemo` omission without render-frequency, cost, or
identity evidence.

Expected: Reject or downgrade to a measurement question.

## ADJ-2: Duplicate cross-domain finding

Seed: Design and accessibility critics both report the same unlabeled control,
with different downstream consequences.

Expected: Merge the defect while retaining accessibility and public-component
contract consequences.

## ADJ-3: Missing docs benchmark

Seed: The architecture critic reports valid findings but omits `Docs
Benchmark`.

Expected: Mark the report invalid and return it to the same critic before
adjudication.

## ADJ-4: Vault conflicts with runtime

Seed: A Vault architecture note says a migration is complete, but current
exports and consumers show both contracts remain active.

Expected: Use runtime evidence, record the note as drift/context, and avoid
treating the note as implemented fact.

## ADJ-5: Wrong-PR provenance

Seed: A critic asserts a file is introduced at PR N. Phase 2b
`git log --diff-filter=A` against the parent-to-head range shows the add at
PR N-1.

Expected: Refuted by the claim ledger in Phase 2b. The orchestrator reports
the target defect before any critic runs; the false provenance never reaches
adjudication as an open finding.

## ADJ-6: Phantom artifact

Seed: A gate instruction names a file that must be cherry-picked. Blob hashes
from `git rev-parse "<ref>:<path>"` are identical across every ref in the
manifest (trunk, mid-stack, tip, and the leaf being closed).

Expected: Refuted by the claim ledger. The instruction is reported as a
target defect (nothing to salvage / nothing to cherry-pick).

## ADJ-7: Unsourced arithmetic

Seed: A finding quotes line counts or file counts (for example "+105/−26")
with no `Verification command`.

Expected: Reject pending the command, even when the conclusion is
directionally right. Do not accept or repair the number by re-running the
diff yourself without recording a process failure.

## ADJ-8: Dirty-tree attribution

Seed: A finding cites content that exists only in the working-tree snapshot
as though it were committed at a pinned ref.

Expected: Reject, or retag as `State: uncommitted` with evidence from the
captured delta. Do not treat the working tree as a revision.

## ADJ-9: Re-litigate remediated claim

Seed: The claim ledger marks the tip Image registry collision
`remediated-by-plan` because Tasks 2/10 already add overrides and regenerate.
A critic re-opens it as `CHANGES REQUIRED` / `BLOCK` with no new
counter-evidence that those tasks are wrong.

Expected: Reject as a closed claim. At most an informational "verify during
Task N" note is allowed.

## ADJ-10: Tip residual vs plan intent

Seed: Tip `useAnnotationUserScope` still binds thread storage from
`AnnotationLayer` with story `DEMO_USER`. The plan's Task 4 is mid-stack v1
host-only chat (`persistKey` removal). The critic scores the tip residual as
`BLOCK`.

Expected: Require `Target layer: tip-residual`. Downgrade to informational
unless the finding falsifies a plan invariant the consolidation must preserve
through restack.

## ADJ-11: False acceptance-criterion model

Seed: Task 11 says "story links non-empty for both [`sources`/`srcSet`]
props." `DocgenPropRow` has no per-prop story fields; links live under
component-level `storybook.stories[]`.

Expected: Score as `Target layer: plan-text` defect in the matrix wording.
Do not treat it as missing product work beyond adding a CSF story and
`argTypes`.

## ADJ-12: Transcript-polling false stall

Seed: The orchestrator polls an in-progress critic transcript, finds no
verdict yet, and declares the critic stalled / a process failure.

Expected: Reject. Classify as `not-yet-returned` and wait for the returned
report. Only `returned-invalid` is a process failure.

## ADJ-13: Self-authored refuted claim

Seed: A plan ships a claim ledger row asserting PR N adds `path`, with a
command. Phase 2b re-runs the command and the add is at PR N-1. The row was
presented as already verified by the author.

Expected: Report as a plan-text / process defect before critics run. Treat a
self-authored refuted row as more serious than an unverified prose claim.
`/a911-harness:plan-check` must return `CHANGES REQUIRED`.

## ADJ-14: T0 critic escalates to T2

Seed: Evidence package resolves tier `T0` and launches only
`design-system-critic`. That critic emits
`Escalation: security-privacy-critic — client-only RBAC gate on shared export`.

Expected: Orchestrator launches `security-privacy-critic` (or records an
explicit refusal). An unactioned escalation becomes a `process` finding and
blocks a clean PASS. Final response lists the escalation under "Escalations
raised and actioned".

## ADJ-15: Call-site recommendation ignores shared layer

Seed: A critic recommends patching one Dispatch consumer for a token misuse
while sibling consumers and the `ui-core` primitive remain untouched. No
instance list or out-of-scope deferral is present.

Expected: Reject or return the finding for correction. Recommendation must
name the shared-layer fix and the complete instance list, or explicitly defer
siblings.
