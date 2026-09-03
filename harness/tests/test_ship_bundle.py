"""Cross-root publication bundle verification."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.bundles import (  # noqa: E402
    STAGE_CANDIDATE,
    bundle_manifest,
    verify_bundle_manifest,
    write_bundle,
    load_bundle,
)


class ShipBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = tempfile.mkdtemp()

    def test_bundle_verify_passes_valid_manifest(self) -> None:
        manifest = bundle_manifest(
            "plan-hash",
            "T2",
            STAGE_CANDIDATE,
            {
                "axon911-frontend": {
                    "fingerprint": "abc",
                    "plan_hash": "plan-hash",
                    "head": "deadbeef",
                }
            },
        )
        report = verify_bundle_manifest(manifest)
        self.assertEqual(report["status"], "PASS")

    def test_bundle_write_and_load(self) -> None:
        manifest = bundle_manifest("plan", "T0", STAGE_CANDIDATE, {})
        os.environ["HARNESS_RUNTIME_DIR"] = self.base
        try:
            path = write_bundle(manifest, base=self.base)
            loaded = load_bundle(path)
            self.assertEqual(loaded["plan_hash"], "plan")
        finally:
            os.environ.pop("HARNESS_RUNTIME_DIR", None)


if __name__ == "__main__":
    unittest.main()
