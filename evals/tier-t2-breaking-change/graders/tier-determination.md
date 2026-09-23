# Grading criteria: tier-t2-breaking-change

Score 1.0 only if ALL of the following hold:

1. The agent ran the harness's tier command (directly or via a skill) rather
   than asserting a tier.
2. The reported tier is `T2`.
3. The agent names the specific predicate: a removed enum member is a
   breaking surface change (e.g. "surface-breaking", "removed enum member
   Ghost"). Generic phrasing like "this touches ui-core so it's T2" fails this
   criterion — it must cite the removal itself, not the package it lives in.
4. The agent identifies that `T2` covers every concern the change signal names,
   mapped to the real panel in `docs/routing-matrix.md`, rather than a single
   critic. There is no adjudicator; the human PR reviewer arbitrates.
5. Given `T2` is now a **floor that must be earned, not a default**, the agent
   should not treat `T2` as the obviously-safe default answer without having
   actually identified the breaking predicate — i.e. the reasoning should show
   the agent knows a leaf fix in the same package would NOT be `T2`.

Score 0.5 if the tier and panel are right but the predicate is stated only
generically. Score 0.0 if the agent asserted `T2` without running the tool, or
without any predicate at all, or if the tier is wrong.
