"""VPS-only protected free-model route, reusing the owner-saved gateway key.

Stage under a non-public Host, verify denial, then publish on the EXISTING gateway
host. No paid model/fallback, retries, new key, Agent Hub ingress or DB changes.
On a failed gate STOP: configuration may be staged; no automatic delete/retry.
"""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

MODEL = "glm-4-flash-250414"
PROVIDER = "zhipu-free"
CONSUMER = "agenthub-private"
ROUTE = "agenthub-glm-free"
STAGE_HOST = "agenthub-glm-staging.invalid"
GATEWAY_HOST = "gateway.discipline-agent.tech"
PATH = "/v1/chat/completions"
MODEL_HEADER = "x-higress-llm-model"
UNKNOWN_MODEL = "agenthub-nonexistent-model-probe"
STAGE_PROOF = Path("/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/agenthub-stage-positive-20261002.json")
ADMIN_HELPER = Path("/root/higress-console-reset-20261002.py")
CALLER_HELPER = Path("/root/agenthub-gateway-credential-20261002-v1.py")
PHP = r'''
require "vendor/autoload.php";
$app=require "bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
try {
 $a=App\Models\Application::where("uuid","3bagut1mvvvxlo9eahll2yqn")->firstOrFail();
 if ($a->git_repository!=="oldweather1/agent-hub" || $a->git_branch!=="main" ||
  $a->settings->is_auto_deploy_enabled || !$a->settings->is_raw_compose_deployment_enabled ||
  !empty($a->fqdn) || !empty($a->ports_mappings)) {throw new RuntimeException();}
 $rows=App\Models\EnvironmentVariable::where("resourceable_type",App\Models\Application::class)
  ->where("resourceable_id",$a->id)->where("key","MODEL_API_KEY")->get();
 $prod=$rows->filter(fn($v)=>!$v->is_preview);
 if ($prod->count()!==1) {throw new RuntimeException();}
 $v=$prod->first(); $value=(string)$v->value;
 if ($value==="" || !$v->is_shown_once || !$v->is_runtime || $v->is_buildtime ||
  !$v->is_literal || $v->getRawOriginal("value")===$value) {throw new RuntimeException();}
 foreach ($rows->filter(fn($v)=>$v->is_preview) as $p) {
  if ((string)$p->value!=="" || $p->is_runtime || $p->is_buildtime) {throw new RuntimeException();}
 }
 echo json_encode(["value"=>$value]);
} catch (Throwable $e) {echo '{"failure":true}';exit(1);}
'''


class GateError(Exception):
    pass


def require(condition, stage):
    if not condition:
        raise GateError(stage)


def route_payload(domain):
    require(domain in (STAGE_HOST, GATEWAY_HOST), "route-domain-out-of-scope")
    return {"name": ROUTE, "domains": [domain],
            "pathPredicate": {"matchType": "PRE", "matchValue": PATH, "caseSensitive": True},
            "headerPredicates": [
                {"key": ":path", "matchType": "EQUAL", "matchValue": PATH, "caseSensitive": True},
                {"key": ":method", "matchType": "EQUAL", "matchValue": "POST", "caseSensitive": True},
                {"key": "content-type", "matchType": "EQUAL", "matchValue": "application/json",
                 "caseSensitive": True}],
            "modelPredicates": [{"matchType": "EQUAL", "matchValue": MODEL, "caseSensitive": True}],
            "upstreams": [{"provider": PROVIDER, "weight": 100, "modelMapping": {MODEL: MODEL}}],
            "authConfig": {"enabled": True, "allowedCredentialTypes": ["key-auth"],
                           "allowedConsumers": [CONSUMER]},
            "fallbackConfig": {"enabled": False},
            "proxyNextUpstream": {"enabled": False, "attempts": 1, "timeout": 90, "conditions": []}}


def verify_route(body, domain):
    require(isinstance(body, dict), "route-response-shape")
    expected = route_payload(domain)
    for field in ("name", "domains", "pathPredicate", "headerPredicates", "modelPredicates",
                  "upstreams", "authConfig"):
        require(body.get(field) == expected[field], "route-persistence-" + field)
    require(body.get("fallbackConfig", {}).get("enabled") is False, "fallback-disabled")
    require(body.get("proxyNextUpstream", {}).get("enabled") is False, "gateway-retries-disabled")


