# Free GLM onboarding (2026-10-02)

## Approved target

- Existing Higress deployment and official All-in-One image; no new installation.
- China BigModel standard API, `open.bigmodel.cn`, HTTPS.
- Native provider `zhipuai`, name `zhipu-free`, console protocol `openai/v1`.
- Current exact model `glm-4-flash-250414`, following the owner's instruction to
  switch models using the same existing BigModel key after GLM-4.7-Flash returned
  provider overload (1305). No new key, key reset, paid model or paid fallback.
- Explicit `zhipuCodePlanMode: false`. The current official console handler can
  default this flag to true, so relying on an omitted/default field is unsafe.
- Provider model mapping is not an authorization allowlist. The eventual AI route
  must restrict the model exactly and use caller authentication before activation.
- Keep Agent Hub private, leave Casdoor and Shared MySQL unchanged.

## Current evidence and staged deployment

**Latest result:** the owner completed the v2 hidden input. The VPS probe of
`glm-4-flash-250414` passed, and `zhipu-free` was saved and read back with token
equality verified without displaying the token. Routes and consumers are still
empty. Gateway inference and Agent Hub inference are **NOT VERIFIED**; a direct
vendor success does not prove either. Earlier failed attempts below are history,
not the current provider status.

Sanitized VPS evidence:
`/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/zhipu-provider-20261002T074613887214Z.json`.
The helper verified no Higress container restart or administrator change; no
Agent Hub, Casdoor or MySQL configuration was changed by it.

Console password recovery passed on the VPS: new login accepted, old login
returned HTTP 401, persisted credential checked, other Secret fields and persisted
YAML unchanged, container ID/start time unchanged. See the recovery document.

An authenticated, sanitized live read confirmed zero LLM providers and zero AI
routes. The owner completed the hidden
API-key input on the VPS. The single direct vendor probe returned **HTTP 429**
at stage `zhipu-free-model-probe`; the helper exited before the provider POST.
No API key was saved by this helper, no AI route was created, and Agent Hub was
not changed or redeployed. The key existed only in the exited process's memory;
any later attempt requires a fresh owner input, not clipboard/history recovery.

The original failure handler recorded only the HTTP status and stage, not the vendor error
body. Therefore this evidence does not distinguish account concurrency/quota
limits from provider overload, and does not prove the key is invalid. Do not
invent a vendor error code or report successful model connectivity. Read-only
inspection of BigModel's signed-in model square still lists GLM-4.7-Flash as free,
but did not establish the account's effective rate limits or this request's cause.
No automatic repeated inference requests, recharge, subscription, paid-model
substitution, or quota changes were performed. Onboarding remains
**BLOCKED / NOT VERIFIED**; the authorized follow-up diagnostic is recorded below.

The owner subsequently authorized a diagnostic attempt. Safe error-code capture
is now implemented: at most 4096 bytes of error JSON are parsed in VPS memory,
only a known official business code and a fixed local label are exposed, and no
vendor message/header is printed. Invalid, unknown or oversized bodies remain
`unknown`; they are not guessed. Thirteen local helper tests passed, including
numeric/string codes, malformed/oversized/hostile bodies, and one-request/no-retry
behavior with a synthetic secret in the error message.

The public script was transferred with SHA-256 verification to root-only
`/root/higress-zhipu-diagnostic-20261002-v1.py` (the previous helper was not
overwritten). The owner completed the hidden prompt, and the single
`--diagnose-only` request returned **HTTP 429, business code 1305,
`reason=model-overloaded`**. The terminal returned to the shell; no automatic
retry was performed. Official BigModel documentation defines 1305 as the model
currently being overloaded, with a later retry recommended. This is a confirmed
provider-side cause for the diagnostic request, not proof of the original
request's unrecorded business code. It is not the account-arrears or account-rate
code, and provides no reason to recharge, reset the key, or change the VPS.

This mode never saves the key and never writes a provider or route, even on
success. Higress provider registration and Agent Hub model inference remain
unverified; Casdoor/MySQL/Agent Hub configuration was unchanged. A later attempt
needs an owner-supplied hidden key again; do not recover secrets from clipboard,
history or logs. Deployment is paused until a permitted attempt can verify the
model's availability; no switch to a paid model is authorized.

## Authorized free-model replacement

