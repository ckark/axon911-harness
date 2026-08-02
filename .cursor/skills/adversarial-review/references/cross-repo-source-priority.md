# Cross-Repository Source Priority

Authority is scoped to the target contract; no repository wins globally.

## For runtime behavior

1. Target repository public exports and executed behavior
2. Target repository tests and real consumers
3. Generated API data tied to that source
4. Target repository instructions and maintained docs
5. Vault decisions and historical notes
6. Generic framework guidance

## For shared or migrating contracts

Compare:

- Package name, version, provenance, and ownership
- Export maps and types
- Runtime assumptions and peer dependencies
- At least one producer and representative consumers
- Migration order, compatibility window, and rollback

Prepared911 is authoritative for current Prepared911 behavior. Axon is
authoritative for its shell, remotes, federation contracts, and vendored
package behavior. Vault is authoritative for its own recorded decisions and
knowledge-management format, but a note is not proof that code implements the
decision.

When sources conflict, cite both, explain the scope of each, and report drift
instead of silently choosing the preferred design.
