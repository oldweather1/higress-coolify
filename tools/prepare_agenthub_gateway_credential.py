"""Owner-entered gateway caller credential: Higress + native Coolify Secret.

This is NOT a BigModel key or a Casdoor credential. No inference route,
application restart, deployment, public Agent Hub or vendor request is created.
On partial failure inspect persisted state; never blindly rerun or delete it.
"""
import base64
import datetime
import getpass
import hmac
import json
import os
from pathlib import Path
import re
import resource
import runpy
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import warnings

CONSUMER = "agenthub-private"
PROVIDER = "zhipu-free"
MODEL = "glm-4-flash-250414"
ADMIN_HELPER = Path("/root/higress-console-reset-20261002.py")
RUNTIME = "3bagut1mvvvxlo9eahll2yqn-agent-hub-1"
PHP = r'''
require "vendor/autoload.php";
$app = require "bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
class GatewaySecretGate extends RuntimeException {}
function gate($ok, $label) { if (!$ok) { throw new GatewaySecretGate($label); } }
try {
 $input=json_decode(stream_get_contents(STDIN),true,8,JSON_THROW_ON_ERROR);
 gate(is_array($input) && is_bool($input["apply"]),"input-shape");
 if ($input["apply"]) { gate(is_string($input["value"]) &&
   preg_match('/\A[A-Za-z0-9_-]{32,128}\z/',$input["value"])===1,"credential-format"); }
 $result=Illuminate\Support\Facades\DB::transaction(function () use ($input) {
  $a=App\Models\Application::where("uuid","3bagut1mvvvxlo9eahll2yqn")->lockForUpdate()->firstOrFail();
  gate($a->git_repository==="oldweather1/agent-hub" && $a->git_branch==="main"
   && !$a->settings->is_auto_deploy_enabled && $a->settings->is_raw_compose_deployment_enabled
   && empty($a->fqdn) && empty($a->ports_mappings),"private-raw-compose-target");
  $q=fn()=>App\Models\EnvironmentVariable::where("resourceable_type",App\Models\Application::class)
   ->where("resourceable_id",$a->id);
  $others=$q()->where("key","!=","MODEL_API_KEY")->orderBy("id")->get()->map(fn($v)=>$v->getRawOriginal())->all();
  $rows=$q()->where("key","MODEL_API_KEY")->lockForUpdate()->get();
  $prod=$rows->filter(fn($v)=>!$v->is_preview);
  gate($prod->count()===1 && $rows->every(fn($v)=>(string)$v->value===""),"empty-gateway-secret-required");
  foreach (["MODEL_BASE_URL","L2_MODEL","L3_MODEL"] as $name) {
   $v=$q()->where("key",$name)->where("is_preview",false)->get();
   gate($v->count()===1 && (string)$v->first()->value==="","model-not-yet-enabled");
  }
  if (!$input["apply"]) { return ["preflight"=>"PASS","private"=>true,"rawCompose"=>true,
    "existingGatewaySecretEmpty"=>true,"modelNotEnabled"=>true,"mutated"=>false]; }
  App\Models\EnvironmentVariable::withoutEvents(function () use ($rows,$input) {
   foreach ($rows as $v) {
    if (!$v->is_preview) { $v->value=$input["value"]; }
    $v->is_shown_once=true; $v->is_buildtime=false; $v->is_runtime=!$v->is_preview;
    $v->is_literal=true; $v->is_multiline=false; $v->is_required=!$v->is_preview;
    $v->comment="Agent Hub gateway caller key only; never the vendor API key; production runtime only.";
    $v->save();
   }
  });
  $saved=$q()->where("key","MODEL_API_KEY")->get(); $prod=$saved->filter(fn($v)=>!$v->is_preview);
  gate($prod->count()===1,"one-production-secret-required"); $v=$prod->first();
  gate(hash_equals($input["value"],(string)$v->value) && $v->is_shown_once && $v->is_runtime
   && !$v->is_buildtime && $v->is_literal && $v->getRawOriginal("value")!==$input["value"],"secret-postcondition");
  foreach ($saved->filter(fn($v)=>$v->is_preview) as $v) {
   gate((string)$v->value==="" && !$v->is_runtime && !$v->is_buildtime,"preview-disabled");
  }
  $after=$q()->where("key","!=","MODEL_API_KEY")->orderBy("id")->get()->map(fn($v)=>$v->getRawOriginal())->all();
  gate($after===$others,"unrelated-variables-unchanged");
  return ["secretSave"=>"PASS","name"=>"MODEL_API_KEY","locked"=>true,"runtimeOnly"=>true,
   "nativeEncryptedStorage"=>true,"previewInjectionDisabled"=>true,"unrelatedVariablesUnchanged"=>true];
 });
 echo json_encode($result,JSON_THROW_ON_ERROR);
} catch (Throwable $e) {
 echo json_encode(["failure"=>true,"safeGate"=>$e instanceof GatewaySecretGate ? $e->getMessage() : "native-operation-failed"]);
 exit(1);
}
'''


