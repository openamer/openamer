#!/usr/bin/env python3
"""cron_mesh_daemon.py — ensure the Go mesh-daemon is running (5-min cron).

Probes http://127.0.0.1:18920/health; if down, starts the binary detached.
Prints one short line (cron-safe). Zero LLM tokens.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

DAEMON = Path(r"C:\Users\damir\openamer-repo\go\mesh-daemon\mesh-daemon.exe")
HEALTH = "http://127.0.0.1:18920/health"


def probe() -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main() -> int:
    st = probe()
    if st:
        print(f"mesh-daemon ok: uptime={st.get('uptime_sec')}s "
              f"mesh_alive={st.get('mesh_alive')} mem={st.get('mem_alloc_mb'):.1f}MB")
        return 0
    if not DAEMON.exists():
        print(f"mesh-daemon binary missing: {DAEMON}")
        return 1
    subprocess.Popen(
        [str(DAEMON), "-interval", "30s"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200,
        close_fds=True,
    )
    import time
    for _ in range(10):
        time.sleep(1.2)
        st = probe()
        if st:
            print(f"mesh-daemon started: mesh_alive={st.get('mesh_alive')}")
            return 0
    print("mesh-daemon failed to start")
    return 1


if __name__ == "__main__":
    sys.exit(main())
