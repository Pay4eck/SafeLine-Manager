from __future__ import annotations

import re
import unittest

from ast_helpers import read_source


REALITY_TEMPLATE = "xray/configs/05_inbounds_02_reality_main.json.j2"
VLESS_TEMPLATE = "xray/configs/common/protocols/vless.pj2"
XRAY_DRIVER = "hiddify-panel/src/hiddifypanel/drivers/xray_api.py"
PANEL_EXPORT = "hiddify-panel/src/hiddifypanel/panel/hiddify.py"


class VlessRealityContractTests(unittest.TestCase):
    def test_reality_template_keeps_vless_and_reality_security(self):
        template = read_source(REALITY_TEMPLATE)
        required_fragments = {
            "{%set protocol='vless'%}",
            '"security": "reality"',
            '"privateKey": "{{hconfigs[\'reality_private_key\']}}"',
            '"serverNames":',
            '"shortIds":',
            '"acceptProxyProtocol": true',
            '"tcpFastOpen": true',
        }
        missing = {fragment for fragment in required_fragments if fragment not in template}
        self.assertEqual(missing, set())

    def test_reality_template_supports_current_xray_transport_modes(self):
        template = read_source(REALITY_TEMPLATE)
        for mode in ("special_reality_tcp", "special_reality_grpc", "special_reality_xhttp"):
            self.assertIn(mode, template)
        self.assertIn("internal_port_special", template)
        self.assertIn("reality_enable", template)

    def test_vless_clients_are_generated_from_active_user_uuids(self):
        template = read_source(VLESS_TEMPLATE)
        self.assertIn("{% for u in users %}", template)
        self.assertIn('"id": "{{ u[\'uuid\'] }}"', template)
        self.assertIn('"flow": "{{flow}}"', template)
        self.assertIn('"decryption": "none"', template)

    def test_template_and_usage_driver_share_runtime_email_suffix(self):
        template = read_source(VLESS_TEMPLATE)
        driver = read_source(XRAY_DRIVER)
        suffix_match = re.search(r'@([a-z0-9.-]+)"', template)
        self.assertIsNotNone(suffix_match)
        suffix = suffix_match.group(1)
        self.assertIn(f'splt[1]=="{suffix}"', driver)

    def test_panel_exports_only_active_users_for_runtime_rendering(self):
        source = read_source(PANEL_EXPORT)
        self.assertIn("def all_configs_for_cli():", source)
        self.assertIn("User.usage_limit > User.current_usage", source)
        self.assertIn("if u.is_active", source)
        self.assertIn('"users": valid_users', source)
        self.assertIn('"domains":', source)
        self.assertIn('"chconfigs":', source)

    def test_config_pipeline_exports_snapshot_and_renders_jinja(self):
        utilities = read_source("common/utils.sh")
        replacement = read_source("common/replace_variables.sh")
        renderer = read_source("common/jinja.py")
        self.assertIn("reload_all_configs", utilities)
        self.assertIn("/opt/hiddify-manager/current.json", utilities)
        self.assertIn("/opt/hiddify-manager/common/jinja.py $MODE", replacement)
        self.assertIn('with open("/opt/hiddify-manager/current.json")', renderer)
        self.assertIn("render_j2_templates", renderer)

    def test_runtime_package_lock_has_hashes_for_both_supported_architectures(self):
        rows = []
        for line in read_source("common/packages.lock").splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            self.assertEqual(len(parts), 5, line)
            name, version, architecture, url, digest = parts
            self.assertIn(architecture, {"amd64", "arm64"})
            self.assertRegex(url, r"^https://")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            rows.append((name, version, architecture))

        for name, version in (("xray", "26.3.27"), ("singbox", "4.0.4")):
            architectures = {
                architecture
                for row_name, row_version, architecture in rows
                if row_name == name and row_version == version
            }
            self.assertEqual(architectures, {"amd64", "arm64"})


if __name__ == "__main__":
    unittest.main()
