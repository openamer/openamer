"""Ten-minute progress report for the translation swarm.

Prints measured numbers only: cache growth since the last report, how many
locales are complete / partial / empty, whether workers are alive, and the last
line a worker actually wrote. When everything is covered it says so once and
then stays silent, so a 10-minute schedule does not become noise.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Cron pipes stdout and this host defaults that pipe to cp1252, which cannot
# encode the emoji below — print() would raise before the first line and the job
# would look like a silent failure. Same defect the notification engine records.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
CACHE = HOME / "tmp"
LOGDIR = HOME / "logs"
STATE = LOGDIR / "translation-report.state.json"
PIDFILE = LOGDIR / "translation-swarm.pid.json"
DONE_MARKER = LOGDIR / "translation-report.done"
FULL = 2180                      # a locale counts as complete at this many strings
TARGET = 194 * 2209              # prose literals across every locale module


def scan() -> tuple[int, int, int, int]:
    total = 0
    full = partial = empty = 0
    for path in CACHE.glob("desktop_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            empty += 1
            continue
        filled = len([v for v in data.values() if isinstance(v, str) and v.strip()])
        total += filled
        if filled >= FULL:
            full += 1
        elif filled:
            partial += 1
        else:
            empty += 1
    return total, full, partial, empty


def alive() -> int:
    if not PIDFILE.is_file():
        return 0
    try:
        import psutil
    except ImportError:
        return 0
    try:
        rec = json.loads(PIDFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    count = 0
    for worker in rec.get("workers", []):
        try:
            if psutil.Process(worker["pid"]).is_running():
                count += 1
        except psutil.Error:
            pass
    return count


def last_activity() -> str:
    logs = sorted(LOGDIR.glob("swarm-desktop-*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return "keine Worker-Logs"
    newest = logs[-1]
    age = (time.time() - newest.stat().st_mtime) / 60
    try:
        lines = [ln.strip() for ln in newest.read_text(encoding="utf-8", errors="replace")
                 .splitlines() if ln.strip()]
    except OSError:
        return "Log nicht lesbar"
    snippet = re.sub(r"\s+", " ", lines[-1])[:90] if lines else "leer"
    return f"vor {age:.0f} min ({snippet})"


def de(value: int) -> str:
    """German thousands separator without pulling in a locale."""
    return f"{value:,}".replace(",", ".")


def main() -> int:
    total, full, partial, empty = scan()
    open_strings = max(TARGET - total, 0)
    previous = None
    if STATE.is_file():
        try:
            previous = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None

    if open_strings == 0:
        if DONE_MARKER.is_file():
            return 0                     # already announced, stay silent
        DONE_MARKER.write_text(str(time.time()), encoding="utf-8")
        print(f"✅ Alle Sprachen abgedeckt — {de(total)} Strings im Cache, "
              f"{full} Sprachen vollständig.")
        return 0

    delta = total - int(previous.get("total", total)) if previous else 0
    minutes = (time.time() - float(previous.get("at", time.time()))) / 60 if previous else 0
    rate = f"~{delta / minutes:.0f}/min" if minutes >= 1 and delta else "—"
    eta = ""
    if delta and minutes >= 1:
        eta = f" · ETA ~{(open_strings / (delta / minutes)) / 60:.1f} h"

    print(
        f"📊 Übersetzung — {time.strftime('%H:%M')}\n"
        f"Cache: {de(total)} Strings ({delta:+d} seit letzter Meldung, {rate})\n"
        f"Sprachen: {full} voll · {partial} teilweise · {empty} leer\n"
        f"Offen: {de(open_strings)} Strings{eta}\n"
        f"Worker: {alive()} aktiv · letzte Aktivität {last_activity()}"
    )

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"total": total, "at": time.time()}), encoding="utf-8",
                     newline="\n")
    notify(f"Übersetzung: {de(total)} Strings · {empty} Sprachen leer · "
           f"{partial} teilweise · {de(open_strings)} offen{eta}")
    return 0


def notify(message: str) -> None:
    """Desktop toast, because this install has no gateway channel to deliver to.

    Without it the 10-minute report would land in a log file nobody reads.
    """
    engine = HOME / "scripts" / "notification-engine.py"
    if not engine.is_file() or os.environ.get("OPENAMER_REPORT_NOTIFY") == "0":
        return
    try:
        subprocess.run([sys.executable, str(engine), "--send", message,
                        "--priority", "info", "--channel", "desktop"],
                       capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


if __name__ == "__main__":
    sys.exit(main())
