#!/usr/bin/env python3
"""Restore-after-update: brings back everything the desktop updater breaks.

The OpenAmer desktop updater rebuilds the venv and restarts the app.
This script restores everything Mini-OpenAmer needs:
  1. Tool server (9 tools on :8081)
  2. SOUL.md (if the updater overwrote it)
  3. Learning loops (online_learning)
  4. World model + self model (verify files intact)
  5. GPU worker (restart on PC via SSH)
"""
import json, os, subprocess, sys, time, urllib.request

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
HOME = r"C:/Users/damir/AppData/Local/openamer-laptop"
SOUL = os.path.join(HOME, "SOUL.md")

def check_and_start(name, url, start_cmd=None, timeout=30):
    """Check if a service is up; start it if not."""
    try:
        urllib.request.urlopen(url, timeout=5)
        print(f"  OK {name}: running")
        return True
    except Exception:
        if start_cmd:
            print(f"  .. {name}: down, restarting...")
            subprocess.Popen(start_cmd, shell=True)
            for _ in range(timeout // 5):
                time.sleep(5)
                try:
                    urllib.request.urlopen(url, timeout=5)
                    print(f"  OK {name}: restarted")
                    return True
                except Exception:
                    continue
            print(f"  FAIL {name}: could not restart")
            return False
        else:
            print(f"  .. {name}: down (no auto-start)")
            return False

def restore():
    print("=== RESTORING AFTER UPDATE ===")
    print()

    # 1. SOUL.md
    if os.path.exists(SOUL):
        size = os.path.getsize(SOUL)
        if size > 1000:
            print(f"  OK SOUL.md: intact ({size} chars)")
        else:
            print(f"  .. SOUL.md: too small ({size} chars)")
            repo_soul = r"C:/Users/damir/openamer-repo/SOUL.md"
            if os.path.exists(repo_soul):
                import shutil
                shutil.copy2(repo_soul, SOUL)
                print("  OK SOUL.md: restored from repo")
    else:
        print("  FAIL SOUL.md: MISSING")
        repo_soul = r"C:/Users/damir/openamer-repo/SOUL.md"
        if os.path.exists(repo_soul):
            import shutil
            shutil.copy2(repo_soul, SOUL)
            print("  OK SOUL.md: restored from repo")

    # 2. Tool server
    check_and_start("Tool server (:8081)", "http://localhost:8081/health",
                   start_cmd=f'python "{T}/tool_server.py"')

    # 3. Online learning loop
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*online_learning*loop*' }).ProcessId"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    pids = [x.strip() for x in r.stdout.strip().split("\n") if x.strip().isdigit()]
    if pids:
        print(f"  OK Online-learning loop: running (PID {pids[0]})")
    else:
        print("  .. Online-learning loop: restarting...")
        subprocess.Popen([sys.executable, f"{T}/online_learning.py", "--loop"])
        print("  OK restarted")

    # 4. World model + self model
    wm = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/world_model.jsonl"
    sm = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/self_model/identity.md"
    for path, name in [(wm, "World model"), (sm, "Self model identity")]:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            print(f"  OK {name}: intact ({os.path.getsize(path)} bytes)")
        else:
            print(f"  .. {name}: missing or empty")

    # 5. GPU worker (PC)
    print()
    print("  GPU worker (PC):")
    try:
        r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
            "damir@192.168.178.23", "curl -s -m 5 http://localhost:8082/health"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        if "alive" in r.stdout:
            print("  OK GPU worker: running (4B on :8082)")
        else:
            print("  .. GPU worker: down. Restart: ssh damir@192.168.178.23 python scripts/training/frontier_server.py")
    except Exception as e:
        print(f"  .. GPU worker: unreachable ({str(e)[:50]})")

    print()
    print("=== RESTORE COMPLETE ===")

if __name__ == "__main__":
    restore()
