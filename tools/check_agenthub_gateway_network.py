"""Read-only VPS check with Agent Hub's network, Docker DNS and CA bundle.

No application/user credential, inference, network change or container restart.
The namespace helper shares the host filesystem, not the runtime root filesystem;
therefore both DNS and the CA file are explicitly taken from the target container.
"""
import json
import os
from pathlib import Path
import resource
import socket
import ssl
import struct
import subprocess
import sys

CONTAINER = "3bagut1mvvvxlo9eahll2yqn-agent-hub-1"
HOST = "gateway.discipline-agent.tech"


def skip_name(body, offset):
    for _ in range(128):
        size = body[offset]
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(body):
                raise ValueError()
            return offset + 2
        if size > 63 or offset + 1 + size > len(body):
            raise ValueError()
        offset += 1
        if not size:
            return offset
        offset += size
    raise ValueError()


def parse_addresses(body, ident):
    if len(body) < 12:
        raise ValueError()
    actual, flags, questions, answers, _, _ = struct.unpack("!6H", body[:12])
    if actual != ident or not flags & 0x8000 or flags & 0x020F or questions != 1:
        raise ValueError()
    offset = skip_name(body, 12) + 4
    addresses = []
    for _ in range(answers):
        offset = skip_name(body, offset)
        kind, cls, _, size = struct.unpack("!HHIH", body[offset:offset + 10])
        offset += 10
        if offset + size > len(body):
            raise ValueError()
        if kind == 1 and cls == 1 and size == 4:
            addresses.append(socket.inet_ntoa(body[offset:offset + size]))
        offset += size
    if not addresses:
        raise ValueError()
    return addresses


def network_probe(dns, ca):
    result = {"dns": "NOT_VERIFIED", "tls": "NOT_VERIFIED", "httpStatus": None,
              "inference": "NOT_VERIFIED", "credentialsUsed": False}
    stage = "dns"
    try:
        ident = 27182
        name = b"".join(bytes([len(part)]) + part.encode() for part in HOST.split(".")) + bytes([0])
        query = struct.pack("!6H", ident, 0x0100, 1, 0, 0, 0) + name + struct.pack("!HH", 1, 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conn:
            conn.settimeout(5)
            conn.sendto(query, (dns, 53))
            body, sender = conn.recvfrom(4096)
            if sender != (dns, 53):
                raise ValueError()
        addresses = parse_addresses(body, ident)
        result["dns"] = "PASS"
        stage = "tls"
        context = ssl.create_default_context(cafile=ca)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((addresses[0], 443), timeout=8) as raw:
            with context.wrap_socket(raw, server_hostname=HOST) as conn:
                result["tls"] = "PASS"
                result["tlsVersion"] = conn.version()
                stage = "http"
                conn.sendall(("GET /v1/models HTTP/1.1\r\nHost: " + HOST
                              + "\r\nConnection: close\r\n\r\n").encode())
                first = conn.recv(4096).split(b"\r\n", 1)[0].split()
                result["httpStatus"] = int(first[1])
    except Exception as error:
        result.update(failedStage=stage, failure=type(error).__name__)
        for attr in ("errno", "verify_code"):
            value = getattr(error, attr, None)
            if isinstance(value, int):
                result[attr] = value
    return result


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if os.geteuid() != 0 or socket.gethostname() != "srv1399091":
        raise ValueError()
    if len(sys.argv) == 4 and sys.argv[1] == "--namespace-probe":
        result = network_probe(sys.argv[2], sys.argv[3])
        print(json.dumps(result))
        return int("failedStage" in result)
    if sys.argv[1:]:
        raise ValueError()
    info = json.loads(subprocess.check_output(["docker", "inspect", CONTAINER],
                                             stderr=subprocess.DEVNULL, timeout=10))[0]
    if not info["State"]["Running"] or set(info["NetworkSettings"]["Networks"]) != {"coolify"}:
        raise ValueError()
    pid = info["State"]["Pid"]
    ca = "/proc/" + str(pid) + "/root/etc/ssl/certs/ca-certificates.crt"
    if not Path(ca).is_file():
        raise ValueError()
    dns = [line.split()[1] for line in Path(info["ResolvConfPath"]).read_text().splitlines()
           if line.startswith("nameserver ")]
    if dns != ["127.0.0.11"]:
        raise ValueError()
    path = Path(__file__).resolve()
    if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise ValueError()
    proc = subprocess.run(["nsenter", "-t", str(pid), "-n", "/usr/bin/python3", str(path),
                           "--namespace-probe", dns[0], ca], capture_output=True, text=True, timeout=20)
    report = json.loads(proc.stdout)
    report.update(target=CONTAINER, dnsSource="Docker runtime resolv.conf",
                  caSource="runtime CA bundle", namespace="actual runtime network",
                  containerRestarted=False, networkChanged=False)
    print(json.dumps(report))
    return proc.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"networkPreflight": "FAIL", "failure": type(error).__name__,
                          "inference": "NOT_VERIFIED"}))
        sys.exit(1)