The owner selected changing the model rather than replacing the API key, and
authorized continuation. The current helper now targets only
`glm-4-flash-250414`. It uses the same China standard endpoint and native
`zhipuai` provider, explicitly disables Coding Plan mode, and omits the previous
model's thinking-mode option. The existing key must be entered again by its
owner because neither failed process persisted it; this is not a key rotation.
Fourteen local safety tests passed, including the exact replacement model,
bounded single-request probe, no thinking option, and no fixture-key output.
Registration and model connectivity remain unverified until the live attempt.
The new root-only VPS artifact
`/root/higress-zhipu-free250414-20261002-v1.py` was installed without overwriting
prior scripts, with its SHA-256 checked. Its live preflight confirmed zero
providers/routes and the exact replacement model. After the input prompt it
exited with `STOPPED: ValueError; verification incomplete`, without a vendor
HTTP/business code or probe-success marker. The explicit `ValueError` in the
helper is its local key-input guard (empty input or whitespace/control characters).
This is consistent with an input rejection, not evidence that the replacement
model is overloaded or the actual key is invalid; the submitted secret was not
inspected or retained, so the exact rejected input condition is unknown.

A separate authenticated, read-only inventory then confirmed providers=0 and
AI routes=0, without a model call or configuration writes. No provider was saved.
The terminal is back at the shell, **not** a hidden key prompt: the owner must
not paste a key there. A subsequent authorized attempt requires preparing the
hidden prompt again. Provider connectivity and model inference remain unverified.

The owner then authorized continuation. The input guard now uses fixed,
non-secret stage identifiers for empty input, surrounding whitespace, control
characters and internal whitespace; it does not trim, echo, retain or recover
the submitted credential. Fifteen local tests passed. The root-only artifact
`/root/higress-zhipu-free250414-20261002-v2.py` was transferred with SHA-256
verification and started without overwriting prior versions. Live preflight
again confirmed zero providers/routes before the owner completed its hidden
prompt. Its single free-model probe and provider registration then passed, as
recorded above. It exited successfully; the terminal is now at the shell, not a
credential prompt. Do not paste a key at the shell.

Without `--diagnose-only`, `tools/configure_zhipu_provider.py` performs staged
provider registration:

1. Authenticate using the existing console credential in VPS memory, over verified
   HTTPS, without copying that password into the browser or Agent Hub.
2. Refuse existing providers/routes rather than overwrite them.
3. Hand off one hidden API-key input to the owner. Enter submits that credential.
4. Probe only `glm-4-flash-250414` directly from the VPS with a synthetic `OK`
   prompt and 128 maximum output tokens. No product/user data is sent.
5. Save the provider through the official API and verify persisted token equality
   without displaying the token, a fragment, headers, cookies or response text.
6. Verify AI routes remain empty and the administrator/container unchanged.

The direct vendor probe is provider-connectivity evidence, not proof of Higress
gateway or Agent Hub inference. No AI route is created by this helper. A failed
or rate-limited provider probe stops before saving; a later failure may occur
after saving, so inspect state and never blindly retry or delete resources.

The successful v2 registration persisted the API key through Higress's native
configuration mechanism in its VPS volume. Do not claim it is irrecoverable to root/Docker/Higress administrators or
encrypted at rest merely because input was hidden. Never print or commit the
provider resource containing the key. The Agent Hub gateway credential will be
separate and stored as a locked, runtime-only Coolify Secret, not the vendor key.

## Still pending

- Authenticated exact-model AI route; no paid fallback or anonymous access.
- Verified TLS gateway endpoint reachable from Agent Hub's actual private network.
- Agent Hub runtime variables, deployment, and gateway/Agent Hub inference tests.
- Product-login-token end-to-end test (no product repository exists yet).
- Credits/Metering item 17 remains deferred.

Tools/documents are currently local changes in this private repository checkout.
The main webhook must not accidentally redeploy the unpinned `latest` image just
to publish these records. Publication and any necessary deployment must account
for the actual trigger and image version; do not claim a push/deployment occurred.

## Post-provider read-only checks

- `/v1/consumers`: zero; `/v1/ai/routes`: zero.
- Verified HTTPS request from the VPS to
  `https://gateway.discipline-agent.tech/v1/models` returned HTTP 404. This proves
  VPS DNS/TLS reachability, not model routing, authentication or Agent Hub-network
  reachability.
- Actual Higress network: `a3tix4epqop6sr3hw6knb7vz`; actual Agent Hub network:
  `coolify`. Do not assume they share a Docker network or bypass TLS by joining
  additional networks without checking the security impact.
- Running Higress image repository digest:
  `sha256:113ea2a6a673f627b13338bf399d42322b85ccbdd9ddc7f521fa6557d4cf7423`.
  Compose still references `latest`; no replacement image has been pulled.
- Official route creation writes the Ingress before its auth resources. Do not
  activate a public inference route first and add authentication afterwards.
  Stage with a non-public domain, verify authentication, then expose only the
  existing gateway host. Exact model routing and header-spoof rejection require
  actual verification before reporting success.

