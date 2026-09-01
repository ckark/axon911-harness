You are working in `axon911-frontend`. A component inside
`packages/ui-core/src/components/tooltip/` has a minor rendering bug: the
tooltip's `arrow` element does not respect the `size` prop when it is set to
`"small"`. The fix is a one-line change inside `tooltip/index.tsx`'s render
body — no exported name changes, no new props, no prop type changes.

Before writing any code, use the `a911-harness` review harness to determine
the blast-radius tier this change should be reviewed at, and report the tier
and why. Do not implement the fix yet — this case is only about the tier
determination step.
