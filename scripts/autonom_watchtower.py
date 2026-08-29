#!/usr/bin/env python3
"""autonom_watchtower.py — 24/7 self-driving guardian for the OpenAmer instance.

Runs as a no_agent cron (zero LLM tokens, zero cost). Every tick it checks the
core organs and either logs a healthy heartbeat (silent) or, on a real failure,
attempts a bounded, safe recovery and prints a concrete report (which the cron
can deliver).

Checks (all local/cheap, no paid API):
  1. Chrome CDP :9222 alive & real (not HeadlessChrome impostor).
  2. session_to_brain daemon pid alive.
  3. Core server ports the fleet expects (webhook-engine on-demand; won't fail on these).
  4. A2A worker workflow present in the repo + config standard resolvable.
  5. Release venv importable (openamer_cli a2a).
Recovery it may take (bounded, never destructive):
  - (re)spawn session_to_brain.daemon if its pid died.
  - restart Chrome CDP with the persisted profile if :9222 is gone.
Prints only on (a) a failure + recovery/action, or (b) a summary when requested.
Exit 0 with clean state -> cron stays quiet (deliver local, silent watchdog).
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
OPENAMER = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
REPO = Path(r"C:\Users\damir\openamer-repo")
CHROME_PROFILE = OPENAMER / "chrome-profile"
STATE = OPENAMER / "autonom-state.json"


def _http(port, path="/", timeout=4):
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}",
                                      timeout=timeout).status
    except Exception:
        return None


def _pid_alive(pidfile: Path) -> bool:
    if not pidfile.exists():
        return False
    try:
        pid = int(pidfile.read_text().strip())
    except ValueError:
        return False
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                       capture_output=True, text=False, timeout=8)
    out = (r.stdout or b"").decode("utf-8", "replace")
    return str(pid) in out


def _chrome_cdp_alive() -> bool:
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=4)
        import json
        ua = json.loads(req.read().decode("utf-8", "replace")).get("Browser", "")
        return "HeadlessChrome" not in ua          # real Chrome only
    except Exception:
        return False


def _config_standard_ok() -> bool:
    sys.path.insert(0, str(REPO))
    try:
        from scripts.a2a_worker import _load_model_default
        std = _load_model_default()
        return bool(std and std.get("provider") and std.get("model"))
    except Exception:
        return False


def _start_session_to_brain():
    sys.path.insert(0, str(OPENAMER / "openamer-agent"))
    try:
        from openamer_cli.session_to_brain_daemon import spawn
        spawn()
        return True
    except Exception as e:
        print(f"[watchtower] session_to_brain spawn failed: {e}")
        return False


def _start_chrome():
    exe = Path(r"C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not exe.exists():
        return False
    subprocess.Popen([str(exe), "--remote-debugging-port=9222",
                      "--remote-allow-origins=*",
                      f"--user-data-dir={CHROME_PROFILE}",
                      "--no-first-run", "--start-maximized"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW)
    return True


def _dashboard_serve_alive() -> bool:
    """Dashboard/serve on 127.0.0.1:9119 — the API the renderer/browser dashboard needs."""
    try:
        r = urllib.request.urlopen("http://127.0.0.1:9119/api/health", timeout=4)
        return r.status == 200
    except Exception:
        return False


def _start_dashboard_serve() -> bool:
    """Start `serve --host 127.0.0.1 --port 9119` so the dashboard frontend never
    hits ERR_CONNECTION_REFUSED. Uses the managed venv python, no new window."""
    py = OPENAMER / "openamer-agent" / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        return False
    try:
        subprocess.Popen(
            [str(py), "-m", "openamer_cli.main", "serve",
             "--host", "127.0.0.1", "--port", "9119", "--insecure"],
            cwd=str(OPENAMER / "openamer-agent"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False


def main() -> int:
    problems = []
    actions = []

    # 1) session_to_brain daemon
    pidf = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer")) / "session_to_brain.pid"
    if not _pid_alive(pidf):
        problems.append("session_to_brain daemon down")
        if _start_session_to_brain():
            actions.append("respawning session_to_brain")
        time.sleep(1)

    # 2) Chrome CDP (real, not headless)
    if not _chrome_cdp_alive():
        problems.append("Chrome CDP :9222 down")
        if _start_chrome():
            actions.append("restarting Chrome CDP :9222")

    # 2b) Dashboard serve :9119 — API the renderer/browser dashboard needs.
    if not _dashboard_serve_alive():
        problems.append("Dashboard serve :9119 down")
        if _start_dashboard_serve():
            actions.append("starting dashboard serve :9119")

    # 3) config standard resolvable (A2A uses the user's declared provider)
    if not _config_standard_ok():
        problems.append("config model standard unresolved")

    # 4b) reboot-flag pending (safe_restart.py) - tell user a restart is due
    _oa_home = Path(os.environ.get("OPENAMER_HOME") or Path.home() / "AppData/Local/openamer-laptop")
    rb = _oa_home / "reboot-flag.json"
    if rb.exists():
        try:
            _rf = json.loads(rb.read_text(encoding="utf-8"))
            if not _rf.get("handled"):
                problems.append(f"REBOOT PENDING: {_rf.get('reason')} - run: openamer desktop")
                actions.append("flag reboot-pending")
        except Exception:
            pass


    # 4) A2A worker present
    if not (REPO / ".github/workflows/a2a-worker.yml").exists():
        problems.append("a2a-worker.yml missing")

    state = {
        "ts": time.time(),
        "healthy": not problems,
        "problems": problems,
        "actions": actions,
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    if problems:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        print("[watchtower] took actions:", actions or "none")
        return 0 if not problems or actions else 1
    # healthy -> silent (cron stays quiet unless --verbose)
    if "--verbose" in sys.argv:
        print("[watchtower] OK — all organs healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())