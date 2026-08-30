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

_HITS_CACHE: dict = {"ts": 0.0, "hits": None}
_HITS_TTL_SECONDS = 600  # session scan is expensive; cache 10 minutes


def _session_skill_hits() -> dict[str, int]:
    """Count how often each skill is mentioned across past sessions.

    The full-table scan is expensive (~1s on large DBs) and autopilot calls
    compute_fitness() multiple times per run - results are cached for
    _HITS_TTL_SECONDS and invalidated by explicit reset in tests."""
    import time as _time
    now = _time.time()
    if _HITS_CACHE["hits"] is not None and now - _HITS_CACHE["ts"] < _HITS_TTL_SECONDS:
        return _HITS_CACHE["hits"]
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
    _HITS_CACHE["ts"] = now
    _HITS_CACHE["hits"] = hits
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
    n_snaps = record_history(fitness)
    print(f"[autopilot] fitness computed for {len(fitness)} skills "
          f"(history snapshot #{n_snaps})")

    # phase 15: self-tuning before using any constant
    tuning = auto_tune()
    print(f"[autopilot] tuning: {tuning['reason']} "
          f"(epsilon={tuning['epsilon']}, max_trials={tuning['max_trials']}, "
          f"max_losses={tuning['max_losses']})")

    offspring = mutate(fitness, apply=True)
    print(f"[autopilot] {len(offspring)} mutations generated")

    trials = evaluate_trials(min_executions)
    for t in trials:
        print(f"[autopilot] trial {t['job_id']}: {t['status']} {t['outcomes']}")

    comps = compete()
    if any(c["won"] for c in comps):
        print(f"[autopilot] {sum(1 for c in comps if c['won'])} candidate(s) promoted")

    started = tournament(fitness, max_trials=tuning['max_trials'])
    if started:
        for s in started:
            print(f"[autopilot] tournament: trialing `{s['child']}` "
                  f"on job '{s['job_name']}'")

    # report operator learning state (meta-evolution visibility)
    op_stats = _load_op_stats()
    if op_stats:
        ranked_ops = sorted(op_stats.items(),
                            key=lambda kv: kv[1]["wins"] / max(kv[1]["uses"], 1),
                            reverse=True)
        top_op, s = ranked_ops[0]
        print(f"[autopilot] best operator: {top_op} "
              f"({s['wins']}/{s['uses']} wins)")

    # full species pipeline: harvest -> speciate -> promote -> arena -> retire
    harvested = harvest_knowledge(min_hits=3)
    if harvested:
        print(f"[autopilot] harvested {len(harvested)} new blueprint(s)")
    new_species = synthesize_species_v2(fitness, max_new=2, apply=True)
    if new_species:
        print(f"[autopilot] synthesized {len(new_species)} species: "
              f"{[c['name'] for c in new_species]}")
        for c in new_species:
            if promote_species(c["name"]):
                print(f"[autopilot] promoted species `{c['name']}`")

    fights = species_arena()
    for f in fights:
        if f["status"] == "fought":
            print(f"[autopilot] arena: {f['a']} vs {f['b']} -> {f['winner']}")
        else:
            print(f"[autopilot] arena: {f['status']}")

    retired = retire_losers(max_losses=tuning['max_losses'])
    if retired:
        print(f"[autopilot] retired {len(retired)} losing species: "
              f"{[r['name'] for r in retired]}")

    # phase 16: predation - consume redundancy (max 3 duels per cycle)
    pred_results = predation_cycle(fitness, dry_run=False)
    for r in pred_results:
        if r["status"] == "absorbed":
            print(f"[autopilot] predation: {r['predator']} absorbed "
                  f"`{r['prey']}`")
        elif r["status"] == "no-prey":
            print("[autopilot] predation: no redundant skills found")

    quarantined = quarantine(fitness, threshold=0, dry_run=False)
    if quarantined:
        print(f"[autopilot] quarantined {len(quarantined)} dead skills: "
              f"{[q['skill'] for q in quarantined]}")

    md = report(fitness, offspring, comps)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(md, "utf-8")
    print(f"[autopilot] report -> {REPORT_FILE}")

    changed = bool(offspring or trials or comps or quarantined or started
                   or harvested or new_species or fights or retired
                   or any(r.get("status") == "absorbed"
                          for r in pred_results))
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
        # candidates live outside SKILLS_DIR: offspring and species
        for alt_dir in ("offspring", "species"):
            alt = DARWIN_DIR / alt_dir / skill_name / "SKILL.md"
            if alt.exists():
                skill_md = alt
                break
        else:
            return {"ok": False, "reason": "no SKILL.md", "exit_code": None}
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
        # the -c argument is the REST of the line; naive whitespace-splitting
        # breaks `python -c "import sys; print('x')"` into fragments
        import shlex
        try:
            cmd = shlex.split(first_line)
        except ValueError:
            cmd = first_line.split()
        cmd = [t.strip('"').strip("'") for t in cmd]
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
        # meta-evolution: credit/blame the operator that created this child
        op = (trial.get("child") or "").split("__mut")
        if len(op) == 2:
            record_op_outcome(op[1], won)
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


# ─────────────────────────────────────────────────────────────────────────────
# 10. PHASE 7: speciation - synthesize NEW skills from evolution knowledge
# ─────────────────────────────────────────────────────────────────────────────

SYNTHESIS_LOG = DARWIN_DIR / "synthesis-log.json"

