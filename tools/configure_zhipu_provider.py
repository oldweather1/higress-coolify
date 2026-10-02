"""Operator-entered API key onboarding on the approved VPS; no route creation."""

import base64
import datetime
import getpass
import json
import os
from pathlib import Path
import resource
import runpy
import socket
import sys
import urllib.error
import urllib.request
import warnings

PROVIDER_NAME = "zhipu-free"
MODEL = "glm-4-flash-250414"
VENDOR_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
HELPER = Path("/root/higress-console-reset-20261002.py")
VENDOR_ERROR_REASONS = {
    "1000": "authentication-failed", "1001": "authentication-header-missing",
    "1003": "authentication-expired", "1005": "second-factor-required",
    "1113": "account-arrears", "1210": "invalid-request-parameters",
    "1211": "model-not-found", "1220": "api-access-denied",
    "1302": "account-rate-limit", "1305": "model-overloaded",
    "1308": "usage-limit", "1309": "coding-plan-expired",
    "1310": "weekly-or-monthly-limit", "1311": "model-not-in-plan",
    "1313": "fair-use-restriction", "1314": "enterprise-plan-inactive",
    "1315": "enterprise-coding-key-only", "1316": "five-hour-limit-and-no-balance",
    "1317": "seven-day-limit-and-no-balance", "1318": "five-hour-and-subaccount-limit",
    "1319": "seven-day-and-subaccount-limit", "1320": "five-hour-and-enterprise-limit",
    "1321": "seven-day-and-enterprise-limit",
}


class ApiFailure(Exception):
    def __init__(self, stage, status=None, vendor_code=None):
        self.stage = stage
        self.status = status
        self.vendor_code = vendor_code if vendor_code in VENDOR_ERROR_REASONS else None


def safe_vendor_error_code(error):
    """Read bounded JSON; expose only an allowlisted code, never message/headers."""
    try:
        raw = error.read(4097)
        if len(raw) > 4096:
            return None
        body = json.loads(raw)
        detail = body.get("error") if isinstance(body, dict) else None
        code = detail.get("code") if isinstance(detail, dict) else None
        if isinstance(code, int) and not isinstance(code, bool):
            code = str(code)
        return code if isinstance(code, str) and code in VENDOR_ERROR_REASONS else None
    except Exception:
        return None


def provider_payload(key):
    if not key:
        raise ApiFailure("key-input-empty; no model request sent")
    if key != key.strip():
        raise ApiFailure("key-input-leading-or-trailing-whitespace; no model request sent")
    if any(ord(c) < 32 or ord(c) == 127 for c in key):
        raise ApiFailure("key-input-control-character; no model request sent")
    if any(c.isspace() for c in key):
        raise ApiFailure("key-input-internal-whitespace; no model request sent")
    return {
        "name": PROVIDER_NAME,
        "type": "zhipuai",
        "protocol": "openai/v1",
        "tokens": [key],
        "rawConfigs": {
            "zhipuDomain": "open.bigmodel.cn",
            "zhipuCodePlanMode": False,
            "modelMapping": {MODEL: MODEL},
        },
    }


def request(opener, url, stage, payload=None):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with opener.open(req, timeout=30) as response:
            body = json.loads(response.read(1024 * 1024))
            if not isinstance(body, dict) or body.get("success") is False:
                raise ApiFailure(stage, response.status)
            return body.get("data", body)
    except urllib.error.HTTPError as error:
        raise ApiFailure(stage, error.code) from None


def items(body):
    if isinstance(body, dict):
        body = body.get("data", body.get("items"))
    if not isinstance(body, list):
        raise ApiFailure("inventory-shape")
    return body


def inventory(opener, base):
    providers = items(request(opener, base + "/v1/ai/providers", "provider-inventory"))
    routes = items(request(opener, base + "/v1/ai/routes", "route-inventory"))
    if providers or routes:
        raise ApiFailure("existing-provider-or-route; no overwrite permitted")