### Runtime-network verification (not inference)

The first ad-hoc `nsenter` check reported a DNS error (`gaierror`, errno -3).
It used the host's resolver from inside a container network namespace; that was
a test-context error, not proof that Agent Hub's own resolver or TLS was broken.
A subsequent inline diagnostic also failed locally before a network request.
Neither failure is counted as an application failure or a successful check.

`tools/check_agenthub_gateway_network.py` was installed as the root-only,
SHA-256-verified `/root/agenthub-gateway-network-20261002-v1.py`. It explicitly
uses Agent Hub's Docker resolver (`127.0.0.11`), actual network namespace and
the CA bundle inside its running container. Its VPS result was:

- DNS: **PASS**.
- Hostname/CA verification and TLS: **PASS**, TLS 1.3.
- Unauthenticated `/v1/models`: HTTP 404 (still no inference route).
- No credentials, model call, network mutation or container restart.

This is network/TLS evidence, not proof of the Go application's model request
or authorization path. The helper tests include valid/compressed DNS answers,
wrong IDs, DNS errors, truncated responses and malformed names.

## Separate gateway caller credential handoff

`tools/prepare_agenthub_gateway_credential.py` prepares a unique owner-entered
gateway caller key, separate from the existing BigModel key. It refuses an
existing caller or AI route, a non-private/non-Raw-Compose Agent Hub target,
an already enabled model configuration, or nonempty existing `MODEL_API_KEY`.

After the owner's hidden input and Enter it will:

1. Create only Higress consumer `agenthub-private`, with Bearer key-auth.
2. Verify credential persistence in VPS memory without displaying it.
3. Save the same key through Coolify's native encrypted model as locked,
   literal, runtime-only `MODEL_API_KEY`; disable Preview injection.
4. Check unrelated variables, runtime/container starts and the console
   administrator remain unchanged, and AI routes are still empty.

The key is carried to the Coolify child process on stdin, not in shell history,
command arguments, output or Git. Root/Docker/Higress/Coolify administrators
remain trusted and can recover deployed secrets; locking is UI concealment, not
a cryptographic authorization boundary. The key is not a Casdoor Client secret.

This helper does **not** create an AI route, enable Agent Hub models, perform a
vendor/model request or redeploy containers. A partial failure may leave a
consumer persisted: inspect state and reuse the approved existing credential
safely, never delete/regenerate or ask the owner to repeat it blindly.

Twenty-five local helper tests passed. The actual credential-save and route
verification results must be recorded after the owner finishes this new input;
preparing a prompt is not evidence that the new key has been saved.

The owner completed the first gateway-credential prompt. It stopped at
`gateway-key-format`, before the consumer POST or Coolify save. This guard
requires 32-128 letters/digits/hyphens/underscores with no whitespace; the
submitted value was neither inspected nor retained, so its precise rejected
condition is unknown. This is an input rejection, not a model/vendor error.
An authenticated read-only follow-up confirmed consumers=0, AI routes=0 and
production/Preview `MODEL_API_KEY` still empty; no inference or writes occurred.
The hidden prompt has been reopened after that check. Owner input is pending;
do not paste credentials into the shell or recover the exited process's input
from clipboard/history/logs. No route or application deployment has completed.

The owner completed the reopened prompt successfully. Higress caller credential
`agenthub-private` was read back with equality verified without displaying it.
Coolify `MODEL_API_KEY` was saved and verified locked, runtime-only, natively
encrypted, with Preview disabled. Unrelated variables and container start times
were unchanged; AI routes remained empty. This supersedes the preceding pending
handoff, but does not yet prove route or Agent Hub inference.

Sanitized evidence:
`/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/agenthub-gateway-credential-20261002T080452078444Z.json`.

## Protected route implementation (verification pending)

`tools/configure_agenthub_route.py` reuses that existing saved caller key in VPS
memory; there is no repeated credential input, new key or privilege expansion.
It refuses existing AI routes rather than overwrite/delete them.

- Stage on `agenthub-glm-staging.invalid`, which must not be mapped by the public
  Traefik proxy, before changing the domain to the existing gateway host.
- Permit only the exact free model, JSON POST, `/v1/chat/completions`, and caller
  `agenthub-private` via Bearer key-auth. Extra exact `:path`/`:method` predicates
  are included because the native AI route path field only supports prefixes.
  Their installed-runtime effectiveness still requires verification.
- Explicitly disable fallback and `proxyNextUpstream`; the official current
  service otherwise defaults next-upstream attempts to three and includes
  `non_idempotent`. Never automatically retry a successful/failed inference probe.
- Before activation test anonymous, invalid-key, unknown-model, model-header
  spoof, non-JSON, and unwanted path-suffix denial. Only anonymous rejection
  checks wait for control-plane propagation.
