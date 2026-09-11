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

# Training-lock: the 8 GB card cannot host the 7.9 GB 4B model and a training
# run at once. If a finetune is active on the GPU box, DO NOT restart the
# frontier server — doing so steals VRAM from training (observed live
# 2026-09-11: the watchdog re-launched the 4B minutes after it was stopped for a
# training run, and both then contended for the card). A training run is the
# higher-value use of the GPU; the worker can wait for its 10-minute probe.
LOCK_REMOTE_TASK = "OpenAmerTrain"
TRAIN_LOG = r"C:\Users\damir\train.log"


def training_active():
    """True when a finetune currently holds the GPU box's card.

    Primary signal: PowerShell's `Get-ScheduledTask .State` — an invariant
    English enum (Running/Ready/Disabled) that survives the SSH transport. The
    localized `schtasks` "Status:" text does not: German "Wird ausgeführt"
    arrives as raw cp850 bytes (0x81), so under encoding="utf-8",
    errors="replace" the umlaut becomes U+FFFD and a UTF-8 substring match
    never fires. Observed live 2026-09-11: training_active() returned False for
    a whole run, so the watchdog restarted the 4B worker into an active
    finetune and both contended for the 8 GB card.

    Secondary signal: an in-flight training log (no EXIT_CODE yet, fresh mtime).
    """
    rc, out = _ssh(
        "powershell -NoProfile -Command "
        "\"(Get-ScheduledTask -TaskName '" + LOCK_REMOTE_TASK + "').State\"")
    if rc == 0 and "running" in (out or "").lower():
        return True
    # Fallback: an in-flight training log (no EXIT_CODE yet, fresh mtime).
    # NOTE: build the value with Write-Output, NOT an escaped \"...\" — inner
    # double quotes do not survive cmd.exe on the far side of ssh (that call
    # died with "Das System kann den angegebenen Pfad nicht finden.", rc=255),
    # so this branch never executed either.
    rc2, log = _ssh(
        'powershell -NoProfile -Command "'
        f"$f=Get-Item '{TRAIN_LOG}' -EA SilentlyContinue; "
        f"if($f){{ $age=(New-TimeSpan -Start $f.LastWriteTime).TotalMinutes; "
        f"$done=(Select-String -Path '{TRAIN_LOG}' -Pattern 'EXIT_CODE' -Quiet); "
        f"Write-Output ($age.ToString() + '|' + $done) }}\"")
    if rc2 == 0 and "|" in log:
        try:
            line = [l for l in log.strip().splitlines() if "|" in l][-1]
            age_s, done_s = line.strip().strip('"').split("|")
            # $age.ToString() is locale-formatted (German uses a decimal comma),
            # so normalize before float() — the old float(age_s) raised here too.
            age = float(age_s.replace(",", "."))
            done = done_s.strip().lower() == "true"
            return (not done) and age < 20
        except Exception:
            return False
    return False


def probe(timeout=6):
    """Return the /health JSON dict, or None if the worker is unreachable."""
    try:
        with urllib.request.urlopen(
                f"http://{GPU_IP}:{GPU_PORT}/health", timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def _ssh(cmd, timeout=60):
    """Run cmd on the GPU PC over SSH. Returns (rc, stdout).

    stdout only: OpenSSH prints a post-quantum warning banner on connect to
    stderr, and folding it into the parsed value is what made the training
    probe's "|" split ambiguous. stderr is folded back in only when a failed
    run produced no stdout at all, so real errors stay visible.
    """
    try:
        p = subprocess.run(SSH + [cmd], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        out = p.stdout or ""
        if p.returncode != 0 and not out.strip():
            out = p.stderr or ""
        return p.returncode, out
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
    # Down. Before restarting, check the GPU isn't busy training — a restart
    # would steal VRAM from the higher-value run.
    if training_active():
        print(json.dumps({"ok": True, "worker": "down",
                          "action": "deferred: training holds the GPU",
                          "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
        return 0
    # try to bring it up. Qwen3.5-4B needs ~40-60s to load into VRAM.
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
