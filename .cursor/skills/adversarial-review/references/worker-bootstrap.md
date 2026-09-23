# Worker Bootstrap

Load this file at the start of every specialist run.

## Boundaries

- The review is read-only. Do not edit, format, generate, commit, or update
  snapshots.
- Use the evidence package as a starting index, not as proof.
- Verify material claims in source, tests, public exports, generated API data,
  rendered behavior, or command output.
- Read the complete `docs/review-contract.md` before reporting.
- Apply repository instructions from the target root. Do not transfer
  Prepared911-specific rules to another repository without evidence.
- Do not manufacture findings. A clean `PASS` is valid.

## Progressive loading

1. Read the assigned domain context map.
2. Load only the instructions, skills, docs, and source paths triggered by the
   target.
3. Expand to callers and consumers when the changed contract crosses a package
   or repository boundary.
4. Record unavailable evidence instead of guessing.
5. Stop loading context once the material behavior and failure paths are
   supported well enough to issue or reject a finding.

## Evidence discipline

Every accepted finding needs:

- An exact location as `<ref>:<path>:<line>`, never a bare path
- Directly observed evidence at that ref via `git show <ref>:<path>`
- A plausible execution or user-impact path
- The smallest correction
- A deterministic verification method, or an explicit measurement request
- `State: committed`, `uncommitted`, or `both`
- `Target layer: plan-text` | `mid-stack-head` | `tip-residual` | `process`
- A `Verification command` whenever the finding asserts provenance or a number

Reading the working tree is valid only for a finding explicitly about
uncommitted state, and such a finding must be tagged `State: uncommitted` or
`State: both`. The working tree is not a revision.

Do not restate a claim from the target as evidence. If the claim ledger marks
something `unverifiable`, say so rather than assuming it true. Prefer the
recipes in [evidence-capture.md](evidence-capture.md).

If the claim ledger marks a row `remediated-by-plan` or `out-of-scope`, do not
raise it as `CHANGES REQUIRED` or `BLOCK` without new counter-evidence that the
plan's fix is wrong. Tip residual the plan scopes out is at most informational
unless it falsifies a plan invariant.

Preferences, generic best practices, and undocumented assumptions are not
defects.
