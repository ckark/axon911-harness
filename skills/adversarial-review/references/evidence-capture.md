# Evidence Capture

Use this cookbook before any specialist runs. Every claim about repository
state must resolve against a pinned revision, not the working tree by default.

## Ref manifest

For each PR, branch, or label the target names, record:

| Field | How to obtain |
|---|---|
| Branch name | Target text, or `gh pr view <n> --json headRefName` |
| Head SHA | `git rev-parse <branch>` |
| Parent branch head SHA | Previous stack branch head, or `git merge-base <branch> <trunk>` when no stack parent is named |
| Merge-base with trunk | `git merge-base <branch> <trunk>` |

Build the branch inventory with:

```bash
git for-each-ref --format='%(objectname) %(refname:short)' refs/heads
gh pr list --json number,headRefName,baseRefName --limit 100
```

Include the manifest verbatim in the evidence package. Critics cite rows from
this table; they do not invent SHAs.

## Working-tree snapshot

Capture and attach before evidence collection:

```bash
git status --porcelain=v1 -uall
git diff
git diff --cached
git stash list
git worktree list
```

State one scope decision explicitly:

- `committed-only` — review against pinned refs; attach the dirty delta so
  critics know what they are excluding
- `committed-plus-delta` — review against pinned refs plus the captured
  uncommitted changes; tag every finding that depends on uncommitted content
  as `State: uncommitted` or `State: both`

Never treat an unclean working tree as if it were a commit.

## Claim recipes

Resolve each falsifiable claim with the matching recipe. Record the exact
command and raw output in the claim ledger.

### Which commit adds or deletes a path

```bash
git log --diff-filter=A --name-only <ref> -- <path>
git log --diff-filter=D --name-only <ref> -- <path>
```

Use `--diff-filter=A` for introductions and `D` for deletions. Restrict the
range when the claim is about one PR:

```bash
git log --diff-filter=A --name-only <parent-head>..<this-head> -- <path>
```

### Which PR owns a commit

```bash
git branch --contains <sha>
```

Take the lowest branch in stack order (the first stack branch that contains
the commit and whose parent does not). Confirm with:

```bash
git merge-base --is-ancestor <sha> <branch-head> && echo contained
```

### Size of a change within one PR

```bash
git diff --numstat <parent-head> <this-head> -- <path>
git diff --shortstat <parent-head> <this-head>
```

Always diff the parent branch head against this PR's head. Never use the tip
commit alone.

### Whether a path exists at a ref

```bash
git ls-tree -r --name-only <ref> -- <path>
```

Empty output means absent at that ref.

### Whether a file is byte-identical across refs

```bash
git rev-parse "<ref-a>:<path>"
git rev-parse "<ref-b>:<path>"
```

Identical blob hashes mean byte-identical content. Brace-quote the
`ref:path` form so zsh does not treat `:t` as a history modifier.

### Contents of a generated artifact

```bash
git show "<ref>:<path>"
```

Pipe to a parser when needed. Never read the working-tree copy of a generated
file when the claim is about a committed revision.

## Claim ledger format

Emit one row per claim into the evidence package:

| Claim as written | Command | Raw result | Verdict | Plan disposition |
|---|---|---|---|---|
| … | exact shell command | truncated raw output | `confirmed` / `refuted` / `unverifiable` | `open` / `remediated-by-plan` / `out-of-scope` (for `confirmed` only) |

Refuted claims are defects in the target. Report them before any critic runs.
Do not hand them to specialists as open questions.

For `confirmed` claims, set plan disposition from the target plan text:

- `open` — the plan does not address it
- `remediated-by-plan` — the plan already contains the fix
- `out-of-scope` — the plan explicitly defers it

## Blast radius

Judge review tier and "affected" verification by callers, not by file count.
A `T0` classification requires the importer count, not an assertion.

For each changed public export or shared helper name:

```bash
rg -l --glob '!**/node_modules/**' '\b<ExportName>\b' turbo/ apps/
```

When the target spans Axon as well, also search that root's `apps/`,
`remotes/`, and `packages/` with the same pattern. Record the importer count
per changed export in the evidence package.

To see which directories a PR range touches before counting callers:

```bash
git diff --name-only <parent-head> <this-head> | xargs -n1 dirname | sort -u
```

Map counts and surfaces to tiers using `docs/routing-matrix.md`:

- Few importers, no exported surface → candidate `T0` (only with the count)
- App-shared or package-internal contract → `T1`
- Public `ui-*` export, token/theme, auth/PII, realtime lifecycle, cross-root
  contract, or too large to hold in one head → `T2`

## Acceptance-criterion recipe

Before scoring a verification-matrix row or acceptance check in the target:

1. Resolve the **actual** consumer API — TypeScript types, generators, MDX
   helpers, Storybook/docgen schema — at the pinned ref.
2. Confirm the matrix property can be expressed by that API.
3. If the matrix asks for something the API cannot express (for example
   per-prop Storybook links when `DocgenPropRow` only has component-level
   `storybook.stories[]`), score it as a `plan-text` defect in the matrix
   wording, not as missing product work.

Do not invent product requirements from impossible acceptance language.

## Traps

These produced wrong claims in prior reviews. Avoid them.

### Tip commit is not the PR range

`git show --stat <branch-head>` shows only the tip commit. A PR with many
commits will look like it touches two files. Always:

```bash
git diff --stat <parent-head> <this-head>
git diff --name-status <parent-head> <this-head>
```

### Rename detection hides delete/add pairs

Git may present a substantial rewrite as a rename, or hide a delete/add pair.
When the claim is about a rename, run both:

```bash
git diff --name-status <parent-head> <this-head>
git diff --name-status -M <parent-head> <this-head>
```

Compare content with `--numstat` before calling a transition a rename.

### zsh word-splitting and history modifiers

The default shell is often zsh. Unquoted variables do not word-split, and
`$ref:turbo/...` is parsed as a history modifier (`:t`). Wrap multi-ref loops
in `bash -c` and brace-quote paths:

```bash
bash -c 'for ref in a b c; do git rev-parse "${ref}:apps/docs/vercel.json"; done'
```
