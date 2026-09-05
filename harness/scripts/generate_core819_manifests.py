#!/usr/bin/env python3
"""Generate CORE-819 definitive execution and evidence manifests."""

from __future__ import annotations

import json
import os
import sys

HARNESS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from lib.execution_manifest import execution_manifest_hash  # noqa: E402
from lib.migration_evidence import manifest_sha256  # noqa: E402
from lib.paths import harness_root, runtime_dir  # noqa: E402

PLAN_SHA256 = "de582facd176d72e097dc7e6465409cb7408f08d41867f35d73a1dca20146513"
EXECUTION_ID = "core819-definitive-v4"
PLAN_HASH = EXECUTION_ID

REFS = {
    "prepared911_trunk": "5f740ee165aacb40f90b19dad5bc0aebbf253829",
    "axon_trunk": "7750f30cf8ebc3be395fa3eddbb5a5b183f13f0f",
    "pr_26166": "8dc898c414372e5df311948d1f22fd4daac954ed",
    "pr_26176": "58a12d4d034008a04b866ea98112e27fde7b7b28",
    "pr_26203": "e502ef2e50e711f18f95174c1d846e8c3b6d4e54",
    "pr_26204": "f4fdcd672242794095a66dd31709628a38e967d8",
    "pr_26205": "bdb468a9edc0cf2e13eddc6db3a35a17d33bd8a6",
    "pr_26352": "12d496f29b5c5515724cd88690aaa9116121dcc4",
    "pr_541": "67cf66aae752d6c29ecee19c3091c99947c4d2fb",
    "harness_head": "3571938455e6d88a39ea254d998c31a36b1d977d",
}

CAPTURE_DEFAULTS = {
    "theme": "dark",
    "brand": "prepared",
    "viewport": "1280x720",
    "state": "default",
}


def _story(**kwargs: object) -> dict:
    return {**CAPTURE_DEFAULTS, **kwargs}


def _route(**kwargs: object) -> dict:
    return {**CAPTURE_DEFAULTS, **kwargs}


