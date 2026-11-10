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


def render_html(total: int, full: int, partial: int, empty: int, open_strings: int,
                delta: int, rate: str, eta: str, activity: str, workers: int) -> str:
    """Static snapshot the preview pane can render and auto-reload.

    Chat delivery needs a gateway channel (none is configured here) and desktop
    toasts fail on this host, so a file the user keeps open is the only channel
    that is verifiably visible.
    """
    pct = min(100.0, total / TARGET * 100) if TARGET else 0.0
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<title>Uebersetzungs-Schwarm</title>
<style>
 body{{background:#0e1116;color:#e6edf3;font:15px/1.5 ui-sans-serif,system-ui,sans-serif;margin:0;padding:28px}}
 h1{{font-size:19px;margin:0 0 4px;font-weight:600}}
 .sub{{color:#8b949e;font-size:13px;margin-bottom:22px}}
 .bar{{height:10px;background:#1c232c;border-radius:6px;overflow:hidden;margin:10px 0 26px}}
 .fill{{height:100%;background:linear-gradient(90deg,#2f81f7,#3fb950);width:{pct:.1f}%}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}}
 .card{{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px 16px}}
 .k{{color:#8b949e;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 .v{{font-size:26px;font-weight:650;margin-top:6px}}
 .d{{color:#3fb950;font-size:13px;margin-top:4px}}
 .foot{{margin-top:24px;color:#8b949e;font-size:12.5px}}
 code{{color:#e6edf3;background:#161b22;padding:1px 5px;border-radius:4px}}
</style></head><body>
<h1>Uebersetzungs-Schwarm</h1>
<div class="sub">Stand {time.strftime('%d.%m.%Y %H:%M')} &middot; laedt alle 60 s neu, Cron schreibt alle 10 min</div>
<div class="bar"><div class="fill"></div></div>
<div class="grid">
 <div class="card"><div class="k">Strings im Cache</div><div class="v">{de(total)}</div><div class="d">{delta:+d}</div></div>
 <div class="card"><div class="k">Sprachen voll</div><div class="v">{full}</div></div>
 <div class="card"><div class="k">teilweise</div><div class="v">{partial}</div></div>
 <div class="card"><div class="k">leer</div><div class="v">{empty}</div></div>
 <div class="card"><div class="k">Offen</div><div class="v">{de(open_strings)}</div><div class="d">{rate}{eta}</div></div>
 <div class="card"><div class="k">Worker</div><div class="v">{workers}</div></div>
</div>
<div class="foot">Abdeckung <code>{pct:.1f}%</code> von {de(TARGET)} Prosa-Strings &middot;
letzte Aktivitaet: {activity}</div>
</body></html>
"""


def write_html(body: str) -> None:
    path = LOGDIR / "translation-report.html"
    tmp = path.with_suffix(".html.tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


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

    write_html(render_html(total, full, partial, empty, open_strings,
                           delta, rate, eta, last_activity(), alive()))
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
