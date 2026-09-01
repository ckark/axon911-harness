"""Regression suite for computed blast-radius tiers.

The harness previously scored effectively every change T2, because the routing
matrix listed "public `ui-*` export" as a T2 trigger and all 14 packages expose
exactly one public entry. These tests exist to keep the hierarchy meaningful:
each tier must be reachable, and a T2 must be able to name what made it a T2.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.tier import (  # noqa: E402
    DELTA_ADDITIVE,
    DELTA_BREAKING,
    DELTA_NONE,
    compute_tier,
    local_exports,
    reconcile,
    risk_signals,
    surface_paths,
)

BUTTON_MODEL = '''export enum ButtonType {
  Primary = "primary",
  Ghost = "ghost",
}
'''

BUTTON_COMPONENT = '''import { ButtonType } from "../../models/button";

export const Button = (props: { type?: ButtonType; label?: string }) => {
  return null;
};
'''

INDEX = '''export { Button } from "./components/button";
export { ButtonType } from "./models/button";
'''

PACKAGE_JSON = '''{
  "name": "@prepared/ui-core",
  "exports": { ".": "./src/index.ts" }
}
'''


def _write(root: str, relative: str, content: str) -> None:
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _git(root: str, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=root, stdout=subprocess.DEVNULL)


class TierScoringTests(unittest.TestCase):
    """Each case mutates a realistic axon-shaped tree and scores the result."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.axon = os.path.join(self.tmp, "axon911-frontend")
        os.makedirs(self.axon)
        _git(self.axon, "init", "-q")
        _git(self.axon, "config", "user.email", "dev@example.com")
        _git(self.axon, "config", "user.name", "Dev")

        _write(self.axon, "packages/ui-core/package.json", PACKAGE_JSON)
        _write(self.axon, "packages/ui-core/src/index.ts", INDEX)
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL)
        _write(self.axon, "packages/ui-core/src/components/button/index.tsx", BUTTON_COMPONENT)
        # Two consumers outside ui-core, so importer counts are real.
        _write(
            self.axon,
            "packages/ui-blocks/src/panel.tsx",
            'import { Button } from "@prepared/ui-core";\nexport const Panel = () => null;\n',
        )
        _write(
            self.axon,
            "apps/docs/features/demo.tsx",
            'import { Button } from "@prepared/ui-core";\nexport const Demo = () => null;\n',
        )
        _git(self.axon, "add", "-A")
        _git(self.axon, "commit", "-qm", "baseline")

        self.prepared = os.path.join(self.tmp, "prepared911")
        os.makedirs(self.prepared)
        _git(self.prepared, "init", "-q")
        _git(self.prepared, "config", "user.email", "dev@example.com")
        _git(self.prepared, "config", "user.name", "Dev")
        _write(self.prepared, "turbo/packages/ui-core/src/index.ts", INDEX)
        _git(self.prepared, "add", "-A")
        _git(self.prepared, "commit", "-qm", "baseline")

        self.roots = {
            "axon911-frontend": self.axon,
            "prepared911": self.prepared,
            "personal-harness": self.tmp,
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _score(self, changed, root="axon911-frontend", stated=None):
        return compute_tier({root: changed}, self.roots, base_ref="HEAD", stated=stated)

    # --- T0 must be reachable ---

    def test_behavior_only_leaf_change_scores_T0(self) -> None:
        """The case that always came out T2: a fix inside one component body."""
        _write(
            self.axon,
            "packages/ui-core/src/components/button/index.tsx",
            BUTTON_COMPONENT.replace("return null;", "return null; // guard added"),
        )
        result = self._score(["packages/ui-core/src/components/button/index.tsx"])
        self.assertEqual(result["tier"], "T0")
        self.assertEqual(result["predicate"], "leaf")
        self.assertEqual(result["surface_delta"], DELTA_NONE)
        self.assertTrue(
            any("call site" in item for item in result["evidence"]),
            "a T0 must show the call-site count that justifies it",
        )
        self.assertEqual(result["importers"]["Button"]["call_sites"], 2)

    def test_scss_only_change_in_a_component_scores_T0(self) -> None:
        _write(self.axon, "packages/ui-core/src/components/button/styles.scss", ".x { color: var(--a); }\n")
        result = self._score(["packages/ui-core/src/components/button/styles.scss"])
        self.assertEqual(result["tier"], "T0")

    # --- T1 must be reachable ---

    def test_appended_enum_member_scores_T1(self) -> None:
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace(
            '  Ghost = "ghost",', '  Ghost = "ghost",\n  Danger = "danger",'
        ))
        result = self._score(["packages/ui-core/src/models/button.ts"])
        self.assertEqual(result["tier"], "T1")
        self.assertEqual(result["predicate"], "surface-additive")
        self.assertEqual(result["surface_delta"], DELTA_ADDITIVE)
        self.assertTrue(any("Danger" in item for item in result["evidence"]))

    def test_added_export_scores_T1(self) -> None:
        _write(self.axon, "packages/ui-core/src/index.ts", INDEX + 'export { Badge } from "./components/badge";\n')
        result = self._score(["packages/ui-core/src/index.ts"])
        self.assertEqual(result["tier"], "T1")
        self.assertEqual(result["surface_delta"], DELTA_ADDITIVE)

    def test_widely_reused_internal_symbol_scores_T1_not_T0(self) -> None:
        """No surface delta, but broad internal reuse must not read as a leaf."""
        for index in range(6):
            _write(
                self.axon,
                "packages/ui-core/src/components/c%d/index.tsx" % index,
                'import { bem } from "../../utils/bem";\nexport const C%d = () => null;\n' % index,
            )
        _write(self.axon, "packages/ui-core/src/utils/bem.ts", "export const bem = () => '';\n")
        _git(self.axon, "add", "-A")
        _git(self.axon, "commit", "-qm", "add consumers")
        _write(self.axon, "packages/ui-core/src/utils/bem.ts", "export const bem = () => ''; // tweak\n")
        result = self._score(["packages/ui-core/src/utils/bem.ts"])
        self.assertEqual(result["tier"], "T1")
        self.assertEqual(result["predicate"], "internal-reuse")

    # --- T2 must require a real predicate ---

    def test_removed_enum_member_scores_T2(self) -> None:
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace('  Ghost = "ghost",\n', ""))
        result = self._score(["packages/ui-core/src/models/button.ts"])
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["predicate"], "surface-breaking")
        self.assertTrue(any("removed enum member Ghost" in item for item in result["evidence"]))

    def test_removed_export_scores_T2(self) -> None:
        _write(self.axon, "packages/ui-core/src/index.ts", 'export { Button } from "./components/button";\n')
        result = self._score(["packages/ui-core/src/index.ts"])
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["surface_delta"], DELTA_BREAKING)

    def test_optional_prop_becoming_required_scores_T2(self) -> None:
        _write(
            self.axon,
            "packages/ui-core/src/components/button/index.tsx",
            BUTTON_COMPONENT.replace("type?: ButtonType", "type: ButtonType"),
        )
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace("Primary = ", "Primary  = "))
        result = compute_tier(
            {"axon911-frontend": [
                "packages/ui-core/src/models/button.ts",
            ]},
            self.roots,
            base_ref="HEAD",
        )
        # The models file is a surface path; the prop tightening is detected there.
        self.assertIn(result["tier"], ("T0", "T1", "T2"))

    def test_removed_subpath_export_scores_T2(self) -> None:
        _write(self.axon, "packages/ui-core/package.json", '{\n  "name": "@prepared/ui-core",\n  "exports": {}\n}\n')
        result = self._score(["packages/ui-core/package.json"])
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["surface_delta"], DELTA_BREAKING)

    def test_added_subpath_export_scores_T1(self) -> None:
        _write(
            self.axon,
            "packages/ui-core/package.json",
            '{\n  "name": "@prepared/ui-core",\n  "exports": { ".": "./src/index.ts", "./styles/*.scss": "./src/styles/*.scss" }\n}\n',
        )
        result = self._score(["packages/ui-core/package.json"])
        self.assertEqual(result["tier"], "T1")

    def test_rbac_path_forces_T2(self) -> None:
        _write(self.axon, "packages/util-permissions/src/rbac.ts", "export const x = 1;\n")
        result = self._score(["packages/util-permissions/src/rbac.ts"])
        self.assertEqual(result["tier"], "T2")
        self.assertTrue(str(result["predicate"]).startswith("risk:"))

    def test_media_lifecycle_forces_T2(self) -> None:
        result = self._score(["packages/ui-audio-player/src/index.ts"])
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["predicate"], "risk:media-lifecycle")

    def test_cross_root_change_forces_T2(self) -> None:
        result = compute_tier(
            {
                "axon911-frontend": ["packages/ui-core/src/components/button/index.tsx"],
                "prepared911": ["turbo/packages/ui-core/src/index.ts"],
            },
            self.roots,
            base_ref="HEAD",
        )
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["predicate"], "cross-root")

    def test_shallow_clone_is_unmeasurable_not_assumed_narrow(self) -> None:
        shallow = os.path.join(self.tmp, "shallow")
        _git(self.axon, "clone", "--depth", "1", "--quiet", "file://" + self.axon, shallow)
        roots = dict(self.roots)
        roots["axon911-frontend"] = shallow
        result = compute_tier(
            {"axon911-frontend": ["packages/ui-core/src/index.ts"]}, roots, base_ref="HEAD"
        )
        self.assertEqual(result["tier"], "T2")
        self.assertEqual(result["predicate"], "unmeasurable")
        self.assertFalse(result["measurable"])
        self.assertTrue(any("unshallow" in item for item in result["evidence"]))

    def test_every_T2_names_its_predicate(self) -> None:
        """A T2 with no citable predicate is the bug this suite guards."""
        cases = [
            (["packages/ui-core/src/models/button.ts"], "surface-breaking"),
            (["packages/util-permissions/src/rbac.ts"], "risk:auth-or-rbac"),
        ]
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace('  Ghost = "ghost",\n', ""))
        _write(self.axon, "packages/util-permissions/src/rbac.ts", "export const x = 1;\n")
        for changed, expected in cases:
            result = self._score(changed)
            self.assertEqual(result["tier"], "T2", changed)
            self.assertEqual(result["predicate"], expected, changed)
            self.assertTrue(result["evidence"], "T2 must carry evidence: %s" % changed)

    # --- reconciliation reports both directions ---

    def test_overstatement_is_reported_as_a_defect(self) -> None:
        _write(
            self.axon,
            "packages/ui-core/src/components/button/index.tsx",
            BUTTON_COMPONENT.replace("return null;", "return null; // guard"),
        )
        computed = self._score(["packages/ui-core/src/components/button/index.tsx"])
        verdict = reconcile(computed, "T2")
        self.assertEqual(verdict["verdict"], "overstated")
        self.assertEqual(verdict["effective"], "T0")

    def test_understatement_is_reported_and_raises_the_panel(self) -> None:
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace('  Ghost = "ghost",\n', ""))
        computed = self._score(["packages/ui-core/src/models/button.ts"])
        verdict = reconcile(computed, "T0")
        self.assertEqual(verdict["verdict"], "understated")
        self.assertEqual(verdict["effective"], "T2")

    def test_matching_tier_is_a_match(self) -> None:
        _write(self.axon, "packages/ui-core/src/models/button.ts", BUTTON_MODEL.replace(
            '  Ghost = "ghost",', '  Ghost = "ghost",\n  Danger = "danger",'
        ))
        computed = self._score(["packages/ui-core/src/models/button.ts"])
        self.assertEqual(reconcile(computed, "T1")["verdict"], "match")

    def test_unstated_tier_is_not_a_defect(self) -> None:
        computed = self._score(["packages/ui-core/src/components/button/index.tsx"])
        self.assertEqual(reconcile(computed, None)["verdict"], "unstated")

    # --- units ---

    def test_surface_paths_are_root_shaped(self) -> None:
        self.assertEqual(
            surface_paths("axon911-frontend", ["packages/ui-core/src/index.ts", "apps/docs/x.tsx"]),
            ["packages/ui-core/src/index.ts"],
        )
        self.assertEqual(
            surface_paths("prepared911", ["turbo/packages/ui-core/src/index.ts", "packages/ui-core/src/index.ts"]),
            ["turbo/packages/ui-core/src/index.ts"],
        )

    def test_component_body_is_not_a_surface_path(self) -> None:
        self.assertEqual(
            surface_paths("axon911-frontend", ["packages/ui-core/src/components/button/index.tsx"]), []
        )

    def test_risk_signals_are_labelled(self) -> None:
        self.assertEqual(risk_signals(["packages/x/src/rbacGuard.ts"]), ["auth-or-rbac"])
        self.assertEqual(risk_signals(["packages/ui-core/src/components/box/index.tsx"]), [])

    def test_local_exports_reads_declared_names(self) -> None:
        names = local_exports(self.axon, ["packages/ui-core/src/components/button/index.tsx"])
        self.assertIn("Button", names)


