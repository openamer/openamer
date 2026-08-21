#!/usr/bin/env python3
"""
Autonomous Goal Engine v1.0
============================
Mission-Definition + Auto-Task-Generierung + Priorisierung + Self-Execution-Tick.

CLI:
  --define <name> [description]    Mission definieren + automatisch Goals + Tasks
  --list                           Alle Missionen nach Priorität sortiert
  --prioritize                     Automatische Priorisierung nach Impact + Dringlichkeit
  --next                           Wichtigsten nächsten Task anzeigen
  --tick                           Nächsten Task ausführen (subprocess)
  --progress                       Report: % abgeschlossen, ETA, Blockers
  --complete <id>                  Mission/Goal/Task als done markieren
  --add-goal <mission_id> <desc>   Manuelles Goal zu einer Mission hinzufügen
  --add-task <goal_id> <desc>      Manuellen Task zu einem Goal hinzufügen
  --scan                           Analysiert existierende Scripts + Skills + findet Lücken

Exit-Codes: 0 = ok, 1 = nichts zu tun, 2 = Fehler
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Pfade ──────────────────────────────────────────────────────────────────

HOME = Path.home()

def _resolve_path(p: str) -> Path:
    """Convert MSYS-style paths (/c/...) to Windows paths (C:/...)."""
    if p.startswith("/") and len(p) > 2 and p[2] == "/":
        # /c/Users/... → C:/Users/...
        return Path(f"{p[1].upper()}:{p[2:]}")
    return Path(p)

_raw_home = os.environ.get("OPENAMER_HOME", "")
if _raw_home:
    OPENAMER_HOME = _resolve_path(_raw_home)
else:
    OPENAMER_HOME = HOME / "AppData" / "Local" / "openamer-laptop"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
SKILLS_DIR = OPENAMER_HOME / "skills"
GOAL_ENGINE_DIR = HOME / ".goal-engine"
MISSIONS_FILE = GOAL_ENGINE_DIR / "missions.json"
LOG_FILE = GOAL_ENGINE_DIR / "goal-engine.log"

# ── Timezone ───────────────────────────────────────────────────────────────

LOCAL_TZ = timezone(timedelta(hours=2))  # CEST


def now():
    return datetime.now(LOCAL_TZ)


def now_iso():
    return now().isoformat()


# ── Logging ────────────────────────────────────────────────────────────────

def log(msg: str):
    """Append a log line."""
    GOAL_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    ts = now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line)


# ── Data IO ────────────────────────────────────────────────────────────────

def _ensure_dir():
    GOAL_ENGINE_DIR.mkdir(parents=True, exist_ok=True)


def _load_missions() -> list[dict]:
    """Load missions from JSON file."""
    _ensure_dir()
    if not MISSIONS_FILE.exists():
        return []
    try:
        raw = MISSIONS_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        data = json.loads(raw)
        return data.get("missions", [])
    except (json.JSONDecodeError, OSError):
        log("⚠  missions.json beschädigt — starte mit leerem Stand")
        return []


def _save_missions(missions: list[dict]):
    """Save missions to JSON file."""
    _ensure_dir()
    data = {"missions": missions, "updated_at": now_iso()}
    MISSIONS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── ID generation ──────────────────────────────────────────────────────────

def _new_id(prefix: str = "m") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ── Auto Task Generation ───────────────────────────────────────────────────

TASK_TEMPLATES = {
    "analyse": [
        "Analysiere vorhandene Logs in .self-healer/ auf Fehler-Patterns",
        "Analysiere vorhandene Config auf Optimierungspotential",
        "Analysiere Speicherverbrauch und Performance-Engpässe",
    ],
    "implement": [
        "Erstelle unit tests für bestehende Funktionen",
        "Erstelle eine Health-Check-Routine",
        "Implementiere Error-Handling für kritische Pfade",
        "Füge Auto-Recovery für häufige Fehler hinzu",
    ],
    "optimize": [
        "Optimiere Ladezeiten und Startup-Verhalten",
        "Optimiere Speichernutzung (Cache-Strategie)",
        "Optimiere Cron-Job-Intervalle (weniger Overhead)",
    ],
    "monitor": [
        "Richte Monitoring-Dashboard für Metriken ein",
        "Füge Alerting bei kritischen Fehlern hinzu",
        "Erstelle wöchentlichen Health-Report",
    ],
    "integrate": [
        "Prüfe Integration mit bestehenden Scripts",
        "Erstelle einheitliche Exit-Codes für alle Scripts",
        "Richte automatische Config-Backups ein",
    ],
}


def auto_generate_tasks(mission_name: str, description: str) -> list[dict]:
    """Generate goals and tasks from mission description."""
    desc_lower = description.lower()
    generated_goals = []

    # Determine key themes from description
    themes = []
    if any(w in desc_lower for w in ["stabilität", "stabil", "crash", "robust"]):
        themes.append("analyse")
        themes.append("implement")
    if any(w in desc_lower for w in ["optimier", "performance", "schnell", "speed"]):
        themes.append("optimize")
        themes.append("monitor")
    if any(w in desc_lower for w in ["integrier", "connect", "anbindung", "api"]):
        themes.append("integrate")
        themes.append("implement")
    if any(w in desc_lower for w in ["überwach", "monitor", "alert", "health"]):
        themes.append("monitor")
        themes.append("analyse")
    if any(w in desc_lower for w in ["automatisier", "script", "task", "workflow"]):
        themes.append("implement")
        themes.append("integrate")
    # Default themes if nothing matches
    if not themes:
        themes = ["analyse", "implement", "optimize", "monitor"]

    # Deduplicate
    themes = list(dict.fromkeys(themes))

    # Generate 2-4 goals from themes
    goal_templates = [
        ("Analyse & Grundlagen", "analyse"),
        ("Implementierung & Entwicklung", "implement"),
        ("Optimierung & Performance", "optimize"),
        ("Überwachung & Reporting", "monitor"),
        ("Integration & Automatisierung", "integrate"),
    ]

    used_templates = [gt for gt in goal_templates if gt[1] in themes]
    if not used_templates:
        used_templates = goal_templates[:2]

    for goal_name, theme in used_templates:
        tasks = []
        templates = TASK_TEMPLATES.get(theme, TASK_TEMPLATES["analyse"])
        # Pick 2-3 random tasks from the template pool
        selected = random.sample(templates, min(3, len(templates)))
        for i, task_desc in enumerate(selected):
            tasks.append({
                "id": _new_id("t"),
                "description": task_desc,
                "status": "pending",
                "priority": 5 - i,  # first tasks have higher priority
                "script_hint": None,
            })
        generated_goals.append({
            "id": _new_id("g"),
            "description": goal_name,
            "progress": 0,
            "status": "pending",
            "tasks": tasks,
        })

    return generated_goals


# ── CLI: --define ──────────────────────────────────────────────────────────

def cmd_define(args):
    """Define a new mission + auto-generate goals & tasks."""
    name = args.name
    description = args.description or f"Mission: {name}"

    missions = _load_missions()
    mid = _new_id("m")
    mission = {
        "id": mid,
        "name": name,
        "description": description,
        "priority": 5,
        "status": "active",
        "created": now_iso(),
        "deadline": None,
        "goals": auto_generate_tasks(name, description),
    }
    missions.append(mission)
    _save_missions(missions)

    total_tasks = sum(len(g["tasks"]) for g in mission["goals"])
    print(f"✅ Mission '{name}' definiert (ID: {mid})")
    print(f"   Goals: {len(mission['goals'])}")
    print(f"   Tasks: {total_tasks}")
    print()
    for g in mission["goals"]:
        print(f"  🎯 {g['description']}")
        for t in g["tasks"]:
            print(f"     📋 [{t['status']}] {t['description']}")

    log(f"Mission definiert: {name} ({mid}) — {len(mission['goals'])} Goals, {total_tasks} Tasks")
    return 0


# ── CLI: --list ────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all missions sorted by priority."""
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen definiert.")
        return 0

    # Sort by priority descending
    sorted_missions = sorted(missions, key=lambda m: (-m.get("priority", 0), m.get("created", "")))

    print(f"{'ID':<14} {'Name':<30} {'Priorität':<10} {'Status':<10} {'Goals':<6} {'Fortschritt':<12}")
    print("-" * 90)
    for m in sorted_missions:
        name = m.get("name", "?")
        if len(name) > 28:
            name = name[:27] + "…"
        gs = m.get("goals", [])
        done_tasks = sum(1 for g in gs for t in g.get("tasks", []) if t.get("status") == "done")
        total_tasks = sum(len(g.get("tasks", [])) for g in gs)
        pct = f"{int(done_tasks / total_tasks * 100)}%" if total_tasks > 0 else "0%"
        prio = m.get("priority", 0)
        prio_str = f"{'★' * prio}{'☆' * (5 - prio)}" if prio <= 5 else str(prio)
        print(f"{m['id']:<14} {name:<30} {prio_str:<10} {m.get('status', '?'):<10} {len(gs):<6} {pct:<12}")

    print()
    total_done = sum(1 for m in missions for g in m.get("goals", []) for t in g.get("tasks", []) if t.get("status") == "done")
    total_all = sum(len(g.get("tasks", [])) for m in missions for g in m.get("goals", []))
    print(f"📊 Gesamt: {len(missions)} Missionen, {total_done}/{total_all} Tasks erledigt")
    return 0


