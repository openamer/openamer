"""Cron watchdog: keep the translation swarm fed until every locale is filled.

Why: a wave of 36-44 workers owns one locale each and then exits cleanly, so
"0 workers alive" means "wave finished", not "crashed". Without a watchdog the
fleet idles until a human launches the next wave — that idle time was the real
reason the remaining languages crawled.

Silent by design: prints nothing when there is nothing to do, so a 10-minute
schedule does not spam the user. Prints one line only when it launches a wave.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

def find_repo() -> Path:
    """Locate the source tree from either location this script is installed in.

    The cron runs it from OPENAMER_HOME/scripts, a copy step away from the repo;
    resolving parents[1] there points at the install, not the checkout.
    """
    for candidate in (Path(__file__).resolve().parents[1], Path.home() / "openamer-repo"):
        if (candidate / "scripts" / "fill_desktop_locales.py").is_file():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO = find_repo()
HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
PIDFILE = HOME / "logs" / "translation-swarm.pid.json"
PROGRESS = HOME / "logs" / "translation-swarm.progress.json"
CACHE = HOME / "tmp"
PY = sys.executable
STALL_SECONDS = 600          # no cache growth for this long means a stuck wave


def cache_total() -> int:
    """Filled strings across every cache file — the only honest progress signal.

    Measuring PIDs instead was wrong in production: one worker stuck in a slow
    lane kept the count above zero, so the watchdog stayed silent while nothing
    moved (observed: 1 alive, cache frozen, 194k strings open).
    """
    total = 0
    for path in CACHE.glob("desktop_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        total += len([v for v in data.values() if isinstance(v, str) and v.strip()])
    return total


def read_progress() -> tuple[int, float] | None:
    try:
        rec = json.loads(PROGRESS.read_text(encoding="utf-8"))
        return int(rec["total"]), float(rec["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_progress(total: int) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps({"total": total, "at": time.time()}),
                        encoding="utf-8", newline="\n")


def kill_wave() -> int:
    """Terminate the recorded wave so a stalled lane cannot block the fleet."""
    if not PIDFILE.is_file():
        return 0
    try:
        import psutil
    except ImportError:
        return 0
    killed = 0
    try:
        rec = json.loads(PIDFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    for worker in rec.get("workers", []):
        try:
            proc = psutil.Process(worker["pid"])
            proc.terminate()
            proc.wait(timeout=10)
            killed += 1
        except psutil.Error:
            pass
    return killed


def alive() -> int:
    if not PIDFILE.is_file():
        return 0
    try:
        import psutil
    except ImportError:
        return 0
    count = 0
    try:
        rec = json.loads(PIDFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    for worker in rec.get("workers", []):
        try:
            if psutil.Process(worker["pid"]).is_running():
                count += 1
        except psutil.Error:
            pass
    return count


def open_locale_codes() -> list[str]:
    """Locales whose cache is not yet above half of the English literal count.

    Includes half-translated locales on purpose: `--only-empty` skips them, so a
    watchdog that only counted empty caches would leave every partial locale
    stranded the moment the last empty one is filled.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fill_watch", REPO / "scripts" / "fill_desktop_locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = len(module.parse_en()) // 2
    codes = []
    for path in CACHE.glob("desktop_*.json"):
        code = path.stem.replace("desktop_", "")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            codes.append(code)
            continue
        filled = len([v for v in data.values() if isinstance(v, str) and v.strip()])
        if filled < target:
            codes.append(code)
    return sorted(codes)


def main() -> int:
    total = cache_total()
    previous = read_progress()
    stalled = (previous is not None and total <= previous[0]
               and time.time() - previous[1] > STALL_SECONDS)
    if alive() > 0 and not stalled:
        if previous is None or total > previous[0]:
            write_progress(total)
        return 0                      # real progress or a fresh wave: stay quiet
    killed = kill_wave() if stalled else 0
    codes = open_locale_codes()
    if not codes:
        write_progress(total)
        return 0                      # nothing left; stay quiet
    env = dict(os.environ, OPENAMER_DESKTOP_BATCH="40", OPENAMER_DESKTOP_WORKERS="6")
    proc = subprocess.run(
        [PY, str(REPO / "scripts" / "start_translation_swarm.py"),
         "--workers", "2", "--threads", "6", "--locales", *codes],
        capture_output=True, text=True, env=env, timeout=300)
    tail = (proc.stdout or "").strip().splitlines()
    write_progress(total)
    prefix = f"killed {killed} stalled, " if killed else ""
    print(f"swarm wave: {prefix}{len(codes)} open locales, "
          f"cache {total}: {tail[-1] if tail else 'no output'}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
