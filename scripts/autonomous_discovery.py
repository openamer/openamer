#!/usr/bin/env python3
"""Autonomous Discovery & Evolution — bounded, zero-token discovery cycle.

The loop this implements is the one the Genesis directives ask for:

    DISCOVER -> UNDERSTAND -> COMPARE -> DECIDE -> (DEVELOP -> TEST -> VERIFY)

What it deliberately does NOT do:

* it does not call an LLM (no tokens, no cost, safe to cron every few hours)
* it does not execute or import code found on the internet (a finding is a
  *candidate*, never an auto-install)
* it does not invent a second research stack — it reuses the existing
  ``trend_scout.py`` radar, the cron execution ledger, the learner log and the
  research/hypothesis stores that this install already writes

What it does:

* DISCOVER  — external signals (HN/arXiv/news via trend_scout) plus internal
              telemetry (cron failures, learner rejection rate)
* UNDERSTAND— classify each signal into a capability domain
* COMPARE   — check whether the install already covers that domain, using the
              real skill library and script tree as the inventory; explicitly
              suppresses findings that an existing hypothesis already covers
* DECIDE    — score = impact x gap / effort, and gate the decision:
              ``auto`` only for reversible, dependency-free work; anything that
              needs credentials, money or an irreversible step is ``approval``
* PERSIST   — every stage is appended to ``memory/discovery/ledger.jsonl`` so a
              later session (or the dashboard) can replay why a decision was
              made, and ``state.json`` carries the latest picture

CLI:
    python autonomous_discovery.py --cycle            # run one full cycle
    python autonomous_discovery.py --status           # state as JSON
    python autonomous_discovery.py --status --text    # state as a report
    python autonomous_discovery.py --record-fix \
        --fix-title "..." --fix-before "..." --fix-after "..." \
        --fix-evidence "..." [--fix-finding FD-xxxx]

Exit code is 0 on a healthy cycle (including "nothing new"), 1 on a cycle that
could not write its state.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# ── Locations ──────────────────────────────────────────────────────────────
def _resolve_home() -> Path:
    env = os.environ.get("OPENAMER_HOME")
    if env:
        return Path(env)
    for cand in (
        Path.home() / "AppData" / "Local" / "openamer-laptop",
        Path.home() / "AppData" / "Local" / "openamer",
        Path.home() / ".openamer",
    ):
        if (cand / "cron").is_dir():
            return cand
    return Path.home() / "AppData" / "Local" / "openamer-laptop"


HOME = _resolve_home()
DISCOVERY_DIR = HOME / "memory" / "discovery"
LEDGER = DISCOVERY_DIR / "ledger.jsonl"
STATE = DISCOVERY_DIR / "state.json"
IMPROVEMENTS = DISCOVERY_DIR / "improvements.jsonl"

CRON_JOBS = HOME / "cron" / "jobs.json"
EXECUTIONS_DB = HOME / "cron" / "executions.db"
LEARN_LOG = HOME / "scripts" / "training" / "internet_learn_log.jsonl"
HYPOTHESES = HOME / "memory" / "hypotheses.json"
RESEARCH_LOG = HOME / "memory" / "research_log.jsonl"
SKILLS_DIR = HOME / "skills"
SCRIPTS_DIR = HOME / "scripts"

# Hard bounds so a cycle can never become a runaway.
MAX_EXTERNAL_SIGNALS = 40
MAX_INTERNAL_FINDINGS = 12
MAX_FINDINGS_KEPT = 40
STALE_REPORT_HOURS = 12
CRON_FAILURE_LOOKBACK_HOURS = 72

# ── Capability domains ─────────────────────────────────────────────────────
# Each domain maps a set of trigger tokens (matched against a signal title) to
# the vocabulary used to look the capability up in the local inventory. Keeping
# these two lists separate matters: the trigger decides *what a signal is
# about*, the probe decides *whether we already own it*.
DOMAINS = {
    "memory": {
        "triggers": ("memory", "retrieval", "rag", "embedding", "vector", "context window", "long-term"),
        "probes": ("memory", "longterm", "embedding", "vector", "retrieval"),
    },
    "reasoning": {
        "triggers": ("reasoning", "chain of thought", "planning", "plan", "inference-time", "test-time"),
        "probes": ("reason", "plan", "thinking", "metacog", "hypothes"),
    },
    "multi_agent": {
        "triggers": ("multi-agent", "multi agent", "swarm", "orchestration", "agent-to-agent", "a2a", "crew", "delegation"),
        "probes": ("swarm", "a2a", "agent-mesh", "orchestr", "delegat", "crew", "multi-agent"),
    },
    "tool_use": {
        "triggers": ("tool use", "tool-use", "function calling", "mcp", "model context protocol", "computer use"),
        "probes": ("tool", "mcp", "computer-use", "plugin"),
    },
    "self_improvement": {
        "triggers": ("self-improv", "self improv", "evolution", "evolutionary", "darwin", "rsi", "recursive"),
        "probes": ("self-improv", "darwin", "rsi", "evolv", "si-core", "curator"),
    },
    "evaluation": {
        "triggers": ("benchmark", "eval", "evaluation", "leaderboard", "swe-bench", "measurement"),
        "probes": ("benchmark", "eval", "capability-measurement", "scorecard"),
    },
    "efficiency": {
        "triggers": ("quantization", "quantized", "distill", "efficiency", "latency", "throughput", "tiny", "small model"),
        "probes": ("efficien", "quant", "distill", "local-cpu", "small-model", "sizing"),
    },
    "security": {
        "triggers": ("security", "prompt injection", "vulnerab", "cve", "sandbox", "jailbreak", "supply chain"),
        "probes": ("security", "injection", "cve", "sandbox", "vuln", "pentest"),
    },
    "coding_agent": {
        "triggers": ("coding agent", "code agent", "swe", "refactor", "code generation", "program synthesis"),
        "probes": ("code", "refactor", "simplif", "review", "lint"),
    },
    "infrastructure": {
        "triggers": ("serving", "inference server", "gpu", "npu", "deploy", "kubernetes", "vllm"),
        "probes": ("inference", "gpu", "npu", "serv", "deploy", "docker"),
    },
    # Internal domains: a finding from cron telemetry must be compared against
    # the watchdog/healing/learning capabilities that actually exist, otherwise
    # every reliability signal is scored as a MISSING capability and the queue
    # overstates the gap.
    "reliability": {
        "triggers": ("cron failure", "failed", "timeout", "watchdog", "unreliable"),
        "probes": ("watchdog", "watch", "heal", "guard", "monitor", "reaper", "health"),
    },
    "learning": {
        "triggers": ("learner", "learning", "training", "yield", "no insight"),
        "probes": ("learn", "train", "curriculum", "internet", "memory", "skill"),
    },
}

EFFORT_BY_DOMAIN = {  # 1 = small, 3 = large; only used to rank, never to gate
    "security": 2, "evaluation": 2, "efficiency": 2, "maintenance": 1,
    "reliability": 1, "learning": 1, "memory": 3, "reasoning": 3,
    "multi_agent": 3, "tool_use": 2, "self_improvement": 3, "coding_agent": 3,
    "infrastructure": 3, "external": 2,
}

# Domains whose work always needs a human decision before it runs.
APPROVAL_DOMAINS = {"infrastructure"}  # cost / credentials / irreversibility


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _age_hours(path: Path) -> float:
    try:
        return (_dt.datetime.now().timestamp() - path.stat().st_mtime) / 3600.0
    except OSError:
        return 1e9


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return default


def _iter_jsonl(path: Path, tail: int | None = None):
    """Yield parsed rows; unparsable lines are skipped, never fatal."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return
    if tail:
        lines = lines[-tail:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def append_ledger(cycle_id: str, stage: str, payload: dict) -> None:
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    row = {"ts": _now(), "cycle": cycle_id, "stage": stage, "payload": payload}
    with LEDGER.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ── COMPARE: the capability inventory ──────────────────────────────────────
def build_inventory() -> list[dict]:
    """One entry per installed capability: skills (name+description) + scripts."""
    inv: list[dict] = []
    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        try:
            head = skill_md.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            continue
        name = skill_md.parent.name
        desc = ""
        for line in head.splitlines():
            if line.lower().startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                break
        inv.append({
            "kind": "skill",
            "name": name,
            "text": f"{name} {desc}".lower(),
            "path": str(skill_md.relative_to(HOME)),
        })
    for py in list(SCRIPTS_DIR.glob("*.py")) + list(SCRIPTS_DIR.glob("training/*.py")):
        inv.append({
            "kind": "script",
            "name": py.stem,
            "text": py.stem.replace("_", " ").replace("-", " ").lower(),
            "path": str(py.relative_to(HOME)),
        })
    return inv


def compare_capability(domain: str, inventory: list[dict]) -> dict:
    """MISSING / PARTIAL / PRESENT, with the matching artifacts as evidence."""
    probes = DOMAINS.get(domain, {}).get("probes", ())
    hits = []
    for item in inventory:
        score = sum(1 for p in probes if p in item["text"])
        if score:
            hits.append((score, item))
    hits.sort(key=lambda x: -x[0])
    strong = [h for h in hits if h[0] >= 2]
    if strong:
        status = "PRESENT"
    elif len(hits) >= 2:
        status = "PARTIAL"
    elif hits:
        status = "PARTIAL"
    else:
        status = "MISSING"
    return {
        "domain": domain,
        "status": status,
        "evidence": [{"kind": h[1]["kind"], "name": h[1]["name"], "path": h[1]["path"]}
                     for h in hits[:5]],
        "match_count": len(hits),
    }


def _normalise(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def existing_hypothesis_overlap(title: str) -> str | None:
    """Return a hypothesis id that already covers this signal, if any.

    This is the anti-duplication rule: a signal whose vocabulary is already
    covered by a recorded hypothesis must not spawn a second task.
    """
    hyp = _read_json(HYPOTHESES, {})
    rows = hyp.get("hypotheses", hyp) if isinstance(hyp, dict) else hyp
    if not isinstance(rows, list):
        return None
    want = _normalise(title)
    if len(want) < 3:
        return None
    for row in rows[-400:]:
        text = str(row.get("hypothesis") or row.get("statement") or row.get("question") or "")
        have = _normalise(text)
        if not have:
            continue
        overlap = len(want & have) / len(want)
        if overlap >= 0.6:
            return str(row.get("id") or row.get("hyp_id") or "unknown")
    return None


# ── DISCOVER ───────────────────────────────────────────────────────────────
def discover_external() -> list[dict]:
    """External signals from the existing trend radar (no new fetcher)."""
    signals: list[dict] = []
    report = None
    for cand in (HOME / "reports" / "trend-scout-latest.md",
                 HOME.parent.parent / "openamer-repo" / "reports" / "trend-scout-latest.md",
                 Path(r"C:\Users\damir\openamer-repo\reports\trend-scout-latest.md")):
        if cand.is_file():
            report = cand
            break

    if report is None or _age_hours(report) > STALE_REPORT_HOURS:
        # Reuse the radar rather than duplicating its three fetchers.
        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            import trend_scout  # type: ignore
            trend_scout.main()
            for cand in (HOME / "reports" / "trend-scout-latest.md",
                         Path(r"C:\Users\damir\openamer-repo\reports\trend-scout-latest.md")):
                if cand.is_file():
                    report = cand
                    break
        except Exception as exc:  # network or import failure is not fatal
            append_ledger("n/a", "discover_error", {"source": "trend_scout", "error": str(exc)[:300]})

    if report is None or not report.is_file():
        return signals

    text = report.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- ") or "error:" in line:
            continue
        body = line[2:].strip()
        if len(body) < 15:
            continue
        points = 0
        m = re.search(r"\[HN (\d+)pts\]", body)
        if m:
            points = int(m.group(1))
        signals.append({
            "origin": "external",
            "source": "trend_scout",
            "title": body[:300],
            "strength": points,
        })
        if len(signals) >= MAX_EXTERNAL_SIGNALS:
            break
    return signals


def discover_internal() -> list[dict]:
    """Real telemetry: cron failures and learner throughput."""
    findings: list[dict] = []
    jobs = _read_json(CRON_JOBS, {})
    job_rows = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    names = {str(j.get("id")): (j.get("name") or str(j.get("id"))) for j in job_rows if isinstance(j, dict)}
    enabled = {str(j.get("id")): bool(j.get("enabled")) for j in job_rows if isinstance(j, dict)}

    cutoff = (_dt.datetime.now(_dt.timezone.utc)
              - _dt.timedelta(hours=CRON_FAILURE_LOOKBACK_HOURS)).isoformat(timespec="seconds")
    if EXECUTIONS_DB.is_file():
        try:
            con = sqlite3.connect(f"file:{EXECUTIONS_DB}?mode=ro", uri=True, timeout=5)
            rows = con.execute(
                "select job_id, count(*) from executions "
                "where status in ('error','failed','timeout','timed_out') and started_at >= ? "
                "group by job_id order by count(*) desc limit ?",
                (cutoff, MAX_INTERNAL_FINDINGS),
            ).fetchall()
            con.close()
        except sqlite3.Error as exc:
            append_ledger("n/a", "discover_error", {"source": "executions.db", "error": str(exc)[:300]})
            rows = []
        for job_id, count in rows:
            if not enabled.get(str(job_id), True):
                continue
            findings.append({
                "origin": "internal",
                "source": "cron",
                "title": f"Recurring cron failure: {names.get(str(job_id), job_id)} ({count} in {CRON_FAILURE_LOOKBACK_HOURS}h)",
                "strength": count,
                "domain_hint": "reliability",
                "evidence": f"cron/executions.db job_id={job_id}",
            })

    # Learner throughput over the last 40 cycles.
    tail = list(_iter_jsonl(LEARN_LOG, tail=40))
    if len(tail) >= 10:
        rejected = sum(1 for r in tail if "rejected" in str(r.get("result", "")).lower()
                       or "no insight" in str(r.get("result", "")).lower())
        rate = rejected / len(tail)
        if rate >= 0.5:
            findings.append({
                "origin": "internal",
                "source": "learner",
                "title": (f"Internet learner yield low: {rejected}/{len(tail)} recent cycles produced no "
                          f"training row ({rate:.0%} rejected)"),
                "strength": rejected,
                "domain_hint": "learning",
                "evidence": "scripts/training/internet_learn_log.jsonl (last 40 rows)",
            })

    # Research engine: experiments that end inconclusive do not teach anything.
    research = list(_iter_jsonl(RESEARCH_LOG, tail=60))
    inconclusive = sum(1 for r in research
                       if r.get("action") == "integrate"
                       and "inconclusive" in str(r.get("entry", {}).get("verdict", "")).lower())
    if inconclusive >= 3:
        findings.append({
            "origin": "internal",
            "source": "research_engine",
            "title": f"Research engine produced {inconclusive} inconclusive verdicts in its last 60 events",
            "strength": inconclusive,
            "domain_hint": "evaluation",
            "evidence": "memory/research_log.jsonl",
        })
    return findings


# ── UNDERSTAND / DECIDE ────────────────────────────────────────────────────
def classify(title: str) -> str:
    low = title.lower()
    best, best_hits = "external", 0
    for domain, cfg in DOMAINS.items():
        hits = sum(1 for t in cfg["triggers"] if t in low)
        if hits > best_hits:
            best, best_hits = domain, hits
    return best


def decide(domain: str, comparison: dict, strength: int, origin: str = "external") -> dict:
    gap = {"MISSING": 1.0, "PARTIAL": 0.55, "PRESENT": 0.1}[comparison["status"]]
    # A MEASURED failure is not a capability hypothesis: the defect exists
    # whether or not some watchdog is installed, so the "do we own this?" gap
    # must not discount it. The inventory still says HOW to fix it.
    if origin == "internal":
        gap = 1.0
    effort = EFFORT_BY_DOMAIN.get(domain, 2)
    # Impact is capped so one viral HN post cannot dominate the queue.
    impact = min(1.0, 0.35 + (min(strength, 400) / 400.0) * 0.65)
    score = round((impact * gap) / effort, 3)
    if domain in APPROVAL_DOMAINS:
        authority = "approval"
        reason = "infrastructure work can carry cost, credentials or an irreversible step"
    elif origin == "internal":
        authority = "auto"
        reason = "measured defect in own telemetry; reversible fix, no new dependency"
    elif comparison["status"] == "PRESENT":
        authority = "no-action"
        reason = "capability already installed and evidenced"
    else:
        authority = "auto"
        reason = "reversible, no new dependency, no credentials"
    threshold = 0.05
    return {
        "score": score,
        "gap": gap,
        "effort": effort,
        "impact": round(impact, 3),
        "authority": authority,
        "reason": reason,
        "accepted": score >= threshold and authority != "no-action",
    }


def finding_id(title: str) -> str:
    return "FD-" + hashlib.sha1(title.encode("utf-8", "replace")).hexdigest()[:8]


# ── Cycle ──────────────────────────────────────────────────────────────────
def run_cycle() -> dict:
    cycle_id = "cyc-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

    inventory = build_inventory()
    append_ledger(cycle_id, "inventory", {"capabilities": len(inventory),
                                          "skills": sum(1 for i in inventory if i["kind"] == "skill"),
                                          "scripts": sum(1 for i in inventory if i["kind"] == "script")})

    external = discover_external()
    internal = discover_internal()
    append_ledger(cycle_id, "discover", {"external": len(external), "internal": len(internal)})

    raw = []
    for s in external:
        raw.append({**s, "domain": classify(s["title"])})
    for s in internal:
        raw.append({**s, "domain": s.get("domain_hint") or classify(s["title"])})
    append_ledger(cycle_id, "understand", {"classified": len(raw),
                                           "domains": sorted({r["domain"] for r in raw})})

    seen_titles: set[str] = set()
    findings: list[dict] = []
    for item in raw:
        fid = finding_id(item["title"])
        key = fid
        if key in seen_titles:
            continue
        seen_titles.add(key)

        dup_hyp = existing_hypothesis_overlap(item["title"])
        comparison = compare_capability(item["domain"], inventory)
        decision = decide(item["domain"], comparison, int(item.get("strength") or 0),
                          origin=str(item.get("origin") or "external"))
        if dup_hyp:
            decision["accepted"] = False
            decision["authority"] = "duplicate"
            decision["reason"] = f"already covered by hypothesis {dup_hyp}"

        findings.append({
            "id": fid,
            "title": item["title"],
            "domain": item["domain"],
            "origin": item.get("origin"),
            "source": item.get("source"),
            "evidence": item.get("evidence") or item.get("source"),
            "capability": comparison,
            "decision": decision,
            "first_seen": _now(),
            "cycle": cycle_id,
        })

    findings.sort(key=lambda f: -f["decision"]["score"])
    append_ledger(cycle_id, "compare", {"findings": len(findings),
                                        "missing": sum(1 for f in findings if f["capability"]["status"] == "MISSING"),
                                        "partial": sum(1 for f in findings if f["capability"]["status"] == "PARTIAL"),
                                        "present": sum(1 for f in findings if f["capability"]["status"] == "PRESENT")})
    accepted = [f for f in findings if f["decision"]["accepted"]]
    append_ledger(cycle_id, "decide", {"accepted": len(accepted),
                                       "top": [{"id": f["id"], "score": f["decision"]["score"],
                                                "authority": f["decision"]["authority"]}
                                               for f in accepted[:5]]})

    previous = _read_json(STATE, {})
    improvements = list(_iter_jsonl(IMPROVEMENTS))
    state = {
        "schema": 1,
        "brand": "OpenAmer — Autonomous Discovery & Evolution",
        "last_cycle": {
            "id": cycle_id,
            "ts": _now(),
            "external_signals": len(external),
            "internal_signals": len(internal),
            "findings": len(findings),
            "accepted": len(accepted),
            "inventory_size": len(inventory),
        },
        "stage_totals": _stage_totals(previous.get("stage_totals", {})),
        "findings": findings[:MAX_FINDINGS_KEPT],
        "queue": [{"id": f["id"], "title": f["title"], "domain": f["domain"],
                   "score": f["decision"]["score"], "authority": f["decision"]["authority"]}
                  for f in accepted[:10]],
        "improvements": improvements[-25:],
        "improvement_count": len(improvements),
        "cycle_count": int(previous.get("cycle_count", 0)) + 1,
    }
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(STATE)
    append_ledger(cycle_id, "persist", {"state": str(STATE), "findings_kept": len(state["findings"])})
    return state


def _stage_totals(prev: dict) -> dict:
    totals = dict(prev) if isinstance(prev, dict) else {}
    stages = {"discover": 0, "understand": 0, "compare": 0, "decide": 0, "develop": 0, "test": 0, "verify": 0}
    for row in _iter_jsonl(LEDGER):
        stage = row.get("stage")
        if stage in stages:
            stages[stage] += 1
    for imp in _iter_jsonl(IMPROVEMENTS):
        stages["develop"] += 1
        if imp.get("tested"):
            stages["test"] += 1
        if imp.get("verified"):
            stages["verify"] += 1
    totals.update(stages)
    return totals


def record_fix(title: str, before: str, after: str, evidence: str, finding: str | None,
               tested: bool, verified: bool) -> dict:
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now(),
        "title": title,
        "finding": finding,
        "before": before,
        "after": after,
        "evidence": evidence,
        "tested": tested,
        "verified": verified,
    }
    with IMPROVEMENTS.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    append_ledger("manual", "improve", row)
    state = _read_json(STATE, {})
    if state:
        state["improvements"] = list(_iter_jsonl(IMPROVEMENTS))[-25:]
        state["improvement_count"] = sum(1 for _ in _iter_jsonl(IMPROVEMENTS))
        state["stage_totals"] = _stage_totals(state.get("stage_totals", {}))
        STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return row


def render_text(state: dict) -> str:
    lc = state.get("last_cycle", {})
    lines = [
        "OpenAmer — Autonomous Discovery & Evolution",
        "=" * 52,
        f"cycles run        : {state.get('cycle_count', 0)}",
        f"last cycle        : {lc.get('id', '-')} at {lc.get('ts', '-')}",
        f"signals           : external {lc.get('external_signals', 0)} / internal {lc.get('internal_signals', 0)}",
        f"findings          : {lc.get('findings', 0)} ({lc.get('accepted', 0)} accepted)",
        f"capability inventory: {lc.get('inventory_size', 0)} artifacts",
        f"verified improvements: {state.get('improvement_count', 0)}",
        "",
        "Stage totals:",
    ]
    for stage, n in (state.get("stage_totals") or {}).items():
        lines.append(f"  {stage:<10} {n}")
    lines += ["", "Top queue:"]
    for q in (state.get("queue") or [])[:8]:
        lines.append(f"  [{q['score']:.3f}] {q['authority']:<9} {q['domain']:<12} {q['title'][:80]}")
    if not state.get("queue"):
        lines.append("  (nothing accepted this cycle)")
    lines += ["", "Recent improvements:"]
    for imp in (state.get("improvements") or [])[-5:]:
        mark = "verified" if imp.get("verified") else ("tested" if imp.get("tested") else "recorded")
        lines.append(f"  [{mark}] {imp.get('title', '')[:70]}")
    return "\n".join(lines)


def _cron_report(new_findings: list[dict], state: dict) -> str:
    """Compact line for a no-agent cron slot.

    Prints ONLY when the cycle produced findings that were not in the previous
    state, so a quiet install stays silent instead of paging the user every
    few hours with the same list.
    """
    if not new_findings:
        return ""
    top = new_findings[:3]
    lines = [f"Autonomous Discovery: {len(new_findings)} new finding(s) "
             f"(cycle {state.get('cycle_count', '?')})"]
    for f in top:
        lines.append(f"- [{f['decision']['score']:.3f}] {f['domain']}/{f['capability']['status']}: "
                     f"{f['title'][:110]}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OpenAmer autonomous discovery cycle")
    ap.add_argument("--cycle", action="store_true", help="run one full discovery cycle")
    ap.add_argument("--status", action="store_true", help="print current state")
    ap.add_argument("--text", action="store_true", help="human-readable status")
    ap.add_argument("--cron", action="store_true",
                    help="run a cycle and print ONLY new accepted findings (quiet otherwise)")
    ap.add_argument("--record-fix", action="store_true", help="record a verified improvement")
    ap.add_argument("--fix-title", default="")
    ap.add_argument("--fix-before", default="")
    ap.add_argument("--fix-after", default="")
    ap.add_argument("--fix-evidence", default="")
    ap.add_argument("--fix-finding", default=None)
    ap.add_argument("--no-test", action="store_true", help="record fix as untested")
    args = ap.parse_args(argv)

    if args.record_fix:
        if not args.fix_title:
            print("--record-fix needs --fix-title", file=sys.stderr)
            return 2
        row = record_fix(args.fix_title, args.fix_before, args.fix_after, args.fix_evidence,
                         args.fix_finding, tested=not args.no_test, verified=bool(args.fix_after))
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0

    if args.cron:
        previous_ids = {f.get("id") for f in (_read_json(STATE, {}).get("findings") or [])}
        state = run_cycle()
        fresh = [f for f in state.get("findings", [])
                 if f["id"] not in previous_ids and f["decision"]["accepted"]]
        report = _cron_report(fresh, state)
        if report:
            print(report)
        return 0

    if args.cycle:
        state = run_cycle()
        print(render_text(state) if not args.status else json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    state = _read_json(STATE, {})
    if not state:
        print("no discovery state yet — run --cycle", file=sys.stderr)
        return 1
    print(render_text(state) if (args.text or not args.status) else json.dumps(state, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
