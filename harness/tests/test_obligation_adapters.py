"""Root-specific UI/docs/rendered-evidence obligation adapters."""

from __future__ import annotations

import os
import sys
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.obligations import (  # noqa: E402
    cross_root_receipt_valid,
    product_ui_enabled,
    required_ids,
    triggered_obligations,
)


class ObligationAdapterTests(unittest.TestCase):
    def test_prepared911_ui_path_triggers_four_independent_ids(self) -> None:
        paths = ["turbo/packages/ui-core/src/button.tsx"]
        ids = [item["id"] for item in triggered_obligations("prepared911", paths)]
        self.assertEqual(
            ids,
            [
                "prepared911.ui-allowlist",
                "prepared911.docs-registry",
                "prepared911.docs-page",
                "prepared911.rendered-evidence",
            ],
        )

    def test_axon_layout_does_not_use_turbo_prefix(self) -> None:
        paths = ["packages/ui-core/src/button.tsx"]
        ids = [item["id"] for item in triggered_obligations("axon911-frontend", paths)]
        self.assertTrue(all(item.startswith("axon911-frontend.") for item in ids))
        self.assertFalse(triggered_obligations("prepared911", paths))

    def test_docs_only_edit_does_not_satisfy_allowlist(self) -> None:
        paths = ["turbo/apps/docs/mdx/design/components/button.mdx"]
        ids = [item["id"] for item in triggered_obligations("prepared911", paths)]
        self.assertNotIn("prepared911.ui-allowlist", ids)

    def test_vault_and_harness_disable_product_ui(self) -> None:
        self.assertFalse(product_ui_enabled("vault-core-ux"))
        self.assertFalse(product_ui_enabled("personal-harness"))
        self.assertFalse(triggered_obligations("vault-core-ux", ["packages/ui-core/x.tsx"]))

    def test_filename_containing_ui_does_not_trigger(self) -> None:
        paths = ["apps/dispatch/src/guides.tsx"]
        self.assertFalse(triggered_obligations("prepared911", paths))

    def test_rendered_evidence_before_after_for_existing_surface(self) -> None:
        ids = required_ids("prepared911", ["turbo/packages/ui-core/src/button.tsx"], True, True)
        self.assertIn("prepared911.rendered-evidence.before-after", ids)

    def test_non_visible_change_skips_rendered_evidence(self) -> None:
        ids = required_ids("prepared911", ["turbo/packages/ui-core/src/button.tsx"], False, False)
        self.assertNotIn("prepared911.rendered-evidence", ids)

    def test_consumer_only_via_selector_suppresses_docs(self) -> None:
        from lib.path_selector import select_obligations

        profile = {
            "profiled": True,
            "scope": ["turbo/apps/dispatch/**"],
            "mirror_intent": "consumer-only",
            "path_surfaces": {},
        }
        selection = select_obligations(
            "prepared911",
            ["turbo/packages/ui-core/src/button.tsx"],
            profile,
            "T0",
        )
        self.assertNotIn("prepared911.docs-registry", selection["required_obligation_ids"])
        self.assertNotIn("prepared911.docs-page", selection["required_obligation_ids"])

    def test_cross_root_receipt_rejected(self) -> None:
        self.assertFalse(cross_root_receipt_valid("prepared911", "axon911-frontend"))
        self.assertTrue(cross_root_receipt_valid("prepared911", "prepared911"))


if __name__ == "__main__":
    unittest.main()
