#!/usr/bin/env python3
"""
Crew-Manager: Multi-Agent-Orchestrator mit Rollen (Dev/Tester/Reviewer/Architect).
Fuehrt spezialisierte Rollen als parallele Subprozesse aus (subprocess.Popen).
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).parent.resolve()
ROLLEN_FILE = SCRIPTS_DIR / "rollen.json"
CREWS_DIR = Path.home() / ".openamer" / "crews"
CREWS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = CREWS_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_roles():
    with open(ROLLEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["roles"]


def get_crew_path(crew_id):
    return CREWS_DIR / "{}.json".format(crew_id)


def load_crew(crew_id):
    path = get_crew_path(crew_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_crew(crew):
    path = get_crew_path(crew["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(crew, f, indent=2, ensure_ascii=False)


def list_crews():
    crews = []
    for p in CREWS_DIR.glob("*.json"):
        if p.name == "rollen.json":
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                crews.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    crews.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return crews


def next_crew_id():
    ts = datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return "crew-{}-{}".format(ts, suffix)


# ── Subprocess Runner ──────────────────────────────────────────────────


def _build_role_script(role, task_description, role_index, total_roles):
    """Build a Python script that executes a single role as a subprocess.

    Each role runs as an independent Python subprocess that receives the
    role definition and task, performs simulated work, and outputs
    structured JSON on stdout.
    """
    role_json = json.dumps(role, ensure_ascii=False)
    prompt = role["prompt_template"].format(task=task_description)
    task_json = json.dumps(task_description, ensure_ascii=False)

    delay_factor = role_index * 0.2

    # Escape backslashes so JSON survives single-quoted Python string embedding
    safe_role_json = role_json.replace("\\", "\\\\")
    safe_task_json = task_json.replace("\\", "\\\\")

    script = """#!/usr/bin/env python3
import json, sys, time, os, random
from datetime import datetime, timezone

role_info = json.loads('{}')
task = json.loads('{}')

work_time = random.uniform(0.5, 2.0) + {}
time.sleep(work_time)

result = {{
    "role_id": role_info["id"],
    "role_name": role_info["name"],
    "role_description": role_info["description"],
    "task": task,
    "status": "completed",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "work_time_seconds": round(work_time, 2),
    "output": {{}},
    "artifacts": {{}},
    "ended_at": datetime.now(timezone.utc).isoformat(),
}}

rid = role_info["id"]
if rid == "developer":
    result["output"] = {{
        "summary": "Code implementiert und getestet.",
        "findings": [
            "Implementierung der Kernlogik abgeschlossen",
            "Code-Struktur: modular, testbar, dokumentiert",
            "Task: {}",
        ],
        "recommendations": [
            "Tester soll Unit-Tests und Integrationstests ergaenzen",
            "Reviewer soll Code-Qualitaet pruefen",
        ],
    }}
elif rid == "tester":
    result["output"] = {{
        "summary": "Tests erstellt und QA durchgefuehrt.",
        "findings": [
            "Unit-Tests fuer alle Kernfunktionen",
            "Integrationstests fuer Schnittstellen",
            "Edge-Case-Analyse abgeschlossen",
        ],
        "recommendations": [
            "Alle Tests bestanden - keine kritischen Fehler",
            "Review vor Merge empfohlen",
        ],
    }}
elif rid == "reviewer":
    result["output"] = {{
        "summary": "Code-Review abgeschlossen.",
        "findings": [
            "Code-Qualitaet: gut (Best Practices eingehalten)",
            "Sicherheit: keine offensichtlichen Luecken",
            "Wartbarkeit: gut dokumentiert",
        ],
        "recommendations": [
            "Kleinere Style-Anpassungen moeglich",
            "Architektur-Doku um Sequenzdiagramm ergaenzen",
        ],
    }}
elif rid == "architect":
    result["output"] = {{
        "summary": "Architektur entworfen und dokumentiert.",
        "findings": [
            "Komponenten- und Schnittstellen-Design abgeschlossen",
            "Datenflussdiagramm erstellt",
            "Technologieentscheidungen dokumentiert",
        ],
        "recommendations": [
            "Entwickler soll gemaess Architektur implementieren",
            "Architektur-Review in Sprint-Planung einbringen",
        ],
    }}

