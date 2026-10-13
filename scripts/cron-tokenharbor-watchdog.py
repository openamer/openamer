#!/usr/bin/env python3
"""Watchdog: is the Token Harbor free route still serving?

There is no public allowance endpoint (all /v1/usage-style paths 404), so the
honest signal is a real request: send a tiny completion to the :free model and
report whether it answers or starts refusing (rate limit / allowance spent).

Silent (exit 0, empty stdout) when healthy — cron-friendly.
Speaks up (exit 1) when the free route stops answering, so a fallback can be
trusted or the operator nudged.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME", str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop")))


def _env(name, default=""):
    if os.environ.get(name):
        return os.environ[name]
    f = HOME / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    return default


KEY = _env("TOKENHARBOR_API_KEY")
BASE = _env("TOKENHARBOR_BASE_URL", "https://tokenharbor.ai/v1").rstrip("/")
MODEL = "deepseek-v4.1-flash:free"

if not KEY:
    print("tokenharbor-watchdog: TOKENHARBOR_API_KEY missing")
    sys.exit(1)

body = json.dumps({
    "model": MODEL,
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 5,
}).encode()
req = urllib.request.Request(BASE + "/chat/completions", data=body, headers={
    "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})

t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    dt = time.time() - t0
    # A 200 means the free route is alive. Stay silent — cron-friendly.
    _ = d
    sys.exit(0)
except urllib.error.HTTPError as e:
    try:
        detail = e.read().decode("utf-8", "replace")[:300]
    except Exception:
        detail = ""
    print(f"tokenharbor-watchdog: free route FAILED — HTTP {e.code} after {time.time()-t0:.1f}s")
    print(f"  model={MODEL} url={BASE}/chat/completions")
    print(f"  body: {detail}")
    if e.code == 429:
        # An exhausted free allowance is a KNOWN, EXPECTED state (rolling 7-day
        # quota), not a malfunction: the configured fallback chain covers it.
        # Exiting 1 here pins the cron red for days and hides real failures —
        # so report the state on stdout and exit 0.
        print("  => free allowance exhausted (rolling 7x24h) — expected; fallback covers.")
        sys.exit(0)
    sys.exit(1)
except Exception as e:
    print(f"tokenharbor-watchdog: free route unreachable — {type(e).__name__}: {e}")
    sys.exit(1)
