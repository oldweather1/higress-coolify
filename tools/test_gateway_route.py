import copy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from configure_agenthub_route import (CONSUMER, GATEWAY_HOST, GateError, MODEL, PATH, STAGE_HOST,
                                     await_denial, negative_checks, route_payload, verify_route)
from configure_agenthub_route import route_digest, verify_stage_proof


class ProtectedRouteTests(unittest.TestCase):
    def test_exact_model_and_bearer_auth_no_fallback_or_retry(self):
        body = route_payload(STAGE_HOST)
        self.assertEqual(body["authConfig"], {"enabled": True, "allowedCredentialTypes": ["key-auth"],
                                            "allowedConsumers": [CONSUMER]})
        self.assertEqual(body["modelPredicates"][0]["matchValue"], MODEL)
        self.assertEqual(body["modelPredicates"][0]["matchType"], "EQUAL")
        self.assertFalse(body["fallbackConfig"]["enabled"])
        self.assertFalse(body["proxyNextUpstream"]["enabled"])
        self.assertEqual(body["upstreams"][0]["modelMapping"], {MODEL: MODEL})
        self.assertEqual(body["headerPredicates"][0]["matchValue"], PATH)
        verify_route(body, STAGE_HOST)

    def test_reject_other_domain(self):
        with self.assertRaises(GateError):
            route_payload("different.example")

    def test_readback_rejects_security_drift(self):
        for field, replacement in (("authConfig", {"enabled": False}),
                                   ("domains", []), ("upstreams", []), ("modelPredicates", []),
                                   ("headerPredicates", []), ("fallbackConfig", {"enabled": True}),
                                   ("proxyNextUpstream", {"enabled": True})):
            body = copy.deepcopy(route_payload(GATEWAY_HOST))
            body[field] = replacement
            with self.assertRaises(GateError):
                verify_route(body, GATEWAY_HOST)

    def test_anonymous_propagation_only_no_key_retry(self):
        with patch("configure_agenthub_route.probe", side_effect=[(503, b""), (403, b"")]) as probe:
            with patch("configure_agenthub_route.time.sleep"):
                await_denial(None, "http://192.0.2.1", STAGE_HOST)
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(probe.call_args.args, (None, "http://192.0.2.1", STAGE_HOST))

    def test_anonymous_not_found_is_denial_not_inference_acceptance(self):
        with patch("configure_agenthub_route.probe", return_value=(404, b"")) as probe:
            await_denial(None, "http://192.0.2.1", STAGE_HOST)
        self.assertEqual(probe.call_count, 1)

    def test_anonymous_success_stops_without_repeated_request(self):
        with patch("configure_agenthub_route.probe", return_value=(200, b"fixture")) as probe:
            with self.assertRaises(GateError):
                await_denial(None, "http://192.0.2.1", STAGE_HOST)
        self.assertEqual(probe.call_count, 1)

    def test_spoof_or_other_model_not_accepted_on_vendor_error(self):
        with patch("configure_agenthub_route.probe", side_effect=[(403, b""), (400, b"")]) as probe:
            with self.assertRaises(GateError):
                negative_checks(None, "http://192.0.2.1", STAGE_HOST, "synthetic_gateway_key")
        self.assertEqual(probe.call_count, 2)

    def test_prior_stage_proof_binds_actual_route_key_and_container(self):
        route = route_payload(STAGE_HOST)
        key, snapshot = "synthetic_gateway_key", ("container-id", "start-time")
        proof = {"httpStatus": 200, "model": MODEL, "hasAssistantContent": True,
                 "source": "operator-observed-single-VPS-request", "routeDigest": route_digest(route),
                 "callerDigest": hashlib.sha256(key.encode()).hexdigest(), "higressSnapshot": list(snapshot)}
        mock = MagicMock()
        mock.is_symlink.return_value = False
        mock.stat.return_value = SimpleNamespace(st_uid=0, st_mode=0o600)
        mock.read_bytes.return_value = json.dumps(proof).encode()
        with patch("configure_agenthub_route.STAGE_PROOF", mock):
            verify_stage_proof(route, key, snapshot)
            for field, value in (("httpStatus", 404), ("hasAssistantContent", False),
                                 ("routeDigest", "different"), ("callerDigest", "different"),
                                 ("higressSnapshot", ["different", "start-time"])):
                changed = copy.deepcopy(proof)
                changed[field] = value
                mock.read_bytes.return_value = json.dumps(changed).encode()
                with self.assertRaises(GateError):
                    verify_stage_proof(route, key, snapshot)


if __name__ == "__main__":
    unittest.main()
