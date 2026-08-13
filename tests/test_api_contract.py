from __future__ import annotations

import unittest

from ast_helpers import (
    class_assignment_names,
    method_call_names,
    route_literals,
    string_literals,
)


ADMIN_API_INIT = "hiddify-panel/src/hiddifypanel/panel/commercial/restapi/v2/admin/__init__.py"
ADMIN_USER_API = "hiddify-panel/src/hiddifypanel/panel/commercial/restapi/v2/admin/user_api.py"
ADMIN_USERS_API = "hiddify-panel/src/hiddifypanel/panel/commercial/restapi/v2/admin/users_api.py"
ADMIN_SCHEMA = "hiddify-panel/src/hiddifypanel/panel/commercial/restapi/v2/admin/schema.py"
USER_API_INIT = "hiddify-panel/src/hiddifypanel/panel/commercial/restapi/v2/user/__init__.py"
AUTH = "hiddify-panel/src/hiddifypanel/auth.py"


class ApiContractTests(unittest.TestCase):
    def test_admin_api_exposes_user_collection_and_item_routes(self):
        routes = route_literals(ADMIN_API_INIT)
        self.assertIn("/user/", routes)
        self.assertIn("/user/<uuid:uuid>/", routes)

    def test_user_api_exposes_profile_and_config_routes(self):
        routes = route_literals(USER_API_INIT)
        self.assertTrue({"/me/", "/all-configs/", "/short/", "/apps/"}.issubset(routes))

    def test_user_schema_retains_bot_adapter_fields(self):
        fields = class_assignment_names(ADMIN_SCHEMA, "UserSchema")
        required_fields = {
            "uuid",
            "name",
            "usage_limit_GB",
            "package_days",
            "start_date",
            "current_usage_GB",
            "telegram_id",
            "enable",
            "is_active",
        }
        self.assertTrue(required_fields.issubset(fields), required_fields - fields)

    def test_create_user_updates_runtime_and_reapplies_user_configs(self):
        calls = method_call_names(ADMIN_USERS_API, "UsersApi", "post")
        required_calls = {
            "User.add_or_update",
            "user_driver.add_client",
            "hiddify.quick_apply_users",
        }
        self.assertTrue(required_calls.issubset(calls), required_calls - calls)

    def test_update_user_removes_old_runtime_identity_then_reapplies(self):
        calls = method_call_names(ADMIN_USER_API, "UserApi", "patch")
        required_calls = {
            "user_driver.remove_client",
            "User.add_or_update",
            "user_driver.add_client",
            "hiddify.quick_apply_users",
        }
        self.assertTrue(required_calls.issubset(calls), required_calls - calls)

    def test_delete_user_reapplies_runtime_configs(self):
        calls = method_call_names(ADMIN_USER_API, "UserApi", "delete")
        self.assertIn("user.remove", calls)
        self.assertIn("hiddify.quick_apply_users", calls)

    def test_legacy_api_header_name_remains_explicitly_characterized(self):
        self.assertIn("Hiddify-API-Key", string_literals(AUTH))


if __name__ == "__main__":
    unittest.main()