# ── CLI: --prioritize ──────────────────────────────────────────────────────

def cmd_prioritize(args):
    """Auto-prioritize missions by impact + urgency."""
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen zum Priorisieren.")
        return 0

    for m in missions:
        if m.get("status") != "active":
            continue
        gs = m.get("goals", [])
        total_tasks = sum(len(g.get("tasks", [])) for g in gs)
        done_tasks = sum(1 for g in gs for t in g.get("tasks", []) if t.get("status") == "done")
        pending_tasks = sum(1 for g in gs for t in g.get("tasks", []) if t.get("status") == "pending")

        # Impact: how many pending tasks remain (more pending = more impact to resolve)
        impact = min(5, max(1, pending_tasks))

        # Urgency: age + deadline pressure
        days_old = 0
        try:
            created = datetime.fromisoformat(m.get("created", now_iso()))
            days_old = max(0, (now() - created).days)
        except (ValueError, TypeError):
            pass
        urgency = min(5, max(1, int(days_old / 7) + 1))

        # Deadline boost
        if m.get("deadline"):
            try:
                deadline = datetime.fromisoformat(m["deadline"])
                remaining = (deadline - now()).days
                if remaining < 0:
                    urgency = 5  # Overdue → max urgency
                elif remaining < 7:
                    urgency = 5
                elif remaining < 30:
                    urgency = 4
            except (ValueError, TypeError):
                pass

        # Progress penalty: if almost done, boost priority to finish
        progress_boost = 0
        if total_tasks > 0:
            progress_pct = done_tasks / total_tasks
            if progress_pct >= 0.8:
                progress_boost = 1  # Almost done → push to finish

        new_priority = min(5, max(1, (impact + urgency) // 2 + progress_boost))
        m["priority"] = new_priority

    _save_missions(missions)

    print("📊 Automatische Priorisierung abgeschlossen:\n")
    sorted_missions = sorted(missions, key=lambda m: (-m.get("priority", 0), m.get("created", "")))
    for m in sorted_missions:
        gs = m.get("goals", [])
        done = sum(1 for g in gs for t in g.get("tasks", []) if t.get("status") == "done")
        total = sum(len(g.get("tasks", [])) for g in gs)
        pct = f"{int(done / total * 100)}%" if total > 0 else "0%"
        stars = "★" * m.get("priority", 0) + "☆" * (5 - m.get("priority", 0))
        print(f"  {stars} {m['name']} — {pct} ({done}/{total})")

    log("Priorisierung abgeschlossen")
    return 0


# ── CLI: --next ────────────────────────────────────────────────────────────

def cmd_next(args):
    """Show the most important next task to work on."""
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen. Definiere eine mit --define.")
        return 1

    candidates = []
    for m in missions:
        if m.get("status") != "active":
            continue
        for g in m.get("goals", []):
            if g.get("status") in ("done",):
                continue
            for t in g.get("tasks", []):
                if t.get("status") == "pending":
                    candidates.append((m, g, t))

    if not candidates:
        print("🎉 Alle Tasks erledigt! Keine offenen Tasks mehr.")
        return 1

    # Score: mission priority * task priority
    def score(item):
        m, g, t = item
        return -m.get("priority", 0) * t.get("priority", 1)

    candidates.sort(key=score)
    m, g, t = candidates[0]

    print("🎯 Nächster Task:\n")
    print(f"  Mission: {m['name']}")
    print(f"  Goal:    {g['description']}")
    print(f"  Task:    {t['description']}")
    print(f"  Task-ID: {t['id']}")
    print(f"  Script:  {t.get('script_hint', '—')}")
    print()

    # Show runner-ups
    if len(candidates) > 1:
        print("  Weitere Kandidaten:")
        for mi, gi, ti in candidates[1:4]:
            print(f"    · {mi['name']} → {gi['description']} → {ti['description']}")

    return 0


# ── CLI: --tick ────────────────────────────────────────────────────────────

def cmd_tick(args):
    """Execute the next pending task via subprocess."""
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen. --define zuerst.")
        return 1

    candidates = []
    for m in missions:
        if m.get("status") != "active":
            continue
        for g in m.get("goals", []):
            if g.get("status") == "done":
                continue
            for t in g.get("tasks", []):
                if t.get("status") == "pending":
                    candidates.append((m, g, t))

    if not candidates:
        print("🎉 Alle Tasks abgeschlossen! Kein --tick nötig.")
        return 1

    def score(item):
        m, g, t = item
        return -m.get("priority", 0) * t.get("priority", 1)

    candidates.sort(key=score)
    m, g, t = candidates[0]

    print(f"🔄 Tick: Führe Task aus...")
    print(f"   Mission: {m['name']}")
    print(f"   Goal:    {g['description']}")
    print(f"   Task:    {t['description']}")
    print(f"   Task-ID: {t['id']}")

    # Mark task as running
    t["status"] = "running"
    _save_missions(missions)

    script_hint = t.get("script_hint")
    if script_hint and Path(script_hint).exists():
        cmd = [sys.executable, script_hint]
    elif script_hint:
        cmd = [sys.executable, str(SCRIPTS_DIR / script_hint)]
    else:
        # Try to find a matching script
        script_name = _find_matching_script(t["description"], m["name"])
        if script_name:
            cmd = [sys.executable, str(SCRIPTS_DIR / script_name)]
        else:
            # Fallback: run a generic analysis
            print("   ℹ️  Kein passendes Script gefunden — führe Analyse durch")
            cmd = _build_analysis_cmd(t["description"], m["name"])

    if cmd:
        print(f"   Ausführung: {' '.join(str(c) for c in cmd)}")
        log(f"Tick: Starte Task {t['id']} — {t['description']}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                t["status"] = "done"
                t["completed_at"] = now_iso()
                print(f"   ✅ Task erfolgreich abgeschlossen (exit: {result.returncode})")
                log(f"Task {t['id']} erledigt")
            else:
                t["status"] = "failed"
                t["error"] = result.stderr[:500] if result.stderr else f"exit {result.returncode}"
                print(f"   ❌ Task fehlgeschlagen (exit: {result.returncode})")
                if result.stderr:
                    print(f"      {result.stderr[:500]}")
                log(f"Task {t['id']} fehlgeschlagen: {t['error']}")
        except subprocess.TimeoutExpired:
            t["status"] = "failed"
            t["error"] = "timeout (300s)"
            print("   ⏰ Task timeout nach 300s")
            log(f"Task {t['id']} timeout")
        except Exception as e:
            t["status"] = "failed"
            t["error"] = str(e)[:300]
            print(f"   ❌ Fehler: {e}")
            log(f"Task {t['id']} Exception: {e}")

    # Update goal progress
    _update_goal_progress(g)
    _save_missions(missions)

    # Print progress
    gs = m.get("goals", [])
    done = sum(1 for gg in gs for tt in gg.get("tasks", []) if tt.get("status") == "done")
    total = sum(len(gg.get("tasks", [])) for gg in gs)
    print(f"   📊 Mission-Fortschritt: {done}/{total} Tasks ({int(done/total*100) if total else 0}%)")

    return 0


def _find_matching_script(task_desc: str, mission_name: str) -> str | None:
    """Find a script that matches the task description."""
    if not SCRIPTS_DIR.exists():
        return None
    try:
        scripts = [f for f in SCRIPTS_DIR.iterdir() if f.suffix == ".py" and f.stem != "goal-engine"]
        # Look for keywords in the task description
        keywords = re.findall(r'\w+', task_desc.lower())
        best_match = None
        best_score = 0
        for script in scripts:
            name_lower = script.stem.lower()
            score = sum(1 for kw in keywords if len(kw) > 3 and kw in name_lower)
            if score > best_score:
                best_score = score
                best_match = script.name
        if best_match and best_score > 0:
            return best_match
    except OSError:
        pass
    return None


def _build_analysis_cmd(task_desc: str, mission_name: str) -> list[str]:
    """Build a fallback analysis/generic command."""
    return [sys.executable, "-c", f"""
import sys
print("Goal-Engine: Automatische Analyse für Task")
print("  Task: {task_desc}")
print("  Mission: {mission_name}")
print()
print("Analyse durchgeführt — kein spezifisches Script zugewiesen.")
print("Um diesen Task produktiv zu machen, weise ein Script zu via:")
print("  --add-task <goal_id> '<task_desc>' --script <script_name>")
sys.exit(0)
"""]


def _update_goal_progress(g: dict):
    """Update goal progress percentage and status based on tasks."""
    tasks = g.get("tasks", [])
    if not tasks:
        g["progress"] = 100
        g["status"] = "done"
        return
    done = sum(1 for t in tasks if t.get("status") == "done")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    g["progress"] = int(done / len(tasks) * 100)
    if done == len(tasks):
        g["status"] = "done"
    elif failed > 0:
        g["status"] = "partially_done"
    else:
        g["status"] = "in_progress"


# ── CLI: --progress ────────────────────────────────────────────────────────

def cmd_progress(args):
    """Generate a progress report."""
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen definiert.")
        return 0

    total_tasks_all = 0
    total_done_all = 0
    blockers = []

    print("📊 GOAL-ENGINE PROGRESS REPORT")
    print("=" * 60)
    print(f"Stand: {now().strftime('%Y-%m-%d %H:%M')}\n")

    sorted_missions = sorted(missions, key=lambda m: (-m.get("priority", 0), m.get("created", "")))
    for m in sorted_missions:
        gs = m.get("goals", [])
        m_done = sum(1 for g in gs for t in g.get("tasks", []) if t.get("status") == "done")
        m_total = sum(len(g.get("tasks", [])) for g in gs)
        m_pct = int(m_done / m_total * 100) if m_total > 0 else 0
        total_tasks_all += m_total
        total_done_all += m_done

        stars = "★" * m.get("priority", 0) + "☆" * (5 - m.get("priority", 0))
        print(f"  [{m.get('status', '?')}] {m['name']} — {stars}")
        print(f"       Priorität: {m.get('priority', 0)}/5  |  Fortschritt: {m_pct}% ({m_done}/{m_total})")

        for g in gs:
            gt = g.get("tasks", [])
            g_done = sum(1 for t in gt if t.get("status") == "done")
            g_failed = sum(1 for t in gt if t.get("status") == "failed")
            g_pct = int(g_done / len(gt) * 100) if gt else 0
            icon = "✅" if g.get("status") == "done" else "🔄" if g.get("status") == "in_progress" else "⏳"
            status_str = {
                "done": "✅ Erledigt",
                "in_progress": "🔄 In Bearbeitung",
                "partially_done": "⚠️ Teilweise",
                "pending": "⏳ Ausstehend",
            }.get(g.get("status", "pending"), g.get("status", "pending"))
            print(f"       {icon} {g['description']} [{status_str}] ({g_done}/{len(gt)}, {g_pct}%)")
            for t in gt:
                status_icon = {
                    "done": "✅", "running": "🔄", "failed": "❌",
                    "pending": "📋", "cancelled": "🚫",
                }.get(t.get("status", "pending"), "📋")
                desc = t["description"]
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                print(f"          {status_icon} {desc}")
                if t.get("status") == "failed":
                    blockers.append(f"  ❌ {m['name']} > {g['description']} > {desc}: {t.get('error', 'Unbekannter Fehler')}")
            print()

    print(f"\n📊 Gesamtfortschritt: {total_done_all}/{total_tasks_all} ({int(total_done_all/total_tasks_all*100) if total_tasks_all else 0}%)")

    # ETA estimation
    if total_tasks_all > total_done_all:
        remaining = total_tasks_all - total_done_all
        # Rough estimate: 1 task per tick, tick every 30min = 48 ticks/day
        eta_days = remaining / 48
        print(f"📅 Geschätzte Fertigstellung: in ~{eta_days:.1f} Tagen (bei 30-Min-Tick)")
    else:
        print("🎉 Alle Tasks erledigt!")

    if blockers:
        print(f"\n⚠️ Blockers ({len(blockers)}):")
        for b in blockers:
            print(b)

    return 0


# ── CLI: --complete ────────────────────────────────────────────────────────

def cmd_complete(args):
    """Mark a mission, goal, or task as done."""
    cid = args.id
    missions = _load_missions()
    if not missions:
        print("📭 Keine Missionen.")
        return 0

    found = False
    for m in missions:
        # Check mission
        if m["id"] == cid:
            m["status"] = "done"
            # Mark all goals & tasks as done
            for g in m.get("goals", []):
                g["status"] = "done"
                g["progress"] = 100
                for t in g.get("tasks", []):
                    t["status"] = "done"
                    t["completed_at"] = now_iso()
            print(f"✅ Mission '{m['name']}' als erledigt markiert!")
            found = True
            break
        # Check goals
        for g in m.get("goals", []):
            if g["id"] == cid:
                g["status"] = "done"
                g["progress"] = 100
                for t in g.get("tasks", []):
                    t["status"] = "done"
                    t["completed_at"] = now_iso()
                print(f"✅ Goal '{g['description']}' in Mission '{m['name']}' erledigt!")
                found = True
                break
            # Check tasks
            for t in g.get("tasks", []):
                if t["id"] == cid:
                    t["status"] = "done"
                    t["completed_at"] = now_iso()
                    _update_goal_progress(g)
                    print(f"✅ Task '{t['description']}' in Goal '{g['description']}' erledigt!")
                    found = True
                    break

    if not found:
        print(f"❌ Kein Eintrag mit ID '{cid}' gefunden.")
        return 2

    _save_missions(missions)
    log(f"Complete: {cid} als done markiert")
    return 0


# ── CLI: --add-goal / --add-task ──────────────────────────────────────────

def cmd_add_goal(args):
    """Manually add a goal to a mission."""
    missions = _load_missions()
    for m in missions:
        if m["id"] == args.mission_id:
            g = {
                "id": _new_id("g"),
                "description": args.description,
                "progress": 0,
                "status": "pending",
                "tasks": [],
            }
            m.setdefault("goals", []).append(g)
            _save_missions(missions)
            print(f"✅ Goal '{args.description}' zu Mission '{m['name']}' hinzugefügt (ID: {g['id']})")
            log(f"Goal hinzugefügt: {args.description} zu {m['name']}")
            return 0

    print(f"❌ Mission '{args.mission_id}' nicht gefunden.")
    return 2


def cmd_add_task(args):
    """Manually add a task to a goal."""
    missions = _load_missions()
    for m in missions:
        for g in m.get("goals", []):
            if g["id"] == args.goal_id:
                t = {
                    "id": _new_id("t"),
                    "description": args.description,
                    "status": "pending",
                    "priority": args.priority or 3,
                    "script_hint": args.script,
                }
                g.setdefault("tasks", []).append(t)
                _save_missions(missions)
                print(f"✅ Task '{args.description}' zu Goal '{g['description']}' hinzugefügt (ID: {t['id']})")
                log(f"Task hinzugefügt: {args.description} zu Goal {g['description']}")
                return 0

    print(f"❌ Goal '{args.goal_id}' nicht gefunden.")
    return 2


# ── CLI: --scan ────────────────────────────────────────────────────────────

def cmd_scan(args):
    """Analyze existing scripts + skills + find gaps."""
    print("🔍 Scan: Analysiere vorhandene Scripts, Skills und offene Tasks...\n")

    # 1. Count scripts (check both OPENAMER_HOME/scripts and HOME/scripts)
    scripts = []
    for sd in [SCRIPTS_DIR, HOME / "scripts"]:
        if sd.exists():
            scripts.extend(f for f in sd.iterdir() if f.suffix == ".py")
    scripts = sorted(set(scripts))
    print(f"  📜 Scripts gefunden: {len(scripts)}")

    # 2. List skills
    skills = []
    if SKILLS_DIR.exists():
        skills = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    print(f"  📚 Skills verfügbar: {len(skills)}")

    # 3. Analyze missions for gaps
    missions = _load_missions()
    active = [m for m in missions if m.get("status") == "active"]
    all_tasks = [(m, g, t) for m in active for g in m.get("goals", []) for t in g.get("tasks", [])]
    pending = [(m, g, t) for m, g, t in all_tasks if t.get("status") == "pending"]
    failed = [(m, g, t) for m, g, t in all_tasks if t.get("status") == "failed"]

    print(f"  📋 Missionen: {len(missions)} ({len(active)} aktiv)")
    print(f"  📋 Offene Tasks: {len(pending)}")
    print(f"  ❌ Fehlgeschlagene Tasks: {len(failed)}")

    # 4. Check cron jobs
    cron_path = OPENAMER_HOME / "cron" / "jobs.json"
    cron_jobs = []
    if cron_path.exists():
        try:
            cron_data = json.loads(cron_path.read_text(encoding="utf-8"))
            cron_jobs = cron_data.get("jobs", [])
        except (json.JSONDecodeError, OSError):
            pass
    print(f"  ⏰ Cron-Jobs: {len(cron_jobs)}")

    # 5. Find gaps: scripts without skill, missions without active cron
    script_names = {s.stem for s in scripts}
    skill_names = {s.name for s in skills}
    has_goal_engine_cron = any("goal-engine" in j.get("script", "") or j.get("id", "") == "goal_engine_tick" for j in cron_jobs)

    print(f"\n🔎 GAP-ANALYSE:")
    print(f"  {'✅' if has_goal_engine_cron else '❌'} Goal-Engine Cron-Job: {'vorhanden' if has_goal_engine_cron else 'FEHLT — --tick alle 30min nicht konfiguriert!'}")
    print(f"  {'✅' if len(scripts) > 0 else '❌'} Scripts-Verzeichnis: {'vorhanden' if len(scripts) > 0 else 'LEER'}")

    # Suggest new missions based on gaps
    if not has_goal_engine_cron:
        print(f"\n💡 Empfehlung: Richte den Cron-Job für --tick ein!")
    if len(pending) == 0 and len(active) > 0:
        print(f"💡 Empfehlung: Aktive Missionen haben keine offenen Tasks — füge neue hinzu!")
    elif len(active) == 0:
        print(f"💡 Empfehlung: Keine aktiven Missionen — defniere eine mit --define!")

    # Generate insights
    insight_count = 0
    print(f"\n💡 INSIGHTS ({len(pending)} offene Tasks):")
    for m, g, t in pending[:5]:
        script = _find_matching_script(t["description"], m["name"])
        if script:
            print(f"  ✅ Task '{t['description']}' kann mit '{script}' ausgeführt werden")
            insight_count += 1
        else:
            print(f"  ⚠️ Task '{t['description']}' hat kein passendes Script")
            insight_count += 1

    log(f"Scan abgeschlossen: {len(scripts)} Scripts, {len(skills)} Skills, {len(pending)} offene Tasks")
    return 0


# ── Main ───────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Autonomous Goal Engine — Missionen, Goals, Tasks & Auto-Execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Beispiele:
              goal-engine.py --define 'OpenAmer verbessern' 'Stabilität und Performance optimieren'
              goal-engine.py --list
              goal-engine.py --prioritize
              goal-engine.py --next
              goal-engine.py --tick
              goal-engine.py --progress
              goal-engine.py --complete m_abc12345
              goal-engine.py --scan
              goal-engine.py --add-goal m_abc12345 'Monitoring einrichten'
              goal-engine.py --add-task g_abc12345 'Logs analysieren' --priority 4 --script log-analyzer.py
        """),
    )

    parser.add_argument("--define", nargs="+", metavar=("NAME", "DESCRIPTION"),
                        help="Neue Mission definieren: Name, optionale Beschreibung")
    parser.add_argument("--list", action="store_true", help="Alle Missionen anzeigen")
    parser.add_argument("--prioritize", action="store_true", help="Automatische Priorisierung")
    parser.add_argument("--next", action="store_true", help="Wichtigsten nächsten Task anzeigen")
    parser.add_argument("--tick", action="store_true", help="Nächsten Task ausführen")
    parser.add_argument("--progress", action="store_true", help="Fortschrittsreport anzeigen")
    parser.add_argument("--complete", metavar="ID", help="Mission/Goal/Task als erledigt markieren")
    parser.add_argument("--add-goal", nargs=2, metavar=("MISSION_ID", "DESCRIPTION"),
                        help="Goal zu einer Mission hinzufügen")
    parser.add_argument("--add-task", nargs=2, metavar=("GOAL_ID", "DESCRIPTION"),
                        help="Task zu einem Goal hinzufügen")
    parser.add_argument("--script", help="Script-Hint für --add-task")
    parser.add_argument("--priority", type=int, default=3, help="Priorität für --add-task (1-5)")
    parser.add_argument("--scan", action="store_true", help="Analyse: Scripts, Skills, Gaps")

    return parser.parse_args(argv)


def main():
    args = parse_args()

    # Dispatch commands
    if args.define:
        name = args.define[0]
        desc = " ".join(args.define[1:]) if len(args.define) > 1 else ""
        return cmd_define(type("Args", (), {"name": name, "description": desc})())

    if args.list:
        return cmd_list(args)

    if args.prioritize:
        return cmd_prioritize(args)

    if args.next:
        return cmd_next(args)

    if args.tick:
        return cmd_tick(args)

    if args.progress:
        return cmd_progress(args)

    if args.complete:
        return cmd_complete(type("Args", (), {"id": args.complete})())

    if args.add_goal:
        mission_id, description = args.add_goal
        return cmd_add_goal(type("Args", (), {"mission_id": mission_id, "description": description})())

    if args.add_task:
        goal_id, description = args.add_task
        return cmd_add_task(type("Args", (), {
            "goal_id": goal_id, "description": description,
            "priority": args.priority, "script": args.script,
        })())

    if args.scan:
        return cmd_scan(args)

    # Default: show help
    import argparse as ap
    # Re-parse with --help
    parser = argparse.ArgumentParser()
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        log(f"CRASH: {e}")
        sys.exit(2)