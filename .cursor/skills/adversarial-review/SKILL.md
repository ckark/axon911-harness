---
name: adversarial-review
description: Runs independent Prepared911 design-system, frontend architecture, performance/reliability, security/privacy, and quality/accessibility reviews against a plan or implementation, followed by evidence-based adjudication. Use for formal review gates.
---

# Prepared911 Adversarial Review

This skill performs a read-only formal review. It never applies fixes.

## Context loading

Use progressive disclosure. Do not preload every repository skill or docs page.

1. Read [worker-bootstrap.md](references/worker-bootstrap.md).
2. Resolve the target with
   [repository-router.md](references/repository-router.md).
3. Read [evidence-capture.md](references/evidence-capture.md) before pinning
   revisions or verifying claims.
4. Read [cross-repo-source-priority.md](references/cross-repo-source-priority.md)
   when the target spans repositories, moves a contract, or exposes conflicting
   evidence.
5. Give each worker only the evidence package, contract, and its domain map:
   - Design system:
     [design-system-context-map.md](references/design-system-context-map.md)
   - Frontend architecture:
     [frontend-architecture-context-map.md](references/frontend-architecture-context-map.md)
   - Performance/reliability:
     [performance-context-map.md](references/performance-context-map.md)
   - Security/privacy:
     [security-context-map.md](references/security-context-map.md)
   - Quality/accessibility:
     [quality-accessibility-context-map.md](references/quality-accessibility-context-map.md)
6. Design-system and frontend-architecture workers must also read
   [docs-benchmark.md](references/docs-benchmark.md).

## Inputs

- `mode`: `plan` or `implementation`
- `target`: Plan file, directory, pull-request diff, commit, or Git range
- `scope`: Optional constraints
- `tier`: Optional `T0`, `T1`, or `T2`. When omitted, resolve in Phase 0.

## Phase 0: Resolve the blast-radius tier

Before selecting the panel:

1. Read the tier definitions in `docs/routing-matrix.md`.
2. If the target carries a plan-contract tier, treat it as the stated floor.
3. Run the blast-radius recipe in
   [evidence-capture.md](references/evidence-capture.md) for changed exports
   when caller evidence is available.
4. State the resolved tier (`T0`, `T1`, or `T2`) and the importer counts that
   justify it in the evidence package.
5. Select the panel from **tier plus change signal**:
   - `T0` — one critic, diff-scoped
   - `T1` — two critics
   - `T2` — full panel required by the routing matrix

Tier is a floor. Record why any critic was omitted. For cheap plan-only
gates without specialists, prefer `/plan-check` instead of this skill.

## Phase 1: Resolve the workspace

Follow the repository router. Locate the personal harness using
`docs/review-contract.md` and this skill. Read the full review contract and
routing matrix. When `mode=plan`, also read `docs/plan-contract.md`.

Read applicable layered instructions. Load project skills only when the target
or a context-map row triggers them; record each loaded skill in the evidence
package.

## Phase 2: Establish immutable evidence

For `mode=plan`:

1. Read the complete plan.
2. Read files and documentation directly referenced by it.
3. Inspect existing code **at the ref each claim concerns** (use
   `git show <ref>:<path>`, not the working tree by default).
4. Identify affected packages, apps, APIs, and consumers.

For `mode=implementation`:

1. Identify the approved plan when one exists.
2. Inspect the target diff and every changed file.
3. Inspect relevant callers, tests, exports, package dependencies, and public
   APIs.
4. Record verification output supplied by the user or available read-only.
5. Do not assume a successful build proves architectural correctness.

For a Git range, inspect at minimum:

```shell
git diff --stat <target>
git diff --name-status <target>
git diff <target>
```

The evidence package must state:

- Mode, target, scope, base SHA, and head SHA when applicable
- Applicable `AGENTS.md` and skills
- Affected packages/apps and consumers
- Evidence collected and unavailable
- Deterministic verification results

Do not mutate generated files, snapshots, caches, or the working tree while
collecting evidence.

## Phase 2a: Pin the revision set

Before further evidence collection, follow
[evidence-capture.md](references/evidence-capture.md):

1. When the target already carries a plan-contract **ref manifest**, verify
   each row against the repository instead of rebuilding it from scratch.
   Rebuild only missing or incorrect rows.
2. Otherwise build the **ref manifest** for every PR, branch, or label the
   target names (branch, head SHA, parent head SHA, merge-base with trunk).
3. Capture the **working-tree snapshot** (`status`, unstaged and staged diffs,
   stash list, worktree list).
4. State one scope decision in the evidence package:
   - `committed-only`, or
   - `committed-plus-delta`

If the tree is dirty and the decision is `committed-only`, still attach the
captured uncommitted delta so critics can see what they are excluding.

Critics must cite pinned refs from this manifest. The working tree is not a
revision unless the finding is explicitly about uncommitted state.

## Phase 2b: Mechanical claim verification

When the target carries a plan-contract **self-authored claim ledger**, verify
that ledger rather than constructing a parallel one. Re-run each stated
command, compare raw results, and add any falsifiable claims present in the
plan prose but missing from the ledger.

