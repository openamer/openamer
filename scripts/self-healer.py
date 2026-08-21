#!/usr/bin/env python3
"""
Self-Healing Daemon v2.0
=========================
Scannt Cron-Logs, erkennt Fehler-Patterns, führt Workarounds aus,
lernt aus Fehlern und speichert in .self-healer/memory.json

Exit-Codes:  0 = sauber (keine Fehler)
             1 = Fehler gefunden (nicht heilbar)
             2 = geheilt (Workaround erfolgreich)
"""

import json
import os
import re
import time
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# ── Pfade ──────────────────────────────────────────────────────────────────
HOME = Path.home()
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    HOME / "AppData" / "Local" / "openamer-laptop",
))

CRON_OUTPUT_DIR = OPENAMER_HOME / "cron" / "output"
CRON_JOBS_FILE = OPENAMER_HOME / "cron" / "jobs.json"
SELF_HEALER_DIR = HOME / ".self-healer"
MEMORY_FILE = SELF_HEALER_DIR / "memory.json"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"

# ── Fehler-Patterns ─────────────────────────────────────────────────────────
# Jedes Pattern: (regex, name, severity)
ERROR_PATTERNS = [
    (re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),   "traceback",   10),
    (re.compile(r"(?:^|\n)\s*Traceback", re.MULTILINE),                 "traceback2",   10),
    (re.compile(r"(?:Exception|Error|FATAL|CRITICAL):\s", re.IGNORECASE),"exception",   10),
    (re.compile(r"Script not found:", re.IGNORECASE),                    "script_not_found", 9),
    (re.compile(r"Script Error", re.IGNORECASE),                         "script_error", 9),
    (re.compile(r"exit code.*?\b[1-9]\d*\b", re.IGNORECASE),            "exit_nonzero", 8),
    (re.compile(r"exit \[-?\d+\]", re.IGNORECASE),                       "exit_negative", 8),
    (re.compile(r"FAILED|FAILURE", re.IGNORECASE),                       "failed",       7),
    (re.compile(r"❌|✗|✘|⚠"),                                             "status_icon",  7),
    (re.compile(r"connection refused|connection.*?fail|timeout", re.IGNORECASE), "connection", 8),
    (re.compile(r"killed|segfault|signal \d+|oom", re.IGNORECASE),       "killed",      10),
    (re.compile(r"ModuleNotFoundError|ImportError", re.IGNORECASE),      "import_error", 9),
    (re.compile(r"Permission denied", re.IGNORECASE),                    "permission",   8),
    (re.compile(r"No such file or directory|FileNotFoundError", re.IGNORECASE), "file_not_found", 8),
    (re.compile(r"\[SILENT\]"),                                           "silent",      1),  # Low severity — just an observation
]

# ── Bekannte Workarounds ────────────────────────────────────────────────────
# Jeder Workaround: (pattern_name, match_fn, apply_fn, description)
WORKAROUNDS = []

