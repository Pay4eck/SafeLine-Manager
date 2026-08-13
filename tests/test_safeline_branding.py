from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from ast_helpers import source_path
from safeline.brand import BRAND


FRONTEND_ROOT = source_path("safeline/frontend")
STATIC_FRONTEND = source_path("safeline/static/user-front")


def normalized_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


class SafeLineBrandingTests(unittest.TestCase):
    def test_central_brand_values_match_release_scope(self):
        self.assertEqual(BRAND.product_name, "SafeLine")
        self.assertEqual(BRAND.full_name, "SafeLine VPN")
        self.assertEqual(BRAND.manager_name, "SafeLine Manager")
        self.assertEqual(BRAND.version, "0.1.0")

    def test_panel_entrypoint_uses_the_isolated_branding_wrapper(self):
        entrypoint = source_path("hiddify-panel/app.py").read_text(encoding="utf-8")
        self.assertIn("from safeline.branding import create_app", entrypoint)
        self.assertNotIn("hiddifypanel.create_app()", entrypoint)
        self.assertIn("/opt/hiddify-manager/.venv313/bin/python", entrypoint)

    def test_modern_profile_template_uses_safeline_assets_and_keeps_protocol_scheme(self):
        template = source_path("safeline/templates/new.html").read_text(encoding="utf-8")
        self.assertIn("<title>{{ brand.full_name }}</title>", template)
        self.assertIn("window.brand = {{ brand | tojson }}", template)
        self.assertIn("window.appVersion = window.brand.version", template)
        self.assertIn("../safeline-static/user-front/assets/", template)
        self.assertIn('window.deepLink = "hiddify://import/', template)
        self.assertNotIn("index-ccb9873c.js", template)

    def test_generated_frontend_contains_reviewed_product_branding(self):
        javascript_files = list((STATIC_FRONTEND / "assets").glob("index-*.js"))
        self.assertEqual(len(javascript_files), 1)
        javascript = javascript_files[0].read_text(encoding="utf-8")
        self.assertIn("Based on Hiddify Manager", javascript)
        self.assertIn("upstream_repository_url", javascript)
        self.assertIn("repository_url", javascript)
        self.assertNotIn("Powered by Hiddify", javascript)
        self.assertNotIn("youtube.com/@hiddify", javascript)
        self.assertNotIn("twitter.com/hiddify_com", javascript)
        # These are real compatible client names, not SafeLine product chrome.
        self.assertIn("Hiddify Next", javascript)

    def test_frontend_source_and_toolchain_are_locked(self):
        lock = json.loads((FRONTEND_ROOT / "frontend.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(
            lock["source_commit"],
            "5dc87f743f233b8fd0ff0c40b9a3ddbbe7c2812a",
        )
        self.assertEqual(
            lock["gh_pages_commit"],
            "2d3edc24321f80c3292465f4034c94e522d4031d",
        )
        self.assertEqual(lock["node_version"], "16.20.2")
        self.assertEqual(lock["yarn_version"], "1.22.22")
        patch = FRONTEND_ROOT / lock["patch"]
        self.assertEqual(normalized_sha256(patch), lock["patch_sha256"])

    def test_compatibility_layer_preserves_critical_identifiers(self):
        source = source_path("safeline/branding.py").read_text(encoding="utf-8")
        self.assertIn("import hiddifypanel", source)
        for forbidden_mutation in (
            "ALTER TABLE",
            "hiddify-panel.service =",
            "HIDDIFY_CFG_PATH =",
            "hiddify:// =",
        ):
            self.assertNotIn(forbidden_mutation, source)

    def test_profile_defaults_are_branded_without_overwriting_admin_customization(self):
        from safeline.branding import _brand_profile_payload

        config_module = types.ModuleType("hiddifypanel.models.config")
        enum_module = types.ModuleType("hiddifypanel.models.config_enum")
        panel_module = types.ModuleType("hiddifypanel")
        panel_module.__path__ = []
        models_module = types.ModuleType("hiddifypanel.models")
        models_module.__path__ = []
        enum_module.ConfigEnum = types.SimpleNamespace(
            branding_title="title",
            branding_freetext="message",
            branding_site="site",
        )

        def fake_url_for(endpoint, **values):
            self.assertEqual(endpoint, "safeline_brand.asset")
            return f"https://panel.example/{values['proxy_path']}/{values['filename']}"

        with patch.dict(
            sys.modules,
            {
                "hiddifypanel": panel_module,
                "hiddifypanel.models": models_module,
                "hiddifypanel.models.config": config_module,
                "hiddifypanel.models.config_enum": enum_module,
            },
        ):
            config_module.hconfig = lambda key: ""
            defaults = {
                "brand_title": "Hiddify",
                "brand_icon_url": "old.ico",
                "admin_message_html": "upstream",
                "admin_message_url": "https://t.me/hiddify",
            }
            _brand_profile_payload(defaults, "client", fake_url_for)
            self.assertEqual(defaults["brand_title"], "SafeLine VPN")
            self.assertIn("safeline-mark.svg", defaults["brand_icon_url"])
            self.assertEqual(defaults["admin_message_url"], BRAND.repository_url)

            config_module.hconfig = lambda key: f"custom-{key}"
            customized = {
                "brand_title": "Customer VPN",
                "brand_icon_url": "customer.ico",
                "admin_message_html": "Customer message",
                "admin_message_url": "https://customer.example",
            }
            _brand_profile_payload(customized, "client", fake_url_for)
            self.assertEqual(customized["brand_title"], "Customer VPN")
            self.assertEqual(customized["brand_icon_url"], "customer.ico")
            self.assertEqual(customized["admin_message_html"], "Customer message")
            self.assertEqual(customized["admin_message_url"], "https://customer.example")


if __name__ == "__main__":
    unittest.main()
