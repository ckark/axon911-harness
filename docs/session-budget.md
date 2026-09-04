# Session Budget

Long single-session work is the dominant token cost. Context grows with every
turn and is re-sent on each subsequent turn, so cost is roughly quadratic in
session length.

## Hard stop

End the session and start fresh when **either** threshold is reached:

- **60 assistant turns** in the current session
- **~80k tokens** of accumulated context (roughly 320 KB of transcript)

`python3 harness/cli.py budget-check <transcript>` and `capture-ready` enforce these
limits mechanically before screenshot capture, visual acceptance, or ship phases.
When a gate blocks, write a handoff and open a new chat for the next phase.

## One phase per session

| Phase | Goal |
|---|---|
| Explore / plan | Resolve ownership, score tier, freeze scope |
| Implement | Make the change; run mechanical checks |
| Review | `/adversarial-review` only when the panel trigger list applies |
| Ship | Commit, push, open PR |

Do not mix phases. A plan that changes direction mid-session invalidates any
review already run against the old scope.

## Handoff artifact

Before ending a session, write:

`.harness/runtime/handoff/<plan-hash>.md`

Include:

- Current phase and next action
- Decisions made (root, tier, scope)
- Open findings by ID
- Commands already run and their exit status
- Paths touched

A fresh session should read only the handoff plus the files it needs to edit,
not the prior transcript.

## Orchestrator rule

The orchestrator delegates exploration to subagents and does not re-read what a
subagent already reported. If an explore agent returned a file list or summary,
trust it; do not run the same searches again in the main thread.
