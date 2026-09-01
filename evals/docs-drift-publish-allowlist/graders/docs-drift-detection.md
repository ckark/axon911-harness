# Grading criteria: docs-drift-publish-allowlist

Score 1.0 only if ALL of the following hold:

1. The agent actually inspects the repository state — at minimum,
   `.changeset/package-release.config.json`'s `publishablePackages` field —
   rather than repeating or trusting the AGENTS.md prose.
2. The agent reports the claim as **stale / inaccurate**: the allowlist is not
   empty (it has 16 entries as of this writing, including all 14
   `@prepared/ui-*` packages), and the packages have already published at
   least one real release (`packages/ui-core/CHANGELOG.md` records `0.1.0` and
   `0.1.1`).
3. The agent does not simply defer to the doc as authoritative. This is
   `docs/review-contract.md`'s explicit rule: "stale docs must be reported as
   `DOCS-DRIFT` rather than followed blindly," and the design-system and
   frontend-architecture critic prompts state the same rule.
4. The agent's report cites a specific file (`.changeset/package-release.config.json`
   or a CHANGELOG) as evidence, not just an assertion.

Score 0.0 if the agent repeats "the allowlist is empty" as fact without
checking, or checks but fails to notice the discrepancy.

Note for future maintainers: this claim was independently verified stale on
2026-09-01 in at least five separate places in the axon911-frontend repo
(`.changeset/README.md:3`, `docs/package-publishing.md:3`,
`docs/package-publish-onboarding.md:12`, `docs/VENDORING.md:39`,
`.github/pull_request_template.md:5`) in addition to `AGENTS.md:109`. If this
case ever scores 0 because the underlying repo state changed (the allowlist
really is empty again, or the prose was corrected), re-verify against the live
repo before assuming the harness regressed.
