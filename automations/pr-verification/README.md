# PR verification automation pack

Dormant source templates for later Cursor Automation activation. These files
are not live Automations. Do not create or refresh Automations from this pack
until a human completes `activation-checklist.md` in the Agents Window.

Configuration lives in `config.json`. Prompts live beside it. Keep that
separation so later editor fields can change without rewriting the prompts.

## Templates

- `static-pr-inspect.md` — schema-constrained PR inspection. Never execute
  PR-head code.
- `deep-runtime-verify.md` — rendered runtime verification. Inactive until
  PR-head hook isolation, identity, secrets, and egress are proven. Returns
  `INCONCLUSIVE` rather than executing PR code when those requirements fail.

## Trust boundary

Deep verification is eligible only for a trusted same-repository SHA and a
maintainer-applied label. Use a dedicated least-privilege identity. Do not
attach personal OAuth, secrets, OIDC, MCP, Slack, deployment, reviewer, or
unrelated write capability. Allowlist egress only. Use a trusted prebuilt
environment. Do not run a PR-controlled install lifecycle. Keep memory
disabled. Follow base-branch instructions only. Keep output fixed and
bounded.

Checkout and result publication bind to the trigger SHA. Re-fetch current
head before posting. If head moved, return non-passing `INCONCLUSIVE`. Do
not rerun product CI.
