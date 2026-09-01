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
