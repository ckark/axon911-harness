# Grading criteria: tier-t0-leaf-fix

Score 1.0 only if ALL of the following hold in the transcript or final report:

1. The agent used the `a911-harness` harness to determine the tier — either by
   running `harness/cli.py tier` directly, or by invoking a skill
   (`harness-mode` or `plan-check`) that does so internally. A tier asserted
   from reasoning alone, without running the tool, fails this case even if the
   number happens to be right.
2. The reported tier is `T0`.
3. The agent's stated reason cites a **call-site count** or an equivalent
   concrete measurement (not just "this is a small change" or "it's a leaf
   component" without a number) — mirroring the plan contract's rule that a
   `T0` claim is incomplete without a printed call-site count.
4. The agent does NOT default to `T2` on the reasoning that this is a
   "public `ui-*` package" or "design-system component" — that reasoning is
   exactly the bug this harness fixed (every one of the 14 `@prepared/ui-*`
   packages exposes exactly one public entry, so that predicate was true for
   any change to any of them, which is why it was removed as a `T2` trigger).

Score 0.5 if the agent used the harness and got the right tier, but did not
cite the call-site count. Score 0.0 if the agent asserted a tier without
running the harness tool, or reported `T1`/`T2` for this change.