- Stage checks use the existing Docker-only Higress HTTP listener from the
  trusted VPS host. No host port or new network is exposed. Final inference and
  Agent Hub's configured endpoint use verified HTTPS; this is not a TLS bypass
  for the application.
- After activation repeat rejection checks over HTTPS, then send one synthetic
  free-model prompt. Never print the answer, keys, cookies or raw errors.
- A failed gate stops and leaves staged/current resources for inspection, with
  no automatic deletion or positive inference retry. This helper does not enable
  Agent Hub models or redeploy applications.

Thirty-three local helper tests passed. These are implementation checks, not proof
of installed-version route behavior or completed gateway inference. Broader
fuzzing, JSON parser ambiguity, load tests and real product-token acceptance
must not be inferred from these scoped probes.

### Actual staging result and corrected test interpretation

The first route run saved the exact staged route and read it back successfully,
but stopped at `auth-propagation-not-verified`: its anonymous-only wait expected
401/403 while the runtime returned 404. The route was **not** switched to the
real gateway domain and Agent Hub's model variables remained disabled.

Read-only inspection confirmed the staged route in Envoy, exact path/method and
JSON/model predicates, key-auth allowlist, and active global model-router. A
separate anonymous request explicitly supplying the internal model header
returned 401. Plugin artifact access returned 200; selected captured Docker log
keyword counters were zero, which does not prove all logs or failure modes clean.

One standard private request with the **correct saved caller key**, no manually
supplied routing header and the approved free model then returned **HTTP 200**,
exact response model `glm-4-flash-250414`, and nonempty assistant content. The
answer/key were not displayed. Therefore the earlier provisional suspicion
that model extraction was broken is superseded: the failure was the test's
interpretation of anonymous 404, not a demonstrated plugin defect. No plugin
configuration, debug logging, code fork or image upgrade was performed.

The corrected test accepts 404 as a *denial*, never as positive inference proof.
Before public activation it additionally requires standard authenticated
inference to have passed. For this continuation an operator-observed, root-only
attestation records the actual preceding successful terminal result, bound to
the exact route, caller fingerprint and container identity/start time:
`/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/agenthub-stage-positive-20261002.json`.
It contains no raw key and is not committed or printed. It is an operator
attestation of the observed request, not a new independently replayed request.
`--resume-staged-after-probe` refuses a different route/key/container context;
fresh runs still require their own successful stage inference. Neither mode
automatically retries positive inference, deletes resources or allows anonymous
success. The continuation repeats the missing rejection cases, then performs
one independent verified-HTTPS test on the existing gateway domain.

## Actual protected HTTPS route acceptance — 2026-10-02

The corrected continuation completed. `agenthub-glm-free` now matches only
`gateway.discipline-agent.tech`, exact POST `/v1/chat/completions`, exact
`application/json` and model `glm-4-flash-250414`; only consumer
`agenthub-private` is permitted. Fallback and next-upstream retries are disabled.
Anonymous denial passed during propagation; invalid key, nonexistent model,
spoofed internal model header, non-JSON content type and unwanted path suffix
were rejected both privately and over verified HTTPS (401/403/404 accepted only
as denial). One correct-caller HTTPS inference returned 200, exact model and
nonempty assistant content. No key/answer/raw error was displayed.

Sanitized root-only evidence:
`/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/agenthub-protected-route-20261002T082124612968Z.json`.
Provider/caller/route state lives in the existing named `higress_data` volume;
the vendor credential is not Agent Hub's caller credential. This is gateway
acceptance, not authenticated product→Agent Hub chat acceptance.

The Compose image is pinned to the exact already-running digest
`sha256:113ea2a6a673f627b13338bf399d42322b85ccbdd9ddc7f521fa6557d4cf7423`.
This prevents an automatic main Webhook from upgrading mutable `latest` during
documentation/helper publication. Publication and post-Webhook acceptance are
recorded separately below; pinning alone is not deployed proof.

## References

- [BigModel model and standard endpoint](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)
- [Replacement free model](https://docs.bigmodel.cn/cn/guide/models/free/glm-4-flash-250414)
- [BigModel official HTTP/business error codes](https://docs.bigmodel.cn/cn/faq/api-code)
- [Native Zhipu provider handler](https://github.com/higress-group/higress-console/blob/main/backend/sdk/src/main/java/com/alibaba/higress/sdk/service/ai/ZhipuAILlmProviderHandler.java)
- [Provider API](https://github.com/higress-group/higress-console/blob/main/backend/console/src/main/java/com/alibaba/higress/console/controller/ai/LlmProvidersController.java)
