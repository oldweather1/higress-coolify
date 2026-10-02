import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("reset_console_password", Path(__file__).with_name("reset_console_password.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PasswordValidationTest(unittest.TestCase):
    def test_matching_password(self):
        module.validate_password("example-fixture-new-1", "example-fixture-new-1", "fixture-old")

    def test_unicode(self):
        module.validate_password("测试密码仅用于测试-123456", "测试密码仅用于测试-123456", "fixture-old")

    def test_mismatch(self):
        with self.assertRaises(ValueError):
            module.validate_password("example-fixture-new-1", "example-fixture-new-2", "fixture-old")

    def test_short_or_control_character(self):
        for value in ("short", "test-password\nsecret", "x" * 257):
            with self.assertRaises(ValueError):
                module.validate_password(value, value, "fixture-old")

    def test_same_as_previous(self):
        with self.assertRaises(ValueError):
            module.validate_password("same-fixture-123", "same-fixture-123", "same-fixture-123")

    def test_redirects_refused(self):
        with self.assertRaises(RuntimeError):
            module.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.example")


if __name__ == "__main__":
    unittest.main()
