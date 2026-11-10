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
CACHE = HOME / "tmp"
PY = sys.executable


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
    if alive() > 0:
        return 0                      # a wave is already running; stay quiet
    codes = open_locale_codes()
    if not codes:
        return 0                      # nothing left; stay quiet
    env = dict(os.environ, OPENAMER_DESKTOP_BATCH="40", OPENAMER_DESKTOP_WORKERS="6")
    proc = subprocess.run(
        [PY, str(REPO / "scripts" / "start_translation_swarm.py"),
         "--workers", "2", "--threads", "6", "--locales", *codes],
        capture_output=True, text=True, env=env, timeout=300)
    tail = (proc.stdout or "").strip().splitlines()
    print(f"swarm wave launched for {len(codes)} open locales: "
          f"{tail[-1] if tail else 'no output'}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
