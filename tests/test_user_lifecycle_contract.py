from __future__ import annotations

import datetime
import unittest

from ast_helpers import compile_method


USER_MODEL = "hiddify-panel/src/hiddifypanel/models/user.py"


class Account:
    def __init__(
        self,
        *,
        enable: bool = True,
        usage_limit: int = 100,
        current_usage: int = 0,
        remaining_days: int = 30,
    ):
        self.enable = enable
        self.usage_limit = usage_limit
        self.current_usage = current_usage
        self.remaining_days = remaining_days


class MissingAccount:
    def __bool__(self):
        return False


class UserLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.is_active = staticmethod(compile_method(USER_MODEL, "User", "is_active"))
        cls.remaining_days = staticmethod(
            compile_method(
                USER_MODEL,
                "User",
                "remaining_days",
                globals_namespace={"datetime": datetime},
            )
        )

    def test_enabled_user_inside_quota_and_time_is_active(self):
        self.assertTrue(self.is_active(Account()))

    def test_disabled_or_missing_user_is_inactive(self):
        self.assertFalse(self.is_active(Account(enable=False)))
        self.assertFalse(self.is_active(MissingAccount()))

    def test_usage_above_limit_is_inactive(self):
        self.assertFalse(self.is_active(Account(usage_limit=100, current_usage=101)))

    def test_usage_exactly_at_limit_remains_active_in_upstream(self):
        self.assertTrue(self.is_active(Account(usage_limit=100, current_usage=100)))

    def test_negative_remaining_days_is_inactive_but_zero_is_active(self):
        self.assertFalse(self.is_active(Account(remaining_days=-1)))
        self.assertTrue(self.is_active(Account(remaining_days=0)))

    def test_package_without_start_date_has_full_duration_remaining(self):
        account = Account()
        account.package_days = 90
        account.start_date = None
        self.assertEqual(self.remaining_days(account), 90)

    def test_started_package_counts_elapsed_calendar_days(self):
        account = Account()
        account.package_days = 30
        account.start_date = datetime.date.today() - datetime.timedelta(days=12)
        self.assertEqual(self.remaining_days(account), 18)

    def test_missing_package_duration_is_expired(self):
        account = Account()
        account.package_days = None
        account.start_date = None
        self.assertEqual(self.remaining_days(account), -1)


if __name__ == "__main__":
    unittest.main()