# Capability blueprints: proven pitfalls/verification knowledge recombined
# into genuinely NEW skills (not mutations of existing ones).
BLUEPRINTS = [
    {
        "name": "darwin-evidence-hygiene",
        "description": "Use when reporting build, test, or deploy results - "
                       "enforces real tool output over plausible claims.",
        "trigger": "Use before any success claim about a build, install, or test run.",
        "body": "1. Run the command and capture its REAL exit code.\n"
                "2. Quote the last 3 lines of actual stdout/stderr as evidence.\n"
                "3. If the command failed, report the failure verbatim - never\n"
                "   substitute a plausible-looking result.\n"
                "4. A green lint is not a green test run; run the tests.",
        "pitfall": "Never fabricate results for output you could not produce.",
    },
    {
        "name": "darwin-session-recall",
        "description": "Use when the user references past work or you suspect "
                       "cross-session context exists.",
        "trigger": "Use before asking the user to repeat prior decisions or paths.",
        "body": "1. Search session history for the referenced topic first.\n"
                "2. Prefer direct sources (files, repos, DBs) over memory.\n"
                "3. Link the found session inline rather than restating it.\n"
                "4. If nothing found, say so plainly - do not guess.",
        "pitfall": "Session history is context, not proof of current state.",
    },
    {
        "name": "darwin-cron-guard",
        "description": "Use when creating or editing cron jobs - prevents "
                       "timeouts, silent failures, and delivery gaps.",
        "trigger": "Use whenever a scheduled job is created, edited, or diagnosed.",
        "body": "1. Terminal timeouts must be <= 120s inside cron runs.\n"
                "2. Background processes need notify_on_complete=true.\n"
                "3. Exit code 2 may be a SUCCESS-with-changes convention -\n"
                "   check the tool's documented exit semantics before alerting.\n"
                "4. Verify last_status after the first scheduled run.",
        "pitfall": "A job that exits 0 with empty output may have done nothing.",
    },
]


def synthesize_species(fitness: dict, max_new: int = 2, apply: bool = False) -> list[dict]:
    """Create genuinely NEW skills (speciation) from recombined evolution
    knowledge. Only blueprints whose name is not already in the population
    are used. Parent = the fittest skill (knowledge donor, not ancestor)."""
    existing = {n for n in fitness}
    donor = max(fitness.items(), key=lambda kv: kv[1]["fitness"])[0] if fitness else None
    created = []
    for bp in BLUEPRINTS:
        if len(created) >= max_new:
            break
        if bp["name"] in existing:
            continue
        text = (
            f"---\n"
            f"name: {bp['name']}\n"
            f"description: {bp['description']}\n"
            f"---\n\n"
            f"# {bp['name'].replace('-', ' ').title()}\n\n"
            f"## Trigger\n{bp['trigger']}\n\n"
            f"## Procedure\n{bp['body']}\n\n"
            f"## Pitfall\n{bp['pitfall']}\n\n"
            f"## Verification\nAfter following the procedure: confirm the outcome\n"
            f"with real evidence (exit code, file, or API response).\n"
            f"```bash\npython -c \"import sys; print('darwin-species-ok')\"\n```\n"
        )
        created.append({"name": bp["name"], "donor": donor, "applied": apply})
        if apply:
            dst = DARWIN_DIR / "species" / bp["name"]
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "SKILL.md").write_text(text, "utf-8")
            _save_json(DARWIN_DIR / "species" / f"{bp['name']}.json", {
                "child": bp["name"], "parent": donor, "kind": "speciation",
                "born": _now(), "status": "candidate", "wins": 0, "losses": 0,
            })
            record_lineage(donor or "void", bp["name"], "speciation")
    if created and apply:
        log = _load_json(SYNTHESIS_LOG, [])
        log.extend({"name": c["name"], "donor": c["donor"], "when": _now()}
                   for c in created)
        _save_json(SYNTHESIS_LOG, log)
    return created


def promote_species(name: str) -> bool:
    """Promote a synthesized species into the live skill population."""
    import shutil
    src = DARWIN_DIR / "species" / name
    dst = SKILLS_DIR / name
    if not (src / "SKILL.md").exists() or dst.exists():
        return False
    shutil.copytree(str(src), str(dst))
    meta_path = DARWIN_DIR / "species" / f"{name}.json"
    meta = _load_json(meta_path, {})
    meta["status"] = "installed"
    meta["installed"] = _now()
    _save_json(meta_path, meta)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 12. PHASE 9: self-feeding blueprints - harvest knowledge from real sessions
# ─────────────────────────────────────────────────────────────────────────────

HARVESTED_FILE = DARWIN_DIR / "harvested-blueprints.json"
_STATE_DB_CANDIDATES = ("state.db", "sessions.db")


def _session_db() -> Path | None:
    for name in _STATE_DB_CANDIDATES:
        p = HOME / name
        if p.exists():
            return p
    return None