CHANGES = [
    {
        "change_id": "localization-docs",
        "title": "Localization docs guidance",
        "pr": 26166,
        "head_ref": "pr_26166",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/docs/mdx/engineering/working-on-features/localization.mdx"],
        "capture": _route(
            route="/docs/engineering/working-on-features/localization",
            entrypoint="docs",
            scenario_id="localization-docs",
        ),
    },
    {
        "change_id": "staff-panel-summaries",
        "title": "Staff Panel channel summaries",
        "pr": 26166,
        "head_ref": "pr_26166",
        "evidence_state": "expected_unchanged",
        "expected_visual_result": "unchanged",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/staff-panel/components/StaffPanelSettings.tsx"],
        "capture": _route(route="/", entrypoint="dispatch", scenario_id="staff-panel-summaries"),
    },
    {
        "change_id": "share-banner-notes",
        "title": "ShareBanner acknowledgement notes",
        "pr": 26176,
        "head_ref": "pr_26176",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/chatroom/components/ShareBanner/ShareBanner.tsx"],
        "capture": _route(route="/chatroom/cr-1", entrypoint="dispatch", scenario_id="share-banner-notes"),
    },
    {
        "change_id": "protocol-config-invalid",
        "title": "Protocol config invalid submit",
        "pr": 26203,
        "head_ref": "pr_26203",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/unified-qa-protocol/components/ProtocolConfigDrawer.tsx"],
        "capture": _route(
            route="/supervisor/protocols?tab=incident-types",
            entrypoint="dispatch",
            scenario_id="protocol-config-invalid",
        ),
    },
    {
        "change_id": "critical-misses",
        "title": "Critical Misses Callout section",
        "pr": 26203,
        "head_ref": "pr_26203",
        "evidence_state": "changed",
        "capture_kind": "storybook",
        "source_paths": [
            "turbo/apps/dispatch/src/modules/unified-qa-analysis/components/CriticalMissesSection/CriticalMissesSection.tsx"
        ],
        "capture": _story(story_id="QA/UnifiedAnalysis/CriticalMissesSection"),
    },
    {
        "change_id": "sampling-validation",
        "title": "Sampling run validation error",
        "pr": 26203,
        "head_ref": "pr_26203",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/unified-qa-sampling/pages/SamplingRunNewPage.tsx"],
        "capture": _route(
            route="/qa/configure/sampling-runs/new",
            entrypoint="dispatch",
            scenario_id="sampling-validation",
        ),
    },
    {
        "change_id": "sampling-dropped-settings",
        "title": "Sampling run dropped settings",
        "pr": 26203,
        "head_ref": "pr_26203",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/unified-qa-sampling/pages/SamplingRunNewPage.tsx"],
        "capture": _route(
            route="/qa/configure/sampling-runs/new?copyFrom=run-3",
            entrypoint="dispatch",
            scenario_id="sampling-dropped-settings",
        ),
    },
    {
        "change_id": "anet-disabled-banner",
        "title": "ANET disabled banner",
        "pr": 26204,
        "head_ref": "pr_26204",
        "evidence_state": "changed",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/triage/components/AnetDisabledBanner.tsx"],
        "capture": _route(route="/triage", entrypoint="dispatch", scenario_id="anet-disabled-banner"),
    },
    {
        "change_id": "malformed-dkf",
        "title": "Malformed DKF upload",
        "pr": 26352,
        "head_ref": "pr_26352",
        "evidence_state": "expected_unchanged",
        "expected_visual_result": "unchanged",
        "capture_kind": "product-route",
        "source_paths": ["turbo/apps/dispatch/src/modules/radio-settings/components/DigitalKeyFillUpload.tsx"],
        "capture": _route(route="/supervisor/radio", entrypoint="dispatch", scenario_id="malformed-dkf"),
    },
    {
        "change_id": "formatter-typing",
        "title": "Formatter typing enforcement",
        "pr": 26205,
        "head_ref": "pr_26205",
        "evidence_state": "static_only",
        "capture_kind": "not-applicable",
        "source_paths": ["turbo/packages/tool-localization/src/formatters/formatter.ts"],
        "static_check": "pnpm --filter @prepared/tool-localization typecheck",
    },
    {
        "change_id": "row-layout",
        "title": "Callout row layout rhythm",
        "pr": 541,
        "head_ref": "pr_541",
        "root": "axon911-frontend",
        "evidence_state": "changed",
        "capture_kind": "storybook",
        "source_paths": ["packages/ui-core/src/components/typography/styles.scss"],
        "capture": _story(story_id="Packages/ui-core/Callout/RowLayout", brand="axon"),
    },
    {
        "change_id": "semantic-content-color-matrix",
        "title": "Semantic content color matrix",
        "pr": 541,
        "head_ref": "pr_541",
        "root": "axon911-frontend",
        "evidence_state": "new_visible",
        "capture_kind": "storybook",
        "source_paths": ["packages/ui-core/src/components/callout/index.stories.tsx"],
        "capture": _story(story_id="Packages/ui-core/Callout/SemanticContentColorMatrix", brand="axon"),
    },
]


