#!/usr/bin/env python3
"""Watchdog for the remote GPU worker (frontier_server.py -> :8082 on the GPU PC).

The GPU box's frontier server has no local supervisor, so it stays dead after a
crash until someone notices (observed 2026-09-11: :8082 down for hours, GPU idle
at 0%). This watchdog probes the worker from the laptop and, if it is down,
re-launches it on the GPU PC over SSH via the `OpenAmerFrontier` scheduled task
(created with /sc ONSTART so it also survives a reboot).

Exit 0 when the worker answers (or was successfully restarted); exit 1 with a
concise reason otherwise — so the cron status stays truthful.
"""
import json
import subprocess
import sys
import time
import urllib.request

GPU_IP = "192.168.178.23"
GPU_PORT = 8082
SSH = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
       "-o", "StrictHostKeyChecking=no", f"damir@{GPU_IP}"]


def probe(timeout=6):
    """Return the /health JSON dict, or None if the worker is unreachable."""
    try:
        with urllib.request.urlopen(
                f"http://{GPU_IP}:{GPU_PORT}/health", timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def _ssh(cmd, timeout=60):
    try:
        p = subprocess.run(SSH + [cmd], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 99, f"ssh failed: {e}"


def restart():
    """(Re)launch frontier_server.py on the GPU PC via the scheduled task."""
    rc, out = _ssh("schtasks /run /tn OpenAmerFrontier")
    ok = rc == 0 or "ERFOLGREICH" in out or "SUCCESS" in out
    return ok, out.strip().splitlines()[-1] if out.strip() else ""


def main():
    health = probe()
    if health is not None:
        print(json.dumps({"ok": True, "worker": "up", "health": health,
                          "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
        return 0
    # Down -> try to bring it up. Qwen3.5-4B needs ~40-60s to load into VRAM.
    started, info = restart()
    if not started:
        print(json.dumps({"ok": False, "worker": "down", "restart": "failed",
                          "detail": info, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
        return 1
    deadline = time.time() + 100
    while time.time() < deadline:
        time.sleep(5)
        health = probe()
        if health is not None:
            print(json.dumps({"ok": True, "worker": "restarted", "health": health,
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
            return 0
    print(json.dumps({"ok": False, "worker": "down",
                      "restart": "no /health after 100s",
                      "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