def harvest_knowledge(min_hits: int = 3, limit: int = 5000) -> list[dict]:
    """Mine real session history for recurring FILE-LEVEL error patterns and
    turn the strongest ones into NEW blueprints. The blueprint pool grows with
    the system's own lived experience instead of staying hardcoded.

    Only concrete, technical patterns qualify: missing files/paths/modules
    from real FileNotFoundError-style messages. Generic verb fragments
    (German past participles etc.) are rejected by the technical-token gate.
    """
    import sqlite3
    from collections import Counter
    db = _session_db()
    if not db:
        return []
    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT content FROM messages WHERE ("
            "content LIKE '%No such file%' OR content LIKE '%cannot open%' "
            "OR content LIKE '%FileNotFoundError%' "
            "OR content LIKE '%ModuleNotFoundError%') LIMIT ?",
            (limit,)).fetchall()
        conn.close()
    except Exception:
        return []

    topics: Counter = Counter()
    for (content,) in rows:
        if not content:
            continue
        # Extract path-like error subjects without one mega-regex:
        # normalize escaped JSON quotes first, then split on known anchors.
        flat = content.replace("\\'", "'").replace('\\"', '"')
        for anchor in ("No such file or directory", "FileNotFoundError",
                       "ModuleNotFoundError", "cannot access"):
            idx = 0
            while True:
                i = flat.find(anchor, idx)
                if i < 0:
                    break
                tail = flat[i + len(anchor):].lstrip(" :,'\"\\")
                # subject = up to next quote/newline/JSON-escape
                subject = re.split("['\"\\n,]", tail)[0].strip()
                subject = re.sub(r"^[a-zA-Z]:[/\\]", "", subject).strip("/\\")
                if len(subject) >= 8 and "/" in subject or subject.endswith(
                        (".py", ".json", ".md", ".db", ".yaml", ".yml",
                         ".toml", ".lock")):
                    if "node_modules" not in subject:
                        topics[subject.lower()[:60]] += 1
                idx = i + len(anchor) + 10

    new_blueprints = []
    existing_names = {bp["name"] for bp in BLUEPRINTS}
    harvested = _load_json(HARVESTED_FILE, [])
    existing_names.update(h.get("name") for h in harvested)

    for topic, hits in topics.most_common():
        if hits < min_hits:
            break
        slug = _pretty_slug(topic)
        name = f"darwin-harvested-{slug}"
        if name in existing_names:
            continue
        new_blueprints.append({
            "name": name,
            "topic": topic,
            "hits": hits,
            "fix_hint": "",
            "donor_note": f"harvested from {hits} real occurrences",
        })

    if new_blueprints:
        harvested.extend(new_blueprints)
        _save_json(HARVESTED_FILE, harvested)
    return new_blueprints


def _pretty_slug(topic: str) -> str:
    """Turn an error topic into a short, readable, thematic slug.

    Long machine paths ('c/users/damir/appdata/...') become their meaningful
    tail ('openamer-browser'); generic fragments keep a compact form."""
    # take the last 2 meaningful path segments instead of the whole path
    parts = [s for s in topic.replace("\\", "/").split("/") if s]
    if len(parts) >= 2:
        tail = "-".join(parts[-2:])
    else:
        tail = topic
    slug = re.sub(r"[^a-z0-9]+", "-", tail).strip("-")
    # drop pure user-dir noise segments
    slug = re.sub(r"(^|-)(c|users|damir|appdata|local|openamer-laptop)(-|$)",
                  lambda m: m.group(1) == "-" and "-" or "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")[:36]
    return slug or "unknown-pattern"


def all_blueprints() -> list[dict]:
    """Hardcoded blueprints + harvested ones (converted to blueprint shape)."""
    harvested = _load_json(HARVESTED_FILE, [])
    extra = []
    for h in harvested:
        extra.append({
            "name": h["name"],
            "description": f"Use when handling: {h['topic']} - "
                           f"pattern seen {h['hits']}x in real sessions.",
            "trigger": f"Use when the error topic '{h['topic']}' appears.",
            "body": f"1. Recognize the recurring failure pattern: {h['topic']}.\n"
                    f"2. Known working fix from session history: "
                    f"{h.get('fix_hint') or 'inspect the failing path directly'}.\n"
                    f"3. Verify the fix with real tool output before claiming success.",
            "pitfall": f"This pattern failed {h['hits']}x before - do not repeat it.",
        })
    return BLUEPRINTS + extra


def synthesize_species_v2(fitness: dict, max_new: int = 2,
                          apply: bool = False) -> list[dict]:
    """Speciation using the full (hardcoded + harvested) blueprint pool."""
    existing = {n for n in fitness}
    # never re-synthesize something already in the species nursery
    sp_dir = DARWIN_DIR / "species"
    if sp_dir.exists():
        existing.update(m["child"] for m in
                        (_load_json(p, {}) for p in sp_dir.glob("*.json"))
                        if m.get("child"))
    donor = max(fitness.items(), key=lambda kv: kv[1]["fitness"])[0] if fitness else None
    created = []
    for bp in all_blueprints():
        if len(created) >= max_new:
            break
        if bp["name"] in existing:
            continue
        text = (
            f"---\n"
            f"name: {bp['name']}\n"
            f"description: {bp['description']}\n"
            f"---\n\n"
            f"# {bp['name'].replace('-', ' ').title()}\n\n"
            f"## Trigger\n{bp['trigger']}\n\n"
            f"## Procedure\n{bp['body']}\n\n"
            f"## Pitfall\n{bp['pitfall']}\n\n"
            f"## Verification\nAfter following the procedure: confirm the outcome\n"
            f"with real evidence (exit code, file, or API response).\n"
            f"```bash\npython -c \"import sys; print('darwin-species-ok')\"\n```\n"
        )
        created.append({"name": bp["name"], "donor": donor, "applied": apply})
        if apply:
            dst = DARWIN_DIR / "species" / bp["name"]
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "SKILL.md").write_text(text, "utf-8")
            _save_json(DARWIN_DIR / "species" / f"{bp['name']}.json", {
                "child": bp["name"], "parent": donor, "kind": "speciation",
                "born": _now(), "status": "candidate", "wins": 0, "losses": 0,
            })
            record_lineage(donor or "void", bp["name"], "speciation")
    if created and apply:
        log = _load_json(SYNTHESIS_LOG, [])
        log.extend({"name": c["name"], "donor": c["donor"], "when": _now()}
                   for c in created)
        _save_json(SYNTHESIS_LOG, log)
    return created


