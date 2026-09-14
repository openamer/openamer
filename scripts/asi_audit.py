#!/usr/bin/env python3
"""ASI Capability Audit — what we can actually do, with evidence, not claims.

WHAT THIS IS
-----------
An honest inventory of the cognitive building blocks that "super-intelligence"
is usually defined by, each one scored against *executable evidence* rather
than a README sentence.

WHAT THIS IS NOT
----------------
It is NOT a claim that OpenAmer is an ASI. It is the opposite: the whole point
is that a system which cannot state its own limits honestly is not on that path
at all. A capability is scored PROVEN only when its implementation exists AND
something actually runs it — otherwise it is PARTIAL or ABSENT, out loud.

Scoring (deliberately strict):
  PROVEN   every evidence file exists AND at least one runtime signal is live
           (its cron job is enabled and last ran ok). Implementation + usage.
  PARTIAL  the implementation exists but nothing proven runs it — a capability
           on a shelf is not a capability.
  ABSENT   the implementation is missing.

Runtime evidence is read from the real cron store, so a capability silently
going dark shows up here as PARTIAL instead of staying "done" forever.

Exit code: 0 always (this is a report, not a gate) unless --strict, which exits
non-zero when any ABSENT capability remains.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop"))
REPO = Path(os.environ.get("OPENAMER_REPO", Path.home() / "openamer-repo"))

# The building blocks. `evidence` = files that must exist; `runtime` = cron job
# names that must be enabled and last-green. Keep the claim honest and narrow —
# a capability that can't be stated as one falsifiable line does not belong here.
CAPABILITIES = [
    {
        "name": "recursive self-improvement",
        "claim": "improves its own code or skills without being asked",
        "evidence": ["scripts/training/self_improve.py", "scripts/darwin_engine.py"],
        "runtime": ["self-improvement-loop", "Darwin Engine - hourly skill evolution"],
    },
    {
        "name": "calibrated self-knowledge",
        "claim": "states how sure it is, and is right about that",
        "evidence": ["scripts/training/predict_validate.py", "memory/calibration_ledger.jsonl"],
        "runtime": ["prediction-validator"],
    },
    {
        "name": "self-model",
        "claim": "maintains a model of its own identity and state",
        "evidence": ["scripts/training/self_model.py", "memory/self_model"],
        "runtime": ["self-model-evolution"],
    },
    {
        "name": "world model",
        "claim": "predicts outcomes from accumulated experience",
        "evidence": ["scripts/training/world_model.py", "memory/world_model.jsonl"],
        "runtime": ["knowledge-to-action"],
    },
    {
        "name": "episodic memory",
        "claim": "remembers what happened and retrieves it later",
        "evidence": ["scripts/longterm_memory.py", "memory/longterm_episodes.jsonl"],
        "runtime": ["longterm-memory-indexer"],
    },
    {
        "name": "analogical transfer",
        "claim": "applies a structure learned in one domain to another",
        "evidence": ["scripts/training/analogy_engine.py"],
        # Called as a subprocess by the online-learning daemon
        # (online_learning.py: `analogy_engine.py extract-batch`), which the
        # watchdog keeps alive — so the runtime signal is indirect but real.
        "runtime": ["online-learning-watchdog"],
    },
    {
        "name": "tool creation",
        "claim": "authors new tools/skills, not just calls existing ones",
        "evidence": ["scripts/training/auto_skill_creation.py"],
        "runtime": ["auto-skill-creation"],
    },
    {
        "name": "multi-agent coordination",
        "claim": "delegates and coordinates several agents",
        "evidence": ["scripts/training/swarm_intelligence.py"],
        "runtime": ["swarm-intelligence-cycle"],
    },
    {
        "name": "desktop embodiment",
        "claim": "acts on a real GUI and proves the effect with pixels",
        "evidence": ["scripts/desktop_ledger.py", "tools/computer_use/cua_backend.py"],
        "runtime": ["desktop-ledger-integrity"],
    },
    {
        "name": "continuous learning loop",
        "claim": "learns from the internet/diary on a schedule",
        "evidence": ["scripts/training/internet_learner.py", "scripts/training/session_diary.py"],
        "runtime": ["internet-learner-247"],
    },
]


def _cron_jobs() -> dict:
    path = HOME / "cron" / "jobs.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    return {j.get("name"): j for j in jobs if isinstance(j, dict)}


def _exists(rel: str) -> bool:
    return (HOME / rel).exists() or (REPO / rel).exists()


def audit() -> dict:
    jobs = _cron_jobs()
    rows = []
    for cap in CAPABILITIES:
        present = [e for e in cap["evidence"] if _exists(e)]
        missing = [e for e in cap["evidence"] if not _exists(e)]
        live, dark = [], []
        for name in cap["runtime"]:
            job = jobs.get(name)
            if job and job.get("enabled") and job.get("last_status") == "ok":
                live.append(name)
            else:
                dark.append(name)
        if missing or not present:
            status = "ABSENT"
        elif cap["runtime"] and not live:
            status = "PARTIAL"  # built, but nothing proven runs it
        elif not cap["runtime"]:
            status = "PARTIAL"  # no runtime signal asserted -> cannot call it proven
        else:
            status = "PROVEN"
        rows.append({
            "name": cap["name"],
            "claim": cap["claim"],
            "status": status,
            "evidence_present": present,
            "evidence_missing": missing,
            "runtime_live": live,
            "runtime_dark": dark,
        })
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("PROVEN", "PARTIAL", "ABSENT")}
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
        "capabilities": rows,
    }


def report(result: dict) -> str:
    c = result["counts"]
    lines = [
        "# ASI Capability Audit",
        "",
        f"_{result['ts']} — PROVEN {c['PROVEN']} · PARTIAL {c['PARTIAL']} · ABSENT {c['ABSENT']}_",
        "",
        "PROVEN means the implementation exists **and** something actually runs it.",
        "This is an inventory of building blocks, **not** a claim of super-intelligence —",
        "a system that cannot state its own limits is not on that path at all.",
        "",
        "| capability | status | evidence | runtime |",
        "|---|---|---|---|",
    ]
    for r in result["capabilities"]:
        ev = f"{len(r['evidence_present'])}/{len(r['evidence_present']) + len(r['evidence_missing'])} files"
        rt = ", ".join(r["runtime_live"]) if r["runtime_live"] else (", ".join(r["runtime_dark"]) or "— none asserted")
        icon = {"PROVEN": "✅", "PARTIAL": "🟡", "ABSENT": "❌"}[r["status"]]
        lines.append(f"| {r['name']} | {icon} {r['status']} | {ev} | {rt} |")
    gaps = [r for r in result["capabilities"] if r["status"] != "PROVEN"]
    if gaps:
        lines += ["", "## What is honestly missing", ""]
        for r in gaps:
            if r["status"] == "ABSENT":
                lines.append(f"- ❌ **{r['name']}** — {r['claim']} · missing: `{', '.join(r['evidence_missing'])}`")
            else:
                detail = r["runtime_dark"][0] if r["runtime_dark"] else "no runtime signal asserted"
                lines.append(f"- 🟡 **{r['name']}** — built, but not proven to run ({detail})")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ASI capability audit (evidence-based)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything is ABSENT")
    ap.add_argument("--save", action="store_true", help="write the report under memory/")
    args = ap.parse_args(argv)

    result = audit()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(report(result))
    if args.save:
        out = HOME / "memory" / "asi_audit.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.strict and result["counts"]["ABSENT"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())