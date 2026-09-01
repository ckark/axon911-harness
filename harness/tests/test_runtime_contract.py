"""Runtime contract invariants: fingerprints, schemas, and privacy allowlists."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, HARNESS)

from lib.constants import ALLOWED_PERSISTED_FIELDS, MAX_EVENT_BYTES  # noqa: E402
from lib.fingerprint import hash_text, snapshot  # noqa: E402
from lib.ledger import append_record  # noqa: E402
from lib.schema import SchemaError, parse_event  # noqa: E402


def _git_repo() -> str:
    import subprocess

    path = tempfile.mkdtemp()
    subprocess.check_call(["git", "init", "-q"], cwd=path)
    subprocess.check_call(["git", "config", "user.email", "dev@example.com"], cwd=path)
    subprocess.check_call(["git", "config", "user.name", "Dev"], cwd=path)
    subprocess.check_call(["git", "config", "core.filemode", "true"], cwd=path)
    with open(os.path.join(path, "README"), "w", encoding="utf-8") as handle:
        handle.write("one\n")
    subprocess.check_call(["git", "add", "README"], cwd=path)
    subprocess.check_call(["git", "commit", "-qm", "init"], cwd=path)
    return path


class RuntimeContractTests(unittest.TestCase):
    def test_fingerprint_changes_with_unstaged_edit(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo, plan_hash="a")
        with open(os.path.join(repo, "README"), "a", encoding="utf-8") as handle:
            handle.write("two\n")
        second = snapshot("personal-harness", repo, plan_hash="a")
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_changes_with_untracked_file(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        with open(os.path.join(repo, "extra.txt"), "w", encoding="utf-8") as handle:
            handle.write("x\n")
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_plan_hash_is_part_of_fingerprint(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo, plan_hash="one")
        second = snapshot("personal-harness", repo, plan_hash="two")
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_event_payload_limit(self) -> None:
        raw = b'{"command":"' + (b"a" * (MAX_EVENT_BYTES + 1)) + b'"}'
        with self.assertRaises(SchemaError):
            parse_event("beforeShellExecution", raw)

    def test_malformed_json_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            parse_event("stop", b"{not json")

    def test_ledger_strips_disallowed_fields(self) -> None:
        base = tempfile.mkdtemp()
        record = append_record(
            {
                "kind": "observation",
                "root": "personal-harness",
                "command": "git commit -am secret",
                "prompt": "do not store",
                "status": "PASS",
                "worktree_id": "wt",
                "fingerprint": "abc",
            },
            base=base,
        )
        self.assertNotIn("command", record)
        self.assertNotIn("prompt", record)
        for key in record:
            if key == "version":
                continue
            self.assertIn(key, ALLOWED_PERSISTED_FIELDS)

    def test_hash_text_stable(self) -> None:
        self.assertEqual(hash_text("abc"), hash_text("abc"))
        self.assertNotEqual(hash_text("abc"), hash_text("abd"))

    def test_fingerprint_changes_with_deletion(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        os.remove(os.path.join(repo, "README"))
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_changes_with_rename(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        os.rename(os.path.join(repo, "README"), os.path.join(repo, "README.md"))
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_changes_with_mode(self) -> None:
        import subprocess

        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        subprocess.check_call(["git", "update-index", "--chmod=+x", "README"], cwd=repo)
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_changes_with_symlink(self) -> None:
        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        os.symlink("README", os.path.join(repo, "link"))
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_changes_with_head(self) -> None:
        import subprocess

        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        with open(os.path.join(repo, "README"), "a", encoding="utf-8") as handle:
            handle.write("commit-me\n")
        subprocess.check_call(["git", "add", "README"], cwd=repo)
        subprocess.check_call(["git", "commit", "-qm", "second"], cwd=repo)
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["head"], second["head"])
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_fingerprint_includes_submodule_oid(self) -> None:
        import subprocess

        repo = _git_repo()
        nested = os.path.join(repo, "vendor")
        os.mkdir(nested)
        subprocess.check_call(["git", "init", "-q"], cwd=nested)
        subprocess.check_call(["git", "config", "user.email", "dev@example.com"], cwd=nested)
        subprocess.check_call(["git", "config", "user.name", "Dev"], cwd=nested)
        with open(os.path.join(nested, "x"), "w", encoding="utf-8") as handle:
            handle.write("sub\n")
        subprocess.check_call(["git", "add", "x"], cwd=nested)
        subprocess.check_call(["git", "commit", "-qm", "nested"], cwd=nested)
        first = snapshot("personal-harness", repo)
        with open(os.path.join(nested, "x"), "a", encoding="utf-8") as handle:
            handle.write("more\n")
        subprocess.check_call(["git", "add", "x"], cwd=nested)
        subprocess.check_call(["git", "commit", "-qm", "nested2"], cwd=nested)
        second = snapshot("personal-harness", repo)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_isolated_formatter_rewrite_changes_fingerprint(self) -> None:
        repo = _git_repo()
        before = snapshot("personal-harness", repo)
        with open(os.path.join(repo, "README"), "w", encoding="utf-8") as handle:
            handle.write("formatted-by-fixture\n")
        after = snapshot("personal-harness", repo)
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])

    def test_schema_version_is_part_of_fingerprint(self) -> None:
        import lib.fingerprint as fingerprint_mod

        repo = _git_repo()
        first = snapshot("personal-harness", repo)
        original = fingerprint_mod.OBLIGATION_SCHEMA_VERSION
        fingerprint_mod.OBLIGATION_SCHEMA_VERSION = "changed"
        try:
            second = snapshot("personal-harness", repo)
        finally:
            fingerprint_mod.OBLIGATION_SCHEMA_VERSION = original
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_axon_formatter_hook_is_after_file_edit(self) -> None:
        path = "/Users/ckark/Documents/GitHub/axon911-frontend/.cursor/hooks.json"
        if not os.path.isfile(path):
            self.skipTest("axon checkout missing")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        command = data["hooks"]["afterFileEdit"][0]["command"]
        self.assertEqual(command, "pnpm run fix")

    def test_same_head_different_worktrees_differ(self) -> None:
        import subprocess

        repo = _git_repo()
        other = tempfile.mkdtemp()
        subprocess.check_call(["git", "worktree", "add", "--detach", "-q", other], cwd=repo)
        first = snapshot("personal-harness", repo)
        second = snapshot("personal-harness", other)
        self.assertEqual(first["head"], second["head"])
        self.assertNotEqual(first["worktree_id"], second["worktree_id"])
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_contained_path_rejects_symlink_and_fifo(self) -> None:
        from lib.paths import PathError, contained_path

        repo = _git_repo()
        link = os.path.join(repo, "link")
        os.symlink("README", link)
        with self.assertRaises(PathError):
            contained_path(link, repo)
        fifo = os.path.join(repo, "pipe")
        os.mkfifo(fifo)
        with self.assertRaises(PathError):
            contained_path(fifo, repo)


if __name__ == "__main__":
    unittest.main()
