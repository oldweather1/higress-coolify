"""VPS-only, operator-entered Higress console password recovery.

Uses the official password-change API. Never prints credentials, cookies or
response bodies; does not edit/delete the persisted Secret or restart Docker.
"""

import base64
import datetime
import getpass
import hashlib
import hmac
import http.cookiejar
import json
import os
from pathlib import Path
import resource
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
import warnings

import yaml

CONTAINER = "higress-a3tix4epqop6sr3hw6knb7vz-075039625064"
VOLUME = "a3tix4epqop6sr3hw6knb7vz_higress-data"
DATA = Path("/var/lib/docker/volumes") / VOLUME / "_data"
SECRET = DATA / "secrets/higress-console.yaml"
BASE_URL = "https://higress.discipline-agent.tech"
USERNAME = "2862407329@qq.com"
BACKUPS = Path("/etc/higress-console-recovery-a3tix4epqop6sr3hw6knb7vz")


class PasswordValidationError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirect refused")


def client():
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        NoRedirect(),
    )


def call(opener, path, payload):
    if path not in ("/session/login", "/user/changePassword"):
        raise RuntimeError("Endpoint out of scope")
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=15) as response:
        body = json.loads(response.read(65536))
        if not isinstance(body, dict) or body.get("success") is False:
            raise RuntimeError("API rejected operation")
        return body.get("data", body)


def login(opener, password):
    user = call(opener, "/session/login", {
        "username": USERNAME, "password": password, "autoLogin": False,
    })
    if not isinstance(user, dict) or user.get("name") != USERNAME:
        raise RuntimeError("Unexpected identity")


def read_secret():
    if SECRET.is_symlink() or SECRET.resolve() != SECRET:
        raise RuntimeError("Unexpected Secret path")
    raw = SECRET.read_bytes()
    doc = yaml.safe_load(raw)
    if doc.get("kind") != "Secret" or doc.get("metadata", {}).get("name") != "higress-console":
        raise RuntimeError("Unexpected Secret object")
    data = doc["data"]
    name = base64.b64decode(data["adminUsername"], validate=True).decode()
    if name != USERNAME:
        raise RuntimeError("Unexpected administrator")
    return raw, data


def config_snapshot():
    return {
        str(path.relative_to(DATA)): hashlib.sha256(path.read_bytes()).digest()
        for path in DATA.rglob("*.yaml") if path != SECRET
    }


def container_snapshot():
    info = json.loads(subprocess.check_output(
        ["docker", "inspect", CONTAINER], stderr=subprocess.DEVNULL,
    ))[0]
    if not info["State"]["Running"]:
        raise RuntimeError("Higress is not running")
    if not any(m["Destination"] == "/data" and m.get("Name") == VOLUME for m in info["Mounts"]):
        raise RuntimeError("Unexpected volume")
    return info["Id"], info["State"]["StartedAt"]


def backup(raw):
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    stat = BACKUPS.stat()
    if BACKUPS.is_symlink() or stat.st_uid != 0 or stat.st_mode & 0o077:
        raise RuntimeError("Backup directory is not root-only")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUPS / ("before-password-reset-" + stamp + ".yaml")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    print("BACKUP_READY: root-only 0600", flush=True)
    return path


def validate_password(first, second, old):
    if not hmac.compare_digest(first.encode(), second.encode()):
        raise PasswordValidationError("Passwords do not match; no change made")
    if not 12 <= len(first) <= 256 or any(ord(char) < 32 for char in first):
        raise PasswordValidationError("Use 12-256 characters without control characters; no change made")
    if hmac.compare_digest(first.encode(), old.encode()):
        raise PasswordValidationError("Use a different password; no change made")


def main():
    if os.geteuid() != 0 or socket.gethostname() != "srv1399091" or not sys.stdin.isatty():
        raise RuntimeError("Requires the approved VPS root interactive terminal")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    warnings.simplefilter("error", getpass.GetPassWarning)
    before_container = container_snapshot()
    before_config = config_snapshot()
    raw, before_secret = read_secret()
    old = base64.b64decode(before_secret["adminPassword"], validate=True).decode()
    opener = client()
    login(opener, old)
    print("EXISTING_ACCOUNT_VERIFIED: " + USERNAME, flush=True)
    backup_path = backup(raw)
    print("NEW_PASSWORD_HANDOFF: type twice; input is hidden; second Enter submits.", flush=True)
    first = getpass.getpass("New Higress password (12+ characters): ")
    second = getpass.getpass("Repeat new Higress password: ")
    validate_password(first, second, old)
    if (read_secret()[1] != before_secret or config_snapshot() != before_config
            or container_snapshot() != before_container):
        raise RuntimeError("Configuration changed concurrently; no reset submitted")
    call(opener, "/user/changePassword", {"oldPassword": old, "newPassword": first})
    print("PASSWORD_CHANGE_SUBMITTED", flush=True)
    login(client(), first)
    print("NEW_PASSWORD_LOGIN: PASS", flush=True)
    try:
        login(client(), old)
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise RuntimeError("Old-password rejection not verified") from None
    else:
        raise RuntimeError("Old password remains accepted")
    print("OLD_PASSWORD_REJECTED: PASS", flush=True)
    _, after_secret = read_secret()
    if base64.b64decode(after_secret["adminPassword"], validate=True).decode() != first:
        raise RuntimeError("Persistence not verified")
    if {k: v for k, v in after_secret.items() if k != "adminPassword"} != {
        k: v for k, v in before_secret.items() if k != "adminPassword"
    }:
        raise RuntimeError("Other Secret fields changed")
    if config_snapshot() != before_config or container_snapshot() != before_container:
        raise RuntimeError("Configuration or container changed")
    print("PERSISTENCE_AND_UNCHANGED_CONFIG: PASS", flush=True)
    print("HIGRESS_PASSWORD_RESET: PASS; no containers restarted", flush=True)
    print("Backup retained at " + str(backup_path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("STOPPED: operator cancelled; verify state before resuming", flush=True)
        sys.exit(1)
    except PasswordValidationError:
        print("STOPPED: password validation failed; no password change submitted", flush=True)
        sys.exit(1)
    except Exception as error:
        # Never print exception messages, HTTP bodies, local variables or tracebacks.
        print("STOPPED: " + type(error).__name__ + "; verification incomplete; do not repeat reset blindly", flush=True)
        sys.exit(1)
