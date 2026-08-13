from __future__ import annotations

import hashlib
import json
import tomllib
import unittest

from ast_helpers import REPOSITORY_ROOT, source_path


FIXTURE_PATH = source_path("tests/fixtures/upstream-v12.3.3.json")


class UpstreamBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_manager_version_matches_imported_release(self):
        self.assertEqual(source_path("VERSION").read_text(encoding="utf-8").strip(), "12.3.3")

    def test_panel_version_matches_imported_release(self):
        with source_path("hiddify-panel/src/pyproject.toml").open("rb") as project_file:
            panel_project = tomllib.load(project_file)
        self.assertEqual(panel_project["project"]["version"], "12.3.3")

    def test_panel_submodule_source_is_recorded(self):
        gitmodules = source_path(".gitmodules").read_text(encoding="utf-8")
        self.assertIn("path = hiddify-panel/src", gitmodules)
        self.assertIn("https://github.com/hiddify/Hiddify-Panel.git", gitmodules)

    def test_reviewed_upstream_files_match_fingerprints(self):
        mismatches: list[str] = []
        for relative_path, expected_digest in self.fixture["sha256"].items():
            path = REPOSITORY_ROOT / relative_path
            if not path.is_file():
                mismatches.append(f"{relative_path}: missing")
                continue
            normalized_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            actual_digest = hashlib.sha256(normalized_bytes).hexdigest()
            if actual_digest != expected_digest:
                mismatches.append(
                    f"{relative_path}: expected {expected_digest}, got {actual_digest}"
                )
        self.assertEqual(
            mismatches,
            [],
            "Protected upstream files changed; review the diff and update one fixture entry at a time.",
        )


if __name__ == "__main__":
    unittest.main()