Otherwise extract every falsifiable claim the target makes about repository
state — which PR adds a file, which files a change touches, what a generated
artifact contains, how large a diff is — and resolve each with a recipe from
[evidence-capture.md](references/evidence-capture.md).

Emit a **claim ledger** into the evidence package. One row per claim:

- Claim as written
- Exact command run
- Raw result
- Verdict: `confirmed`, `refuted`, or `unverifiable`

**Refuted claims are defects in the target.** Report them as findings by the
orchestrator **before any critic runs**. Do not hand them to specialists as
open questions. A **self-authored** row that verifies as `refuted` is a more
serious plan-contract defect: the author asserted a false repository fact
with a command. Mark it `Target layer: plan-text` and `process` when the
false claim was presented as already verified.

For each `confirmed` claim, also classify **plan disposition**:

- `open` — the plan does not address it
- `remediated-by-plan` — the plan already contains the fix
- `out-of-scope` — the plan explicitly defers it

Critics may not emit `CHANGES REQUIRED` or `BLOCK` against
`remediated-by-plan` or `out-of-scope` rows without **new counter-evidence**
that the plan's fix is wrong or incomplete. Re-raises without that evidence
are informational "verify during Task N" notes only.

Critics begin from the verified ledger rather than re-deriving provenance in
parallel.

## Phase 3: Independent specialist reviews

Send the same evidence package and worker bootstrap independently to the
critics selected in Phase 0. The full specialist set is:

1. `design-system-critic`
2. `frontend-architecture-critic`
3. `performance-reliability-critic`
4. `security-privacy-critic`
5. `quality-accessibility-critic`

Include only that specialist's context map and other references explicitly
triggered by the target. Tell each specialist the resolved tier: a narrow
tier scopes depth, not rigor. Pass the review-contract **Escalation**
mechanism: a specialist that spots material risk outside its domain must emit
`Escalation: <critic> — <reason>` rather than staying silent or inventing
out-of-domain findings.

Use the routing matrix to omit a clearly irrelevant critic only when the
final response records the reason. Do not show specialists one another's
reports during this phase.

The design-system and frontend-architecture critics must benchmark against the
Prepared911 docs app. Their reports are invalid without `Docs Benchmark`.

## Phase 4: Validate reports (blocking gate)

Classify each required critic as exactly one of:

- `returned-valid` — report received and contract-complete
- `returned-invalid` — report received but missing a required section
- `not-yet-returned` — still running

Only `returned-invalid` is a **process failure**. `not-yet-returned` means
**wait**. Never infer failure by reading a critic's in-flight transcript;
completion is signalled by the returned report alone. If the user forces
adjudication before all critics return, the final response must say
`Partial panel: <critic> not-yet-returned` — distinct from a process failure.

For each `returned-valid` or `returned-invalid` report, verify:

- Required report sections exist
- Finding IDs use the correct domain prefix
- Evidence and plausible failure mode are present
- Classifications distinguish defects from measurement needs
- Required docs benchmark sections exist (DS/FA)
- Citations use `<ref>:<path>:<line>` (or an explicit uncommitted tag)
- Provenance and numeric claims include a `Verification command`
- Findings include `Target layer` (`plan-text` / `mid-stack-head` /
  `tip-residual` / `process`)
- Recommendations name the shared layer and instance list when applicable
- No specialist modified files

Collect every `Escalation` field. For each one, either:

1. Launch the named critic with the same evidence package and fold its report
   into this gate, or
2. Record an explicit refusal with reason.

An unactioned escalation is a `process` finding and blocks a clean PASS.

**Adjudication does not start** until every required critic is
`returned-valid` (or the user explicitly accepts a partial panel) and every
escalation is actioned or refused. A `returned-invalid` report is returned to
the same specialist for correction. Record each rejection and re-submission
in the final response so a silently skipped benchmark cannot recur.

## Phase 5: Adjudication

Send the reports, target, and evidence package to `review-adjudicator`.
Adjudication validates evidence; it does not count votes.

## Final response

Return:

1. Final verdict
2. Blocking findings
3. Required changes
4. Non-blocking concerns
5. Rejected or disputed findings
6. Docs impact and drift
7. Verification still required
8. Recommended next action
9. Process failures (Phase 4 `returned-invalid` rejections, absorbed
   verification, missing ledger rows), when any occurred
10. Partial panel note, when any required critic was `not-yet-returned`
11. Escalations raised and actioned (critic named, reason, launched or
    refused)
12. Resolved blast-radius tier and the importer counts that justified it

Do not implement corrections. Corrections require a separate user request.
Follow-up fixes must satisfy `docs/implementation-contract.md`.

## Harness maintenance

When changing this skill or its agents, use the representative cases in:

- [seeded-design-system-cases.md](evals/seeded-design-system-cases.md)
- [seeded-architecture-cases.md](evals/seeded-architecture-cases.md)
- [adjudication-cases.md](evals/adjudication-cases.md)

Do not load these evals during an ordinary review.