def main() -> int:
    root = harness_root()
    evidence_path = os.path.join(root, "harness", "manifests", "core819-definitive-v4.json")
    os.makedirs(os.path.dirname(evidence_path), exist_ok=True)
    evidence_manifest = {
        "schema_version": 3,
        "plan_hash": PLAN_HASH,
        "execution_id": EXECUTION_ID,
        "plan_sha256": PLAN_SHA256,
        "refs": REFS,
        "changes": CHANGES,
    }
    evidence_manifest["manifest_sha256"] = manifest_sha256(evidence_manifest)
    with open(evidence_path, "w", encoding="utf-8") as handle:
        json.dump(evidence_manifest, handle, indent=2)
        handle.write("\n")

    execution_path = os.path.join(runtime_dir(), "executions", EXECUTION_ID, "execution-manifest.json")
    os.makedirs(os.path.dirname(execution_path), exist_ok=True)
    harness_allowed = [
        "docs/plan-contract.md",
        "docs/implementation-contract.md",
        "docs/runtime-contract.md",
        "docs/session-budget.md",
        "docs/review-contract.md",
        ".cursor/skills/capture-evidence/**",
        ".cursor/skills/implementation-check/**",
        "cursor/skills/capture-evidence/**",
        "cursor/skills/implementation-check/**",
        "harness/cli.py",
        "harness/lib/**",
        "harness/scripts/storybook-capture.mjs",
        "harness/scripts/route-capture.mjs",
        "harness/scripts/core819_definitive_run.py",
        "harness/scripts/generate_core819_manifests.py",
        "harness/manifests/core819-definitive-v4.json",
        "harness/fixtures/core819-route-scenarios/**",
        "harness/fixtures/core819-stories-base/**",
        "harness/fixtures/core819-stories-head/**",
        "harness/fixtures/core819-stories-modules/**",
        "harness/scripts/core819_capture_batch.py",
        "harness/scripts/core819_evidence_run.py",
        "harness/tests/**",
    ]
    harness_required = [
        ".cursor/skills/capture-evidence/SKILL.md",
        ".cursor/skills/implementation-check/SKILL.md",
        "docs/plan-contract.md",
        "docs/implementation-contract.md",
        "docs/runtime-contract.md",
        "docs/session-budget.md",
        "docs/review-contract.md",
        "harness/lib/execution_manifest.py",
        "harness/lib/execution_state.py",
        "harness/lib/capture_provenance.py",
        "harness/lib/capture_receipt.py",
        "harness/lib/storybook_session.py",
        "harness/lib/route_capture.py",
        "harness/lib/capture_ready.py",
        "harness/scripts/core819_definitive_run.py",
        "harness/manifests/core819-definitive-v4.json",
        "harness/tests/test_core819_regression.py",
    ]
    execution_manifest = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "plan_hash": PLAN_HASH,
        "plan_sha256": PLAN_SHA256,
        "plan_path": "/Users/ckark/.cursor/plans/core819-definitive-evidence_7d0db4ba.plan.md",
        "tier": "T2",
        "refs": REFS,
        "evidence_manifest_path": evidence_path,
        "target_roots": {
            "personal-harness": {
                "base_oid": REFS["harness_head"],
                "allowed_paths": harness_allowed,
                "required_paths": harness_required,
                "mirror_intent": "",
                "evidence_states": {pattern: "none" for pattern in harness_allowed},
            },
            "prepared911": {
                "base_oid": REFS["prepared911_trunk"],
                "allowed_paths": [".harness/runtime/**"],
                "required_paths": [],
                "mirror_intent": "capture-subject-only",
                "evidence_states": {".harness/runtime/**": "before-after"},
            },
            "axon911-frontend": {
                "base_oid": REFS["axon_trunk"],
                "allowed_paths": [
                    "apps/docs/mdx/design/primitives/typography/api-dev.mdx",
                    "packages/ui-core/src/components/typography/styles.scss",
                ],
                "required_paths": ["packages/ui-core/src/components/typography/styles.scss"],
                "mirror_intent": "",
                "evidence_states": {
                    "apps/docs/mdx/design/primitives/typography/api-dev.mdx": "none",
                    "packages/ui-core/src/components/typography/styles.scss": "before-after",
                },
            },
        },
        "budgets": {"max_assistant_turns": 60, "max_context_bytes": 320000},
        "phase_limits": {
            "remove-worktrees": 1,
            "profile-compile": 1,
            "v4-implementation": 3,
            "axon-fix": 2,
            "capture-ready": 2,
            "scenario-probe": 2,
            "baseline-capture": 2,
            "sentinel-capture": 2,
            "after-capture": 2,
            "local-validation": 2,
            "upload-verify": 2,
            "visual-acceptance": 1,
            "implementation-review": 2,
            "commit-reattest": 1,
            "pr-body-publication": 1,
            "rollback-verification": 2,
        },
    }
    execution_manifest["execution_manifest_sha256"] = execution_manifest_hash(execution_manifest)
    with open(execution_path, "w", encoding="utf-8") as handle:
        json.dump(execution_manifest, handle, indent=2)
        handle.write("\n")
    print(evidence_path)
    print(execution_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
