"""SI Core health — does the executor of my goals still execute them?

The desire engine turns a measured deficit into a goal and hands it to the SI
core (`POST http://127.0.0.1:8123/goals`). That core is the only thing that
turns the goal into work. Measured 2026-11-06: it had **no** watchdog inside the
heartbeat — the `si-core-watchdog` cron was retired by the curator, and nothing
else referenced the core. A dead executor would have left
`memory/self_model/desires.json` looking perfectly healthy ("chosen: curiosity,
goal emitted") while nothing ever ran it.

Liveness alone is not the question. A process answering `/status` while its goal
queue stands still is exactly the "health probe passes, the leg is broken" false
positive. So this probe measures BEHAVIOUR:

  * is it answering at all,
  * has the `done` count in `memory/si/goals.json` moved since the last probe,
  * are goals sitting `active` for longer than they should,
  * if it is down: attempt one restart through the existing watchdog script.

It never waits for the core to come up (a tick must not block), and it keeps its
own baseline so "consuming" is a delta, not a guess.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

SI_API = "http://127.0.0.1:8123"
PROBE_TIMEOUT = 5.0
RESTART_TIMEOUT = 20.0
# A goal older than this while still "active" means the executor is not picking
# work up. The worker normally completes a small goal within a couple of minutes
# (measured: created 21:23 -> done 21:42 for a real one).
STALE_ACTIVE_MINUTES = 120
# With nothing active, a `done` count that has not moved for this long is only a
# warning: an idle machine with no open goals is healthy.
IDLE_TOLERANCE_MINUTES = 180


def _home() -> Path:
    env = __import__("os").environ.get("OPENAMER_HOME", "").strip()
    if env:
        return Path(env)
    base = Path.home() / "AppData" / "Local"
    for cand in (base / "openamer", base / "openamer-laptop"):
        if (cand / "memory").is_dir():
            return cand
    return base / "openamer"


HOME = _home()
GOALS = HOME / "memory" / "si" / "goals.json"
BASELINE = HOME / "memory" / "si" / ".si_core_probe.json"
WATCHDOG = HOME / "scripts" / "si_core_watchdog.py"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _alive() -> bool:
    try:
        with urllib.request.urlopen(SI_API + "/status", timeout=PROBE_TIMEOUT) as r:
            return r.status == 200
    except Exception:
        return False


def _goal_counts():
    """(done, active_rows) from the goal store, with the active ages."""
    goals = _read_json(GOALS, [])
    if not isinstance(goals, list):
        return 0, []
    done = sum(1 for g in goals if isinstance(g, dict) and g.get("status") == "done")
    active = []
    for g in goals:
        if not isinstance(g, dict) or g.get("status") != "active":
            continue
        created = str(g.get("created") or "")
        age_min = None
        try:
            ts = datetime.datetime.fromisoformat(created)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            age_min = round((_now() - ts).total_seconds() / 60.0, 1)
        except Exception:
            pass
        active.append({"id": g.get("id"), "age_minutes": age_min,
                       "desc": str(g.get("desc"))[:80]})
    return done, active


def _restart() -> str:
    """Ask the existing watchdog to bring the core back — never wait for it."""
    if not WATCHDOG.exists():
        return "no watchdog script to restart it"
    try:
        r = subprocess.run(
            [sys.executable, str(WATCHDOG)],
            capture_output=True, text=True, timeout=RESTART_TIMEOUT, check=False,
        )
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return f"restart attempted (rc={r.returncode}): {out[-1][:120] if out else 'no output'}"
    except Exception as exc:
        return f"restart failed: {exc}"


def health() -> dict:
    """Probe the goal executor. Returns the heartbeat's native result shape."""
    alive = _alive()
    done, active = _goal_counts()
    prev = _read_json(BASELINE, {}) or {}
    prev_done = prev.get("done")
    prev_ts = prev.get("ts")

    delta = None if not isinstance(prev_done, int) else done - prev_done
    idle_minutes = None
    if prev_ts:
        try:
            idle_minutes = round(
                (_now() - datetime.datetime.fromisoformat(prev_ts)).total_seconds() / 60.0, 1)
        except Exception:
            idle_minutes = None

    stale = [a for a in active
             if isinstance(a.get("age_minutes"), (int, float))
             and a["age_minutes"] > STALE_ACTIVE_MINUTES]

    reasons = []
    hard = False
    if not alive:
        reasons.append("core not answering on :8123")
        hard = True
    if stale:
        reasons.append(
            f"{len(stale)} goal(s) active longer than {STALE_ACTIVE_MINUTES}m "
            f"(oldest {stale[0]['age_minutes']}m)")
        hard = True
    if (alive and active and isinstance(delta, int) and delta == 0
            and prev_ts and (idle_minutes or 0) > 60):
        # work is waiting and the counter has not moved for an hour
        reasons.append(f"{len(active)} active goal(s) but done-count frozen at {done}")
        hard = True
    if (alive and not active and isinstance(delta, int) and delta == 0
            and prev_ts and (idle_minutes or 0) > IDLE_TOLERANCE_MINUTES):
        # nothing to do and nothing moving is fine â€” reported, not failed
        reasons.append(f"idle: no active goals and done-count unchanged for "
                       f"{idle_minutes}m")

    restart = None
    if not alive:
        restart = _restart()

    try:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({
            "ts": _now().isoformat(), "done": done, "alive": alive,
        }), encoding="utf-8")
    except Exception:
        pass

    return {
        "success": alive and not hard,
        "alive": alive,
        "done_total": done,
        "done_delta": delta,
        "active": len(active),
        "stale_active": stale[:5],
        "idle_minutes_since_last_probe": idle_minutes,
        "restart": restart,
        "reasons": reasons,
    }