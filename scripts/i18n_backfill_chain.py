"""Run backfill rounds back to back until the pending list is empty.

`i18n_backfill.py` is a single round with a 120-minute budget. When it ends the
30-minute cron takes over, but each cron tick only works 25 of its 30 minutes
and spends the first two reading state -- measured 2026-11-17, that drops the
throughput from ~308 to ~250 strings/min. This chain closes the gap: as soon as
one round exits it starts the next one, and it stops when nothing is pending.

It also waits instead of colliding: if a backfill round is already running it
polls until that process is gone, so starting the chain next to a live round is
safe.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path.home() / "openamer-repo"
HOME = pathlib.Path(os.path.expanduser("~/AppData/Local/openamer-laptop"))
STATE = HOME / "reports" / "i18n-backfill-state.json"
LOG = HOME / "reports" / "i18n-backfill-chain.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def backfill_running() -> bool:
    """True while a driver round is alive (matches i18n_backfill.py, not this file)."""
    cmd = (
        "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*i18n_backfill.py*' }).Count"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=120)
        return r.stdout.strip() not in ("", "0")
    except (OSError, subprocess.SubprocessError):
        return False


def pending_count() -> int | None:
    """Pending locales from the last round's state file; None when unreadable.

    A locale counts as pending when it still has a real gap. `share` alone is
    the wrong measure: `el` reports share 0.9929 with `real_gaps: 0` and
    `share_real: 1.0` -- a value that differs from English only in its own
    punctuation is translated, not missing. Measured 2026-11-17: counting on
    `share` claimed all 185 locales were pending.
    """
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = data.get("locales") or data.get("rows") or []
    if isinstance(rows, list) and rows:
        def needs_work(row: object) -> bool:
            if not isinstance(row, dict):
                return False
            if row.get("real_gaps", 0) > 0:
                return True
            real = row.get("share_real")
            if isinstance(real, (int, float)):
                return real < 0.999
            return row.get("share", 1.0) < 0.999
        return sum(1 for r in rows if needs_work(r))
    for key in ("pending", "pending_locales"):
        if isinstance(data.get(key), int):
            return data[key]
    return None


def run_round(n: int) -> int:
    log(f"round {n}: starting i18n_backfill.py in {REPO}")
    before = pending_count()
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "i18n_backfill.py")],
                       cwd=str(REPO))
    after = pending_count()
    log(f"round {n}: exit {r.returncode}, pending {before} -> {after}")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-rounds", type=int, default=8, help="give up after this many rounds")
    ap.add_argument("--wait-seconds", type=int, default=60, help="poll interval while waiting")
    ap.add_argument("--dry-run", action="store_true", help="report state and exit")
    args = ap.parse_args()

    if args.dry_run:
        print(f"backfill running: {backfill_running()} | pending: {pending_count()}")
        return 0

    log(f"chain start (max {args.max_rounds} rounds)")
    for n in range(1, args.max_rounds + 1):
        waited = 0
        while backfill_running():
            if waited == 0:
                log("a backfill round is already running; waiting for it to finish")
            time.sleep(args.wait_seconds)
            waited += args.wait_seconds
            if waited > 6 * 3600:
                log("gave up waiting after 6 h")
                return 1
        pending = pending_count()
        if pending == 0:
            log("nothing pending any more; chain done")
            return 0
        rc = run_round(n)
        if rc != 0:
            log(f"round {n} failed with {rc}; stopping so the cron can take over")
            return rc
        if pending_count() == 0:
            log("all locales at target; chain done")
            return 0
    log(f"reached max rounds ({args.max_rounds}); stopping")
    return 0


if __name__ == "__main__":
    sys.exit(main())