class GateError(Exception):
    pass


def require(condition, stage):
    if not condition:
        raise GateError(stage)


def validate_key(key):
    require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key) is not None,
            "gateway-key-format; use 32-128 random letters/digits/hyphen/underscore; no whitespace")


def consumer_payload(key):
    validate_key(key)
    return {"name": CONSUMER, "credentials": [{"type": "key-auth", "source": "BEARER",
                                               "values": [key]}]}


def verify_consumer(body, key):
    require(isinstance(body, dict) and body.get("name") == CONSUMER, "consumer-name")
    credentials = body.get("credentials")
    require(isinstance(credentials, list) and len(credentials) == 1, "consumer-credential-count")
    credential = credentials[0]
    require(credential.get("type") == "key-auth" and credential.get("source") == "BEARER"
            and credential.get("values") == [key], "consumer-credential-persistence")


def api(opener, base, endpoint, payload=None):
    require(endpoint in ("/v1/consumers", "/v1/consumers/" + CONSUMER,
                         "/v1/ai/providers", "/v1/ai/providers/" + PROVIDER, "/v1/ai/routes"),
            "endpoint-out-of-scope")
    require(payload is None or endpoint == "/v1/consumers", "write-out-of-scope")
    req = urllib.request.Request(base + endpoint,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if payload is not None else "GET")
    try:
        with opener.open(req, timeout=15) as response:
            raw = response.read(1048577)
            require(len(raw) <= 1048576, "response-too-large")
            body = json.loads(raw)
            require(isinstance(body, dict) and body.get("success") is not False, "api-rejected")
            return body.get("data", body)
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        raise GateError("higress-api HTTP=" + str(code)) from None


def list_items(body):
    if isinstance(body, dict):
        body = body.get("data", body.get("items"))
    require(isinstance(body, list), "inventory-shape")
    return body


def inventory(opener, base):
    require(not list_items(api(opener, base, "/v1/consumers")), "consumer-already-exists; inspect-first")
    require(not list_items(api(opener, base, "/v1/ai/routes")), "route-already-exists; inspect-first")
    providers = list_items(api(opener, base, "/v1/ai/providers"))
    require(len(providers) == 1 and providers[0].get("name") == PROVIDER, "provider-inventory")
    provider = api(opener, base, "/v1/ai/providers/" + PROVIDER)
    require(provider.get("type") == "zhipuai" and provider.get("protocol") == "openai/v1",
            "provider-type")
    raw = provider.get("rawConfigs", {})
    require(raw.get("zhipuCodePlanMode") is False and raw.get("zhipuDomain") == "open.bigmodel.cn"
            and raw.get("modelMapping") == {MODEL: MODEL}, "approved-free-provider")
    tokens = provider.get("tokens")
    require(isinstance(tokens, list) and len(tokens) == 1 and isinstance(tokens[0], str)
            and bool(tokens[0]), "provider-token-present")
    return tokens[0]


