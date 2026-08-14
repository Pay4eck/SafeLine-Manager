from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from ast_helpers import source_path


SMOKE_ROOT = source_path("smoke-test")


def canonical_text_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def parse_shell_lock(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


class LinuxSmokeInstallPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = parse_shell_lock(SMOKE_ROOT / "components.lock")
        cls.installer = (SMOKE_ROOT / "install-pinned.sh").read_text(encoding="utf-8")

    def test_bootstrap_accepts_only_an_exact_safeline_commit(self):
        self.assertIn(
            'readonly SAFELINE_REPOSITORY="https://github.com/Pay4eck/SafeLine-Manager.git"',
            self.installer,
        )
        self.assertIn('[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]', self.installer)
        self.assertIn('git -C "$INSTALL_ROOT" fetch --no-tags --depth=1 origin "$COMMIT"', self.installer)
        self.assertIn('[ "$ACTUAL_COMMIT" = "$COMMIT" ]', self.installer)
        for moving_ref in ("refs/heads/", "releases/latest", "/main/", "/master/"):
            self.assertNotIn(moving_ref, self.installer)

    def test_bootstrap_is_self_checksummed_for_the_handoff_command(self):
        checksum_line = (SMOKE_ROOT / "install-pinned.sh.sha256").read_text(encoding="ascii").strip()
        expected, filename = checksum_line.split()
        self.assertEqual(filename, "install-pinned.sh")
        self.assertEqual(
            hashlib.sha256((SMOKE_ROOT / filename).read_bytes()).hexdigest(),
            expected,
        )

    def test_uv_version_check_accepts_architecture_suffix_and_requires_exact_pin(self):
        self.assertIn("uv_output=$(/usr/local/bin/uv --version)", self.installer)
        self.assertIn('uv_version=$(parse_uv_semantic_version "$uv_output")', self.installer)
        self.assertIn('[ "$uv_version" = "$UV_VERSION" ]', self.installer)
        self.assertIn("/usr/local/bin/uv python install", self.installer)
        self.assertIn("/usr/local/bin/uv venv", self.installer)
        self.assertIn("/usr/local/bin/uv sync --frozen", self.installer)
        self.assertNotIn('$(uv --version)', self.installer)

        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is required for the installer parser regression test")

        parser = SMOKE_ROOT / "uv-version.sh"
        check_command = (
            'source "$1"; '
            'uv_version=$(parse_uv_semantic_version "$2") || exit 1; '
            'printf "%s\\n" "$uv_version"; '
            '[ "$uv_version" = "$3" ]'
        )
        completed = subprocess.run(
            [
                bash,
                "-c",
                check_command,
                "uv-version-regression",
                str(parser),
                "uv 0.11.16 (x86_64-unknown-linux-gnu)",
                "0.11.16",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "0.11.16")

        wrong_pin = subprocess.run(
            [
                bash,
                "-c",
                check_command,
                "uv-version-regression",
                str(parser),
                "uv 0.11.17 (x86_64-unknown-linux-gnu)",
                "0.11.16",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(wrong_pin.returncode, 0)

    def test_component_lock_matches_the_imported_panel_and_binary_locks(self):
        baseline = json.loads(source_path("tests/fixtures/upstream-v12.3.3.json").read_text(encoding="utf-8"))
        self.assertEqual(self.lock["PANEL_COMMIT"], baseline["panel"]["commit"])
        self.assertEqual(self.lock["PANEL_VERSION"], "12.3.3")
        self.assertEqual(self.lock["XRAY_VERSION"], "26.3.27")
        self.assertEqual(self.lock["SINGBOX_VERSION"], "4.0.4")
        self.assertEqual(self.lock["UV_VERSION"], "0.11.16")
        self.assertEqual(self.lock["PYTHON_VERSION"], "3.13.9")

        self.assertEqual(
            canonical_text_sha256(source_path("common/packages.lock")),
            self.lock["PACKAGES_LOCK_SHA256"],
        )
        self.assertEqual(
            canonical_text_sha256(source_path("hiddify-panel/src/uv.lock")),
            self.lock["PANEL_UV_LOCK_SHA256"],
        )

        packages = source_path("common/packages.lock").read_text(encoding="utf-8")
        self.assertRegex(
            packages,
            re.compile(
                rf"^xray\|{re.escape(self.lock['XRAY_VERSION'])}\|amd64\|[^\n]+\|{self.lock['XRAY_AMD64_SHA256']}$",
                re.MULTILINE,
            ),
        )
        self.assertRegex(
            packages,
            re.compile(
                rf"^singbox\|{re.escape(self.lock['SINGBOX_VERSION'])}\|amd64\|[^\n]+\|{self.lock['SINGBOX_AMD64_SHA256']}$",
                re.MULTILINE,
            ),
        )

    def test_panel_install_uses_frozen_dependencies_only_in_smoke_mode(self):
        panel_install = source_path("hiddify-panel/install.sh").read_text(encoding="utf-8")
        self.assertIn("SAFELINE_SMOKE_TEST_MODE", panel_install)
        self.assertIn("uv sync --frozen --no-dev", panel_install)
        self.assertIn('uv pip install -e "$HIDDIFY_PANLE_SOURCE_DIR"', panel_install)

    def test_smoke_profile_precedes_component_rendering_and_disables_updates(self):
        install = source_path("install.sh").read_text(encoding="utf-8")
        hook = 'bash ./smoke-test/configure-profile.sh'
        self.assertLess(install.index(hook), install.index("set_config_from_hpanel"))
        profile = (SMOKE_ROOT / "configure-profile.sh").read_text(encoding="utf-8")
        for required in (
            "auto_update=false",
            "core_type=xray",
            "vless_enable=true",
            "reality_enable=true",
            "warp_mode=disable",
            "wireguard_enable=false",
            "dnstt_enable=false",
            "hiddifycli_enable=false",
        ):
            self.assertIn(required, profile)

    def test_all_legacy_manager_panel_bootstraps_fail_before_upstream_fetch(self):
        guarded_files = (
            "update.sh",
            "common/download.sh",
            "common/download_install.sh",
            "common/download_install_easylink.sh",
            "common/downgrade.sh",
            "common/docker-installer.sh",
            "common/hiddify_installer.sh",
        )
        for relative in guarded_files:
            source = source_path(relative).read_text(encoding="utf-8")
            self.assertIn("exit 78", source, relative)
            first_exit = source.index("exit 78")
            remote_positions = [
                source.find(token)
                for token in (
                    "raw.githubusercontent.com/hiddify",
                    "github.com/hiddify/Hiddify-Manager",
                    "github.com/hiddify/hiddify-manager/releases",
                    "git+https://github.com/hiddify/HiddifyPanel",
                )
                if source.find(token) >= 0
            ]
            if remote_positions:
                self.assertLess(first_exit, min(remote_positions), relative)

        compose = source_path("docker-compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("ghcr.io/hiddify/hiddify-manager", compose)
        self.assertIn("build: .", compose)
        cloud_init = source_path("cloud-init.yml").read_text(encoding="utf-8")
        self.assertNotIn("git clone", cloud_init)

    def test_document_contains_every_mandatory_acceptance_area(self):
        document = source_path("docs/LINUX_SMOKE_TEST.md").read_text(encoding="utf-8")
        for heading in (
            "### System",
            "### Web",
            "### User lifecycle",
            "### Reality",
            "### Real client connection (the actual acceptance criterion)",
            "### Reboot",
            "## Removal and rollback",
        ):
            self.assertIn(heading, document)
        self.assertIn("install-pinned.sh.sha256", document)
        self.assertIn("xray run -test", document)
        self.assertIn("destroy the disposable VPS", document)


if __name__ == "__main__":
    unittest.main()
