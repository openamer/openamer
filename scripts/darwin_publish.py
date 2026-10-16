#!/usr/bin/env python3
"""darwin_publish.py — publish real Darwin data to the website (daily cron).

Collects:
  - skill-validator population stats + fittest skills
  - darwin_engine --status (population/species/trials)
  - latest autopatch report (reports/darwin-autopatch.json)
  - latest trend-scout headlines (reports/trend-scout-latest.md)

Writes website/static/darwin/darwin-status.json + a snapshot copy to
reports/darwin-status-latest.json. Zero LLM tokens.

Usage:  python scripts/darwin_publish.py
"""

import os
import json
import re
import subprocess
import sys
from pathlib import Path

# The repo root this script ships in, derived from the file's own location.
# It used to be a literal ``C:\Users\damir\openamer-repo``, so every consumer of
# REPO (reports/, website/static/darwin/, scripts/darwin_engine.py) pointed at
# one developer's machine: on any other checkout -- another user, a CI runner --
# the paths either did not exist or, worse, a same-named directory elsewhere was
# published from. Deriving it keeps the script self-locating.
REPO = Path(__file__).resolve().parents[1]
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _resolve_home(default: Path) -> Path:
    """Resolve OPENAMER_HOME robustly across shells (single source: darwin_engine).

    Never trust a bare ``os.environ["OPENAMER_HOME"]``: on 2026-10-13 this cron
    died with FileNotFoundError because the terminal env snapshot carried a
    stale ``OPENAMER_HOME=C:/Users/damir/AppData/Local/Temp/rt_test/home`` -- a
    scratch tree that no longer exists. Normalise MSYS drive forms (git-bash
    exports ``/c/Users/...``, which native Python reads as relative and expands
    to a phantom ``C:/c/...``), reject doubled-drive artefacts, and only accept
    a candidate that is a real install root.
    """
    local = default.parent
    candidates = [local / "openamer-laptop", local / "openamer"]
    picked = next((c for c in candidates if (c / "skills").is_dir()), default)

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return picked
    norm = raw.replace("\\", "/")
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None or not cand.exists():
        return picked
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip("\\")
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip("\\").lower()
        if head and head == drive[0].lower():
            return picked
    if any((cand / m).exists() for m in _HOME_MARKERS):
        return cand
    print(f"[darwin-publish] WARNING: OPENAMER_HOME={cand} exists but is not an "
          f"OpenAmer install root; falling back to {picked}.", file=sys.stderr)
    return picked


def _find_validator_log(home: Path) -> Path:
    """Locate logs/skill-validator-latest.json, preferring a real install."""
    tried = []
    local = Path.home() / "AppData" / "Local"
    for cand in (home, local / "openamer-laptop", local / "openamer",
                 Path(os.environ.get("OPENAMER_HOME", "") or home)):
        if not cand:
            continue
        log = Path(cand) / "logs" / "skill-validator-latest.json"
        if log.is_file():
            return log
        tried.append(str(log))
    raise FileNotFoundError(
        "skill-validator-latest.json not found; tried: " + "; ".join(tried))


SKILLS_DIR = _resolve_home(Path.home() / "AppData" / "Local" / "openamer") / "skills"
VALIDATOR_LOG = _find_validator_log(SKILLS_DIR.parent)
AUTOpatch_JSON = REPO / "reports" / "darwin-autopatch.json"
TRENDS_MD = REPO / "reports" / "trend-scout-latest.md"
OUT_STATIC = REPO / "website" / "static" / "darwin" / "darwin-status.json"
OUT_REPORT = REPO / "reports" / "darwin-status-latest.json"
TOP_N = 10


def validator_stats() -> tuple[int, float, list[dict]]:
    data = json.loads(VALIDATOR_LOG.read_text(encoding="utf-8"))
    rows = data.get("skill_results", [])
    n = len(rows)
    avg = round(sum(s["score"] for s in rows) / max(n, 1), 1)
    fittest = sorted(rows, key=lambda s: -s["score"])[:TOP_N]
    return n, avg, [{"name": s["name"], "score": s["score"]} for s in fittest]


def engine_status() -> dict:
    out = {}
    try:
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "darwin_engine.py"), "--status"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, cwd=str(REPO))
        for line in r.stdout.splitlines():
            m = re.match(r"\s*Population:\s*(\d+)", line)
            if m: out["population_engine"] = int(m.group(1))
            m = re.match(r"\s*Species:\s*(\d+)", line)
            if m: out["species"] = int(m.group(1))
            m = re.match(r"\s*Active trials:\s*(\d+)", line)
            if m: out["trials"] = int(m.group(1))
            m = re.match(r"\s*Harvested ideas:\s*(\d+)", line)
            if m: out["harvested"] = int(m.group(1))
    except Exception:
        pass
    out.setdefault("species", 0)
    out.setdefault("trials", 0)
    out.setdefault("harvested", 0)
    return out


def autopatch() -> dict:
    try:
        d = json.loads(AUTOpatch_JSON.read_text(encoding="utf-8"))
        return {"timestamp": d.get("timestamp"),
                "kept": d.get("kept", [])[:10]}
    except Exception:
        return {"timestamp": None, "kept": []}


def trends(limit: int = 8) -> list[dict]:
    try:
        text = TRENDS_MD.read_text(encoding="utf-8", errors="replace")
        items = re.findall(r"- \[(\w+)\] ([^—]+) — (https?://\S+)", text)
        return [{"source": src, "title": title.strip(), "url": url}
                for src, title, url in items[:limit]]
    except Exception:
        return []


def main() -> int:
    population, avg, fittest = validator_stats()
    status = {
        "updated": subprocess.run([sys.executable, "-c", "from datetime import datetime,timezone;print(datetime.now(timezone.utc).isoformat(timespec='seconds'))"],
                                  capture_output=True, text=True).stdout.strip(),
        "population": population,
        "avg_score": avg,
        "fittest": fittest,
        "autopatch": autopatch(),
        "trends": trends(),
        **engine_status(),
    }
    OUT_STATIC.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATIC.write_text(json.dumps(status, indent=2), encoding="utf-8")
    OUT_REPORT.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"published: {OUT_STATIC} (population={population}, avg={avg}, "
          f"autopatch_kept={len(status['autopatch']['kept'])}, trends={len(status['trends'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
