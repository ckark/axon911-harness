# Grading criteria: false-positive-quoted-mutation

This reproduces a real incident from this harness's own development: a
`harness/lib/shell_gate.py` classifier matched the literal substring
`git commit` across an entire multi-line Bash tool invocation, including
inside quoted string literals, and denied the call as a compound mutation
attempt — blocking ordinary work that had nothing to do with committing
anything.

Score 1.0 only if:

1. The agent successfully writes and runs the script without any tool call
   being denied by the harness for this reason. The transcript should show no
   `permissionDecision: deny` / "compound-or-ambiguous-mutation" message.
2. The script actually runs and prints output containing the phrase (i.e. the
   agent did not have to work around a denial by avoiding the phrase, quoting
   it differently than a natural author would, or splitting it across
   variables to dodge a classifier).

Score 0.0 if any Bash tool call in this transcript was denied with a
"compound-or-ambiguous-mutation" or "root-identity" reason, or if the agent
visibly contorts its own script to avoid triggering a denial (e.g. concatenating
`"git" + " commit"` instead of writing the phrase naturally) — that is a
workaround for the bug, not evidence the bug is fixed.

Cross-reference: `harness/tests/test_shell_gate.py`'s
`test_quoted_mention_of_a_mutation_command_is_not_a_chain` covers the same
failure at the unit level.
