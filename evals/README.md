# a911-harness eval suite

Seeded with two kinds of cases, per `docs/routing-matrix.md`'s design change and
one live incident from this build:

- **Tier cases** — the regression suite for the fix to the routing matrix. The
  previous criteria listed "public `ui-*` export" as a `T2` trigger, and every
  one of the 14 `@prepared/ui-*` packages exposes exactly one public entry, so
  the predicate was true by construction for any change to any of them. These
  cases assert that a leaf fix scores `T0`, an additive export scores `T1`, and
  only a genuinely breaking change scores `T2` — with a named, cited predicate
  in every case.
- **`DOCS-DRIFT` cases** — built from real, verified drift in
  axon911-frontend's own documentation (see `[[ui-package-ownership-core-754]]`
  in memory): five files state the publish allowlist is empty when it is fully
  populated and has already shipped two releases. This is exactly the shape
  `docs/review-contract.md` asks critics to catch: report stale docs as
  `DOCS-DRIFT` rather than following them.
- **A regression case for a live incident** — `false-positive-quoted-mutation`
  reproduces the exact failure that blocked real development mid-build: a
  script whose test payload contains the phrase `git commit` inside a quoted
  string was denied as a chained mutation attempt before
  `harness/lib/shell_gate.py`'s quoted-span stripping fix landed. The unit
  tests in `harness/tests/test_shell_gate.py` cover the library function
  directly; this eval case covers the same failure at the level a user would
  actually hit it — an agent writing an ordinary test script.

## Running

```bash
claude plugin eval . --ablation with-without --report evals/results/report.html
```

## Known limitation: not yet executed

`claude plugin eval` returned `` `plugin eval` is currently in early access ``
on this installation (Claude Code 2.1.220), with no documented settings key,
CLI flag, or environment variable to enable it, and no public docs page for
the case schema exists yet. These cases are authored by hand against the
documented directory convention (`evals/**/prompt.md` + `graders/*.md`) and the
field names visible in `claude plugin eval --help` (`case.runs`,
`scaffold_script`, tags), but have **not** been mechanically run. Re-run the
command above once early access is available, and treat the first run's
results as the actual baseline — not the tier-scoring assertions written here,
which come from the Python unit suite (`harness/tests/test_tier_scoring.py`),
already verified.
