#!/usr/bin/env python3
"""
Darwin Engine — Evolutionary skill ecosystem for OpenAmer
==========================================================

The first engine that treats skills like populations:

  1. FITNESS   : Jedes Skill bekommt einen fitness score from REAL signals
                 (session usage, cron failure rate, age).
  2. SELEKTION : Weak skills get flagged (archive/deprecate), strong ones become parents.
  3. MUTATION  : Variants are generated from strong skills (prompts, trigger conditions) - one genome per skill.
  4. KREUZUNG  : Two parent skills produce a child combining their strengths.
  5. AUSLESE   : Varianten treten per A/B-Signal (Cron-Exit-Codes,
                 usage frequency) against each other; the winner replaces
                 den Elternteil, der Verlierer wird archiviert.

Core idea: no human curates skills anymore - the population evolves itself. Unique among agent frameworks.

CLI:
  --scan      compute fitness for all skills -> reports/darwin-fitness.json
  --mutate    generate mutations from top parents (dry-run until --apply)
  --crossover crossover two skills -> child skill (draft)
  --compete   collect A/B signals, install winner
  --report    human-readable report -> reports/darwin-report.md
  --full      scan -> mutate -> compete -> report

Exit codes: 0 = ok, 1 = no data, 2 = evolution made changes.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
SKILLS_DIR = HOME / "skills"
REPORTS_DIR = Path("reports")
DARWIN_DIR = HOME / "darwin"
POPULATION_FILE = DARWIN_DIR / "population.json"
FITNESS_FILE = REPORTS_DIR / "darwin-fitness.json"
REPORT_FILE = REPORTS_DIR / "darwin-report.md"

NOW = datetime.now(timezone.utc)


def _now() -> str:
    return NOW.isoformat()


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 1. FITNESS — echte Signale aus dem System sammeln
# ─────────────────────────────────────────────────────────────────────────────

def _session_skill_hits() -> dict[str, int]:
    """Count how often each skill is mentioned across past sessions."""
    hits: dict[str, int] = {}
    db_candidates = [
        HOME / "state.db",
        HOME / "sessions.db",
        HOME / "data" / "sessions.db",
    ]
    db = next((p for p in db_candidates if p.exists()), None)
    if not db:
        return hits
    try:
        import sqlite3
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT content FROM messages WHERE role='user' OR role='assistant'"
        ).fetchall()
        conn.close()
        skill_names = [d.name for d in SKILLS_DIR.iterdir() if d.is_dir()]
        for (content,) in rows:
            if not content:
                continue
            for name in skill_names:
                if name in content:
                    hits[name] = hits.get(name, 0) + 1
    except Exception:
        pass
    return hits


def _cron_skill_status() -> dict[str, str]:
    """Last status of each skill cron job (best effort)."""
    status: dict[str, str] = {}
    cron_dir = HOME / "cron"
    for f in cron_dir.glob("*.json"):
        data = _load_json(f, {})
        skills = data.get("skills") or []
        st = data.get("last_status", "")
        for s in skills:
            status[s] = st
    return status


CRON_JOBS_FILE = HOME / "cron" / "jobs.json"


def _load_cron_jobs() -> dict:
    return _load_json(CRON_JOBS_FILE, {})


def _save_cron_jobs(jobs: dict) -> None:
    CRON_JOBS_FILE.write_text(
        json.dumps(jobs, indent=2, ensure_ascii=False), "utf-8")


def _job_skills(job: dict) -> list:
    return job.get("skills") or ([job["skill"]] if job.get("skill") else [])


def start_trial(parent: str, child: str, job_id: str | None = None) -> dict | None:
    """Temporarily swap a cron job's skill from `parent` to `child`.

    Picks the first enabled job that references the parent skill (or the
    explicit job_id). Records the original skill(s) so end_trial() can
    restore them. Returns trial metadata or None if no job matches.
    """
    jobs = _load_cron_jobs()
    if not jobs:
        return None
    items = jobs.get("jobs") if isinstance(jobs, dict) else jobs
    if items is None:
        return None
    for job in items:
        if job_id and job.get("id") != job_id:
            continue
        if not job_id and (not job.get("enabled") or parent not in _job_skills(job)):
            continue
        trial = {
            "child": child,
            "parent": parent,
            "job_id": job.get("id"),
            "job_name": job.get("name"),
            "original_skills": _job_skills(job),
            "started": _now(),
            "executions_before": _execution_count(job.get("id")),
        }
        # swap skills on the job
        if "skills" in job and isinstance(job.get("skills"), list):
            job["skills"] = [child if s == parent else s for s in job["skills"]]
        elif job.get("skill") == parent:
            job["skill"] = child
        _save_cron_jobs(jobs)
        trial_path = DARWIN_DIR / "trials" / f"{job.get('id')}.json"
        _save_json(trial_path, trial)
        return trial
    return None


def end_trial(job_id: str, won: bool) -> dict | None:
    """Restore the original skill on a trial job (if the child lost)."""
    trial_path = DARWIN_DIR / "trials" / f"{job_id}.json"
    trial = _load_json(trial_path, {})
    if not trial:
        return None
    jobs = _load_cron_jobs()
    items = jobs.get("jobs") if isinstance(jobs, dict) else jobs
    if items is None:
        return None
    for job in items:
        if job.get("id") != job_id:
            continue
        if "skills" in job and isinstance(job.get("skills"), list):
            job["skills"] = [
                trial["parent"] if s == trial["child"] else s for s in job["skills"]
            ]
        elif job.get("skill") == trial["child"]:
            job["skill"] = trial["parent"]
        _save_cron_jobs(jobs)
        break
    trial["ended"] = _now()
    trial["won"] = won
    _save_json(trial_path, trial)
    return trial


def _execution_count(job_id: str | None) -> int:
    """Number of completed executions for a job (from executions.db)."""
    if not job_id:
        return 0
    db = HOME / "cron" / "executions.db"
    if not db.exists():
        return 0
    try:
        import sqlite3
        conn = sqlite3.connect(str(db))
        n = conn.execute(
            "SELECT COUNT(*) FROM executions WHERE job_id=? AND status='completed'",
            (job_id,),
        ).fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def _execution_outcomes(job_id: str, since_count: int) -> dict:
    """Post-trial execution outcomes: completed vs error counts."""
    db = HOME / "cron" / "executions.db"
    result = {"completed": 0, "error": 0}
    if not db.exists() or not job_id:
        return result
    try:
        import sqlite3
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT status FROM executions WHERE job_id=?", (job_id,)
        ).fetchall()
        conn.close()
        # newest executions are at the end of the table
        new_rows = rows[since_count:]
        for (st,) in new_rows:
            if st == "completed":
                result["completed"] += 1
            else:
                result["error"] += 1
    except Exception:
        pass
    return result


def evaluate_trials(min_executions: int = 2) -> list[dict]:
    """Evaluate running trials with REAL execution evidence.

    A child wins when it has at least `min_executions` completed runs and
    zero errors during the trial window. Otherwise the parent is restored.
    """
    results = []
    trials_dir = DARWIN_DIR / "trials"
    if not trials_dir.exists():
        return results
    for tp in sorted(trials_dir.glob("*.json")):
        trial = _load_json(tp, {})
        if trial.get("ended"):
            continue
        job_id = trial.get("job_id", "")
        outcomes = _execution_outcomes(job_id, trial.get("executions_before", 0))
        total = outcomes["completed"] + outcomes["error"]
        if total < min_executions:
            results.append({"job_id": job_id, "child": trial.get("child"),
                            "status": "waiting", "outcomes": outcomes})
            continue
        won = outcomes["completed"] >= min_executions and outcomes["error"] == 0
        end_trial(job_id, won)
        results.append({"job_id": job_id, "child": trial.get("child"),
                        "status": "won" if won else "lost", "outcomes": outcomes})
        # record in population genome
        population = _load_json(POPULATION_FILE, {})
        genome = population.setdefault(trial.get("parent", ""), {"wins": 0, "losses": 0})
        if won:
            genome["losses"] = genome.get("losses", 0) + 1  # parent lost a slot
            promote_child(trial["parent"], trial["child"])
            record_lineage(trial["parent"], trial["child"], "trial_win",
                           {"job_id": job_id, "outcomes": outcomes})
        else:
            genome["wins"] = genome.get("wins", 0) + 1
        _save_json(POPULATION_FILE, population)
    return results


def promote_child(parent: str, child: str) -> bool:
    """Install the winning child: replace parent's SKILL.md content and
    archive the parent. Never deletes data."""
    import shutil
    child_dir = DARWIN_DIR / "offspring" / child
    parent_dir = SKILLS_DIR / parent
    if not (child_dir / "SKILL.md").exists() or not parent_dir.exists():
        return False
    archive = DARWIN_DIR / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / f"{parent}_{NOW.strftime('%Y%m%d_%H%M%S')}"
    if not target.exists():
        shutil.copytree(str(parent_dir), str(target))
        shutil.rmtree(str(parent_dir))
    shutil.copytree(str(child_dir), str(parent_dir))
    # mark offspring meta installed
    meta_path = DARWIN_DIR / "offspring" / f"{child}.json"
    meta = _load_json(meta_path, {})
    meta["status"] = "installed"
    meta["installed"] = _now()
    _save_json(meta_path, meta)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 6. PHASE 3: autopilot, quarantine prune, rollback
# ─────────────────────────────────────────────────────────────────────────────

ROLLBACK_LOG = DARWIN_DIR / "rollback-log.json"


def _cron_referenced_skills() -> set[str]:
    """All skills referenced by any cron job (jobs.json + legacy *.json)."""
    protected: set[str] = set()
    jobs = _load_cron_jobs()
    items = jobs.get("jobs") if isinstance(jobs, dict) else jobs
    if items:
        for job in items:
            protected.update(_job_skills(job))
    for f in (HOME / "cron").glob("*.json"):
        if f.name == "jobs.json":
            continue
        data = _load_json(f, {})
        protected.update(data.get("skills") or [])
    return protected


def quarantine(fitness: dict, threshold: int = 0, dry_run: bool = True) -> list[dict]:
    """Move zero-signal skills to quarantine (reversible, not deleted).

    A skill is quarantined when fitness <= threshold AND usage == 0 AND it
    has no active cron job. Quarantine dir keeps them out of the population
    scan while remaining fully recoverable via --rollback.
    """
    import shutil
    protected = _cron_referenced_skills()
    q_dir = DARWIN_DIR / "quarantine"
    q_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for name, s in fitness.items():
        if s["fitness"] > threshold or s["usage"] > 0:
            continue
        if name in protected:
            continue  # skill referenced by a job -> never quarantine blindly
        src = SKILLS_DIR / name
        if not src.exists():
            continue
        moved.append({"skill": name, "fitness": s["fitness"], "when": _now()})
        if not dry_run:
            shutil.move(str(src), str(q_dir / name))
    if moved and not dry_run:
        log = _load_json(ROLLBACK_LOG, [])
        log.extend(moved)
        _save_json(ROLLBACK_LOG, log)
    return moved


def rollback(count: int = 1) -> list[str]:
    """Restore the last N quarantined skills to the live population."""
    import shutil
    log = _load_json(ROLLBACK_LOG, [])
    restored = []
    for entry in reversed(log[-count:]):
        name = entry.get("skill")
        src = DARWIN_DIR / "quarantine" / name
        dst = SKILLS_DIR / name
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            restored.append(name)
    if restored:
        _save_json(ROLLBACK_LOG, [e for e in log if e.get("skill") not in restored])
    return restored


def autopilot(min_executions: int = 2) -> int:
    """Full unattended evolution cycle. Returns exit code (2 = changes made)."""
    fitness = compute_fitness()
    _save_json(FITNESS_FILE, {"updated": _now(), "skills": fitness})
    print(f"[autopilot] fitness computed for {len(fitness)} skills")

    offspring = mutate(fitness, apply=True)
    print(f"[autopilot] {len(offspring)} mutations generated")

    trials = evaluate_trials(min_executions)
    for t in trials:
        print(f"[autopilot] trial {t['job_id']}: {t['status']} {t['outcomes']}")

    comps = compete()
    if any(c["won"] for c in comps):
        print(f"[autopilot] {sum(1 for c in comps if c['won'])} candidate(s) promoted")

    started = tournament(fitness, max_trials=2)
    if started:
        for s in started:
            print(f"[autopilot] tournament: trialing `{s['child']}` "
                  f"on job '{s['job_name']}'")

    quarantined = quarantine(fitness, threshold=0, dry_run=False)
    if quarantined:
        print(f"[autopilot] quarantined {len(quarantined)} dead skills: "
              f"{[q['skill'] for q in quarantined]}")

    md = report(fitness, offspring, comps)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(md, "utf-8")
    print(f"[autopilot] report -> {REPORT_FILE}")

    changed = bool(offspring or trials or comps or quarantined or started)
    return 2 if changed else 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. PHASE 4: lineage, mermaid tree, genome sync
# ─────────────────────────────────────────────────────────────────────────────

LINEAGE_FILE = DARWIN_DIR / "lineage.json"


def record_lineage(parent: str, child: str, kind: str, extra: dict | None = None) -> None:
    """Append an evolution event to the lineage graph (persistent family tree)."""
    graph = _load_json(LINEAGE_FILE, {"events": []})
    event = {"parent": parent, "child": child, "kind": kind, "when": _now()}
    if extra:
        event.update(extra)
    graph["events"].append(event)
    _save_json(LINEAGE_FILE, graph)


def lineage_mermaid(limit: int = 40) -> str:
    """Render the evolution family tree as a Mermaid graph for the report."""
    graph = _load_json(LINEAGE_FILE, {"events": []})
    events = graph["events"][-limit:]
    if not events:
        return ""
    lines = ["```mermaid", "graph TD"]
    seen: set[str] = set()
    for e in events:
        child = (e.get("child") or "unknown").replace('"', "")
        parent = (e.get("parent") or "unknown").replace('"', "")
        style = {"mutation": "-->", "crossover": "==>", "trial_win": "-.->"}\
            .get(e.get("kind", "mutation"), "-->")
        lines.append(f'    {parent}["{parent}"] {style} {child}["{child}"]')
        seen.add(parent)
        seen.add(child)
    lines.append("```")
    return "\n".join(lines)


def export_genome(path: Path | None = None) -> Path:
    """Export the full evolution state (fitness, lineage, population, archive
    manifest) as one portable genome file - for fleet sync across machines."""
    state = {
        "exported": _now(),
        "population": _load_json(POPULATION_FILE, {}),
        "lineage": _load_json(LINEAGE_FILE, {"events": []}),
        "offspring": [
            _load_json(p, {}) for p in (DARWIN_DIR / "offspring").glob("*.json")
        ] if (DARWIN_DIR / "offspring").exists() else [],
        "quarantine_log": _load_json(ROLLBACK_LOG, []),
    }
    out = path or (REPORTS_DIR / "darwin-genome.json")
    _save_json(out, state)
    return out


def import_genome(path: Path) -> dict:
    """Merge an exported genome (another machine's evolution state) into
    this one. Conflicts resolved by keeping the higher W/L count."""
    incoming = _load_json(path, {})
    if not incoming:
        return {"merged": 0}
    merged = {"population": 0, "lineage": 0, "offspring": 0}
    local_pop = _load_json(POPULATION_FILE, {})
    for name, genome in (incoming.get("population") or {}).items():
        local = local_pop.get(name, {})
        if (genome.get("wins", 0) + genome.get("losses", 0)) > \
           (local.get("wins", 0) + local.get("losses", 0)):
            local_pop[name] = genome
            merged["population"] += 1
    _save_json(POPULATION_FILE, local_pop)

    local_lin = _load_json(LINEAGE_FILE, {"events": []})
    known = {(e.get("child"), e.get("when")) for e in local_lin["events"]}
    for e in (incoming.get("lineage") or {}).get("events", []):
        if (e.get("child"), e.get("when")) not in known:
            local_lin["events"].append(e)
            merged["lineage"] += 1
    _save_json(LINEAGE_FILE, local_lin)

    off_dir = DARWIN_DIR / "offspring"
    off_dir.mkdir(parents=True, exist_ok=True)
    for meta in incoming.get("offspring", []):
        child = meta.get("child")
        if not child:
            continue
        mp = off_dir / f"{child}.json"
        if not mp.exists():
            _save_json(mp, meta)
            merged["offspring"] += 1
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# 8. PHASE 5: tournament - auto-trial the best offspring
# ─────────────────────────────────────────────────────────────────────────────

TRIAL_STATE_FILE = DARWIN_DIR / "trial-state.json"


def _active_trial_jobs() -> set[str]:
    """Job IDs that already have a running trial (never double-book)."""
    active = set()
    trials_dir = DARWIN_DIR / "trials"
    if trials_dir.exists():
        for tp in trials_dir.glob("*.json"):
            t = _load_json(tp, {})
            if not t.get("ended"):
                active.add(t.get("job_id", ""))
    return active


def tournament(fitness: dict, max_trials: int = 2) -> list[dict]:
    """Rank candidate offspring by (op impact, parent fitness) and start
    live trials for the top candidates whose parent owns a cron job.

    Guards: never exceed max_trials at once, never double-book a job,
    never trial a child whose parent has no cron job.
    """
    if len(_active_trial_jobs()) >= max_trials:
        return []
    protected = _cron_referenced_skills()
    ranked = sorted(fitness.items(), key=lambda kv: kv[1]["fitness"], reverse=True)
    parent_rank = {name: i for i, (name, _) in enumerate(ranked)}

    off_dir = DARWIN_DIR / "offspring"
    candidates = []
    if off_dir.exists():
        for mp in off_dir.glob("*.json"):
            meta = _load_json(mp, {})
            if meta.get("status") != "candidate":
                continue
            parent = meta.get("parent", "")
            if parent not in protected:
                continue  # parent must own a cron job to trial
            candidates.append({
                "child": meta.get("child"),
                "parent": parent,
                "op": meta.get("op", ""),
                "parent_rank": parent_rank.get(parent, 999),
            })
    candidates.sort(key=lambda c: (c["parent_rank"], c["op"]))

    started = []
    jobs = _load_cron_jobs()
    items = jobs.get("jobs") if isinstance(jobs, dict) else jobs or []
    busy = _active_trial_jobs()
    for cand in candidates:
        if len(busy) + len(started) >= max_trials:
            break
        trial = start_trial(cand["parent"], cand["child"])
        if trial:
            started.append({**cand, "job_id": trial["job_id"],
                            "job_name": trial["job_name"]})
    return started


# ─────────────────────────────────────────────────────────────────────────────
# 9. PHASE 6: head-to-head runner - REAL skill execution, not just labels
# ─────────────────────────────────────────────────────────────────────────────

def run_skill_check(skill_name: str, timeout: int = 90) -> dict:
    """Actually execute a skill and measure its real behavior.

    A skill's SKILL.md contains executable context: any fenced bash block
    under a '## Verification' or '## Quick start' section, else the first
    fenced bash block in the file. Returns real stdout/stderr/exit_code.
    """
    import subprocess
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_md.exists():
        # offspring live outside SKILLS_DIR
        alt = DARWIN_DIR / "offspring" / skill_name / "SKILL.md"
        if not alt.exists():
            return {"ok": False, "reason": "no SKILL.md", "exit_code": None}
        skill_md = alt
    text = skill_md.read_text("utf-8", errors="replace")

    blocks = re.findall(r"```(?:bash|sh|shell)\n(.*?)```", text, re.S)
    if not blocks:
        return {"ok": False, "reason": "no executable block", "exit_code": None}
    # prefer a verification/quick-start block if present
    script = blocks[-1]
    for i, b in enumerate(blocks):
        section = text[:text.find("```" + b)].lower() if "```" + b in text else ""
        if "verification" in section or "quick start" in section:
            script = b
            break

    script = script.strip()
    # resolve repo-root-relative script paths against the repo, not SKILLS_DIR
    repo = Path(__file__).resolve().parents[1]
    script = script.replace(r"C:\Users\damir\openamer-repo", str(repo))

    first_line = script.split("\n")[0]
    if first_line.startswith("python "):
        # extract a quoted script path if present; strip inline quotes
        parts = first_line.split()
        cmd = [parts[0]]
        for tok in parts[1:]:
            cmd.append(tok.strip('"').strip("'"))
    else:
        cmd = ["bash", "-c", script]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(repo))
        return {"ok": True, "exit_code": r.returncode,
                "stdout_tail": r.stdout[-300:], "stderr_tail": r.stderr[-200:]}
    except subprocess.TimeoutExpired:
        return {"ok": True, "exit_code": 124, "stdout_tail": "", "stderr_tail": "timeout"}


def head_to_head(parent: str, child: str, timeout: int = 90) -> dict:
    """Execute parent and child skills REALLY, compare outcomes.

    Scoring (real evidence only):
      - exit_code 0 beats non-zero
      - both zero: child wins on having executable proof at all
      - a skill that cannot execute cannot defend its title
    """
    p_res = run_skill_check(parent, timeout)
    c_res = run_skill_check(child, timeout)
    p_ok = p_res.get("ok") and p_res.get("exit_code") == 0
    c_ok = c_res.get("ok") and c_res.get("exit_code") == 0
    if c_ok and not p_ok:
        winner = "child"
    elif p_ok and not c_ok:
        winner = "parent"
    elif c_ok and p_ok:
        winner = "child"  # both fine: child carries the newer mutation
    else:
        winner = "neither"  # neither executable -> no verdict
    result = {"parent": parent, "child": child, "winner": winner,
              "parent_result": p_res, "child_result": c_res, "when": _now()}
    h2h_dir = DARWIN_DIR / "head2head"
    h2h_dir.mkdir(parents=True, exist_ok=True)
    stamp = NOW.strftime("%Y%m%d_%H%M%S")
    _save_json(h2h_dir / f"{child}_{stamp}.json", result)
    return result


def resolve_stuck_trials(timeout_hours: float = 24.0, do_run: bool = False) -> list[dict]:
    """For trials that produced no cron evidence (e.g. no_agent jobs where the
    skill is only a label), settle them with a REAL head-to-head execution.

    Without this, such trials stay 'waiting' forever. With do_run=True the
    head-to-head actually executes both skills.
    """
    settled = []
    trials_dir = DARWIN_DIR / "trials"
    if not trials_dir.exists():
        return settled
    from datetime import timedelta
    for tp in sorted(trials_dir.glob("*.json")):
        trial = _load_json(tp, {})
        if trial.get("ended"):
            continue
        outcomes = _execution_outcomes(trial.get("job_id", ""),
                                       trial.get("executions_before", 0))
        if outcomes["completed"] + outcomes["error"] > 0:
            continue  # cron gave evidence - normal path handles it
        started = datetime.fromisoformat(trial["started"])
        if NOW - started < timedelta(hours=timeout_hours):
            continue  # give cron a chance first
        if not do_run:
            settled.append({"child": trial.get("child"), "status": "stuck",
                            "reason": "no execution evidence, overdue"})
            continue
        h2h = head_to_head(trial["parent"], trial["child"])
        won = h2h["winner"] == "child"
        end_trial(trial["job_id"], won)
        population = _load_json(POPULATION_FILE, {})
        genome = population.setdefault(trial["parent"], {"wins": 0, "losses": 0})
        if won:
            genome["losses"] = genome.get("losses", 0) + 1
            promote_child(trial["parent"], trial["child"])
            record_lineage(trial["parent"], trial["child"], "trial_win",
                           {"via": "head_to_head"})
        else:
            genome["wins"] = genome.get("wins", 0) + 1
        _save_json(POPULATION_FILE, population)
        settled.append({"child": trial.get("child"), "status":
                        "won" if won else "lost", "via": "head_to_head",
                        "winner": h2h["winner"]})
    return settled



def compute_fitness() -> dict:
    """Fitness pro Skill: Usage + Gesundheit - Strafen."""
    hits = _session_skill_hits()
    cron_status = _cron_skill_status()
    population = _load_json(POPULATION_FILE, {})

    scores = {}
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue

        usage = hits.get(name, 0)
        health = 1 if cron_status.get(name, "ok") == "ok" else 0
        try:
            age_days = (NOW - datetime.fromtimestamp(
                skill_md.stat().st_mtime, tz=timezone.utc)).days
        except OSError:
            age_days = 999

        # Genome: past mutations improve/degrade fitness
        genome = population.get(name, {})
        mutation_bonus = genome.get("wins", 0) * 2 - genome.get("losses", 0)

        fitness = round(
            usage * 3
            + health * 5
            + mutation_bonus
            - min(age_days / 30.0, 10)   # 
            + (2 if (d / "scripts").exists() else 0)
            + (1 if list(d.glob("references/*")) else 0)
        , 2)

        scores[name] = {
            "fitness": fitness,
            "usage": usage,
            "health": health,
            "age_days": age_days,
            "mutations_won": genome.get("wins", 0),
            "mutations_lost": genome.get("losses", 0),
        }

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# 2./3. SELEKTION + MUTATION
# ─────────────────────────────────────────────────────────────────────────────

MUTATION_OPS = ["tighten_trigger", "broaden_trigger", "add_pitfall", "add_verification_step"]

_PITFALL_POOL = [
    "Check Windows paths (MSYS vs native) before running commands.",
    "Verify tool output exists before reporting success - never fabricate results.",
    "Long-running commands need a timeout; foreground shells cap at 600s.",
    "Test after edit: a green lint is not a green test run.",
]
_TRIGGER_TIGHTEN = [
    "Only on explicit user request - no auto-triggers.",
    "Skip when the task is a one-off; require a recurring pattern first.",
    "Do not trigger while a similar skill already handled the request.",
]
_TRIGGER_BROADEN = [
    "Also activate on adjacent topics and near-miss phrasings.",
    "Run opportunistically when related context appears in the session.",
]


def _replace_or_append_section(text: str, header_re: str, new_body: str) -> str:
    """Replace the BODY of the first matching section, or append a new one."""
    pattern = rf"(##\s*{header_re}[^\n]*\n)(.*?)(?=\n##|\Z)"
    m = re.search(pattern, text, re.S)
    if m:
        return text[:m.start(2)] + new_body.rstrip() + "\n" + text[m.end(2):]
    return text.rstrip() + f"\n\n## {header_re}\n{new_body.rstrip()}\n"


def _has_variant_marker(text: str, marker: str) -> bool:
    """Dedup: did this skill already receive this mutation family?"""
    return marker in text


def _semantic_mutation(text: str, op: str, rng: random.Random) -> str:
    """Section-aware mutation: rewrites the section body, not appended boilerplate."""
    if op == "tighten_trigger":
        body = rng.choice(_TRIGGER_TIGHTEN)
        out = _replace_or_append_section(text, "Trigger", body)
        return out if out != text else text + f"\n\n## Trigger\n{body}\n"
    if op == "broaden_trigger":
        body = rng.choice(_TRIGGER_BROADEN)
        return _replace_or_append_section(text, "Trigger", body)
    if op == "add_pitfall":
        if _has_variant_marker(text, "## Pitfall"):
            return _replace_or_append_section(text, "Pitfall", rng.choice(_PITFALL_POOL))
        return text.rstrip() + f"\n\n## Pitfall\n{rng.choice(_PITFALL_POOL)}\n"
    if op == "add_verification_step":
        body = ("After the last step: back the result with real tool output "
                "(exit code, file path, or API response).")
        return _replace_or_append_section(text, "Verification", body)
    return text


def _mutate_skill_md(text: str, op: str) -> str:
    """Generate a skill text variant (deterministic mutation, section-aware)."""
    return _semantic_mutation(text, op, random.Random(42))


def mutate(fitness: dict, top_n: int = 5, apply: bool = False) -> list[dict]:
    """Take top-N skills and generate one mutation each (child variant)."""
    ranked = sorted(fitness.items(), key=lambda kv: kv[1]["fitness"], reverse=True)
    parents = [n for n, s in ranked[:top_n] if s["fitness"] > 0]
    rng = random.Random(42)  # reproducible for audit
    offspring = []
    for parent in parents:
        src = SKILLS_DIR / parent / "SKILL.md"
        if not src.exists():
            continue
        text = src.read_text("utf-8", errors="replace")
        op = rng.choice(MUTATION_OPS)
        mutated = _mutate_skill_md(text, op)
        child_name = f"{parent}__mut{op}"
        offspring.append({
            "parent": parent,
            "child": child_name,
            "op": op,
            "applied": apply,
        })
        if apply:
            dst = DARWIN_DIR / "offspring" / child_name
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "SKILL.md").write_text(mutated, "utf-8")
            _save_json(DARWIN_DIR / "offspring" / f"{child_name}.json", {
                "child": child_name, "parent": parent, "op": op, "born": _now(),
                "status": "candidate", "wins": 0, "losses": 0,
            })
            record_lineage(parent, child_name, "mutation", {"op": op})
    return offspring


# ─────────────────────────────────────────────────────────────────────────────
# 4. KREUZUNG
# ─────────────────────────────────────────────────────────────────────────────

def crossover(name_a: str, name_b: str, apply: bool = False) -> dict | None:
    """Cross two skills: trigger from A + verification from B."""
    a = SKILLS_DIR / name_a / "SKILL.md"
    b = SKILLS_DIR / name_b / "SKILL.md"
    if not a.exists() or not b.exists():
        return None
    ta = a.read_text("utf-8", errors="replace")
    tb = b.read_text("utf-8", errors="replace")

    # Trigger-Abschnitt von A, Verification-Abschnitt von B, Rest von A
    trig = re.search(r"(##\s*Trigger.*?)(?=\n##|\Z)", ta, re.S)
    verif = re.search(r"(##\s*Verification.*?)(?=\n##|\Z)", tb, re.S)
    child_text = ta
    if verif and "## Verification" not in ta:
        child_text += "\n" + verif.group(1).rstrip() + "\n"
    if trig:
        child_text = re.sub(r"(##\s*Trigger.*?)(?=\n##|\Z)",
                            lambda m: m.group(1), child_text, count=1, flags=re.S)

    child_name = f"{name_a}+{name_b}"
    result = {
        "child": child_name,
        "parents": [name_a, name_b],
        "born": _now(),
        "inherits": ["trigger (from A)", "verification (from B)", "body (from A)"],
    }
    if apply:
        dst = DARWIN_DIR / "offspring" / child_name
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "SKILL.md").write_text(child_text, "utf-8")
        _save_json(DARWIN_DIR / "offspring" / f"{child_name}.json",
                   {**result, "status": "candidate", "wins": 0, "losses": 0})
        record_lineage(name_a, child_name, "crossover")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUSLESE (compete)
# ─────────────────────────────────────────────────────────────────────────────

def compete() -> list[dict]:
    """Let candidates compete against their parents.

    Signal: Wenn ein Kandidat mehr als 3 echte Usageen sammelt und seine
    
    """
    results = []
    off_dir = DARWIN_DIR / "offspring"
    if not off_dir.exists():
        return results
    for meta_path in off_dir.glob("*.json"):
        meta = _load_json(meta_path, {})
        if meta.get("status") != "candidate":
            continue
        child, parent = meta.get("child"), meta.get("parent")
        fitness = compute_fitness()
        child_score = fitness.get(child, fitness.get(child.split("__mut")[0], {}))
        
        parent_fit = fitness.get(parent, {}).get("fitness", 0)
        child_fit = child_score.get("fitness", 0) if isinstance(child_score, dict) else 0
        won = child_fit > parent_fit and child_fit > 3
        results.append({"child": child, "parent": parent,
                        "child_fitness": child_fit, "parent_fitness": parent_fit,
                        "won": won})
        if won:
            # Archive parent, promote child
            archive = DARWIN_DIR / "archive"
            archive.mkdir(parents=True, exist_ok=True)
            src = SKILLS_DIR / parent
            if src.exists():
                target = archive / f"{parent}_{NOW.strftime('%Y%m%d')}"
                if not target.exists():
                    target.write_text("") if False else None
                    # Move directory
                    import shutil
                    shutil.move(str(src), str(target))
            meta["status"] = "installed"
            meta["wins"] = meta.get("wins", 0) + 1
        else:
            meta["losses"] = meta.get("losses", 0) + 1
        _save_json(meta_path, meta)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def report(fitness: dict, offspring: list, competitions: list) -> str:
    ranked = sorted(fitness.items(), key=lambda kv: kv[1]["fitness"], reverse=True)
    lines = [
        "# Darwin Engine Report",
        f"_{_now()} — evolutionary skill ecosystem_",
        "",
        f"**Population:** {len(ranked)} Skills | "
        f"**Offspring:** {len(offspring)} | **Competitions:** {len(competitions)}",
        "",
        "## Top 10 (fittest skills)",
        "",
        "| Skill | Fitness | Usage | Age (days) | Mutationen W/L |",
        "|---|---|---|---|---|",
    ]
    for name, s in ranked[:10]:
        lines.append(
            f"| {name} | {s['fitness']} | {s['usage']} | {s['age_days']} "
            f"| {s['mutations_won']}/{s['mutations_lost']} |"
        )
    lines += ["", "## Bottom 5 (selection candidates)", ""]
    for name, s in ranked[-5:]:
        lines.append(f"- **{name}** (Fitness {s['fitness']}, {s['age_days']} days old)")
    if offspring:
        lines += ["", "## New mutations", ""]
        for o in offspring:
            lines.append(f"- {o.get('parent', '?')} → `{o.get('child', '?')}` (op={o.get('op', '?')}, applied={o.get('applied', False)})")
    if competitions:
        lines += ["", "## Competitions", ""]
        for c in competitions:
            emoji = "🏆" if c["won"] else "⏳"
            lines.append(f"- {emoji} `{c['child']}` ({c['child_fitness']}) vs "
                         f"`{c['parent']}` ({c['parent_fitness']})")
    tree = lineage_mermaid()
    if tree:
        lines += ["", "## Evolution Tree", "", tree]
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Darwin Engine - skill evolution")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--mutate", action="store_true")
    ap.add_argument("--apply", action="store_true", help="actually write mutations")
    ap.add_argument("--crossover", nargs=2, metavar=("SKILL_A", "SKILL_B"))
    ap.add_argument("--compete", action="store_true")
    ap.add_argument("--trial", nargs=2, metavar=("PARENT", "CHILD"),
                    help="swap a cron job's skill to CHILD for a live trial")
    ap.add_argument("--trials", action="store_true",
                    help="evaluate running trials from real execution evidence")
    ap.add_argument("--quarantine", action="store_true",
                    help="dry-run: which dead skills would be quarantined")
    ap.add_argument("--quarantine-apply", action="store_true",
                    help="actually quarantine dead skills (reversible)")
    ap.add_argument("--rollback", type=int, metavar="N", default=0,
                    help="restore the last N quarantined skills")
    ap.add_argument("--autopilot", action="store_true",
                    help="full unattended cycle: scan+mutate+trials+compete+prune+report")
    ap.add_argument("--lineage", action="store_true",
                    help="print the evolution family tree (mermaid)")
    ap.add_argument("--export-genome", action="store_true",
                    help="export evolution state to reports/darwin-genome.json")
    ap.add_argument("--import-genome", metavar="PATH",
                    help="merge another machine's genome into this one")
    ap.add_argument("--head-to-head", nargs=2, metavar=("PARENT", "CHILD"),
                    help="really execute both skills, winner by exit code")
    ap.add_argument("--resolve-stuck", action="store_true",
                    help="settle overdue evidence-less trials via head-to-head (dry: list only)")
    ap.add_argument("--resolve-stuck-run", action="store_true",
                    help="like --resolve-stuck but actually executes the duels")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    if not SKILLS_DIR.exists():
        print(f"❌ Skills directory not found: {SKILLS_DIR}")
        return 1

    changed = False

    if args.autopilot:
        code = autopilot(min_executions=2)
        return code

    if args.lineage:
        tree = lineage_mermaid()
        print(tree if tree else "(empty lineage - no evolution events yet)")
        return 0

    if args.export_genome:
        out = export_genome()
        print(f"🧬 genome exported -> {out}")
        return 0

    if args.import_genome:
        merged = import_genome(Path(args.import_genome))
        print(f"🧬 genome merged: {merged}")
        changed = any(merged.values())

    if args.head_to_head:
        h2h = head_to_head(args.head_to_head[0], args.head_to_head[1])
        print(f"⚔️  winner: {h2h['winner']} "
              f"(parent exit={h2h['parent_result'].get('exit_code')}, "
              f"child exit={h2h['child_result'].get('exit_code')})")
        changed = h2h["winner"] != "neither"

    if args.resolve_stuck or args.resolve_stuck_run:
        settled = resolve_stuck_trials(timeout_hours=0.001,
                                       do_run=args.resolve_stuck_run)
        for s in settled:
            print(f"⚔️  {s.get('child')}: {s['status']}"
                  + (f" (winner={s['winner']})" if "winner" in s else ""))
        if not settled:
            print("✅ no stuck trials")
        if any(s["status"] in ("won", "lost") for s in settled):
            changed = True

    if args.rollback:
        restored = rollback(args.rollback)
        print(f"↩️  restored {len(restored)} skill(s): {restored}" if restored
              else "↩️  nothing to restore")
        if restored:
            changed = True

    if args.quarantine or args.quarantine_apply:
        fitness = compute_fitness()
        moved = quarantine(fitness, threshold=0,
                           dry_run=not args.quarantine_apply)
        label = "quarantined" if args.quarantine_apply else "would quarantine"
        print(f"🧊 {label} {len(moved)} skill(s): {[m['skill'] for m in moved]}")
        if moved and args.quarantine_apply:
            changed = True

    if args.trial:
        parent, child = args.trial
        trial = start_trial(parent, child)
        if trial:
            print(f"🧪 Trial started: job '{trial['job_name']}' now runs "
                  f"`{child}` instead of `{parent}` (job {trial['job_id']})")
            changed = True
        else:
            print(f"❌ No enabled cron job references skill '{parent}'.")
            return 1

    if args.trials or args.full:
        trials = evaluate_trials()
        for t in trials:
            emoji = {"won": "🏆", "lost": "↩️", "waiting": "⏳"}.get(t["status"], "?")
            print(f"{emoji} Trial {t['job_id']}: {t['child']} -> {t['status']} {t['outcomes']}")
        if any(t["status"] in ("won", "lost") for t in trials):
            changed = True

    if args.scan or args.full or args.report:
        fitness = compute_fitness()
        _save_json(FITNESS_FILE, {"updated": _now(), "skills": fitness})
        print(f"✅ Fitness computed for {len(fitness)} skills -> {FITNESS_FILE}")

    if args.mutate or args.full:
        fitness = _load_json(FITNESS_FILE, {}).get("skills", compute_fitness())
        offspring = mutate(fitness, apply=args.apply or args.full)
        print(f"🧬 {len(offspring)} mutations generated (applied={args.apply or args.full})")
        if offspring:
            changed = True

    if args.crossover:
        res = crossover(args.crossover[0], args.crossover[1], apply=args.apply)
        if res:
            print(f"💞 Crossover: {res['child']} aus {res['parents']}")
            changed = True
        else:
            print(f"❌ One of the skills does not exist.")
            return 1

    if args.compete or args.full:
        comps = compete()
        print(f"⚔️  {len(comps)} competitions evaluated")
        if any(c["won"] for c in comps):
            changed = True

    if args.report or args.full:
        fitness = _load_json(FITNESS_FILE, {}).get("skills", {})
        off_dir = DARWIN_DIR / "offspring"
        offspring = [
            _load_json(p, {}) for p in (off_dir.glob("*.json") if off_dir.exists() else [])
        ]
        comps = compete() if args.full else []
        md = report(fitness, offspring, comps)
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(md, "utf-8")
        print(f"📄 Report -> {REPORT_FILE}")

    return 2 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
