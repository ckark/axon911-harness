# Seeded Design-System Cases

Use these cases when changing the review skill or critic. They are evaluation
prompts, not repository claims.

## DS-1: Public Button contract

Seed: A plan adds a `ButtonType.Tertiary` Button variant in `ui-core`, changes
token use, and updates one Dispatch consumer but omits docs and other consumers.

Expected:

- Loads the design context map and docs benchmark
- Inspects exports, types, stories/tests, generated API, and consumers
- Distinguishes API/migration risk from aesthetic preference
- Includes a complete Docs Benchmark

## DS-2: Stale documentation

Seed: `usage.mdx` describes a prop removed from current source and types.

Expected:

- Uses API/tests/behavior over stale prose
- Emits `DOCS-DRIFT`, not a request to restore the removed API without evidence
- Identifies generated/prose/example impact separately

## DS-3: Similar cross-repo package

Seed: Axon and Prepared911 contain similarly named UI packages with different
exports.

Expected:

- Does not assume they are identical
- Compares provenance, versions, exports, ownership, and consumers
- Does not copy or recommend migration without a compatibility path

## DS-4: Token-compliant but state is hidden

Seed: A `Banner` uses only semantic tokens and passes the paint audit, but its
pending state renders in the same treatment as its settled state. The plan's
design intent cites `DP-2` and `DP-3`: an operator must be able to tell that an
update is still pending and which incident it belongs to.

Expected:

- Does not treat token compliance as sufficient
- Reports an `INTENT-###` finding naming `DP-2` or `DP-3`, the observed
  behavior, the user consequence, and the smallest correction
- Keeps the finding at `medium` or below, since the principles are draft

## DS-5: Keyboard regression without a visual change

Seed: A refactor of a dialog changes no pixels. The before and after screenshots
hash-match. Tab order now skips the primary action, so keyboard users cannot
reach it. The plan declares the visual row `expected_unchanged`.

Expected:

- Does not accept the matching screenshots as evidence of unchanged behavior
- Requires interaction evidence (Storybook `play`, Playwright, or a recorded
  walkthrough) for the acceptance scenario
- Reports the skipped action as a defect distinct from visual parity

## DS-6: Legitimate exception to a shared pattern

Seed: One PSAP needs its incident list to default to a different sort order.
The team proposes a local prop override rather than a new list component. The
interaction, keyboard behavior, and visual treatment stay identical to the
shared list.

Expected:

- Does not report the divergence as a defect
- Applies the `DP-5` test: this changes policy and defaults, not the
  interaction's meaning, so it is configuration
- Notes `DSP-1`: record the divergence so the system can learn from it, rather
  than forking the component

## DS-7: Intent met, no findings

Seed: The implementation matches the plan's observable acceptance exactly. The
pending state is visually distinct, associated with its incident, and reachable
by keyboard. Stories, tests, and docs are updated.

Expected:

- Returns `PASS`
- Invents no findings to justify the review
- States explicitly that no material issue was found

## Pilot scorecard

Fill this in after piloting the design-intent section on one real UI change.
These four numbers say more about the increment than the count of checks run.

| Measure | Count | Notes |
|---|---|---|
| Missed problems | | Real defects the intent check did not catch |
| False positives | | Findings that named no principle, behavior, or consequence |
| Rework loops | | Times the sentinel failed its outcome and the sweep restarted |
| Time to a usable preview | | From plan acceptance to a sentinel an operator could try |
