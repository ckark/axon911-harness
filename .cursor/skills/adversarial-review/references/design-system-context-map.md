# Design-System Context Map

Load only rows triggered by the target.

| Signal | Prepared911 sources | Additional context | Verification |
|---|---|---|---|
| Tokens, themes, raw color/spacing/type values | `ui-core`, `turbo/apps/docs/mdx/design/foundations`, token catalogs, theme source, `ui-core` styles | `css-best-practices`; Vault UI standards when intent is relevant | Theme/brand variants, contrast, generated docs |
| Primitive or public component API | Matching `usage.mdx`, `api-dev.mdx`, `accessibility.mdx`; package source, exports, tests, stories in `ui-core` | `react-ui-implementation`, `typescript-style`; Axon consumer when affected | Public import, typecheck, story interaction, accessibility |
| Composite component or block | `mdx/design/components`, `mdx/design/blocks`, owning `ui-*` package | Package dependency graph and real app consumers | Duplication, ownership, responsive states |
| Form control | Relevant design docs and package tests | `ui-forms`, `react-forms`, testing skills | Labeling, validation, controlled/uncontrolled behavior |
| Iconography | Icon package, docs catalog, call sites | Migration history only when the target crosses repos | Accessible name, size/color inheritance, bundle impact |
| Shared package migration | Package exports, dependents, changelog/migration docs | Axon vendored package comparison; Vault ownership maps | Consumer inventory and compatibility path |

Always classify the artifact before judging it: foundation, primitive,
component, block, product component, or application-local UI. Require concrete
reuse or boundary evidence before demanding a new abstraction.