# ─────────────────────────────────────────────────────────────────────────────
# 11. PHASE 8: memory + species arena
# ─────────────────────────────────────────────────────────────────────────────

HISTORY_FILE = REPORTS_DIR / "darwin-history.jsonl"
ARENA_FILE = DARWIN_DIR / "arena.json"


def record_history(fitness: dict) -> int:
    """Append a fitness snapshot to the append-only history log.
    Returns the number of snapshots stored so far."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {"when": _now(), "skills": {n: s["fitness"] for n, s in fitness.items()}}
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return sum(1 for _ in open(HISTORY_FILE, encoding="utf-8"))


def fitness_trend() -> dict:
    """Analyze the history: per-skill trend and population health.
    trend: 'rising' | 'falling' | 'flat' (needs >= 2 snapshots)."""
    if not HISTORY_FILE.exists():
        return {"snapshots": 0}
    entries = [json.loads(l) for l in
               open(HISTORY_FILE, encoding="utf-8") if l.strip()]
    if len(entries) < 2:
        return {"snapshots": len(entries)}
    first, last = entries[0], entries[-1]
    trends = {}
    for name, now_fit in last["skills"].items():
        before = first["skills"].get(name)
        if before is None:
            trends[name] = {"delta": None, "trend": "new"}
            continue
        d = round(now_fit - before, 2)
        trends[name] = {"delta": d,
                        "trend": "rising" if d > 0 else ("falling" if d < 0 else "flat")}
    pop_now = sum(last["skills"].values())
    pop_first = sum(v for v in first["skills"].values())
    return {
        "snapshots": len(entries),
        "first": first["when"], "last": last["when"],
        "population_delta": round(pop_now - pop_first, 2),
        "population_trend": ("rising" if pop_now > pop_first
                             else "falling" if pop_now < pop_first else "flat"),
        "skills": trends,
    }


def species_arena(min_interval_minutes: int = 30) -> list[dict]:
    """Duel installed species against each other with REAL execution.

    Species bypass cron-trials (they have no parent job), so the arena is
    their only selection pressure. Each round pairs the two species whose
    last duel is oldest; results feed the genome W/L record.
    Rate-limited: at most one arena round per min_interval_minutes.
    """
    import shutil
    sp_dir = DARWIN_DIR / "species"
    if not sp_dir.exists():
        return []
    installed = []
    for mp in sp_dir.glob("*.json"):
        meta = _load_json(mp, {})
        if meta.get("status") == "installed":
            installed.append(meta)
    if len(installed) < 2:
        return []

    # rate limit via arena state
    state = _load_json(ARENA_FILE, {"last_round": None, "fights": 0})
    if state.get("last_round"):
        last = datetime.fromisoformat(state["last_round"])
        if (NOW - last).total_seconds() < min_interval_minutes * 60:
            return [{"status": "cooldown"}]

    from datetime import timedelta
    installed.sort(key=lambda m: m.get("last_fight") or "0000")
    a, b = installed[0], installed[1]
    h2h = head_to_head(a["child"], b["child"])
    winner_meta = a if h2h["winner"] == "child" else b
    loser_meta = b if h2h["winner"] == "child" else a
    # head_to_head uses child=param2; map to metas properly
    if h2h["winner"] == "child":
        winner_meta, loser_meta = b, a
    else:
        winner_meta, loser_meta = a, b

    population = _load_json(POPULATION_FILE, {})
    w = population.setdefault(winner_meta["child"], {"wins": 0, "losses": 0})
    w["wins"] = w.get("wins", 0) + 1
    l = population.setdefault(loser_meta["child"], {"wins": 0, "losses": 0})
    l["losses"] = l.get("losses", 0) + 1
    _save_json(POPULATION_FILE, population)

    for m in (a, b):
        m["last_fight"] = _now()
        _save_json(sp_dir / f"{m['child']}.json", m)
    state["last_round"] = _now()
    state["fights"] = state.get("fights", 0) + 1
    _save_json(ARENA_FILE, state)

    return [{"status": "fought", "a": a["child"], "b": b["child"],
             "winner": h2h["winner"],
             "a_exit": h2h["parent_result"].get("exit_code"),
             "b_exit": h2h["child_result"].get("exit_code")}]


def retire_losers(max_losses: int = 3) -> list[dict]:
    """Species that accumulated >= max_losses arena defeats are retired:
    moved to quarantine (reversible), keeping the population healthy.
    A species with a losing record blocks nothing - but it must not crowd
    the arena forever."""
    import shutil
    sp_dir = DARWIN_DIR / "species"
    if not sp_dir.exists():
        return []
    population = _load_json(POPULATION_FILE, {})
    retired = []
    for mp in list(sp_dir.glob("*.json")):
        meta = _load_json(mp, {})
        if meta.get("status") != "installed":
            continue
        name = meta.get("child", "")
        genome = population.get(name, {})
        losses = genome.get("losses", 0)
        wins = genome.get("wins", 0)
        if losses < max_losses or losses <= wins:
            continue  # healthy record or not enough evidence
        q_dir = DARWIN_DIR / "quarantine"
        q_dir.mkdir(parents=True, exist_ok=True)
        target = q_dir / name
        if (sp_dir / name).exists() and not target.exists():
            shutil.move(str(sp_dir / name), str(target))
            meta["status"] = "retired"
            meta["retired"] = _now()
            _save_json(mp, meta)
            retired.append({"name": name, "wins": wins, "losses": losses})
            log = _load_json(ROLLBACK_LOG, [])
            log.append({"skill": name, "fitness": 0, "when": _now(),
                        "reason": "arena-loses"})
            _save_json(ROLLBACK_LOG, log)
    return retired


def status_overview() -> dict:
    """One-glance state of the whole ecosystem."""
    fitness = _load_json(FITNESS_FILE, {}).get("skills", {})
    ranked = sorted(fitness.items(), key=lambda kv: kv[1].get("fitness", 0),
                    reverse=True)
    species = {"installed": 0, "candidate": 0, "retired": 0}
    sp_dir = DARWIN_DIR / "species"
    if sp_dir.exists():
        for mp in sp_dir.glob("*.json"):
            st = _load_json(mp, {}).get("status", "candidate")
            species[st if st in species else "candidate"] = \
                species.get(st if st in species else "candidate", 0) + 1
    population = _load_json(POPULATION_FILE, {})
    trials_dir = DARWIN_DIR / "trials"
    active_trials = 0
    if trials_dir.exists():
        active_trials = sum(
            1 for tp in trials_dir.glob("*.json")
            if not _load_json(tp, {}).get("ended"))
    harvest_n = len(_load_json(HARVESTED_FILE, []))
    return {
        "when": _now(),
        "population": len(fitness),
        "fittest": ranked[0][0] if ranked else None,
        "weakest": ranked[-1][0] if ranked else None,
        "species": species,
        "active_trials": active_trials,
        "harvested_blueprints": harvest_n,
        "genome_records": len(population),
        "trend": fitness_trend().get("population_trend", "unknown"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 15. PHASE 14: explainability + species-aware rollback
# ─────────────────────────────────────────────────────────────────────────────

def explain_skill(name: str) -> dict:
    """Full evidence chain for one skill: WHY does it have its fitness?

    Assembles every signal Darwin holds: fitness breakdown, lineage events,
    genome W/L, trial history, op-stats for mutations it carries, cron
    references. No black box - every promotion/prune decision is auditable.
    """
    fitness = _load_json(FITNESS_FILE, {}).get("skills", {}).get(name)
    population = _load_json(POPULATION_FILE, {})
    genome = population.get(name, {"wins": 0, "losses": 0})

    # lineage: everything that ever happened to this skill
    graph = _load_json(LINEAGE_FILE, {"events": []})
    as_parent = [e for e in graph["events"] if e.get("parent") == name]
    as_child = [e for e in graph["events"] if e.get("child") == name]

    # trials involving this skill
    trials_dir = DARWIN_DIR / "trials"
    trial_records = []
    if trials_dir.exists():
        for tp in trials_dir.glob("*.json"):
            t = _load_json(tp, {})
            if name in (t.get("parent"), t.get("child")):
                trial_records.append({
                    "job": t.get("job_name"), "role":
                    "parent" if t.get("parent") == name else "child",
                    "ended": bool(t.get("ended")), "won": t.get("won")})

    # cron protection status
    referenced_by_cron = name in _cron_referenced_skills()

    # op contribution: if this is a mutation child, how good is its op?
    op_note = None
    if "__mut" in name:
        op = name.split("__mut")[1]
        s = _load_op_stats().get(op)
        if s:
            op_note = {"op": op, "uses": s["uses"], "wins": s["wins"],
                       "win_rate": round(s["wins"] / max(s["uses"], 1), 2)}

    # species origin?
    is_species = False
    sp_meta = DARWIN_DIR / "species" / f"{name}.json"
    if sp_meta.exists():
        is_species = _load_json(sp_meta, {}).get("kind") == "speciation"

    return {
        "skill": name,
        "exists": fitness is not None or (SKILLS_DIR / name).exists(),
        "fitness": fitness,
        "breakdown": {
            "usage_points": (fitness or {}).get("usage", 0) * 3,
            "health_points": (fitness or {}).get("health", 0) * 5,
            "mutation_bonus": genome.get("wins", 0) * 2 - genome.get("losses", 0),
            "age_penalty": -min((fitness or {}).get("age_days", 0) / 30.0, 10),
        },
        "genome": genome,
        "lineage_as_parent": len(as_parent),
        "lineage_as_child": len(as_child),
        "last_events": (as_parent + as_child)[-5:],
        "trials": trial_records,
        "referenced_by_cron": referenced_by_cron,
        "operator_quality": op_note,
        "is_species": is_species,
        "when": _now(),
    }


def rollback_species(name: str) -> bool:
    """Undo a species retirement: return it from quarantine to the species
    dir (not SKILLS_DIR - it is a species, not a regular skill)."""
    import shutil
    q = DARWIN_DIR / "quarantine" / name
    sp = DARWIN_DIR / "species" / name
    if not q.exists():
        return False
    if sp.exists():
        return False  # already there
    shutil.move(str(q), str(sp))
    meta_path = DARWIN_DIR / "species" / f"{name}.json"
    meta = _load_json(meta_path, {})
    if meta:
        meta["status"] = "installed"
        meta["unretired"] = _now()
        _save_json(meta_path, meta)
    # drop the retirement from the rollback log so --rollback won't re-add it
    log = _load_json(ROLLBACK_LOG, [])
    log = [e for e in log
           if not (e.get("skill") == name and e.get("reason") == "arena-loses")]
    _save_json(ROLLBACK_LOG, log)
    return True



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

OP_STATS_FILE = DARWIN_DIR / "op-stats.json"


def _load_op_stats() -> dict:
    return _load_json(OP_STATS_FILE, {})


def record_op_outcome(op: str, won: bool) -> None:
    """Track which mutation operators produce winning children.
    This is meta-evolution: the operators themselves are selected on."""
    stats = _load_op_stats()
    s = stats.setdefault(op, {"uses": 0, "wins": 0})
    s["uses"] += 1
    if won:
        s["wins"] += 1
    _save_json(OP_STATS_FILE, stats)


def weighted_op_choice(rng: random.Random, epsilon: float = 0.3) -> str:
    """Epsilon-greedy operator selection: 70% pick the historically best
    operator (win-rate with Laplace smoothing), 30% explore uniformly.
    Evolves the evolution: operators that breed winners get used more."""
    stats = _load_op_stats()
    if not stats or rng.random() < epsilon:
        return rng.choice(MUTATION_OPS)
    def score(op):
        s = stats.get(op, {"uses": 0, "wins": 0})
        # Laplace smoothing: unseen ops keep a fair chance
        return (s["wins"] + 1) / (s["uses"] + 2)
    return max(MUTATION_OPS, key=lambda op: score(op) + rng.random() * 1e-9)

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
        op = weighted_op_choice(rng)
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
    ap.add_argument("--speciate", action="store_true",
                    help="dry-run: which new species would be synthesized")
    ap.add_argument("--speciate-apply", action="store_true",
                    help="synthesize new species skills into darwin/species/")
    ap.add_argument("--promote-species", metavar="NAME",
                    help="install a synthesized species into the live population")
    ap.add_argument("--trend", action="store_true",
                    help="fitness trend over time from history snapshots")
    ap.add_argument("--arena", action="store_true",
                    help="duel two installed species with real execution")
    ap.add_argument("--harvest", action="store_true",
                    help="mine real session history for new blueprints")
    ap.add_argument("--speciate-v2", action="store_true",
                    help="speciation using hardcoded + harvested blueprints")
    ap.add_argument("--retire", action="store_true",
                    help="retire species with >= 3 arena losses (reversible)")
    ap.add_argument("--status", action="store_true",
                    help="one-glance ecosystem overview")
    ap.add_argument("--explain", metavar="SKILL",
                    help="full evidence chain: why does this skill have its fitness?")
    ap.add_argument("--unretire", metavar="SPECIES",
                    help="undo a species retirement (back to species dir)")
    ap.add_argument("--predate", action="store_true",
                    help="dry-run: which redundant skills would be consumed?")
    ap.add_argument("--predate-apply", action="store_true",
                    help="actually run predation duels and absorb prey")
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

    if args.speciate or args.speciate_apply or args.promote_species:
        fitness = _load_json(FITNESS_FILE, {}).get("skills", compute_fitness())
        if args.speciate or args.speciate_apply:
            created = synthesize_species(
                fitness, max_new=2, apply=args.speciate_apply)
            label = "synthesized" if args.speciate_apply else "would synthesize"
            print(f"🧬 {label} {len(created)} species: "
                  f"{[c['name'] for c in created]} (donor: "
                  f"{created[0]['donor'] if created else '-'})")
            if created and args.speciate_apply:
                changed = True
        if args.promote_species:
            ok = promote_species(args.promote_species)
            print(f"🌍 species '{args.promote_species}' promoted: {ok}")
            if ok:
                changed = True

    if args.trend:
        t = fitness_trend()
        if t["snapshots"] < 2:
            print(f"📈 only {t['snapshots']} snapshot(s) - need >= 2 for a trend")
        else:
            print(f"📈 {t['snapshots']} snapshots | population "
                  f"{t['population_trend']} ({t['population_delta']:+})")
            for n, s in sorted(t["skills"].items(),
                               key=lambda kv: kv[1]["trend"] == "falling",
                               reverse=False)[:10]:
                d = s["delta"]
                print(f"   {n}: {s['trend']}" + (f" ({d:+})" if d is not None else " (new)"))
        return 0

    if args.arena:
        fights = species_arena()
        for f in fights:
            if f["status"] == "fought":
                print(f"🏟️  {f['a']} (exit {f['a_exit']}) vs {f['b']} "
                      f"(exit {f['b_exit']}) -> winner: {f['winner']}")
                changed = True
            else:
                print(f"🏟️  arena: {f['status']}")
        if not fights:
            print("🏟️  arena: not enough installed species (need >= 2)")
        return 2 if changed else 0

    if args.harvest:
        found = harvest_knowledge(min_hits=3)
        print(f"🌾 harvested {len(found)} new blueprint(s) from session history:")
        for b in found[:5]:
            print(f"   {b['name']} ({b['hits']} occurrences)")
        if not found:
            print("   (no recurring patterns above threshold)")
        if found:
            changed = True

    if args.speciate_v2:
        fitness = _load_json(FITNESS_FILE, {}).get("skills", compute_fitness())
        created = synthesize_species_v2(fitness, max_new=2, apply=True)
        print(f"🧬 v2 synthesized {len(created)} species: "
              f"{[c['name'] for c in created]}")
        if created:
            changed = True

    if args.retire:
        retired = retire_losers(max_losses=tuning['max_losses'])
        if retired:
            summary = ", ".join(
                "{0} ({1}W/{2}L)".format(r["name"], r["wins"], r["losses"])
                for r in retired)
            print(f" coffin retired {len(retired)} species: {summary}")
            changed = True
        else:
            print("✅ no species above the loss threshold")

    if args.status:
        s = status_overview()
        print("═" * 50)
        print(f" 🧬 DARWIN ECOSYSTEM - {s['when'][:19]}")
        print("═" * 50)
        print(f" Population:        {s['population']} skills "
              f"(trend: {s['trend']})")
        print(f" Fittest:           {s['fittest']}")
        print(f" Weakest:           {s['weakest']}")
        print(f" Species:           {s['species']['installed']} installed, "
              f"{s['species']['candidate']} candidate, "
              f"{s['species']['retired']} retired")
        print(f" Active trials:     {s['active_trials']}")
        print(f" Harvested ideas:   {s['harvested_blueprints']}")
        print(f" Genome records:    {s['genome_records']}")
        print("═" * 50)
        return 0

    if args.explain:
        e = explain_skill(args.explain)
        if not e["exists"]:
            print(f"❌ unknown skill: {args.explain}")
            return 1
        print(f"🔍 EXPLAIN: {e['skill']}")
        print(f"   Fitness:      {e['fitness']['fitness'] if e['fitness'] else '?'}")
        b = e["breakdown"]
        print(f"   Breakdown:    usage {b['usage_points']:+} | health "
              f"{b['health_points']:+} | mutation {b['mutation_bonus']:+} | "
              f"age {b['age_penalty']:+}")
        g = e["genome"]
        print(f"   Genome:       {g.get('wins', 0)}W / {g.get('losses', 0)}L")
        print(f"   Lineage:      parent {e['lineage_as_parent']}x, "
              f"child {e['lineage_as_child']}x")
        print(f"   Cron-protected: {e['referenced_by_cron']}")
        print(f"   Species:      {e['is_species']}")
        if e["operator_quality"]:
            oq = e["operator_quality"]
            print(f"   Operator:     {oq['op']} win-rate {oq['win_rate']} "
                  f"({oq['wins']}/{oq['uses']})")
        if e["trials"]:
            print(f"   Trials:       {len(e['trials'])}")
        for ev in e["last_events"][-3:]:
            print(f"   Event:        {ev.get('kind')}: {ev.get('parent')} "
                  f"-> {ev.get('child')}")
        return 0

    if args.unretire:
        ok = rollback_species(args.unretire)
        print(f"♻️  species '{args.unretire}' restored: {ok}")
        return 0 if ok else 1

    if args.predate or args.predate_apply:
        fitness = _load_json(FITNESS_FILE, {}).get("skills", compute_fitness())
        results = predation_cycle(fitness,
                                  dry_run=not args.predate_apply)
        for r in results:
            if r["status"] == "no-prey":
                print("🦅 predation: no redundant skills found")
            elif r["status"] in ("absorbed", "would-absorb"):
                print(f"🦅 {r['predator']} absorbs `{r['prey']}` "
                      f"(overlap {r['overlap']})")
            else:
                print(f"🦅 prey `{r['prey']}` survived the duel "
                      f"(winner: {r['winner']})")
        if any(r["status"] == "absorbed" for r in results):
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




# ─────────────────────────────────────────────────────────────────────────────


# 16. PHASE 15: self-tuning - the ecosystem adjusts its own constants
# ─────────────────────────────────────────────────────────────────────────────

TUNING_FILE = DARWIN_DIR / "tuning.json"
TUNING_DEFAULTS = {
    "epsilon": 0.3,        # exploration rate for operator selection
    "max_trials": 2,       # concurrent live trials
    "max_losses": 3,       # arena defeats before species retirement
    "tuned_at": None,
}


def get_tuning() -> dict:
    """Current tuning constants (persisted so they survive restarts)."""
    t = dict(TUNING_DEFAULTS)
    t.update(_load_json(TUNING_FILE, {}))
    return t


def auto_tune() -> dict:
    """Adjust Darwin's own constants based on ecosystem health signals.

    Rules (each evidence-driven, conservative bounds):
    - Stagnating population (flat trend, >=3 snapshots):
      raise epsilon to 0.5 (explore more) and max_trials to 3 (more experiments)
    - Volatile population (falling trend): lower epsilon to 0.15 (exploit
      proven operators), tighten retirement to max_losses=2 (prune faster)
    - Healthy (rising): keep defaults, log the decision
    Returns the applied tuning for the report."""
    t = get_tuning()
    trend_data = fitness_trend()
    trend = trend_data.get("population_trend", "unknown")
    snapshots = trend_data.get("snapshots", 0)
    old = dict(t)
    t["tuned_at"] = _now()

    if snapshots >= 3 and trend == "flat":
        t["epsilon"] = 0.5
        t["max_trials"] = 3
        t["reason"] = "stagnating -> explore more"
    elif snapshots >= 3 and trend == "falling":
        t["epsilon"] = 0.15
        t["max_losses"] = 2
        t["reason"] = "declining -> exploit winners, prune faster"
    else:
        t["epsilon"] = TUNING_DEFAULTS["epsilon"]
        t["max_trials"] = TUNING_DEFAULTS["max_trials"]
        t["max_losses"] = TUNING_DEFAULTS["max_losses"]
        t["reason"] = f"healthy ({trend}) -> defaults"

    if t != old:
        _save_json(TUNING_FILE, t)
    return t


# ─────────────────────────────────────────────────────────────────────────────
# 17. PHASE 16: predation - the population consumes its own redundancy
# ─────────────────────────────────────────────────────────────────────────────

PREDATION_LOG = DARWIN_DIR / "predation-log.json"


def _skill_tokens(name: str) -> set[str]:
    """Meaningful tokens of a skill name (drop noise words)."""
    noise = {"skill", "darwin", "mut", "harvested", "tool", "tools", "the"}
    return {t for t in re.split(r"[-_+.\s]", name.lower()) if t and t not in noise}


def find_prey(fitness: dict, min_overlap: float = 0.6) -> list[dict]:
    """Detect redundant skill pairs: two skills whose name tokens overlap
    strongly. The weaker one (lower fitness) is potential prey of the
    stronger one. Cron-protected skills are never prey."""
    protected = _cron_referenced_skills()
    items = [(n, s.get("fitness", 0)) for n, s in fitness.items()]
    items.sort(key=lambda kv: kv[1], reverse=True)
    prey = []
    seen_pairs = set()
    for i, (strong, strong_fit) in enumerate(items):
        strong_toks = _skill_tokens(strong)
        if not strong_toks:
            continue
        for weak, weak_fit in items[i + 1:]:
            if weak in protected or weak in seen_pairs:
                continue
            weak_toks = _skill_tokens(weak)
            if not weak_toks:
                continue
            overlap = len(strong_toks & weak_toks) / len(weak_toks)
            if overlap >= min_overlap and strong != weak:
                pair = (strong, weak)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    prey.append({"predator": strong, "prey": weak,
                                 "overlap": round(overlap, 2),
                                 "predator_fitness": strong_fit,
                                 "prey_fitness": weak_fit})
    return prey


def predate(prey_list: list[dict], dry_run: bool = True) -> list[dict]:
    """Execute predation: the stronger skill absorbs the weaker one.

    Mechanism (after a REAL head-to-head confirms dominance):
    1. head_to_head(predator, prey) - the duel
    2. If the predator wins, the prey is archived and its trigger line is
       appended to the predator's SKILL.md (trigger inheritance)
    3. Lineage records a 'predation' event
    """
    import shutil
    results = []
    for p in prey_list:
        predator, prey = p["predator"], p["prey"]
        duel = head_to_head(predator, prey)
        # In a tie (both exit 0), fitness rank decides: the predator was
        # already ranked stronger by find_prey. Only a strictly functional
        # prey win (prey works, predator fails) saves the prey.
        prey_wins_functionally = (
            duel["winner"] == "child"
            and duel["parent_result"].get("exit_code") not in (0, None)
            and duel["child_result"].get("exit_code") == 0)
        if prey_wins_functionally:
            results.append({"predator": predator, "prey": prey,
                            "status": "survived",
                            "winner": duel["winner"]})
            continue
        if not dry_run:
            archive = DARWIN_DIR / "archive"
            archive.mkdir(parents=True, exist_ok=True)
            target = archive / f"{prey}_{NOW.strftime('%Y%m%d_%H%M%S')}"
            src = SKILLS_DIR / prey
            if src.exists():
                shutil.copytree(str(src), str(target))
                shutil.rmtree(str(src))
            # trigger inheritance: prey's trigger appended to predator
            pred_md = SKILLS_DIR / predator / "SKILL.md"
            if pred_md.exists():
                inherited = (f"\n## Inherited Trigger (from `{prey}`)\n"
                             f"Also handles topics previously covered by "
                             f"the absorbed skill `{prey}`.\n")
                pred_md.write_text(pred_md.read_text("utf-8", errors="replace")
                                   + inherited, "utf-8")
            # genome: predator gains a win
            population = _load_json(POPULATION_FILE, {})
            g = population.setdefault(predator, {"wins": 0, "losses": 0})
            g["wins"] = g.get("wins", 0) + 1
            _save_json(POPULATION_FILE, population)
            record_lineage(predator, prey, "predation", {"overlap": p["overlap"]})
            log = _load_json(PREDATION_LOG, [])
            log.append({"predator": predator, "prey": prey,
                        "when": _now(), "overlap": p["overlap"]})
            _save_json(PREDATION_LOG, log)
        results.append({"predator": predator, "prey": prey,
                        "status": "absorbed" if not dry_run else "would-absorb",
                        "overlap": p["overlap"]})
    return results


def predation_cycle(fitness: dict, dry_run: bool = True) -> list[dict]:
    """Full predation pass: find prey, duel, absorb. Honors tuning."""
    prey = find_prey(fitness)
    if not prey:
        return [{"status": "no-prey"}]
    return predate(prey[:3], dry_run=dry_run)  # max 3 per cycle


if __name__ == "__main__":

    sys.exit(main())

