from __future__ import annotations

import base64
import json
import re
import tempfile
import unittest
from pathlib import Path

from ast_helpers import source_path
from xray_test_support import render_xray_config_directory, validate_rendered_contract


RUNTIME_METADATA = source_path("tests/fixtures/xray-v26.3.27.json")
KEYPAIR_FIXTURE = source_path("tests/fixtures/xray-test-keypair.json")
CURRENT_FIXTURE = source_path("tests/fixtures/xray-full-current.json")
RENDER_RUNTIME_FIXTURE = source_path("tests/fixtures/xray-render-runtime.json")


def package_rows() -> list[tuple[str, str, str, str, str]]:
    rows = []
    for line in source_path("common/packages.lock").read_text(encoding="utf-8").splitlines():
        if line:
            rows.append(tuple(line.split("|")))
    return rows


def numeric_version(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise AssertionError(f"Unexpected non-numeric locked version: {version}")
    return tuple(int(part) for part in version.split("."))


class XrayVersionSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads(RUNTIME_METADATA.read_text(encoding="utf-8"))

    def test_hiddify_install_requests_the_lock_resolver_version(self):
        install_script = source_path("xray/install.sh").read_text(encoding="utf-8")
        self.assertRegex(install_script, r'(?m)^version=""')
        self.assertIn("download_package xray sb.zip $version", install_script)

        package_manager = source_path("common/package_manager.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('if [[ "$requested_version" == "" ]]', package_manager)
        self.assertIn("requested_version=$(get_latest_version $package_name $arch)", package_manager)
        self.assertIn("sort -t'|' -k2.1V | tail -n 1", package_manager)

    def test_selected_version_is_the_highest_locked_version_for_each_architecture(self):
        for architecture in ("amd64", "arm64"):
            versions = [
                version
                for name, version, row_architecture, _url, _digest in package_rows()
                if name == "xray" and row_architecture == architecture
            ]
            selected = max(versions, key=numeric_version)
            self.assertEqual(selected, self.metadata["version"])

    def test_linux_artifacts_exactly_match_hiddify_packages_lock(self):
        rows = {
            (name, version, architecture): (url, digest)
            for name, version, architecture, url, digest in package_rows()
        }
        for architecture in ("amd64", "arm64"):
            artifact = self.metadata["artifacts"][f"linux-{architecture}"]
            self.assertEqual(
                (artifact["url"], artifact["sha256"]),
                rows[("xray", self.metadata["version"], architecture)],
            )
            self.assertEqual(artifact["source"], "hiddify-v12.3.3-packages.lock")

    def test_every_download_is_an_exact_official_release_with_sha256(self):
        for artifact in self.metadata["artifacts"].values():
            self.assertTrue(
                artifact["url"].startswith(
                    "https://github.com/XTLS/Xray-core/releases/download/"
                )
            )
            self.assertIn(f"/v{self.metadata['version']}/", artifact["url"])
            self.assertNotIn("/latest/", artifact["url"])
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_ci_uses_the_pinned_linux_artifact_and_native_config_test_mode(self):
        workflow = source_path(
            ".github/workflows/safeline-characterization.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("Install checksum-verified Xray 26.3.27", workflow)
        self.assertIn("--platform linux-amd64", workflow)
        self.assertIn("xray run -test", workflow)
        self.assertIn("-confdir .test-output/xray-config", workflow)


class XrayRealityFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keypair = json.loads(KEYPAIR_FIXTURE.read_text(encoding="utf-8"))
        cls.context = json.loads(CURRENT_FIXTURE.read_text(encoding="utf-8"))

    def test_x25519_pair_is_test_only_and_contains_raw_32_byte_keys(self):
        self.assertIs(self.keypair["test_only"], True)
        for name in ("private", "public"):
            encoded = self.keypair[f"{name}_key"]
            decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            self.assertEqual(len(decoded), 32)
            self.assertEqual(decoded.hex(), self.keypair[f"{name}_key_hex"])

    def test_full_current_fixture_uses_the_recorded_non_secret_keypair(self):
        hconfigs = self.context["chconfigs"]["0"]
        self.assertEqual(hconfigs["reality_private_key"], self.keypair["private_key"])
        self.assertEqual(hconfigs["reality_public_key"], self.keypair["public_key"])

    def test_known_incompatible_kcp_branch_is_explicitly_disabled(self):
        self.assertIs(self.context["chconfigs"]["0"]["kcp_enable"], False)
        kcp_template = source_path(
            "xray/configs/05_inbounds_02_kcp_main.json.j2"
        ).read_text(encoding="utf-8")
        self.assertIn('"seed": "{{ hconfigs[\'proxy_path\'] }}"', kcp_template)

    def test_reality_short_ids_are_valid_hex_byte_strings(self):
        short_ids = self.context["chconfigs"]["0"]["reality_short_ids"].split(",")
        for short_id in short_ids:
            self.assertRegex(short_id, r"^(?:[0-9a-fA-F]{2}){1,8}$")


class FullHiddifyXrayRenderingTests(unittest.TestCase):
    def test_all_server_templates_render_and_requested_sections_are_present(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            rendered = render_xray_config_directory(
                CURRENT_FIXTURE,
                RENDER_RUNTIME_FIXTURE,
                output_directory,
            )
            coverage = validate_rendered_contract(
                output_directory,
                CURRENT_FIXTURE,
                KEYPAIR_FIXTURE,
            )

        self.assertEqual(len(rendered), 17)
        self.assertEqual(coverage["reality_inbounds"], 3)
        self.assertEqual(coverage["generic_inbounds"], 15)
        self.assertEqual(coverage["users"], 2)
        self.assertTrue(coverage["statistics"])


if __name__ == "__main__":
    unittest.main()
