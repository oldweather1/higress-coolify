import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from prepare_agenthub_gateway_credential import (CONSUMER, GateError, PHP, coolify_secret,
                                                consumer_payload, validate_key, verify_consumer)


class GatewayCredentialTests(unittest.TestCase):
    KEY = "fixture_gateway_key_DO_NOT_USE_1234567890"

    def test_bearer_only_separate_consumer(self):
        body = consumer_payload(self.KEY)
        self.assertEqual(body, {"name": CONSUMER, "credentials": [
            {"type": "key-auth", "source": "BEARER", "values": [self.KEY]}]})
        verify_consumer(body, self.KEY)

    def test_invalid_key_no_secret_in_failure(self):
        for key in ("", "short", " " + self.KEY, self.KEY + "\n", self.KEY + " ",
                    "a" * 129, "a" * 31, self.KEY + "!", self.KEY + "\u00a0"):
            with self.assertRaises(GateError) as caught:
                validate_key(key)
            if key:
                self.assertNotIn(key, str(caught.exception))

    def test_readback_mismatch_refused_without_output(self):
        for body in ({}, {"name": CONSUMER, "credentials": []},
                     {"name": CONSUMER, "credentials": [{"type": "key-auth", "source": "QUERY",
                                                          "values": [self.KEY]}]},
                     consumer_payload("x" * 40)):
            with self.assertRaises(GateError) as caught:
                verify_consumer(body, self.KEY)
            self.assertNotIn(self.KEY, str(caught.exception))

    def test_validation_and_verification_do_not_print_key(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            verify_consumer(consumer_payload(self.KEY), self.KEY)
        self.assertEqual(output.getvalue(), "")

    def test_native_storage_safety_contract(self):
        for guard in ("is_shown_once=true", "is_buildtime=false", "is_runtime=!$v->is_preview",
                      "EnvironmentVariable::withoutEvents", "unrelated-variables-unchanged",
                      "nativeEncryptedStorage", "empty-gateway-secret-required",
                      "is_raw_compose_deployment_enabled", "empty($a->fqdn)"):
            self.assertIn(guard, PHP)
        self.assertNotIn("delete(", PHP)

    def test_secret_transported_in_stdin_not_arguments_or_output(self):
        with patch("prepare_agenthub_gateway_credential.subprocess.run",
                   return_value=SimpleNamespace(returncode=0, stdout='{"secretSave":"PASS"}')) as run:
            self.assertEqual(coolify_secret(self.KEY), {"secretSave": "PASS"})
        arguments, keywords = run.call_args
        self.assertNotIn(self.KEY, repr(arguments))
        self.assertEqual(json.loads(keywords["input"]), {"apply": True, "value": self.KEY})
        self.assertTrue(keywords["capture_output"])

    def test_native_error_exposes_only_fixed_gate(self):
        for gate, expected in (("empty-gateway-secret-required", "empty-gateway-secret-required"),
                               (self.KEY, "operation-failed")):
            with patch("prepare_agenthub_gateway_credential.subprocess.run", return_value=SimpleNamespace(
                    returncode=1, stdout=json.dumps({"failure": True, "safeGate": gate}))):
                with self.assertRaises(GateError) as caught:
                    coolify_secret()
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn(self.KEY, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