def _w_pid_restart(context: dict) -> dict:
    """Restart einen Prozess anhand seiner PID oder Lock-Datei."""
    job_dir = context.get("job_dir", "")
    job_id = context.get("job_id", "")
    result = {"applied": False, "detail": ""}

    # Suche nach PID in der Log-Zeile
    pid_match = re.search(r"PID[:\s]*(\d+)", context.get("match_text", ""))
    lock_match = re.search(r"Lock[-_]?[Dd]atei[^`]*`([^`]+)`", context.get("full_text", ""))

    # Alternative: aus dem Prompt extrahieren
    if not pid_match:
        pid_match = re.search(r"PID[:\s]*`?(\d+)`?", context.get("full_text", ""))

    if pid_match:
        pid = pid_match.group(1)
        try:
            # Prüfen ob Process läuft (Windows)
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10
            )
            if pid in r.stdout:
                # Prozess läuft — alles OK
                result["applied"] = True
                result["detail"] = f"PID {pid} läuft bereits — kein Neustart nötig"
                return result
            else:
                result["detail"] = f"PID {pid} existiert nicht mehr — Neustart empfohlen"
        except Exception as e:
            result["detail"] = f"PID-Check fehlgeschlagen: {e}"

    # Versuche Lock-Datei zu finden und Prozess aus Prompt zu starten
    prompt = context.get("prompt", "")
    start_cmd = None
    for line in prompt.split("\n"):
        if "start" in line.lower() and (".sh" in line or ".bat" in line or "bash" in line):
            start_cmd = line.strip().strip("`").strip()
            break

    if start_cmd:
        try:
            r = subprocess.run(start_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                result["applied"] = True
                result["detail"] = f"Neustart erfolgreich: `{start_cmd}` → exit 0"
            else:
                result["detail"] = f"Neustart fehlgeschlagen: `{start_cmd}` → exit {r.returncode}: {r.stderr[:200]}"
        except Exception as e:
            result["detail"] = f"Neustart Exception: {e}"

    return result


def _w_script_path_fix(context: dict) -> dict:
    """Fix doppelte scripts/scripts/ Pfade im Jobs-JSON."""
    job_id = context.get("job_id", "")
    result = {"applied": False, "detail": ""}

    if not CRON_JOBS_FILE.exists():
        result["detail"] = "jobs.json nicht gefunden"
        return result

    try:
        with open(CRON_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        changed = False
        for job in data.get("jobs", []):
            if job.get("id") != job_id:
                continue
            script_field = job.get("script")
            if script_field and script_field.startswith("scripts/scripts/"):
                old = script_field
                job["script"] = script_field.replace("scripts/scripts/", "scripts/", 1)
                changed = True
                result["detail"] = f"Script-Pfad korrigiert: `{old}` → `{job['script']}`"
            # Auch Prompt-Feld checken
            prompt = job.get("prompt", "")
            if "scripts/scripts/" in prompt:
                old_prompt = prompt
                job["prompt"] = prompt.replace("scripts/scripts/", "scripts/", 1)
                changed = True
                result["detail"] += f" + Prompt-Pfad korrigiert"

        if changed:
            with open(CRON_JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            result["applied"] = True
            if not result["detail"]:
                result["detail"] = "jobs.json aktualisiert"

    except Exception as e:
        result["detail"] = f"jobs.json Patch fehlgeschlagen: {e}"

    return result


def _w_check_and_restart_stealth(context: dict) -> dict:
    """Spezieller Workaround für Stealth Browser Server."""
    result = {"applied": False, "detail": ""}
    stealth_script = SCRIPTS_DIR / "openamer-stealth.sh"

    if not stealth_script.exists():
        # Alternativ-Pfad
        stealth_script = HOME / "openamer-repo" / "scripts" / "openamer-stealth.sh"

    if not stealth_script.exists():
        result["detail"] = "openamer-stealth.sh nicht gefunden"
        return result

    try:
        r = subprocess.run(
            ["bash", str(stealth_script), "status"],
            capture_output=True, text=True, timeout=15
        )
        if "läuft" in r.stdout.lower() or "running" in r.stdout.lower():
            result["applied"] = True
            result["detail"] = "Stealth Server läuft bereits"
        else:
            r2 = subprocess.run(
                ["bash", str(stealth_script), "start"],
                capture_output=True, text=True, timeout=30
            )
            if r2.returncode == 0:
                result["applied"] = True
                result["detail"] = "Stealth Server neu gestartet"
            else:
                result["detail"] = f"Stealth Start fehlgeschlagen: exit {r2.returncode}"
    except Exception as e:
        result["detail"] = f"Stealth Check Exception: {e}"

    return result


WORKAROUNDS = [
    ("script_not_found", _w_script_path_fix,
     "Script-Pfade in jobs.json korrigieren (doppelte scripts/scripts/)"),
    ("script_not_found", _w_check_and_restart_stealth,
     "Stealth Browser Server prüfen und neu starten"),
    ("connection",       _w_pid_restart,
     "Prozess anhand PID prüfen oder neustarten"),
    ("exit_nonzero",     _w_pid_restart,
     "Prozess nach exit!=0 prüfen und neustarten"),
    ("killed",           _w_pid_restart,
     "Prozess nach Kill-Signal neustarten"),
    ("traceback",        _w_pid_restart,
     "Prozess nach Traceback neustarten"),
]


# ── Lern-Memory ─────────────────────────────────────────────────────────────

def load_memory() -> dict:
    """Lade oder initialisiere Lern-Memory."""
    SELF_HEALER_DIR.mkdir(parents=True, exist_ok=True)
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
    return {
        "version": 2,
        "patterns_seen": {},      # pattern_name -> count
        "patterns_learned": [],    # Liste von gelernten Mustern
        "workarounds_applied": [], # Historie der Workarounds
        "last_scan": None,
        "stats": {
            "total_scans": 0,
            "total_errors_found": 0,
            "total_healed": 0,
        },
    }


def save_memory(mem: dict):
    SELF_HEALER_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)


def learn_pattern(mem: dict, pattern_name: str, log_file: str, match_text: str):
    """Neues Muster lernen oder bestehendes verstärken."""
    mem["patterns_seen"][pattern_name] = mem["patterns_seen"].get(pattern_name, 0) + 1

    # Prüfen ob Pattern bereits gelernt
    existing = [p for p in mem["patterns_learned"] if p["pattern"] == pattern_name]
    if existing:
        existing[0]["count"] += 1
        existing[0]["last_seen"] = datetime.now(timezone.utc).isoformat()
        existing[0]["examples"].append({
            "file": log_file,
            "snippet": match_text[:300],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Max 10 Beispiele behalten
        if len(existing[0]["examples"]) > 10:
            existing[0]["examples"] = existing[0]["examples"][-10:]
    else:
        # Neues Pattern — wichtig für zukünftige Heilungen
        mem["patterns_learned"].append({
            "pattern": pattern_name,
            "count": 1,
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "severity": next((s for pn, _, s in ERROR_PATTERNS if pn.pattern == pattern_name or pn == pattern_name), 5),
            "examples": [{
                "file": log_file,
                "snippet": match_text[:300],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        })

    # Automatisch Workaround vorschlagen, wenn Pattern 3+ mal auftritt
    count = mem["patterns_seen"][pattern_name]
    if count >= 3:
        # Prüfen ob schon ein Workaround existiert
        has_wa = any(
            wa.get("for_pattern") == pattern_name
            for wa in mem["workarounds_applied"]
        )
        if not has_wa:
            mem["workarounds_applied"].append({
                "for_pattern": pattern_name,
                "suggested_workaround": "automatic_healing",
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "times_fired": 0,
            })


# ── Log-Scan ────────────────────────────────────────────────────────────────

def scan_cron_logs(mem: dict) -> list:
    """Scanne alle Cron-Output-Logs nach Fehler-Patterns."""
    errors = []
    log_dirs = []

    if CRON_OUTPUT_DIR.exists():
        log_dirs = [d for d in CRON_OUTPUT_DIR.iterdir() if d.is_dir()]

    if not log_dirs:
        # Fallback: per-Job-Scanner aus jobs.json
        return errors

    for job_dir in log_dirs:
        job_id = job_dir.name
        log_files = sorted(job_dir.glob("*.md"))

        # Nur die letzten N Logs scannen (Effizienz)
        for log_file in log_files[-20:]:
            try:
                text = log_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if not text.strip():
                continue

            for pattern_re, pname, severity in ERROR_PATTERNS:
                for match in pattern_re.finditer(text):
                    match_text = match.group().strip()
                    # Silent ist nur eine Info, kein Fehler
                    if pname == "silent":
                        continue

                    error_entry = {
                        "job_id": job_id,
                        "job_dir": str(job_dir),
                        "log_file": str(log_file),
                        "pattern": pname,
                        "severity": severity,
                        "match": match_text[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "full_text_snippet": text[:500],
                    }

                    # Prompt extrahieren (für Workarounds)
                    prompt_match = re.search(
                        r"## Prompt\s*\n(.*?)\n## Response",
                        text, re.DOTALL
                    )
                    if prompt_match:
                        error_entry["prompt"] = prompt_match.group(1).strip()

                    errors.append(error_entry)
                    learn_pattern(mem, pname, str(log_file), match_text)

    return errors


# ── Workaround-Engine ───────────────────────────────────────────────────────

def apply_workarounds(errors: list, mem: dict) -> list:
    """Versuche auf Fehler die passenden Workarounds anzuwenden."""
    healed = []

    for error in errors:
        for pattern_name, apply_fn, desc in WORKAROUNDS:
            if pattern_name == error["pattern"] or error["pattern"].startswith(pattern_name):
                context = {
                    "job_id": error.get("job_id", ""),
                    "job_dir": error.get("job_dir", ""),
                    "match_text": error.get("match", ""),
                    "full_text": error.get("full_text_snippet", ""),
                    "prompt": error.get("prompt", ""),
                    "log_file": error.get("log_file", ""),
                }
                try:
                    result = apply_fn(context)
                    if result.get("applied"):
                        healed.append({
                            "job_id": error["job_id"],
                            "pattern": error["pattern"],
                            "workaround": desc,
                            "detail": result.get("detail", ""),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        mem["workarounds_applied"].append({
                            "for_pattern": error["pattern"],
                            "suggested_workaround": desc,
                            "detail": result.get("detail", ""),
                            "triggered_at": datetime.now(timezone.utc).isoformat(),
                            "times_fired": mem.get("workarounds_applied", [{}])[-1].get("times_fired", 0) + 1,
                        })
                        mem["stats"]["total_healed"] += 1
                except Exception as e:
                    continue

    return healed


# ── Jobs-JSON Health Check ──────────────────────────────────────────────────

def check_jobs_json() -> list:
    """Prüfe jobs.json auf strukturelle Probleme."""
    issues = []
    if not CRON_JOBS_FILE.exists():
        return issues

    try:
        with open(CRON_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [{"type": "jobs_json_corrupt", "detail": str(e)}]

    for job in data.get("jobs", []):
        # Prüfe doppelte scripts/ paths
        script = job.get("script")
        if script and "scripts/scripts/" in script:
            issues.append({
                "type": "double_script_path",
                "job_id": job.get("id"),
                "job_name": job.get("name"),
                "detail": f"Script-Pfad enthält doppeltes scripts/: {script}",
            })
        # Prüfe script_exists
        if script and not script.startswith("scripts/"):
            # Absoluter Pfad?
            full_path = Path(script)
            if not full_path.exists() and not (SCRIPTS_DIR / script).exists():
                issues.append({
                    "type": "script_missing",
                    "job_id": job.get("id"),
                    "job_name": job.get("name"),
                    "detail": f"Script nicht gefunden: {script}",
                })

    return issues


# ── Report (JSON-Output) ────────────────────────────────────────────────────

def main():
    mem = load_memory()
    mem["stats"]["total_scans"] += 1

    scan_start = datetime.now(timezone.utc)

    # 1. Logs scannen
    errors = scan_cron_logs(mem)

    # 2. Jobs-JSON prüfen
    job_issues = check_jobs_json()
    for issue in job_issues:
        # Als error eintragen
        errors.append({
            "job_id": issue.get("job_id", "system"),
            "pattern": issue["type"],
            "severity": 8,
            "match": issue["detail"],
            "timestamp": scan_start.isoformat(),
            "full_text_snippet": issue["detail"],
        })
        learn_pattern(mem, issue["type"], str(CRON_JOBS_FILE), issue["detail"])

    # 3. Workarounds anwenden
    healed = apply_workarounds(errors, mem)

    mem["stats"]["total_errors_found"] += len(errors)
    mem["last_scan"] = scan_start.isoformat()
    save_memory(mem)

    # 4. JSON-Report
    report = {
        "self_healer_version": 2,
        "scan_timestamp": scan_start.isoformat(),
        "errors_found": len(errors),
        "auto_fixes_applied": len(healed),
        "learned_patterns": len(mem["patterns_seen"]),
        "total_scans": mem["stats"]["total_scans"],
        "total_errors_all_time": mem["stats"]["total_errors_found"],
        "total_healed_all_time": mem["stats"]["total_healed"],
        "errors": errors,
        "auto_fixes": healed,
        "learned_patterns_detail": [
            {"pattern": k, "count": v}
            for k, v in sorted(mem["patterns_seen"].items(), key=lambda x: -x[1])
        ],
        "memory_file": str(MEMORY_FILE),
        "cron_output_dir": str(CRON_OUTPUT_DIR),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Exit-Code
    if healed:
        sys.exit(2)
    elif errors:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()