def coolify_secret(key=None):
    payload = {"apply": key is not None}
    if key is not None:
        validate_key(key)
        payload["value"] = key
    proc = subprocess.run(["docker", "exec", "-i", "coolify", "php", "-r", PHP],
                          input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    result = json.loads(proc.stdout)
    if proc.returncode != 0:
        allowed = {"input-shape", "credential-format", "private-raw-compose-target",
                   "empty-gateway-secret-required", "model-not-yet-enabled",
                   "one-production-secret-required", "secret-postcondition", "preview-disabled",
                   "unrelated-variables-unchanged", "native-operation-failed"}
        label = result.get("safeGate")
        raise GateError("coolify-secret-" + (label if label in allowed else "operation-failed")
                        + "; inspect-state-before-retry")
    require(result.get("failure") is not True, "coolify-secret-rejected")
    return result


def runtime_snapshot():
    info = json.loads(subprocess.check_output(["docker", "inspect", RUNTIME],
                                             stderr=subprocess.DEVNULL, timeout=10))[0]
    require(info["State"]["Running"] and not info["HostConfig"]["PortBindings"]
            and set(info["NetworkSettings"]["Networks"]) == {"coolify"}, "private-running-runtime")
    env = dict(row.split("=", 1) for row in info["Config"]["Env"])
    require(all(env.get(name, "") == "" for name in
                ("MODEL_API_KEY", "MODEL_BASE_URL", "L2_MODEL", "L3_MODEL")), "runtime-model-disabled")
    return info["Id"], info["State"]["StartedAt"]


def main():
    require(not sys.argv[1:] and os.geteuid() == 0 and socket.gethostname() == "srv1399091"
            and sys.stdin.isatty(), "approved-interactive-vps-required")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    warnings.simplefilter("error", getpass.GetPassWarning)
    require(not ADMIN_HELPER.is_symlink() and ADMIN_HELPER.stat().st_uid == 0
            and not ADMIN_HELPER.stat().st_mode & 0o077, "trusted-admin-helper")
    helper = runpy.run_path(str(ADMIN_HELPER))
    opener = helper["client"]()
    secret = helper["read_secret"]()[0]
    helper["login"](opener, base64.b64decode(helper["read_secret"]()[1]["adminPassword"]).decode())
    before = helper["container_snapshot"](), runtime_snapshot()
    vendor_key = inventory(opener, helper["BASE_URL"])
    coolify_secret()
    print("PRECHECK: provider configured; consumers=0; AI routes=0; Agent Hub private and model-disabled.", flush=True)
    print("NEW GATEWAY CALLER KEY: use a unique random 32-128-character key from your password manager.", flush=True)
    print("Allowed characters: letters, digits, hyphen, underscore. This is NOT your Zhipu API key.", flush=True)
    print("Enter saves it as Higress consumer agenthub-private and locked runtime-only MODEL_API_KEY.", flush=True)
    print("No inference route, vendor request or application redeploy is performed by this step.", flush=True)
    key = getpass.getpass("Paste NEW gateway caller key (hidden); Enter saves: ")
    validate_key(key)
    require(not hmac.compare_digest(key.encode(), vendor_key.encode()), "must-not-reuse-vendor-key")
    require(inventory(opener, helper["BASE_URL"]) == vendor_key, "concurrent-provider-change")
    coolify_secret()
    require(before == (helper["container_snapshot"](), runtime_snapshot())
            and helper["read_secret"]()[0] == secret, "concurrent-runtime-or-admin-change")
    api(opener, helper["BASE_URL"], "/v1/consumers", consumer_payload(key))
    verify_consumer(api(opener, helper["BASE_URL"], "/v1/consumers/" + CONSUMER), key)
    print("HIGRESS_CALLER_CREDENTIAL: PASS; persisted equality checked without display", flush=True)
    result = coolify_secret(key)
    require(not list_items(api(opener, helper["BASE_URL"], "/v1/ai/routes")), "unexpected-route")
    require(before == (helper["container_snapshot"](), runtime_snapshot())
            and helper["read_secret"]()[0] == secret, "unexpected-runtime-or-admin-change")
    print("COOLIFY_MODEL_API_KEY: PASS; locked, runtime-only, native encrypted storage; Preview disabled", flush=True)
    print("NO_ROUTES_OR_RESTARTS: PASS; model routing and Agent Hub inference NOT VERIFIED yet", flush=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = helper["BACKUPS"]
    require(not folder.is_symlink() and folder.stat().st_uid == 0
            and not folder.stat().st_mode & 0o077, "trusted-evidence-directory")
    path = folder / ("agenthub-gateway-credential-" + stamp + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump({"consumer": CONSUMER, "higressCredentialPersistence": "PASS", "coolify": result,
                   "vendorKeyReused": False, "aiRoutes": 0, "containerRestarted": False,
                   "gatewayInference": "NOT_VERIFIED", "agentHubInference": "NOT_VERIFIED"}, output)
    print("Sanitized evidence: " + str(path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("STOPPED: cancelled; inspect state before retrying", flush=True)
        sys.exit(1)
    except Exception as error:
        print("STOPPED: " + (str(error) if isinstance(error, GateError) else type(error).__name__)
              + "; partial state may exist; do not blindly rerun", flush=True)
        sys.exit(1)
