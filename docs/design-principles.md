# Axon 911 Design Principle Map

A reference map for review and planning. The canonical text lives in Notion,
owned by the Core UX team. This file holds links, revision dates, and short
summaries so a review can cite a principle by id. It is not a copy of the
principles, and it does not add requirements of its own.

## Layers

| Layer | What it governs |
|---|---|
| Design principles (`DP-*`) | The experience and outcomes people should get |
| Design-system principles (`DSP-*`) | How shared components and patterns support those outcomes |
| Zero Vector | The working method: how results are built and judged |
| Harness contracts | What evidence supports completion |

Zero Vector contributes two principles, from
[erikaflowers/zerovector](https://github.com/erikaflowers/zerovector):

- **I. Work in the Medium.** The working preview is the design checkpoint.
- **IV. The Purpose of a System is What It Does.** Judge by observed behavior,
  not by checks completed.

The other Zero Vector principles are stances, not checks, and this harness does
not use them.

## Sources

| Source | URL | Last edited | Status |
|---|---|---|---|
| Design principles | https://app.notion.com/p/542605d9003c44ca96c8535a95b39282 | 2026-09-18 | `draft (advisory)` |
| Design-system principles | https://app.notion.com/p/3dd0b9d7d13981bb9f4ae0c09b34aa78 | 2026-09-18 | `draft (advisory)` |

Both pages are titled `[WIP]` and are unverified in Notion, with open comment
threads. A finding against a draft principle is advisory: at most `medium`, and
it cannot alone produce `CHANGES REQUIRED`. Re-check both pages before treating
any principle as an accepted requirement, and update the date and status here
when that changes.

## Design principles

| ID | Principle | Test | Applies when | Example |
|---|---|---|---|---|
| `DP-1` | Elevate human judgment: automate the work, preserve the judgment | When the system is wrong, what does the user see, and how much work does it take to correct? | A recommendation, autofill, or automated action | A suggested unit dispatch shows why it was suggested and takes one action to override |
| `DP-2` | Cultivate calm: the incident, not the interface, generates urgency | Do the most prominent actions match the most important ones? | Alerting, badges, motion, or stale data | An overdue status update looks different from a current one, and a low-severity notice does not use the critical-alert treatment |
| `DP-3` | Make the system legible: every effect has a visible cause | Can a supervisor reconstruct who acted, what changed, when, on what information, and what the system contributed? | State changes, recommendations, audit | An incident timeline records the operator's action separately from the system's suggestion |
| `DP-4` | Never lose the thread: context follows the incident, not the screen or the role | Follow one incident from call to closure and mark every place a user re-enters something the system already knows | Handoffs, multi-step flows, cross-role views | A call-taker's location note is already present when the dispatcher opens the same incident |
| `DP-5` | Consistency is safety: learn it once, trust it everywhere | Does the exception change the interaction's meaning, or only its policy, defaults, or content? | A new pattern, variant, or one-off interaction | A second "dismiss" gesture that behaves differently from the first is a defect; a PSAP-specific default label is configuration |

## Design-system principles

| ID | Principle | Test | Applies when | Example |
|---|---|---|---|---|
| `DSP-1` | Curate the best patterns in use: divergence is how the system learns | When did the system last change because a team needed something it lacked? | A consumer detaches an instance or invents a local variant | A remote that detaches `Button` to add a missing state is a signal to extend `Button`, not a violation to revert |
| `DSP-2` | Make the right choice the easiest one: defaults are already correct | Does a component work correctly without manual overrides? | Component APIs, prop defaults, tokens | A `Banner` defaults to the severity treatment; callers pass content, not color overrides |
| `DSP-3` | Ship building blocks, not instructions: recurring layout belongs to the system | Does this arrangement repeat? If so, can a team use it whole? If not, can they compose it without fighting the system? | New layout, templates, blocks | A page header repeated across three remotes ships as a block; a one-off incident layout stays composed from primitives |
| `DSP-4` | Everything for a reason: every part earns its place or leaves | Why does this exist, and what would break without it? Does something already in the system cover it? | A new component, token, or variant | A `Card` that duplicates `Panel` needs a reason that `Panel` cannot serve |
| `DSP-5` | Degrade gracefully: intent trumps fidelity | Under the worst supported conditions, is this still right? Does the fallback preserve meaning or only appearance? | Narrow viewports, missing data, failed loads | A map that fails to load still shows the address and the actions that depend on it |

## Where DP-5 and DSP-1 meet

`DP-5` says a thing learned once should behave the same everywhere. `DSP-1`
says a team's divergence is how the system learns. Use the `DP-5` test to tell
them apart: configure local differences of policy, defaults, or content; extend
the shared system when the interaction itself needs to change. A legitimate
exception names which of the two it is.
