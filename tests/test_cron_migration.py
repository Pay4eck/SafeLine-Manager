from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

from ast_helpers import source_path


COMMON_INSTALLER = source_path("common/install.sh")
CRON_JOBS = source_path("common/cron_jobs.sh")
EXPECTED_ENTRY = (
    "@daily root /opt/hiddify-manager/common/daily_actions.sh >> "
    "/opt/hiddify-manager/log/system/daily_actions.log 2>&1\n"
)


class DailyCronMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        cls.common_installer_source = COMMON_INSTALLER.read_text(encoding="utf-8")
        cls.cron_source = CRON_JOBS.read_text(encoding="utf-8")

    def run_installer(
        self,
        cron_directory: Path,
        reload_marker: Path,
        *,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if self.bash is None:
            self.skipTest("bash is required for cron migration regression tests")
        test_environment = os.environ.copy()
        if environment:
            test_environment.update(environment)
        test_environment.update(
            {
                "HIDDIFY_CRON_DIR": str(cron_directory),
                "HIDDIFY_MANAGER_ROOT": "/opt/hiddify-manager",
                "RELOAD_MARKER": str(reload_marker),
            }
        )
        return subprocess.run(
            [
                self.bash,
                "-c",
                'source "$1"; '
                "chown() { return 0; }; "
                'service() { [ "$1" = cron ] && [ "$2" = reload ] || return 80; '
                '[ -f "$HIDDIFY_CRON_DIR/hiddify_daily" ] || return 81; '
                'printf "reloaded\\n" >> "$RELOAD_MARKER"; }; '
                "install_daily_cron",
                "cron-migration",
                str(CRON_JOBS),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=test_environment,
        )

    def test_clean_install_without_legacy_file_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cron_directory = Path(temporary_directory) / "cron.d"
            cron_directory.mkdir()
            reload_marker = Path(temporary_directory) / "cron-reloaded"

            completed = self.run_installer(cron_directory, reload_marker)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(reload_marker.is_file())
            self.assertFalse((cron_directory / "hiddify_daily_memory_release").exists())

    def test_upgrade_removes_legacy_file_and_writes_current_entry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cron_directory = Path(temporary_directory) / "cron.d"
            cron_directory.mkdir()
            legacy_path = cron_directory / "hiddify_daily_memory_release"
            legacy_path.write_text("legacy\n", encoding="utf-8")
            reload_marker = Path(temporary_directory) / "cron-reloaded"

            completed = self.run_installer(cron_directory, reload_marker)

            target_path = cron_directory / "hiddify_daily"
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(legacy_path.exists())
            self.assertEqual(target_path.read_text(encoding="utf-8"), EXPECTED_ENTRY)
            self.assertEqual(stat.S_IMODE(target_path.stat().st_mode), 0o644)

    def test_repeated_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cron_directory = Path(temporary_directory) / "cron.d"
            cron_directory.mkdir()
            reload_marker = Path(temporary_directory) / "cron-reloaded"

            first = self.run_installer(cron_directory, reload_marker)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_content = (cron_directory / "hiddify_daily").read_bytes()
            second = self.run_installer(cron_directory, reload_marker)

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual((cron_directory / "hiddify_daily").read_bytes(), first_content)
            self.assertEqual(reload_marker.read_text(encoding="utf-8"), "reloaded\nreloaded\n")
            self.assertEqual(
                sorted(path.name for path in cron_directory.iterdir()),
                ["hiddify_daily"],
            )

    @unittest.skipIf(os.name == "nt", "POSIX directory permissions are required")
    def test_real_cron_write_error_remains_fatal_and_does_not_reload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cron_directory = Path(temporary_directory) / "cron.d"
            cron_directory.mkdir()
            reload_marker = Path(temporary_directory) / "cron-reloaded"
            cron_directory.chmod(0o500)
            try:
                completed = self.run_installer(cron_directory, reload_marker)
            finally:
                cron_directory.chmod(0o700)

            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(reload_marker.exists())
            self.assertFalse((cron_directory / "hiddify_daily").exists())

    def test_common_installer_uses_fail_fast_cron_migration(self):
        self.assertIn("source cron_jobs.sh || exit $?", self.common_installer_source)
        self.assertIn("install_daily_cron || exit $?", self.common_installer_source)
        self.assertNotIn(
            "mv /etc/cron.d/hiddify_daily_memory_release",
            self.common_installer_source,
        )
        self.assertIn('chmod 0644 "$temp_path"', self.cron_source)
        self.assertIn('chown root:root "$temp_path"', self.cron_source)
        self.assertLess(
            self.cron_source.index('mv -fT -- "$temp_path" "$target_path"'),
            self.cron_source.index("service cron reload"),
        )


if __name__ == "__main__":
    unittest.main()
