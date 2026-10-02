import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, MagicMock
import urllib.error

spec = importlib.util.spec_from_file_location("configure_zhipu_provider", Path(__file__).with_name("configure_zhipu_provider.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProviderSafetyTest(unittest.TestCase):
    def test_standard_api_only(self):
        payload = module.provider_payload("fixture-only-not-a-real-key")
        self.assertEqual(payload["type"], "zhipuai")
        self.assertEqual(payload["protocol"], "openai/v1")
        self.assertIs(payload["rawConfigs"]["zhipuCodePlanMode"], False)
        self.assertEqual(payload["rawConfigs"]["zhipuDomain"], "open.bigmodel.cn")
        self.assertEqual(payload["rawConfigs"]["modelMapping"], {"glm-4-flash-250414": "glm-4-flash-250414"})
        self.assertNotIn("fallbackConfig", payload)

    def test_key_rejected_if_empty_or_contains_whitespace(self):
        for key in ("", "fixture key", " fixture", "fixture\n", "fixture\tkey"):
            with self.assertRaises(module.ApiFailure):
                module.provider_payload(key)

    def test_input_rejection_stage_is_specific_without_echoing_input(self):
        cases = [("", "key-input-empty"),
                 (" fixture-secret", "key-input-leading-or-trailing-whitespace"),
                 ("fixture-secret ", "key-input-leading-or-trailing-whitespace"),
                 ("fixture-secret\n", "key-input-leading-or-trailing-whitespace"),
                 ("fixture-secret\x1b", "key-input-control-character"),
                 ("fixture-secret\x7f", "key-input-control-character"),
                 ("fixture secret", "key-input-internal-whitespace"),
                 ("fixture\u00a0secret", "key-input-internal-whitespace")]
        for key, stage in cases:
            with self.assertRaises(module.ApiFailure) as captured:
                module.provider_payload(key)
            self.assertTrue(captured.exception.stage.startswith(stage))
            self.assertIn("no model request sent", captured.exception.stage)
            self.assertNotIn("fixture", captured.exception.stage)

    def test_verification_checks_token_without_error_echo(self):
        expected = module.provider_payload("fixture-only-not-a-real-key")
        module.verify_provider(expected, expected)
        actual = dict(expected, tokens=["different-fixture-key"])
        with self.assertRaises(module.ApiFailure) as captured:
            module.verify_provider(actual, expected)
        self.assertNotIn("fixture", captured.exception.stage)

    def test_code_plan_cannot_be_silently_enabled(self):
        expected = module.provider_payload("fixture-only-not-a-real-key")
        actual = dict(expected, rawConfigs=dict(expected["rawConfigs"], zhipuCodePlanMode=True))
        with self.assertRaises(module.ApiFailure):
            module.verify_provider(actual, expected)

    def test_error_body_exposes_only_allowlisted_code(self):
        for code in ("1302", 1305, "1113"):
            body = io.BytesIO(json.dumps({"error": {"code": code,
                "message": "fixture-secret-must-not-be-printed"}}).encode())
            self.assertEqual(module.safe_vendor_error_code(body), str(code))

    def test_untrusted_error_codes_and_bodies_are_not_echoed(self):
        bodies = [b"not json", b"[]", b"x" * 4097,
                  b'{"error":{"code":true}}',
                  b'{"error":{"code":"1302\\nfixture-secret"}}',
                  b'{"error":{"code":"9999"}}']
        for body in bodies:
            self.assertIsNone(module.safe_vendor_error_code(io.BytesIO(body)))

    def test_vendor_failure_is_one_request_no_retry_and_no_secret_in_exception(self):
        fixture_key = "fixture-only-not-a-real-key"
        error = urllib.error.HTTPError(module.VENDOR_URL, 429, "Too Many Requests", {},
            io.BytesIO(json.dumps({"error": {"code": "1305", "message": fixture_key}}).encode()))
        opener = Mock()
        opener.open.side_effect = error
        with self.assertRaises(module.ApiFailure) as captured:
            module.vendor_probe(opener, fixture_key)
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(captured.exception.status, 429)
        self.assertEqual(captured.exception.vendor_code, "1305")
        self.assertNotIn(fixture_key, str(captured.exception))
        self.assertNotIn(fixture_key, repr(captured.exception))

    def test_replacement_probe_uses_exact_free_model_without_thinking_options(self):
        fixture_key = "fixture-only-not-a-real-key"
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices":[{"message":{"content":"OK"}}]}'
        opener = Mock()
        opener.open.return_value = response
        output = io.StringIO()
        with redirect_stdout(output):
            module.vendor_probe(opener, fixture_key)
        self.assertEqual(opener.open.call_count, 1)
        request = opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, module.VENDOR_URL)
        self.assertEqual(payload["model"], "glm-4-flash-250414")
        self.assertNotIn("thinking", payload)
        self.assertEqual(payload["max_tokens"], 128)
        self.assertIs(payload["stream"], False)
        self.assertNotIn(fixture_key, output.getvalue())


if __name__ == "__main__":
    unittest.main()
