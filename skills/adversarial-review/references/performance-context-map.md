# Performance and Reliability Context Map

| Signal | Load | Evidence standard |
|---|---|---|
| Rerender or React state claim | Component, hooks, subscribed state, relevant React performance docs/skills | Trace identity or subscription changes; request profiling when impact is unknown |
| Apollo/network change | Queries, mutations, subscriptions, cache policies, callers | Demonstrate waterfall, duplication, staleness, retry, or cleanup path |
| Bundle/dependency change | Package manifests, import form, build configuration, affected entry point | Use bundle output or record measurement required; package size alone is insufficient |
| Long-session feature | Timers, listeners, observers, media, subscriptions, caches | Identify allocation and cleanup lifecycle, reconnection, and boundedness |
| Large list/map/table | Rendering path, pagination/virtualization, selectors | Establish plausible scale and main-thread/DOM impact |
| Module Federation | Host/remote loading, shared dependency config, failure UI | Check duplicate runtime risk, remote failure/retry, version compatibility |
| Next.js page | Server/client payload and cache boundaries | Keep Next.js claims scoped to Next.js apps |

Separate measured regressions, strong code-level risks, and questions requiring
measurement. Never translate a theoretical cost directly into user impact.
