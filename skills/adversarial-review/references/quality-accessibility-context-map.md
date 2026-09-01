# Quality and Accessibility Context Map

| Signal | Load | Verification |
|---|---|---|
| Shared component | Matching docs accessibility page, source, stories, unit/interaction tests | Keyboard, focus, role/name/state, public contract, theme/density variants |
| Form or validation | Form skill, labels/descriptions, error rendering and tests | Submission, invalid focus, announcement, disabled/read-only states |
| Modal, drawer, menu, popover | Primitive docs/source, portal and focus behavior | Open/close trigger, focus trap/return, Escape, outside interaction |
| Navigation or router change | Router/runtime instructions and E2E tests | Link semantics, history, URL state, focus/announcement after navigation |
| Async data | Loading/error/empty/stale/offline UI and mocks | User-observable transitions and deterministic waits |
| Drag, map, audio, video, visualization | Alternate controls and semantic fallback | Keyboard path, labels, captions/transcript where applicable, cleanup |
| Cross-app/shared-package change | Representative consumers and regression suite | Contract tests plus at least one integrated workflow |

Prefer semantic queries and user behavior over implementation-detail
assertions. Use Storybook for isolated shared behavior and Playwright for
integrated flows. A build or snapshot alone is not behavioral evidence.