def api(client, base, endpoint, payload=None, method=None):
    require(endpoint in ("/v1/ai/routes", "/v1/ai/routes/" + ROUTE, "/v1/routes"), "api-out-of-scope")
    method = method or ("POST" if payload is not None else "GET")
    require(method in ("GET", "POST", "PUT") and (method == "GET" or endpoint.startswith("/v1/ai/routes")),
            "write-out-of-scope")
    req = urllib.request.Request(base + endpoint, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with client.open(req, timeout=15) as response:
            raw = response.read(1048577)
            require(len(raw) <= 1048576, "api-response-too-large")
            body = json.loads(raw)
            require(isinstance(body, dict) and body.get("success") is not False, "api-rejected")
            return body.get("data", body)
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise GateError("route-api HTTP=" + str(status)) from None


def caller_key():
    proc = subprocess.run(["docker", "exec", "coolify", "php", "-r", PHP],
                          capture_output=True, text=True, timeout=30)
    require(proc.returncode == 0, "existing-locked-runtime-caller-key")
    key = json.loads(proc.stdout).get("value")
    require(isinstance(key, str) and bool(key), "caller-key-empty")
    return key


def probe(client, url, host, key=None, model=MODEL, spoof=False, content_type="application/json", path=PATH):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply with OK only."}],
                       "max_tokens": 128, "stream": False}).encode()
    headers = {"Content-Type": content_type, "Host": host}
    if key is not None:
        headers["Authorization"] = "Bearer " + key
    if spoof:
        headers[MODEL_HEADER] = MODEL
    req = urllib.request.Request(url + path, method="POST", data=body, headers=headers)
    try:
        with client.open(req, timeout=30) as response:
            raw = response.read(65537)
            require(len(raw) <= 65536, "gateway-response-too-large")
            return response.status, raw
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read(4097)
        error.close()
        return status, raw


def await_denial(client, url, host):
    # Only anonymous checks await control-plane propagation; no successful
    # inference request, vendor overload or positive request is automatically retried.
    for attempt in range(8):
        status, _ = probe(client, url, host)
        if status in (401, 403, 404):
            return
        require(status == 503, "anonymous-not-denied HTTP=" + str(status))
        if attempt < 7:
            time.sleep(2)
    raise GateError("auth-propagation-not-verified")


def negative_checks(client, url, host, key):
    tests = [
        ("invalid-caller-key", {"key": "invalid-public-probe-key"}, {401, 403, 404}),
        ("unknown-model", {"key": key, "model": UNKNOWN_MODEL}, {404}),
        ("spoofed-model-header", {"key": key, "model": UNKNOWN_MODEL, "spoof": True}, {404}),
        ("non-json-content-type", {"key": key, "model": UNKNOWN_MODEL, "spoof": True,
                                   "content_type": "text/plain"}, {404}),
        ("path-suffix-not-allowed", {"key": key, "model": UNKNOWN_MODEL, "spoof": True,
                                    "path": PATH + "-not-allowed"}, {404})]
    for name, kwargs, accepted in tests:
        status, _ = probe(client, url, host, **kwargs)
        require(status in accepted, name + "-not-denied HTTP=" + str(status))
        print("DENIAL_PASS: " + name, flush=True)


def positive_probe(client, base, key, vendor_errors, host=GATEWAY_HOST):
    status, raw = probe(client, base, host, key=key)
    if status != 200:
        code = None
        try:
            detail = json.loads(raw).get("error", {})
            candidate = str(detail.get("code"))
            if candidate in vendor_errors:
                code = candidate
        except Exception:
            pass
        raise GateError("gateway-inference HTTP=" + str(status) + "; vendor_code=" + str(code)
                        + "; reason=" + vendor_errors.get(code, "unknown"))
    body = json.loads(raw)
    require(body.get("model") == MODEL and isinstance(body.get("choices"), list)
            and len(body["choices"]) >= 1 and bool(body["choices"][0].get("message", {}).get("content")),
            "gateway-response-model-or-content")
    print("HIGRESS_AUTHENTICATED_FREE_INFERENCE: PASS (one request; response not displayed)", flush=True)


