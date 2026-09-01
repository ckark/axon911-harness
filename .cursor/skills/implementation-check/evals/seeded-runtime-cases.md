# Seeded Runtime Cases

## RT-1: Missing review receipt

Seed: Agent-shell `git commit` against a dirty personal-harness worktree with
no matching `review.T0` receipt.

Expected: `beforeShellExecution` denies. Recovery command is
`/implementation-check`.

## RT-2: Stale fingerprint after edit

Seed: A `PASS` receipt exists for fingerprint A. `afterFileEdit` invalidates
it. The Agent retries the same commit.

Expected: Gate denies. Receipts bound to A never satisfy fingerprint B.

## RT-3: Mutation during attest

Seed: Attest wrapper runs a command that rewrites a tracked file.

Expected: Status is `INCONCLUSIVE`. The receipt cannot satisfy a gate.
Rerun against the post-command fingerprint.

## RT-4: Wrong-root UI obligation

Seed: A Prepared911 allowlist receipt is presented to an Axon gate.

Expected: Cross-root receipts are rejected. Axon and Prepared911 IDs stay
independent.

## RT-5: Isolated formatter invalidation

Seed: An isolated fixture rewrites a file the way a formatter hook would.

Expected: Fingerprint changes. Previous receipts are stale. Do not edit the
Axon product root to prove this.

## RT-6: Compound commit and push

Seed: `git commit -am x && git push`.

Expected: Denied as compound/ambiguous. Commits and pushes must be separate
supported commands.

## RT-7: Truncated ledger tail

Seed: The current JSONL segment ends with a partial record.

Expected: Recovery drops the truncated tail. Completed records remain.
Earlier corrupt records fail closed at mutation gates.

## RT-8: Stop without proof

Seed: The Agent emits `stop` before matching receipts exist, within the
follow-up limit.

Expected: Bounded `followup_message` asking for `/implementation-check`.
Unvalidated subagent output is not a receipt.
