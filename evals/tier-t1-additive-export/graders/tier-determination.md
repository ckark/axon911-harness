# Grading criteria: tier-t1-additive-export

Score 1.0 only if ALL of the following hold:

1. The agent ran the harness's tier command (directly or via a skill) rather
   than asserting a tier.
2. The reported tier is `T1`.
3. The agent names the predicate as an additive surface change (e.g.
   "surface-additive", "new export, nothing removed") — not a generic
   restatement like "it's a design-system package."
4. The agent identifies that **two** critics are required at `T1`
   (`docs/routing-matrix.md`), not one and not the full panel.

Score 0.5 if the tier and predicate are correct but the critic count is wrong
or unstated. Score 0.0 if the tier is `T0` (undercounts a real surface change)
or `T2` (the old, since-removed default-to-maximum behavior) or if no tool was
run at all.