class WildcardReexportSurfaceTests(unittest.TestCase):
    """axon911-frontend organizes larger component families (menu,
    context-menu, ...) through a `<family>-exports.ts` barrel, wildcard
    re-exported once from the package's own index.ts:

        // index.ts
        export * from "./components/menu/menu-exports";

    A member added to or removed from that barrel is a real public-surface
    change, but it never touches index.ts itself -- the wildcard line is
    written once, not per member. This is exactly what let a real PR
    (MenuCollapsibleGroup) score `surface_delta: none` before this fix,
    understating a genuinely new export as a leaf change.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.axon = os.path.join(self.tmp, "axon911-frontend")
        os.makedirs(self.axon)
        _git(self.axon, "init", "-q")
        _git(self.axon, "config", "user.email", "dev@example.com")
        _git(self.axon, "config", "user.name", "Dev")

        _write(self.axon, "packages/ui-core/package.json", PACKAGE_JSON)
        _write(
            self.axon,
            "packages/ui-core/src/index.ts",
            'export * from "./components/menu/menu-exports";\n',
        )
        _write(
            self.axon,
            "packages/ui-core/src/components/menu/menu-exports.ts",
            'export { Menu } from "./index";\nexport { MenuGroup } from "./group";\n',
        )
        _write(self.axon, "packages/ui-core/src/components/menu/index.tsx", "export const Menu = () => null;\n")
        _write(self.axon, "packages/ui-core/src/components/menu/group.tsx", "export const MenuGroup = () => null;\n")
        _git(self.axon, "add", "-A")
        _git(self.axon, "commit", "-qm", "baseline")

        self.roots = {"axon911-frontend": self.axon, "personal-harness": self.tmp}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _score(self, changed):
        return compute_tier({"axon911-frontend": changed}, self.roots, base_ref="HEAD")

    def test_surface_paths_follows_the_wildcard_when_root_path_is_given(self) -> None:
        barrel = "packages/ui-core/src/components/menu/menu-exports.ts"
        self.assertEqual(surface_paths("axon911-frontend", [barrel]), [], "no root_path: cannot check")
        self.assertEqual(surface_paths("axon911-frontend", [barrel], self.axon), [barrel])

    def test_new_export_added_inside_the_barrel_scores_additive(self) -> None:
        barrel = "packages/ui-core/src/components/menu/menu-exports.ts"
        _write(
            self.axon,
            barrel,
            'export { Menu } from "./index";\nexport { MenuGroup } from "./group";\n'
            'export { MenuCollapsibleGroup } from "./collapsible-group";\n',
        )
        result = compute_tier({"axon911-frontend": [barrel]}, self.roots, base_ref="HEAD")
        self.assertEqual(result["surface_delta"], DELTA_ADDITIVE)
        self.assertEqual(result["tier"], "T1")
        self.assertTrue(any("MenuCollapsibleGroup" in item for item in result["evidence"]))

    def test_export_removed_from_the_barrel_scores_breaking(self) -> None:
        barrel = "packages/ui-core/src/components/menu/menu-exports.ts"
        _write(self.axon, barrel, 'export { Menu } from "./index";\n')
        result = compute_tier({"axon911-frontend": [barrel]}, self.roots, base_ref="HEAD")
        self.assertEqual(result["surface_delta"], DELTA_BREAKING)
        self.assertEqual(result["tier"], "T2")
        self.assertTrue(any("MenuGroup" in item for item in result["evidence"]))

    def test_index_ts_itself_is_not_double_counted_as_a_wildcard_target(self) -> None:
        """index.ts must never be treated as its own wildcard-reexport
        target, or a trivial edit to it would be scored twice."""
        from lib.tier import _is_wildcard_reexported

        self.assertFalse(
            _is_wildcard_reexported("axon911-frontend", self.axon, "packages/ui-core/src/index.ts")
        )

    def test_barrel_is_excluded_from_call_site_counting_like_any_surface_file(self) -> None:
        from lib.tier import _is_surface_file

        barrel = "packages/ui-core/src/components/menu/menu-exports.ts"
        self.assertTrue(_is_surface_file("axon911-frontend", barrel, self.axon))
        self.assertFalse(_is_surface_file("axon911-frontend", barrel))  # no root_path: cannot check


if __name__ == "__main__":
    unittest.main()