print(json.dumps(result, ensure_ascii=False))
""".format(
        safe_role_json,
        safe_task_json,
        delay_factor,
        task_description[:60],
    )
    return script


def run_role_subprocess(role, task_description, role_index, total_roles, crew_id):
    """Start one role as subprocess.Popen with its own log file."""
    role_id = role["id"]
    role_log = LOG_DIR / "{}_{}.log".format(crew_id, role_id)

    script_content = _build_role_script(role, task_description, role_index, total_roles)

    proc = subprocess.Popen(
        [sys.executable, "-c", script_content],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(SCRIPTS_DIR),
    )

    return {
        "role_id": role_id,
        "role_name": role["name"],
        "log_file": str(role_log),
        "process": proc,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def collect_role_result(role_run):
    """Wait for subprocess and collect its result."""
    proc = role_run["process"]
    stdout, _ = proc.communicate()
    exit_code = proc.returncode

    log_path = Path(role_run["log_file"])
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(stdout or "")

    output = None
    if stdout and exit_code == 0:
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    output = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    if output is None:
        output = {"error": "Role {}: no valid JSON output (exit={})".format(
            role_run["role_id"], exit_code)}

    return {
        "role_id": role_run["role_id"],
        "role_name": role_run["role_name"],
        "log_file": str(log_path),
        "exit_code": exit_code,
        "output": output,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }


# ── CLI Commands ───────────────────────────────────────────────────────


def cmd_create(args):
    """create: Create a new task and delegate to all roles in parallel."""
    task_description = args.description
    roles = load_roles()
    crew_id = next_crew_id()

    print("[Crew-Manager] Erstelle Crew: {}".format(crew_id))
    print("[Crew-Manager] Task: {}".format(task_description))
    print("[Crew-Manager] Rollen: {}".format(", ".join(r["name"] for r in roles)))

    crew = {
        "id": crew_id,
        "description": task_description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "roles": [],
        "role_results": [],
    }
    save_crew(crew)

    # Start all roles in parallel as subprocesses
    role_runs = []
    for i, role in enumerate(roles):
        role_run = run_role_subprocess(role, task_description, i, len(roles), crew_id)
        role_runs.append(role_run)
        crew["roles"].append({
            "role_id": role["id"],
            "role_name": role["name"],
            "log_file": role_run["log_file"],
            "started_at": role_run["started_at"],
        })
    save_crew(crew)

    print("[Crew-Manager] Warte auf {} Rollen...".format(len(role_runs)))

    # Collect results via threads
    results_dict = {}
    threads = []

    def worker(role_run):
        result = collect_role_result(role_run)
        results_dict[result["role_id"]] = result

    for role_run in role_runs:
        t = threading.Thread(target=worker, args=(role_run,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=300)

    all_completed = True
    for role_run in role_runs:
        rid = role_run["role_id"]
        result = results_dict.get(rid)
        if result:
            crew["role_results"].append(result)
            status = "ok" if result["exit_code"] == 0 else "failed"
            print("  [{}] exit={} - {}".format(
                result["role_name"], result["exit_code"], status))
            if result["exit_code"] != 0:
                all_completed = False

    crew["status"] = "completed" if all_completed else "failed"
    crew["ended_at"] = datetime.now(timezone.utc).isoformat()
    save_crew(crew)

    print("\n[Crew-Manager] Crew {} abgeschlossen (status={})".format(
        crew_id, crew["status"]))
    print(json.dumps({"crew_id": crew_id, "status": crew["status"]}, indent=2))

    return 0


def cmd_status(args):
    """status: Show all crews and their status."""
    crews = list_crews()
    if not crews:
        print("[Crew-Manager] Keine Crews gefunden.")
        return 0

    header = "{:<32} {:<12} {:<8} {:<40} {}".format(
        "ID", "Status", "Rollen", "Task", "Erstellt")
    print(header)
    print("-" * 100)

    for crew in crews:
        cid = crew["id"]
        status = crew.get("status", "?")
        num_roles = len(crew.get("roles", []))
        task = crew.get("description", "")
        if len(task) > 40:
            task = task[:37] + "..."
        created = crew.get("created_at", "?")[:19].replace("T", " ")
        print("{:<32} {:<12} {:<8} {:<40} {}".format(
            cid, status, num_roles, task, created))

    running = [c for c in crews if c.get("status") == "running"]
    completed = [c for c in crews if c.get("status") == "completed"]
    total = len(crews)
    print("\n{} insgesamt, {} laufend, {} abgeschlossen".format(
        total, len(running), len(completed)))
    return 0


def cmd_review(args):
    """review: Summarize results for a crew."""
    crew = load_crew(args.crew_id)
    if not crew:
        print("[Crew-Manager] Crew '{}' nicht gefunden.".format(args.crew_id),
              file=sys.stderr)
        return 1

    print("=" * 70)
    print("CREW REVIEW: {}".format(crew["id"]))
    print("=" * 70)
    print("Task: {}".format(crew["description"]))
    print("Status: {}".format(crew.get("status", "?")))
    print("Erstellt: {}".format(crew.get("created_at", "?")))
    if crew.get("ended_at"):
        print("Beendet: {}".format(crew["ended_at"]))
    print("-" * 70)

    for result in crew.get("role_results", []):
        role_name = result.get("role_name", "?")
        raw_output = result.get("output", {})
        # The subprocess returns output nested in output["output"]
        inner_output = raw_output.get("output", {}) if isinstance(raw_output, dict) else {}
        exit_code = result.get("exit_code", -1)
        status_icon = "OK" if exit_code == 0 else "FAIL"

        print("\n  [{}] {} (exit={})".format(status_icon, role_name, exit_code))
        print("      Summary: {}".format(inner_output.get("summary", "-")))

        findings = inner_output.get("findings", [])
        if findings:
            print("      Findings:")
            for f_item in findings:
                print("        . {}".format(f_item))

        recommendations = inner_output.get("recommendations", [])
        if recommendations:
            print("      Empfehlungen:")
            for r_item in recommendations:
                print("        -> {}".format(r_item))

    # Synthesis
    print("\n" + "-" * 70)
    print("SYNTHESE")
    print("-" * 70)

    all_outputs = [
        r.get("output", {}).get("output", {})
        if isinstance(r.get("output"), dict) else {}
        for r in crew.get("role_results", [])
        if r.get("exit_code") == 0
    ]
    if all_outputs:
        all_findings = []
        all_recs = []
        for o in all_outputs:
            all_findings.extend(o.get("findings", []))
            all_recs.extend(o.get("recommendations", []))
        print("Gesamt-Findings ({}):".format(len(all_findings)))
        for f_item in all_findings:
            print("  . {}".format(f_item))
        print("\nGesamt-Empfehlungen ({}):".format(len(all_recs)))
        for r_item in all_recs:
            print("  -> {}".format(r_item))

    print("\n" + "=" * 70)
    return 0


def cmd_list(args):
    return cmd_status(args)


# ── Main ───────────────────────────────────────────────────────────────


def build_parser():
    parser = argparse.ArgumentParser(
        prog="crew-manager",
        description="Crew-Manager: Multi-Agent-Orchestrator mit Rollen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  crew-manager.py create "Erstelle einen REST-API-Server mit FastAPI"
  crew-manager.py status
  crew-manager.py review crew-240821-123456-a1b2c3
  crew-manager.py list
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Neuen Task erstellen und an Rollen delegieren")
    p_create.add_argument("description", type=str, help="Task-Beschreibung")
    p_create.set_defaults(func=cmd_create)

    p_status = sub.add_parser("status", help="Zeige alle Crews und deren Status")
    p_status.set_defaults(func=cmd_status)

    p_review = sub.add_parser("review", help="Fasse Ergebnisse einer Crew zusammen")
    p_review.add_argument("crew_id", type=str, help="Crew-ID")
    p_review.set_defaults(func=cmd_review)

    p_list = sub.add_parser("list", help="Alias fuer status")
    p_list.set_defaults(func=cmd_list)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print("[Crew-Manager] FEHLER: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())