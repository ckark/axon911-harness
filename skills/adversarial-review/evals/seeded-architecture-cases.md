# Seeded Frontend-Architecture Cases

## FA-1: Vite versus Next.js

Seed: A Dispatch plan proposes client-side route data loading. The docs app
uses an RSC and `React.cache` pattern for a superficially similar page.

Expected:

- Identifies Dispatch as Vite
- Labels the docs pattern `[next]` and does not impose it
- Still evaluates universal loading, cache, state ownership, and error handling

## FA-2: Shared package migration

Seed: A shared `ui-*` export changes and two Prepared911 apps plus Axon consume
related versions.

Expected:

- Inspects the public export and representative consumers
- Separates Prepared911 and Axon authority
- Requires an ordered compatibility and rollout story when contracts cross
  roots

## FA-3: Federated state ownership

Seed: An Axon remote writes a shell URL key directly.

Expected:

- Loads Axon instructions and the triggered federation/router skills
- Checks shell-owned URL and guest-scope rules
- Produces a concrete failure path rather than generic state-management advice
