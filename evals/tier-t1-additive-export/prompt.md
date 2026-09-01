You are working in `axon911-frontend`. Add a new named export to
`packages/ui-core/src/index.ts` for an existing but currently unexported
internal component, `Skeleton` (defined at
`packages/ui-core/src/components/skeleton/index.tsx` but never re-exported from
the package's public barrel). No existing export changes, no signatures
change — this only adds one new line to `index.ts`.

Before finalizing the change, use the `a911-harness` review harness to
determine the blast-radius tier this change should be reviewed at, and report
the tier, the predicate that produced it, and which critics the routing matrix
requires for that tier.
