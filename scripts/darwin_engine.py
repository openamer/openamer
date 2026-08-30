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


def _mutate_skill_md(text: str, op: str) -> str:
    """Generate a skill text variant (deterministic mutation)."""
    if op == "tighten_trigger":
        if "## Trigger" in text:
            return text.replace("## Trigger", "## Trigger (tightened: fewer false positives)", 1)
        return text + "\n\n## Trigger\nOnly on explicit user request - no auto-triggers.\n"
    if op == "broaden_trigger":
        return text + "\n\n## Trigger (broad)\nAlso activate on adjacent topics.\n"
    if op == "add_pitfall":
        return text + "\n\n## Pitfall\nCheck Windows paths (MSYS vs native) before running commands.\n"
    if op == "add_verification_step":
        return text + "\n\n## Verification\nAfter the last step: back the result with real tool output.\n"
    return text


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
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    if not SKILLS_DIR.exists():
        print(f"❌ Skills directory not found: {SKILLS_DIR}")
        return 1

    changed = False

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
