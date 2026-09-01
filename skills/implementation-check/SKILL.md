---
name: implementation-check
description: Attest root-owned verification, gather fingerprint-bound evidence, validate critic reports, and issue review receipts. Use before Agent-shell commits or pushes, after a stop follow-up, or when claiming implementation done.
disable-model-invocation: true
argument-hint: [root=<root id>] [tier=T0|T1|T2] [plan=<plan file>]
allowed-tools: Read Grep Glob Bash(python3 ${CLAUDE_PLUGIN_ROOT}/harness/*) Bash(git *) Bash(pnpm *)
---

# Implementation Check

Local receipts are cooperative assurance. They are not tamper-proof, not
atomic Git enforcement, and not a security boundary against a hostile local
process.

This skill is the only review-receipt issuer. The attesting wrapper is the
only verification-receipt issuer. Event hooks only record observations.

## Context loading

1. Resolve the harness with `docs/review-contract.md`.
2. Read `docs/runtime-contract.md` completely.
3. Read `docs/implementation-contract.md` for per-root verification commands.
4. Read `docs/routing-matrix.md` only for the blast-radius tier.
5. Resolve roots with
   [repository-router.md](../adversarial-review/references/repository-router.md).

## Inputs

- `root`: One of `personal-harness`, `prepared911`, `axon911-frontend`,
  `vault-core-ux`
- `tier`: `T0`, `T1`, or `T2`
- `plan`: Path to the active plan file, if any

## Procedure

1. Identify changed paths in each affected root. Do not transfer one root's
   commands to another.
2. Hash the plan file and register it:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py register-plan \
     --root <root> --plan-hash <sha256> --tier <tier>
   ```

3. Select root-owned obligations from `docs/runtime-contract.md`. Prepared911
   and Axon UI package edits trigger independent allowlist, docs-registry,
   docs-page, and rendered-evidence IDs. Vault and personal-harness disable
   product UI obligations.
4. Run each repository-owned check through the exclusive attesting wrapper.
   Never treat a mutating command as `PASS`.

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py attest \
     --root <root> --obligation-id <id> --plan-hash <sha256> -- \
     <argv>
   ```

5. Gather fingerprint-bound rendered evidence for user-visible surfaces.
   New surfaces need after-state evidence. Changed existing surfaces need
   before-and-after evidence. Missing, stale, incomplete, or cross-root
   evidence blocks.
6. Re-check plan drift after the first attested command and at phase
   boundaries. If the plan hash moved, register the new hash and rerun.
7. Dispatch a fresh-context review at the required tier. T0 needs one
   applicable critic. T1 needs two independent applicable critics. T2 needs
   the signal-selected panel plus `review-adjudicator`. The mechanical
   verifier supplements these receipts; it never replaces them.
8. Validate each critic report against `docs/review-contract.md` before
   issuing a review receipt. Reject unvalidated `subagentStop` summaries.

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 "${CLAUDE_PLUGIN_ROOT}"/harness/cli.py issue-review-receipt \
     --root <root> --tier <tier> --plan-hash <sha256> --status PASS \
     --critic <id> [--critic <id> ...]
   ```

9. For a supported push, attest `push.oid` against the resolved source OID.
   For `gt submit`, attest `stack-oid-set`. Commits and pushes are separate
   commands.

## Recovery

If a mutation preflight or stop gate denies, rerun this skill against the
current fingerprint. The recovery command is `/a911-harness:implementation-check`.
