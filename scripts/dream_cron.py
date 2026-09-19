#!/usr/bin/env python3
"""Cron wrapper: run dream cycle (REM replay) + memory consolidation (sleep).

Order matters, like human sleep: first REM replays the day, then deep sleep
consolidates it — compressing old low-usefulness episodes, promoting what
mattered, archiving (never deleting) the rest.

Prints the dream report verbatim (watchdog-style delivery), then appends a
one-line consolidation summary.

Guard (added 2026-09-19): the children resolve OPENAMER_HOME themselves, but a
scratch home still exists on this host, so a run that replayed 0 messages while
the real state.db holds hundreds is treated as a FAILURE rather than reported
as a quiet night. That exact silent-green failure is what hid this bug.
"""
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import datetime

# Markers only a real OpenAmer home carries (see scripts/dream_cycle.py).
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth: pathlib.Path) -> bool:
    try:
        return any((pth / m).exists() for m in _HOME_MARKERS)
    except OSError:
        return False


def _resolve_home() -> pathlib.Path:
    """Resolve the live install across shells; never adopt a scratch dir.

    git-bash exports OPENAMER_HOME in MSYS form (/c/tmp/oa-home), which native
    Windows Python reads as a RELATIVE path -> phantom C:\\c\\tmp\\oa-home.
    """
    local = pathlib.Path.home() / "AppData" / "Local"
    candidates = [local / "openamer-laptop", local / "openamer"]
    default = next((c for c in candidates if (c / "skills").is_dir()), candidates[0])

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default

    cand = None
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = pathlib.Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = pathlib.Path(raw)
        if p.is_absolute():
            cand = p

    if cand is not None and cand.exists() and _is_install_root(cand):
        return cand
    return default


BASE = _resolve_home()
day = datetime.date.today().isoformat()


def _messages_today() -> int:
    """How many user/assistant messages the real store holds for *day*."""
    db = BASE / "state.db"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(str(db))
        try:
            return con.execute(
                "SELECT COUNT(*) FROM messages WHERE "
                "date(timestamp, 'unixepoch') = ? AND role IN ('user','assistant')",
                (day,),
            ).fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


# 1. REM: replay the day's sessions -> dreams.json + report
r = subprocess.run([sys.executable, str(BASE / "scripts" / "dream_cycle.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=300)

# 2. Deep sleep: consolidate episodic memory
c = subprocess.run([sys.executable, str(BASE / "scripts" / "training" / "memory_consolidation.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=300)

rep = BASE / "reports" / f"dream-{day}.md"
if rep.exists():
    text = rep.read_text(encoding="utf-8")
    # Sanity gate: a "clear night" is only believable if there was nothing to
    # read. If the store holds messages but the dream replayed none, the run
    # silently resolved the wrong home -- report it as the failure it is.
    m = re.search(r"Replayed (\d+) messages", text)
    real_msgs = _messages_today()
    if m and int(m.group(1)) == 0 and real_msgs > 0:
        print("ERROR: dream replayed 0 messages while the store holds "
              f"{real_msgs} for {day} -- HOME={BASE} (wrong home?)\n")
    print(text)
else:
    print("ERROR: no dream report\n" + r.stdout + (r.stderr or ""))
    if real_msgs := _messages_today():
        print(f"\n[note] the real store holds {real_msgs} messages for {day}; "
              f"HOME resolved to {BASE}")

# consolidation summary (one line, non-fatal)
if c.returncode == 0 and c.stdout.strip():
    print("\n---\n" + c.stdout.strip())
elif c.returncode != 0:
    print("\n---\n[consolidation] ERROR: " + (c.stderr or c.stdout).strip()[:300])

# 3. Diary: write yesterday's first-person entry (continuity of self)
try:
    d = subprocess.run([sys.executable,
                        str(BASE / "scripts" / "training" / "session_diary.py"),
                        "--days", "1"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    if d.stdout.strip():
        print("\n---\n" + d.stdout.strip())
except Exception as ex:
    print(f"\n---\n[diary] skipped: {ex}")
