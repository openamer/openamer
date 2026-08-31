#!/usr/bin/env python3
"""punkt_morning.py — "Punkt" morning companion (data collector for cron).

Gathers overnight state and prints a compact German briefing:
  - cron fleet health (errors first)
  - git activity (last 24h commits, open issues/PRs)
  - trend scout latest headlines
  - darwin ecosystem status
Silent-failure safe: every block is wrapped, missing sources are skipped.

Used by cron job "Punkt Morgen-Briefing" (07:30 daily).
"""
from __future__ import annotations

import datetime
import json
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
CRON_JOBS = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\cron\jobs.json")
TREND_LATEST = REPO / "reports" / "trend-scout-latest.md"
OUT = REPO / "reports" / "punkt-briefing.md"


def _git(args: list[str]) -> str:
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=20, cwd=str(REPO))
        return r.stdout.strip()
    except Exception:
        return ""


def cron_health() -> str:
    lines = []
    try:
        data = json.loads(CRON_JOBS.read_text(encoding="utf-8"))
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
        if isinstance(jobs, dict):
            jobs = list(jobs.values())
        errors = [j for j in jobs if isinstance(j, dict) and j.get("last_status") == "error" and j.get("enabled")]
        total = len([j for j in jobs if isinstance(j, dict)])
        lines.append(f"Cron-Fleet: {total} Jobs, {len(errors)} mit Fehler")
        for j in errors[:5]:
            lines.append(f"  ❌ {j.get('name', j.get('job_id'))}")
    except Exception as e:
        lines.append(f"Cron-Fleet: nicht lesbar ({e})")
    return "\n".join(lines)


def git_activity() -> str:
    since = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    commits = _git(["log", "--oneline", f"--since={since}"])
    n = len(commits.splitlines()) if commits else 0
    lines = [f"Git (24h): {n} Commits"]
    for c in (commits.splitlines()[:5] if commits else []):
        lines.append(f"  • {c}")
    # GitHub counts (unauthenticated, cached-friendly)
    try:
        with urllib.request.urlopen("https://api.github.com/repos/openamer/openamer", timeout=10) as resp:
            d = json.loads(resp.read())
        lines.append(f"GitHub: ⭐ {d.get('stargazers_count')} 🍴 {d.get('forks_count')} 👁 {d.get('subscribers_count')}")
    except Exception:
        pass
    return "\n".join(lines)


def trends() -> str:
    try:
        text = TREND_LATEST.read_text(encoding="utf-8", errors="replace")
        # first meaningful lines
        picks = [l.strip() for l in text.splitlines() if l.strip().startswith(("#", "-", "##"))][:8]
        return "Trends (trend_scout latest):\n" + "\n".join(f"  {p}" for p in picks) if picks else "Trends: keine Einträge"
    except Exception:
        return "Trends: keine Datei"


def darwin_status() -> str:
    try:
        fitness = REPO / "reports" / "darwin-fitness.json"
        d = json.loads(fitness.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            n = len(d)
            best = max(d.items(), key=lambda kv: kv[1] if isinstance(kv[1], (int, float)) else 0)
            return f"Darwin: {n} Skills getrackt, Fittest: {best[0]} ({best[1]})"
    except Exception:
        pass
    try:
        r = subprocess.run(["python", str(REPO / "scripts" / "darwin_engine.py"), "--status"],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, cwd=str(REPO))
        return "Darwin: " + " | ".join(l.strip() for l in r.stdout.splitlines() if "Population" in l or "Species" in l)
    except Exception:
        return "Darwin: Status nicht verfügbar"


def opportunities() -> str:
    """Derive the day's top-3 actionable opportunities from real signals."""
    items: list[str] = []

    # 1) failing crons = immediate fix opportunities
    try:
        data = json.loads(CRON_JOBS.read_text(encoding="utf-8"))
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
        if isinstance(jobs, dict):
            jobs = list(jobs.values())
        errs = [j for j in jobs if isinstance(j, dict) and j.get("enabled")
                and j.get("last_status") == "error"]
        for j in errs[:2]:
            items.append(f"🔴 Cron '{j.get('name')}' schlug fehl — jetzt fixen "
                         f"(openamer cron run {j.get('job_id', '')})")
    except Exception:
        pass

    # 2) trend radar: newest arxiv entries = content/outreach material
    try:
        text = TREND_LATEST.read_text(encoding="utf-8", errors="replace")
        arxiv = [l.strip() for l in text.splitlines() if "[arXiv]" in l][:2]
        for a in arxiv:
            items.append(f"📈 Trend-Signal für GitHub/Post nutzen: {a[:120]}")
    except Exception:
        pass

    # 3) darwin candidates awaiting promotion
    try:
        cand = list((REPO / "darwin" / "species-candidates").glob("*/SKILL.md"))
        if cand:
            names = ", ".join(c.parent.name for c in cand[:3])
            items.append(f"🧬 {len(cand)} Darwin-Kandidat(en) bereit zur Prüfung: {names}")
    except Exception:
        pass

    if not items:
        items.append("✅ Keine blockierenden Aufgaben — Fokus auf Wachstum/Outreach.")
    return "Top-Chancen:\n" + "\n".join(f"  {i}" for i in items[:3])


def main() -> int:
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    parts = [f"# ☀️ PUNKT — Morgen-Briefing {now}", "",
             cron_health(), "", git_activity(), "", trends(), "", darwin_status(), "",
             opportunities(), ""]
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
