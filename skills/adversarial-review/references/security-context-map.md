# Security and Privacy Context Map

| Signal | Load | Trace |
|---|---|---|
| RBAC, role, permission, feature flag | Prepared RBAC/feature-flag skills, client gate, API resolver/endpoint, tests | User-controlled input to server enforcement; fail-open and migration behavior |
| Emergency data or PII | Data shape, logging/telemetry, URL, storage, errors | Source to browser/log/network/storage sink and retention |
| HTML, URL, redirect, CSS, command input | Producer, sanitizer/validator, sink | Concrete attacker control and execution/escape boundary |
| Cross-origin, iframe, `postMessage`, cookie | Origin checks, headers, listener lifecycle, cookie settings | Trusted origins, message validation, session boundary |
| File transfer | Upload/download handler, content-type and name handling, storage policy | Validation, authorization, content disposition, sensitive-data exposure |
| MFE remote loading | Federation manifest/origin configuration, sandbox/trust assumptions | Whether remote code is trusted code execution and how origins/config are controlled |
| Secret/config change | Build-time and runtime configuration paths | Whether secret material reaches client bundles, logs, or source |

Do not label client-side visibility as authorization. Report a vulnerability
only when a credible data or attack path exists; otherwise use
defense-in-depth or informational classification.