def route_digest(route):
    return hashlib.sha256(json.dumps(route, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_stage_proof(route, key, snapshot):
    require(not STAGE_PROOF.is_symlink() and STAGE_PROOF.stat().st_uid == 0
            and not STAGE_PROOF.stat().st_mode & 0o077, "trusted-prior-stage-proof")
    proof = json.loads(STAGE_PROOF.read_bytes())
    require(proof.get("httpStatus") == 200 and proof.get("model") == MODEL
            and proof.get("hasAssistantContent") is True
            and proof.get("source") == "operator-observed-single-VPS-request"
            and proof.get("routeDigest") == route_digest(route)
            and proof.get("callerDigest") == hashlib.sha256(key.encode()).hexdigest()
            and proof.get("higressSnapshot") == list(snapshot), "prior-stage-proof-context-mismatch")


def trusted(path):
    require(not path.is_symlink() and path.stat().st_uid == 0 and not path.stat().st_mode & 0o077,
            "untrusted-helper")
    return runpy.run_path(str(path))


def main():
    require(sys.argv[1:] in ([], ["--resume-staged-after-probe"])
            and os.geteuid() == 0 and socket.gethostname() == "srv1399091", "approved-vps")
    resume = sys.argv[1:] == ["--resume-staged-after-probe"]
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    helper, caller = trusted(ADMIN_HELPER), trusted(CALLER_HELPER)
    vendor = trusted(Path("/root/higress-zhipu-free250414-20261002-v2.py"))
    admin = helper["client"]()
    admin_bytes, secret = helper["read_secret"]()
    helper["login"](admin, base64.b64decode(secret["adminPassword"]).decode())
    base = helper["BASE_URL"]
    key = caller_key()
    consumer = caller["api"](admin, base, "/v1/consumers/" + CONSUMER)
    caller["verify_consumer"](consumer, key)
    consumers = caller["list_items"](caller["api"](admin, base, "/v1/consumers"))
    require(len(consumers) == 1 and consumers[0].get("name") == CONSUMER, "single-approved-consumer")
    provider = caller["api"](admin, base, "/v1/ai/providers/" + PROVIDER)
    require(provider.get("rawConfigs", {}).get("zhipuCodePlanMode") is False
            and provider.get("rawConfigs", {}).get("modelMapping") == {MODEL: MODEL}
            and key not in provider.get("tokens", []), "free-provider-and-separate-key")
    routes = caller["list_items"](api(admin, base, "/v1/ai/routes"))
    require((not resume and not routes) or (resume and len(routes) == 1 and routes[0].get("name") == ROUTE),
            "unexpected-existing-route; inspect-first")
    general = caller["list_items"](api(admin, base, "/v1/routes"))
    defaults = [r for r in general if r.get("name") == "default"]
    require(len(general) == (2 if resume else 1) and len(defaults) == 1
            and defaults[0].get("path", {}).get("matchType") == "EQUAL"
            and defaults[0].get("path", {}).get("matchValue") == "/"
            and (not resume or {r.get("name") for r in general} == {"default", "ai-route-" + ROUTE + ".internal"}),
            "unexpected-existing-general-route")
    before = helper["container_snapshot"](), caller["runtime_snapshot"]()
    info = json.loads(subprocess.check_output(["docker", "inspect", helper["CONTAINER"]],
                                             stderr=subprocess.DEVNULL, timeout=10))[0]
    require(set(info["NetworkSettings"]["Networks"]) == {"a3tix4epqop6sr3hw6knb7vz"}, "higress-network")
    rules = [v for k, v in info["Config"]["Labels"].items()
             if k.startswith("traefik.http.routers.") and k.endswith(".rule")]
    require(bool(rules) and all("Host(" in rule and "HostRegexp" not in rule
                               and STAGE_HOST not in rule for rule in rules), "staging-host-not-public")
    ip = info["NetworkSettings"]["Networks"]["a3tix4epqop6sr3hw6knb7vz"]["IPAddress"]
    private_base = "http://" + ip + ":8080"
    public_base = "https://" + GATEWAY_HOST
    probe_client = helper["client"]()  # No administrator session/cookie on inference requests.
    print("PRECHECK: saved caller verified; staging Host not mapped by public proxy", flush=True)
    if not resume:
        api(admin, base, "/v1/ai/routes", route_payload(STAGE_HOST))
    staged = api(admin, base, "/v1/ai/routes/" + ROUTE)
    verify_route(staged, STAGE_HOST)
    if resume:
        verify_stage_proof(staged, key, before[0])
        print("PRIOR_STANDARD_REQUEST: PASS; exact route/key/container context; no repeat of the successful stage request", flush=True)
    await_denial(probe_client, private_base, STAGE_HOST)
    negative_checks(probe_client, private_base, STAGE_HOST, key)
    if not resume:
        positive_probe(probe_client, private_base, key, vendor["VENDOR_ERROR_REASONS"], STAGE_HOST)
    print("STAGED_AUTH_AND_MODEL_DENIAL: PASS; now exposing only the existing gateway Host", flush=True)
    final = route_payload(GATEWAY_HOST)
    if staged.get("version") is not None:
        final["version"] = staged["version"]
    api(admin, base, "/v1/ai/routes/" + ROUTE, final, "PUT")
    verify_route(api(admin, base, "/v1/ai/routes/" + ROUTE), GATEWAY_HOST)
    await_denial(probe_client, public_base, GATEWAY_HOST)
    negative_checks(probe_client, public_base, GATEWAY_HOST, key)
    positive_probe(probe_client, public_base, key, vendor["VENDOR_ERROR_REASONS"])
    require(before == (helper["container_snapshot"](), caller["runtime_snapshot"]())
            and helper["read_secret"]()[0] == admin_bytes, "unexpected-runtime-or-admin-change")
    print("NO_RESTART_OR_AGENTHUB_MODEL_ENABLE: PASS; Agent Hub inference NOT VERIFIED yet", flush=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = helper["BACKUPS"]
    require(not folder.is_symlink() and folder.stat().st_uid == 0 and not folder.stat().st_mode & 0o077,
            "trusted-evidence-directory")
    path = folder / ("agenthub-protected-route-" + stamp + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump({"route": ROUTE, "model": MODEL, "caller": CONSUMER, "gatewayInference": "PASS",
                   "anonymousDenied": True, "invalidKeyDenied": True, "unknownModelDenied": True,
                   "modelHeaderSpoofDenied": True, "nonJsonDenied": True, "pathSuffixDenied": True,
                   "fallbackEnabled": False, "automaticRetriesEnabled": False,
                   "agentHubInference": "NOT_VERIFIED", "containerRestarted": False}, output)
    print("Sanitized evidence: " + str(path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("STOPPED: " + (str(error) if isinstance(error, GateError) else type(error).__name__)
              + "; inspect staged/current route; no automatic deletion or inference retry", flush=True)
        sys.exit(1)
