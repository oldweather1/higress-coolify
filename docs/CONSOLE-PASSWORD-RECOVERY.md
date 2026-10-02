# Higress console password recovery

## Scope and status (2026-10-02)

The owner authorized resetting only the existing Higress console administrator
password. The username remains unchanged. The GLM-4.7-Flash provider onboarding
is still pending; no API key is recorded here.

The installed All-in-One container uses the resource's own `/data` Docker volume.
Its console Secret is separate from Shared MySQL and Casdoor. Do not run
standalone `reset.sh`, delete the volume, delete the administrator Secret, disable
authentication, or install a different image to recover this password.

The official console's login page currently renders a forgot-password link without
an implemented recovery handler. The official password-change endpoint is
`POST /user/changePassword`, requiring an authenticated existing administrator
and the old password. The VPS-only helper reads the existing persisted credential
into memory, authenticates over verified HTTPS, and submits the operator's new
password through this normal endpoint. It never prints either password or a
session cookie and does not write passwords to Git, command arguments or logs.

## Operator handoff

Run `python3 tools/reset_console_password.py` only in an interactive root terminal
on the exact approved VPS. The helper rejects a different host, container mount,
administrator, configuration object, redirect, or non-interactive input. PyYAML
must already be present. It does not install dependencies.

Before prompting it creates a root-owned 0700 backup directory and a unique 0600
copy of the existing console Secret. This backup contains sensitive material,
is local to the VPS, and is not an encrypted/offsite/recurring backup. Never
download, print or commit it. Its location is reported without its contents.

The owner enters the new password twice, with echo disabled. Use a unique password
of at least 12 characters and save it in a password manager. The second Enter is
the owner's submission. A mismatch or concurrent configuration change stops the
operation before the password-change request. No default or temporary password
is created. The agent must not enter the new credential on the owner's behalf.

## Verification and failure handling

After submission the helper verifies a fresh login with the new password, explicit
HTTP 401 rejection of the old password, persisted password equality, all other
Secret data fields unchanged, all other persisted YAML files unchanged, and the
same running container ID/start time. Only sanitized PASS/STOPPED lines are printed.

If verification fails after submission, the password may already have changed.
Stop and inspect the precise state without logging credentials. Do not blindly
retry, restart other containers, replace an entire Secret, or restore the old
password. Restoring the backup is a separate credential change requiring owner
direction.

Current status: the owner entered the new password twice and submitted the
reset. The live VPS helper reported `NEW_PASSWORD_LOGIN: PASS`,
`OLD_PASSWORD_REJECTED: PASS`, `PERSISTENCE_AND_UNCHANGED_CONFIG: PASS`, and
`HIGRESS_PASSWORD_RESET: PASS; no containers restarted`. Six local safety tests
passed before execution. The Secret backup remains root-only 0600 at the
VPS-only path below; do not print or commit its contents.

`/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz/before-password-reset-20261002T064717158288Z.yaml`

The helper and this procedure are prepared in the private repository checkout,
but have not been pushed: the existing webhook can redeploy the `latest` image
even for documentation-only changes. Password recovery does not require such
a redeployment. Final publication must account for that deployment trigger.

## Official implementation references

- [Console login page](https://github.com/higress-group/higress-console/blob/main/frontend/src/pages/login/index.tsx)
- [UserController password-change endpoint](https://github.com/higress-group/higress-console/blob/main/backend/console/src/main/java/com/alibaba/higress/console/controller/UserController.java)
- [SessionServiceImpl administrator Secret handling](https://github.com/higress-group/higress-console/blob/main/backend/console/src/main/java/com/alibaba/higress/console/service/SessionServiceImpl.java)

These describe the official implementation; actual VPS checks must pass before
reporting this recovery complete. Repository publication must not trigger an
unnecessary All-in-One `latest` image redeployment solely for password recovery.