def vendor_probe(opener, key):
    req = urllib.request.Request(
        VENDOR_URL,
        data=json.dumps({
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with OK only."}],
            "max_tokens": 128,
            "stream": False,
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with opener.open(req, timeout=30) as response:
            body = json.loads(response.read(65536))
    except urllib.error.HTTPError as error:
        code = safe_vendor_error_code(error)
        error.close()
        raise ApiFailure("zhipu-free-model-probe", error.code, code) from None
    choices = body.get("choices")
    if not choices or not choices[0].get("message", {}).get("content"):
        raise ApiFailure("zhipu-free-model-response")
    # Do not print response text, authorization headers or any key fragment.
    print("ZHIPU_FREE_MODEL_PROBE: PASS (VPS, " + MODEL + " only)", flush=True)


def verify_provider(result, expected):
    if not isinstance(result, dict):
        raise ApiFailure("provider-save-response")
    for field in ("name", "type", "protocol", "tokens"):
        if result.get(field) != expected[field]:
            raise ApiFailure("provider-persistence-" + field)
    raw = result.get("rawConfigs", {})
    for field in ("zhipuDomain", "zhipuCodePlanMode", "modelMapping"):
        if raw.get(field) != expected["rawConfigs"][field]:
            raise ApiFailure("provider-persistence-" + field)


def main(diagnose_only=False):
    if os.geteuid() != 0 or socket.gethostname() != "srv1399091" or not sys.stdin.isatty():
        raise ApiFailure("wrong-host-or-noninteractive")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    warnings.simplefilter("error", getpass.GetPassWarning)
    if HELPER.is_symlink() or HELPER.stat().st_uid != 0 or HELPER.stat().st_mode & 0o077:
        raise ApiFailure("untrusted-admin-helper")
    helper = runpy.run_path(str(HELPER))
    admin = helper["client"]()
    before_container = helper["container_snapshot"]()
    secret_bytes = helper["read_secret"]()[0]
    password = base64.b64decode(helper["read_secret"]()[1]["adminPassword"]).decode()
    helper["login"](admin, password)
    base = helper["BASE_URL"]
    inventory(admin, base)
    print("PRECHECK: authenticated Higress; providers=0, AI routes=0", flush=True)
    print("SAVE SCOPE: zhipu-free, standard BigModel API, " + MODEL + " only.", flush=True)
    print("No AI route will be created; Agent Hub remains private and unchanged.", flush=True)
    if diagnose_only:
        print("DIAGNOSTIC ONLY: one BigModel request; no key/provider/route will be saved.", flush=True)
    else:
        print("Your key will be stored by Higress after one successful BigModel free-model probe.", flush=True)
    print("Paste only your existing API key, without a label, spaces or line breaks. Input is hidden.", flush=True)
    key = getpass.getpass("Paste Zhipu API Key (hidden); Enter submits: ")
    payload = provider_payload(key)
    inventory(admin, base)
    if helper["container_snapshot"]() != before_container or helper["read_secret"]()[0] != secret_bytes:
        raise ApiFailure("concurrent-admin-or-container-change")
    vendor_probe(helper["client"](), key)
    if diagnose_only:
        print("DIAGNOSTIC: PASS; key not saved; Higress and Agent Hub unchanged", flush=True)
        return
    request(admin, base + "/v1/ai/providers", "provider-save", payload)
    result = request(admin, base + "/v1/ai/providers/" + PROVIDER_NAME, "provider-readback")
    verify_provider(result, payload)
    providers = items(request(admin, base + "/v1/ai/providers", "final-provider-inventory"))
    routes = items(request(admin, base + "/v1/ai/routes", "final-route-inventory"))
    if len(providers) != 1 or providers[0].get("name") != PROVIDER_NAME or routes:
        raise ApiFailure("unexpected-provider-or-route")
    if helper["container_snapshot"]() != before_container or helper["read_secret"]()[0] != secret_bytes:
        raise ApiFailure("unexpected-admin-or-container-change")
    print("HIGRESS_ZHIPU_PROVIDER: PASS; token equality checked without display", flush=True)
    print("AI_ROUTES: 0; authenticated gateway route NOT CONFIGURED yet", flush=True)
    print("NO_CONTAINER_RESTART: PASS; no Agent Hub/Casdoor/MySQL changes", flush=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = helper["BACKUPS"] / ("zhipu-provider-" + stamp + ".json")
    fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump({"provider": PROVIDER_NAME, "model": MODEL, "vendorProbe": "PASS",
                   "providerPersistence": "PASS", "aiRoutes": 0,
                   "gatewayInference": "NOT_VERIFIED", "agentHubInference": "NOT_VERIFIED"}, output)
    print("Sanitized evidence: " + str(report), flush=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] not in ([], ["--diagnose-only"]):
            raise ApiFailure("unsupported-arguments")
        main(diagnose_only=sys.argv[1:] == ["--diagnose-only"])
    except (KeyboardInterrupt, EOFError):
        print("STOPPED: operator cancelled; inspect state before resuming", flush=True)
        sys.exit(1)
    except ApiFailure as error:
        print("STOPPED: stage=" + error.stage + "; HTTP=" + str(error.status)
              + "; vendor_code=" + str(error.vendor_code)
              + "; reason=" + VENDOR_ERROR_REASONS.get(error.vendor_code, "unknown")
              + "; verification incomplete; do not repeat blindly", flush=True)
        sys.exit(1)
    except Exception as error:
        print("STOPPED: " + type(error).__name__ + "; verification incomplete", flush=True)
        sys.exit(1)
