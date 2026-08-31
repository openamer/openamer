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
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
SKILLS_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\skills")
VALIDATOR_LOG = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\logs\skill-validator-latest.json")
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
        r = subprocess.run(["python", str(REPO / "scripts" / "darwin_engine.py"), "--status"],
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
        "updated": subprocess.run(["python", "-c", "from datetime import datetime,timezone;print(datetime.now(timezone.utc).isoformat(timespec='seconds'))"],
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
