"""Root-specific obligation adapters."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Sequence

from .constants import ROOT_IDS

Obligation = Dict[str, str]

PREPARED911_UI = r"(^|/)turbo/packages/ui-[^/]+/"
# The design system is `packages/ui` (`@prepared911/ui`, being renamed `@axon911/ui`
# in CORE-1276). The staff-panel allowlist and the docs registry are generated from
# it, so only its changes can make them stale.
AXON_DS = r"(^|/)packages/ui/"
# `packages/ui` or a legacy `packages/ui-*` package. CORE-1276 deletes the legacy
# packages; until then their stories still render in apps/storybook.
AXON_UI = r"(^|/)packages/ui(-[^/]+)?/"
# Module Federation type contract: remotes expose modules the shells consume,
# and CI rejects drift via `pnpm mf:types:check`.
AXON_MF = r"^(remotes/|packages/mfe-core/|apps/(responder|supervisor|switchboard)/)"
AXON_FLAGS = r"(^|/)packages/feature-flags/"

ADAPTERS: Dict[str, List[Obligation]] = {
    "axon911-frontend": [
        {
            "id": "axon911-frontend.ui-allowlist",
            "kind": "ui_allowlist",
            "path": "packages/feature-staff-panel/src/components/annotation/utils/ui-components.generated.ts",
            "trigger": AXON_DS,
            # generate-ui-components.mjs reads @prepared911/ui exports. Staleness
            # rides on the feature-staff-panel `typecheck` script, which runs the
            # generator with --check. There is no separate task.
            "check": "pnpm turbo run typecheck",
            "regenerate": "pnpm gen:ui-components",
        },
        {
            "id": "axon911-frontend.docs-registry",
            "kind": "docs_registry",
            "path": "apps/docs/generated/component-api-registry.json",
            "trigger": AXON_DS,
            # apps/docs/scripts/component-docgen.config.json scans `packages/ui`
            # only. No CI job regenerates or drift-checks this file, so the
            # harness must regenerate and compare rather than trust an empty diff.
            "check": "pnpm --filter docs docs:generate-component-docs",
            "regenerate": "pnpm --filter docs docs:generate-component-docs",
        },
        {
            "id": "axon911-frontend.docs-page",
            "kind": "docs_page",
            "path": "apps/docs/mdx/design",
            "trigger": AXON_DS,
        },
        {
            "id": "axon911-frontend.ds-gates",
            "kind": "package_gates",
            "path": "",
            "trigger": AXON_DS,
            # Root lint ignores `packages/ui`, so `pnpm check` gives no signal
            # there. The package's own check runs ultracite plus the registry,
            # catalog, skills, BUGBOT, and migration-guide drift checks. Filter by
            # path: the package name changes in CORE-1276.
            "check": "pnpm --filter ./packages/ui check",
        },
        {
            "id": "axon911-frontend.rendered-evidence",
            "kind": "rendered_evidence",
            "path": "",
            "trigger": AXON_UI,
            # `packages/ui` stories run in that package's own Storybook (port
            # 5206): `pnpm --filter ./packages/ui test:storybook --run`. Legacy
            # `packages/ui-*` stories run in apps/storybook (`pnpm test:storybook:ci`)
            # until CORE-1276 deletes them. apps/storybook globs `packages/ui-*/src`
            # and the staff panel only, so app and remote changes have no
            # Storybook coverage and need Playwright instead.
            "check": "pnpm --filter ./packages/ui test:storybook --run",
        },
        {
            "id": "axon911-frontend.mf-types",
            "kind": "contract_types",
            "path": "",
            "trigger": AXON_MF,
            "check": "pnpm mf:types:check",
        },
        {
            "id": "axon911-frontend.flag-manifest",
            "kind": "flag_manifest",
            "path": "packages/feature-flags/src/generated/manifest.generated.ts",
            "trigger": AXON_FLAGS,
            "check": "pnpm feature-flags:check",
        },
    ],
    "prepared911": [
        {
            "id": "prepared911.ui-allowlist",
            "kind": "ui_allowlist",
            "path": "turbo/packages/feature-staff-panel/src/components/annotation/utils/ui-components.generated.ts",
            "trigger": PREPARED911_UI,
        },
        {
            "id": "prepared911.docs-registry",
            "kind": "docs_registry",
            "path": "turbo/apps/docs/generated/component-api-registry.json",
            "trigger": PREPARED911_UI,
        },
        {
            "id": "prepared911.docs-page",
            "kind": "docs_page",
            "path": "turbo/apps/docs/mdx/design",
            "trigger": PREPARED911_UI,
        },
        {
            "id": "prepared911.rendered-evidence",
            "kind": "rendered_evidence",
            "path": "",
            "trigger": PREPARED911_UI,
        },
    ],
    "vault-core-ux": [],
    "chroma": [],
    "axon911-design": [],
    "personal-harness": [],
}


# prepared911's ui-* copies are consumed, not authored, post CORE-754 and are
# slated for removal. Their obligations still apply while the code is there.
DEPRECATING_UI_ROOTS = ("prepared911",)


def deprecating_ui(root_id: str) -> bool:
    return root_id in DEPRECATING_UI_ROOTS


def obligations_for(root_id: str) -> List[Obligation]:
    if root_id not in ROOT_IDS:
        return []
    return list(ADAPTERS.get(root_id) or [])


def triggered_obligations(root_id: str, changed_paths: Sequence[str]) -> List[Obligation]:
    selected = []
    for obligation in obligations_for(root_id):
        pattern = re.compile(obligation["trigger"])
        if any(pattern.search(path.replace("\\", "/")) for path in changed_paths):
            selected.append(obligation)
    return selected


def required_ids(root_id: str, changed_paths: Sequence[str], user_visible: bool, existing_surface: bool) -> List[str]:
    """Return path-triggered IDs. Visibility flags do not invent screenshot gates."""
    _ = (user_visible, existing_surface)
    return [
        item["id"]
        for item in triggered_obligations(root_id, changed_paths)
        if not item["id"].endswith(".rendered-evidence")
    ]


def product_ui_enabled(root_id: str) -> bool:
    return bool(obligations_for(root_id))


def cross_root_receipt_valid(receipt_root: str, gate_root: str) -> bool:
    return receipt_root == gate_root
