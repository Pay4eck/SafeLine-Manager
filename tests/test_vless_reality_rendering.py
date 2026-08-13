from __future__ import annotations

import copy
import json
import unittest

import json5
from jinja2 import BaseLoader, Environment, TemplateNotFound

from ast_helpers import REPOSITORY_ROOT, source_path


REALITY_TEMPLATE = "xray/configs/05_inbounds_02_reality_main.json.j2"
CONTEXT_FIXTURE = "tests/fixtures/vless-reality-context.json"
UPSTREAM_INSTALL_PREFIX = "opt/hiddify-manager/"


class RepositoryTemplateLoader(BaseLoader):
    """Map upstream absolute include names onto this repository checkout."""

    def get_source(self, environment: Environment, template: str):
        normalized_name = template.replace("\\", "/").lstrip("/")
        if normalized_name.startswith(UPSTREAM_INSTALL_PREFIX):
            normalized_name = normalized_name[len(UPSTREAM_INSTALL_PREFIX):]

        candidate = (REPOSITORY_ROOT / normalized_name).resolve()
        try:
            candidate.relative_to(REPOSITORY_ROOT)
        except ValueError as error:
            raise TemplateNotFound(template) from error

        if not candidate.is_file():
            raise TemplateNotFound(template)

        source = candidate.read_text(encoding="utf-8-sig")
        original_stat = candidate.stat()

        def is_up_to_date() -> bool:
            try:
                current_stat = candidate.stat()
            except OSError:
                return False
            return (
                current_stat.st_mtime_ns == original_stat.st_mtime_ns
                and current_stat.st_size == original_stat.st_size
            )

        return source, str(candidate), is_up_to_date


class VlessRealityRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = json.loads(source_path(CONTEXT_FIXTURE).read_text(encoding="utf-8"))
        cls.environment = Environment(
            loader=RepositoryTemplateLoader(),
            autoescape=False,
            keep_trailing_newline=True,
        )

    def render(self, context=None):
        template = self.environment.get_template(REALITY_TEMPLATE)
        rendered = template.render(**(context or copy.deepcopy(self.context)))
        return json5.loads(rendered)

    def test_tcp_reality_inbound_renders_as_valid_json5(self):
        rendered = self.render()
        self.assertEqual(len(rendered["inbounds"]), 1)

        inbound = rendered["inbounds"][0]
        self.assertEqual(inbound["tag"], "realityin_tcp_12000")
        self.assertEqual(inbound["listen"], "@@realityin_12000")
        self.assertEqual(inbound["protocol"], "vless")
        self.assertEqual(inbound["settings"]["decryption"], "none")

    def test_active_users_are_rendered_with_expected_runtime_identity(self):
        clients = self.render()["inbounds"][0]["settings"]["clients"]
        expected_uuids = [user["uuid"] for user in self.context["users"]]
        self.assertEqual([client["id"] for client in clients], expected_uuids)
        self.assertEqual(
            [client["email"] for client in clients],
            [f"{uuid}@hiddify.com" for uuid in expected_uuids],
        )
        self.assertTrue(all(client["flow"] == "xtls-rprx-vision" for client in clients))

    def test_reality_tls_settings_preserve_sni_key_and_short_id(self):
        settings = self.render()["inbounds"][0]["streamSettings"]["realitySettings"]
        self.assertFalse(settings["show"])
        self.assertEqual(settings["dest"], "www.cloudflare.com:443")
        self.assertEqual(settings["serverNames"], ["www.cloudflare.com"])
        self.assertEqual(settings["privateKey"], "safeline-test-reality-private-key")
        self.assertEqual(settings["shortIds"], ["", "0123456789abcdef"])

    def test_debug_log_level_enables_reality_diagnostics(self):
        context = copy.deepcopy(self.context)
        context["hconfigs"]["log_level"] = "DEBUG"
        settings = self.render(context)["inbounds"][0]["streamSettings"]["realitySettings"]
        self.assertTrue(settings["show"])

    def test_disabled_reality_renders_an_empty_document(self):
        context = copy.deepcopy(self.context)
        context["hconfigs"]["reality_enable"] = False
        self.assertEqual(self.render(context), {})

    def test_non_xray_core_does_not_render_tcp_reality_inbound(self):
        context = copy.deepcopy(self.context)
        context["hconfigs"]["core_type"] = "singbox"
        self.assertEqual(self.render(context)["inbounds"], [])


if __name__ == "__main__":
    unittest.main()
