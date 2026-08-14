from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from ast_helpers import source_path


INSTALLER = source_path("install.sh")
UTILS = source_path("common/utils.sh")
REDIS_INSTALLER = source_path("other/redis/install.sh")


class InstallerReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer_source = INSTALLER.read_text(encoding="utf-8")
        cls.utils_source = UTILS.read_text(encoding="utf-8")
        cls.redis_source = REDIS_INSTALLER.read_text(encoding="utf-8")
        cls.bash = shutil.which("bash")

    def run_bash(self, script: str, *arguments: str, env: dict[str, str] | None = None):
        if self.bash is None:
            self.skipTest("bash is required for installer behavior regression tests")
        return subprocess.run(
            [self.bash, "-c", script, "installer-reliability", *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_runsh_preserves_child_exit_status_after_popd(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            component = Path(temporary_directory)
            (component / "install.sh").write_text("#!/bin/bash\nexit 23\n", encoding="utf-8")
            completed = self.run_bash(
                'source "$1"; runsh install.sh "$2"; exit $?',
                str(INSTALLER),
                str(component),
            )
        self.assertEqual(completed.returncode, 23, completed.stderr)

    def test_install_run_does_not_call_run_script_after_failed_install(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            component = Path(temporary_directory) / "component"
            component.mkdir()
            marker = Path(temporary_directory) / "run-called"
            (component / "install.sh").write_text("#!/bin/bash\nexit 29\n", encoding="utf-8")
            (component / "run.sh").write_text(
                '#!/bin/bash\ntouch "$RUN_MARKER"\n',
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["RUN_MARKER"] = str(marker)
            completed = self.run_bash(
                'source "$1"; MODE=release; DO_NOT_INSTALL=false; DO_NOT_RUN=false; '
                'systemctl() { return 0; }; install_run "$2"; exit $?',
                str(INSTALLER),
                str(component),
                env=environment,
            )
            self.assertFalse(marker.exists(), completed.stdout + completed.stderr)
        self.assertEqual(completed.returncode, 29, completed.stderr)

    def test_failed_package_installation_propagates_nonzero(self):
        completed = self.run_bash(
            'source "$1"; apt() { return 42; }; '
            'is_installed_package() { return 1; }; '
            'install_package redis-server; exit $?',
            str(UTILS),
        )
        self.assertEqual(completed.returncode, 42, completed.stderr)

    def test_missing_package_after_successful_apt_is_still_failure(self):
        completed = self.run_bash(
            'source "$1"; apt() { return 0; }; '
            'is_installed_package() { return 1; }; '
            'install_package redis-server; exit $?',
            str(UTILS),
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_foundational_and_component_installs_are_serialized(self):
        common = self.installer_source.index(
            'run_required_step "Common prerequisites installation"'
        )
        redis = self.installer_source.index('run_required_step "Redis installation"')
        mariadb = self.installer_source.index('run_required_step "MariaDB installation"')
        panel = self.installer_source.index('run_required_step "Panel installation"')
        self.assertLess(common, redis)
        self.assertLess(redis, mariadb)
        self.assertLess(mariadb, panel)
        for required_step in (
            'run_required_step "Common prerequisites installation"',
            'run_required_step "Redis installation"',
            'run_required_step "MariaDB installation"',
            'run_required_step "Panel installation"',
        ):
            step_line = next(
                line for line in self.installer_source.splitlines() if required_step in line
            )
            self.assertIn("|| return $?", step_line)
        self.assertNotRegex(
            self.installer_source,
            re.compile(r"^\s*(?:runsh|install_run)\b.*&\s*$", re.MULTILINE),
        )
        self.assertNotRegex(
            self.installer_source,
            re.compile(r"^\s*wait\s*$", re.MULTILINE),
        )

    def test_former_background_component_failure_stops_installation(self):
        completed = self.run_bash(
            'source "$1"; run_required_step "simulated component" '
            "bash -c 'exit 37'; exit $?",
            str(INSTALLER),
        )
        self.assertEqual(completed.returncode, 37, completed.stderr)

    def test_missing_redis_package_or_identity_is_fatal(self):
        missing_package = self.run_bash(
            'source "$1"; redis_package_installed() { return 1; }; '
            'redis_server_available() { return 0; }; redis_user_available() { return 0; }; '
            'redis_group_available() { return 0; }; verify_redis_package; exit $?',
            str(REDIS_INSTALLER),
        )
        self.assertNotEqual(missing_package.returncode, 0)

        missing_user = self.run_bash(
            'source "$1"; redis_package_installed() { return 0; }; '
            'redis_server_available() { return 0; }; redis_user_available() { return 1; }; '
            'redis_group_available() { return 0; }; verify_redis_package; exit $?',
            str(REDIS_INSTALLER),
        )
        self.assertNotEqual(missing_user.returncode, 0)

        for required_check in (
            "dpkg-query -W -f='${Status}' redis-server",
            "command -v redis-server",
            "getent passwd redis",
            "getent group redis",
        ):
            self.assertIn(required_check, self.redis_source)
        self.assertNotIn("useradd redis", self.redis_source)

    def test_redis_log_path_is_prepared_before_service_start(self):
        for required_operation in (
            'mkdir -p "$log_dir"',
            'touch "$log_file"',
            'chown redis:redis "$log_file"',
            "systemctl daemon-reload",
            "systemctl enable --now hiddify-redis",
        ):
            self.assertIn(required_operation, self.redis_source)

        main = self.redis_source[self.redis_source.index("redis_install_main()") :]
        self.assertLess(main.index("install_redis_package"), main.index("verify_redis_package"))
        self.assertLess(main.index("verify_redis_package"), main.index("prepare_redis_files"))
        self.assertLess(main.index("prepare_redis_files"), main.index("start_redis_service"))
        self.assertLess(main.index("start_redis_service"), main.index("wait_for_redis_readiness"))

    def test_redis_readiness_checks_service_port_and_authenticated_ping(self):
        for readiness_check in (
            "systemctl is-active --quiet hiddify-redis",
            '127.0.0.1:6379',
            'REDISCLI_AUTH="$redis_password" redis-cli',
            '[ "$response" = "PONG" ]',
        ):
            self.assertIn(readiness_check, self.redis_source)


if __name__ == "__main__":
    unittest.main()
