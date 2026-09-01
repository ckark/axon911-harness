# Frontend Architecture Context Map

First identify the runtime and package boundary.

| Signal | Load | Key questions |
|---|---|---|
| Prepared911 Vite app (`dispatch`, `responder`, `caller`) | App `AGENTS.md`, docs shared architecture/data guidance, Apollo/state source, affected package exports | Is state owned at the right layer? Are loading/error/offline paths explicit? Never import Next.js/RSC prescriptions. |
| Prepared911 Next.js app (`beacon`, `docs`) | App instructions, docs architecture, app router source, server/client boundaries | Are async, caching, serialization, and client boundaries valid for the installed Next.js version? |
| Shared `ui-*` package | Package manifest/exports/source/tests and consumers | Is dependency direction stable? Is public API explicit? Does migration cover consumers? |
| Axon shell or remote | Axon `AGENTS.md`; `mf`, `mfe-module-federation`, `vite`, or `tanstack-router` skill as triggered | Does shell own global/URL state? Does a remote respect guest scope and domain methods? Are federation contracts compatible? |
| Cross-repo package or MFE contract | Both roots' manifests, exports, type contracts, consumer usage | Which repo owns the contract? Are versions/forks compatible? Is rollout ordered? |
| Vault architecture proposal | Relevant `20-architecture` note plus linked index; then runtime source | Is the note current and implemented, or only proposed intent? |

For state decisions, identify whether the state is local, module, contextual,
shell/global, server/cache, URL, or persisted. For every boundary, inspect at
least one producer and one real consumer.
