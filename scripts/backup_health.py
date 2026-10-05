#!/usr/bin/env python3
"""Survival-health probe — is self-preservation actually current?

A heartbeat TICK must PROBE, never RUN the heavy job. Running the full backup
inside a tick would blow the subsystem timeout; running second_home's git push
every 30 min would be noisy. The daily/12h CRONS do the work; this probe only
checks that they are doing it — the organ's health, not its labour.

Checks (fast, read-only):
  * newest filesystem backup age      (warn if > 48h)
  * DNA snapshot / wakeup manifest age (warn if > 30h)

Watchdog pattern: prints nothing when both are current; one line when stale.
Always exits 0 (a stale backup is a warning, not a crash).
"""
import os
import time
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
BACKUP_DIR = Path.home() / "openamer-backups"
REPO_LIFE = Path.home() / "openamer-repo" / "life"
DNA = REPO_LIFE / "dna-snapshot.json"

BACKUP_MAX_AGE_H = 48
DNA_MAX_AGE_H = 30


def _age_h(path: Path) -> float | None:
    try:
        return (time.time() - path.stat().st_mtime) / 3600
    except OSError:
        return None


def _newest_backup_age() -> float | None:
    try:
        subs = [p for p in BACKUP_DIR.iterdir() if p.is_dir()]
        if not subs:
            return None
        return min(_age_h(p) for p in subs if _age_h(p) is not None)
    except OSError:
        return None


def main() -> int:
    problems = []
    b = _newest_backup_age()
    if b is None:
        problems.append("no filesystem backup found")
    elif b > BACKUP_MAX_AGE_H:
        problems.append(f"newest backup is {b:.0f}h old (limit {BACKUP_MAX_AGE_H}h)")
    d = _age_h(DNA)
    if d is None:
        problems.append("no DNA snapshot found")
    elif d > DNA_MAX_AGE_H:
        problems.append(f"DNA snapshot is {d:.0f}h old (limit {DNA_MAX_AGE_H}h)")

    if problems:
        print("survival-health: " + "; ".join(problems))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
