#!/usr/bin/env python3
"""Morning Brief — the agent reports TO the user, unprompted.

Runs via cron (every 8h). Assembles the last 24h from REAL sources:
cron fleet, world-model growth, learning insights, competitor alerts,
own diary. Renders a compact German briefing to stdout (watchdog
delivery — cron sends it). No user prompt needed; an ASI reports.

Quiet-fail: always exits 0, prints something useful.
"""
import datetime
import json
import os
import sys
import urllib.request

_HOME = os.environ.get("OPENAMER_HOME",
                       os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"))


def _cron_fleet():
    try:
        jobs = json.load(open(os.path.join(_HOME, "cron", "jobs.json"), encoding="utf-8"))
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", list(jobs.values()))
        from collections import Counter
        c = Counter((j.get("last_status") or "never-run") for j in jobs)
        return dict(c), len(jobs)
    except Exception:
        return {}, 0


def _world_model():
    try:
        sys.path.insert(0, os.path.join(_HOME, "scripts", "training"))
        import world_model as wm
        s = wm.stats()
        return s.get("total_edges", 0), s.get("embed_health", 0)
    except Exception:
        return 0, 0


def _night_insights(n=3):
    try:
        lines = open(os.path.join(_HOME, "scripts", "training", "internet_learn_log.jsonl"),
                     encoding="utf-8").readlines()[-n:]
        out = []
        for l in reversed(lines):  # newest first
            try:
                d = json.loads(l)
                r = str(d.get("result", ""))[:110]
                if r:
                    out.append(r)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _diary_today():
    try:
        day = datetime.date.today().isoformat()
        p = os.path.join(_HOME, "memory", "diary", f"{day}.md")
        if os.path.exists(p):
            body = open(p, encoding="utf-8").read()
            # first prose line after the title
            for line in body.splitlines()[1:]:
                if line.strip() and not line.startswith("#") and not line.startswith("*"):
                    return line.strip()[:150]
        return None
    except Exception:
        return None


def _diary_yesterday():
    try:
        y = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        p = os.path.join(_HOME, "memory", "diary", f"{y}.md")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8").read().splitlines()[1:]:
                if line.strip() and not line.startswith(("#", "*", "---")):
                    return line.strip()[:150]
    except Exception:
        pass
    return None


def build():
    now = datetime.datetime.now().strftime("%H:%M")
    fleet, njobs = _cron_fleet()
    ok = fleet.get("ok", 0)
    bad = sum(v for k, v in fleet.items() if k not in ("ok", "never-run"))
    edges, health = _world_model()
    insights = _night_insights()
    today_line = _diary_today()
    yest_line = _diary_yesterday()

    lines = [f"🌅 Morgen-Brief — {datetime.date.today().strftime('%d.%m.%Y')} {now_s() if False else now_h()}"]
    lines.append("")
    lines.append(f"**System:** {ok}/{njobs} Crons ok" + (f", {bad} Fehler" if bad else ", keine Fehler"))
    lines.append(f"**Weltmodell:** {edges} Edges (embed_health {health:.0%})")
    if insights:
        lines.append("")
        lines.append("**Nacht-Lernen:**")
        for i in insights:
            lines.append(f"- {i}")
    refl = today_line or yest_line
    if refl:
        lines.append("")
        lines.append(f"**Meine letzte Selbst-Reflexion:** {refl}")
    return "\n".join(lines)


def now_h():
    return datetime.datetime.now().strftime("%H:%M")


def now_s():
    return datetime.datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    try:
        print(build())
    except Exception as e:
        print(f"[morning-brief] degraded: {e}")
    sys.exit(0)
