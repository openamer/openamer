#!/usr/bin/env python3
"""
Smart Cron Scheduler — Job-Analyse + System-Auslastung + optimierte Schedules.

Analysiert alle Cron-Jobs in OpenAmer Home, misst die Systemauslastung,
klassifiziert Jobs nach Priorität und schlägt optimierte Zeitpläne vor.

CLI:
  python smart-cron-scheduler.py              # dry-run (Vorschläge)
  python smart-cron-scheduler.py --dry-run    # explizit dry-run
  python smart-cron-scheduler.py --apply      # Änderungen umsetzen
  python smart-cron-scheduler.py --json       # Roh-Ausgabe als JSON
  python smart-cron-scheduler.py --verbose    # ausführliche Logs
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────
# Pfade & Konstanten
# ──────────────────────────────────────────────────────────────────────

OPENAMER_HOME = Path(os.environ.get(
    "LOCALAPPDATA",
    str(Path.home() / "AppData/Local"),
)) / "openamer-laptop"

JOBS_PATH = OPENAMER_HOME / "cron" / "jobs.json"

# Prioritäten je Job-Name (Substring-Matching)
JOB_PRIORITIES: List[Tuple[str, str]] = [
    # Kritisch — Sicherheit, Datenintegrität
    ("security",      "critical"),
    ("vulnerability", "critical"),
    ("self-reflection","high"),
    ("memory-healing", "high"),
    ("brain-collect",  "high"),
    # Hoch — aktive Entwicklung
    ("auto-test",     "high"),
    ("test-runner",   "high"),
    ("pr agent",      "high"),
    ("pr_approval",   "high"),
    ("bugbot",        "high"),
    # Mittel — Wartung
    ("self-healer",   "medium"),
    ("stealth",       "medium"),
    ("hub cache",     "medium"),
    ("cache warmer",  "medium"),
    ("deepseek",      "medium"),
    # Niedrig — Analyse, Berichte
    ("skill-knowledge","low"),
    ("perf-optimizer","low"),
    ("knowledge-graph","low"),
]

# Optimierte Basis-Schedules (in Minuten) je Priorität
PRIORITY_INTERVALS: Dict[str, int] = {
    "critical": 240,   # alle 4h (Sicherheit)
    "high":     240,   # alle 4h (Analyse, Tests)
    "medium":   360,   # alle 6h (Wartung)
    "low":      1440,  # täglich (Berichte, Wissen)
}

# Spezielle Job-Ausnahmen — override für bestimmte Job-IDs oder -Namen
# (job_id oder job_name -> (min_interval, max_interval))
# Match muss exakt oder als Wortgrenze sein, nicht per Substring!
JOB_INTERVAL_OVERRIDES: Dict[str, Tuple[int, int]] = {
    # Watchdog/Hearbeat — müssen häufig laufen
    "stealth browser":   (15, 15),    # Stealth Browser Watchdog — fix 15min
    "self-healer": (30, 60),  # Self-Healer — 30-60min
    # Session-Erfassung
    "brain-collect": (120, 240),  # 2-4h
    # System-Gesundheit
    "memory-healing": (120, 360), # 2-6h
}

# Quiet Hours: Niedrige Prio zwischen 02:00-06:00 UTC (nutzerdefinierte Schlafenszeit)
QUIET_HOURS_START = 2   # 02:00
QUIET_HOURS_END   = 6   # 06:00

# Jobs, die NIEMALS in Quiet Hours verschoben werden dürfen
KEEP_AWAKE_JOBS = [
    "stealth", "self-healer",
]


# ──────────────────────────────────────────────────────────────────────
# System Auslastung messen (Windows)
# ──────────────────────────────────────────────────────────────────────

def get_cpu_usage() -> float:
    """Gibt aktuelle CPU-Auslastung in % zurück (0-100). Nutzt PowerShell."""
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if output:
            return float(output)
    except Exception as e:
        sys.stderr.write(f"[WARN] CPU-Messung fehlgeschlagen: {e}\n")
        try:
            # Fallback: wmic direkt (Sysnative für Git-Bash)
            for wmic_path in [
                r"C:\Windows\System32\wbem\wmic.exe",
                r"C:\Windows\Sysnative\wbem\wmic.exe",
            ]:
                if os.path.exists(wmic_path):
                    result = subprocess.run(
                        [wmic_path, "cpu", "get", "loadpercentage", "/format:csv"],
                        capture_output=True, text=True, timeout=10,
                    )
                    for line in result.stdout.strip().splitlines():
                        parts = line.split(",")
                        if len(parts) >= 2 and parts[-1].strip().isdigit():
                            return float(parts[-1].strip())
        except Exception:
            pass
    return 0.0


def get_memory_usage() -> Tuple[float, float, float]:
    """
    Gibt (free_mb, total_mb, usage_percent) zurück.
    Nutzt PowerShell für Kompatibilität.
    """
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "$os=Get-CimInstance Win32_OperatingSystem; "
            "$free=[math]::Round($os.FreePhysicalMemory/1024,1); "
            "$total=[math]::Round($os.TotalVisibleMemorySize/1024,1); "
            "$used=[math]::Round(($total-$free)/$total*100,1); "
            "Write-Output \"$free,$total,$used\""
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if output and "," in output:
            parts = output.split(",")
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception as e:
        sys.stderr.write(f"[WARN] RAM-Messung fehlgeschlagen: {e}\n")
    return 0.0, 0.0, 0.0


def get_disk_usage(path: str = "C:") -> Tuple[float, float, float]:
    """Gibt (free_gb, total_gb, usage_percent) zurück."""
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='{path}'\"; "
            f"$free=[math]::Round($d.FreeSpace/1GB,1); "
            f"$total=[math]::Round($d.Size/1GB,1); "
            f"$used=[math]::Round(($d.Size-$d.FreeSpace)/$d.Size*100,1); "
            "Write-Output \"$free,$total,$used\""
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if output and "," in output:
            parts = output.split(",")
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception as e:
        sys.stderr.write(f"[WARN] Disk-Messung fehlgeschlagen: {e}\n")
    return 0.0, 0.0, 0.0


def get_system_load() -> Dict[str, Any]:
    """Sammelt alle System-Metriken und klassifiziert die Auslastung."""
    cpu = get_cpu_usage()
    free_ram, total_ram, ram_used = get_memory_usage()
    free_disk, total_disk, disk_used = get_disk_usage()

    # Last-Level
    if cpu < 30 and ram_used < 60 and disk_used < 80:
        level = "low"
    elif cpu < 60 and ram_used < 80:
        level = "medium"
    else:
        level = "high"

    # Ist es gerade Nacht / Quiet Time?
    now = datetime.now(timezone.utc)
    is_quiet = QUIET_HOURS_START <= now.hour < QUIET_HOURS_END

    return {
        "cpu_percent": round(cpu, 1),
        "ram_free_mb": round(free_ram, 1),
        "ram_total_mb": round(total_ram, 1),
        "ram_used_percent": round(ram_used, 1),
        "disk_free_gb": round(free_disk, 1),
        "disk_total_gb": round(total_disk, 1),
        "disk_used_percent": round(disk_used, 1),
        "load_level": level,
        "is_quiet_hours": is_quiet,
        "current_hour_utc": now.hour,
        "measured_at": now.isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# Jobs lesen & analysieren
# ──────────────────────────────────────────────────────────────────────

def read_jobs() -> List[Dict[str, Any]]:
    """Liest die jobs.json und gibt die Job-Liste zurück."""
    if not JOBS_PATH.exists():
        sys.stderr.write(f"[ERROR] jobs.json nicht gefunden: {JOBS_PATH}\n")
        sys.exit(1)

    with open(JOBS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("jobs", [])


def classify_priority(name: str) -> str:
    """Klassifiziert einen Job anhand seines Namens."""
    for pattern, priority in JOB_PRIORITIES:
        if pattern.lower() in name.lower():
            return priority
    return "medium"  # default


def parse_schedule_minutes(schedule: Dict[str, Any]) -> Optional[int]:
    """
    Extrahiert das Intervall in Minuten aus dem Schedule-Objekt.
    Gibt None zurück, wenn kein klares Intervall vorliegt (z.B. Cron-Expression).
    """
    kind = schedule.get("kind", "")
    if kind == "interval":
        return schedule.get("minutes")
    elif kind == "cron":
        expr = schedule.get("expr", "")
        # Einfaches Parsen: "0 */6 * * *" → 360 Minuten, "0 2 * * *" → einmal täglich
        parts = expr.strip().split()
        if len(parts) == 5:
            # */N im Stundenfeld
            if parts[1].startswith("*/"):
                try:
                    return int(parts[1][2:]) * 60
                except ValueError:
                    pass
            # */N im Minutenfeld (selten)
            if parts[0].startswith("*/"):
                try:
                    return int(parts[0][2:])
                except ValueError:
                    pass
        # Für Cron-Expressions ohne */N (fest) geben wir None zurück
        return None
    return None


def get_next_quiet_window() -> str:
    """Gibt die nächste Quiet-Window-Zeit als ISO-String zurück."""
    now = datetime.now(timezone.utc)
    target_hour = QUIET_HOURS_START

    if now.hour < QUIET_HOURS_START:
        # Heute Nacht
        next_quiet = now.replace(hour=QUIET_HOURS_START, minute=0, second=0, microsecond=0)
    elif now.hour < QUIET_HOURS_END:
        # Bereits in Quiet Hours — nächstes Fenster ist jetzt
        return now.isoformat()
    else:
        # Morgen früh
        next_quiet = (now + timedelta(days=1)).replace(
            hour=QUIET_HOURS_START, minute=0, second=0, microsecond=0
        )

    return next_quiet.isoformat()


def minutes_until(target_hour_utc: int) -> int:
    """Gibt Minuten bis zur nächsten vollen Stunde target_hour_utc zurück."""
    now = datetime.now(timezone.utc)
    current = now.hour * 60 + now.minute
    target = target_hour_utc * 60
    if current < target:
        return target - current
    else:
        return (24 * 60) - current + target


def analyze_job(job: Dict[str, Any], system_load: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analysiert einen einzelnen Job und erzeugt ggf. einen Optimierungsvorschlag.
    """
    job_id = job.get("id", "")
    job_name = job.get("name", "unnamed")
    enabled = job.get("enabled", True)

    if not enabled:
        return None

    schedule = job.get("schedule", {})
    priority = classify_priority(job_name)
    interval_min = parse_schedule_minutes(schedule)

    if interval_min is None:
        return None  # Kann Intervall nicht bestimmen → kein Vorschlag

    display = schedule.get("display", f"every {interval_min}m")
    system_load_level = system_load["load_level"]
    is_quiet = system_load["is_quiet_hours"]

    current_schedule = display
    proposed_schedule = None
    reason = None

    # ── Check auf Job-Override (Wortgrenzen, nicht Substring!) ──
    override_min = None
    override_max = None
    job_lower = job_name.lower()
    for pattern, (lo, hi) in JOB_INTERVAL_OVERRIDES.items():
        pattern_lower = pattern.lower()
        # Exakte ID-Übereinstimmung
        if pattern_lower == job_id.lower():
            override_min, override_max = lo, hi
            break
        # Wort-weise Übereinstimmung (z. B. "self-healer" matcht "self-healer" aber nicht "self-reflection")
        if pattern_lower in job_lower:
            # Prüfe ob es ein ganzes Wort oder ein Getrennter Begriff ist:
            # Ersetze Trennzeichen durch Leerzeichen und prüfe Wort für Wort
            job_words = set(job_lower.replace("-", " ").replace("_", " ").split())
            pattern_words = set(pattern_lower.replace("-", " ").replace("_", " ").split())
            if pattern_words.issubset(job_words):
                override_min, override_max = lo, hi
                break

    # Optimales Intervall bestimmen: Override > Priority
    if override_min is not None and override_max is not None:
        optimal_min = override_min
        optimal_interval = override_max
    else:
        optimal_min = 15  # Minimum Default
        optimal_interval = PRIORITY_INTERVALS.get(priority, 720)

    # ── 1) Watchdog-Job (< 15min) → immer behalten ──
    if interval_min < 15:
        return None

    # ── 2) Watchdog/Override: Intervall fix ──
    if override_min is not None and override_min == override_max:
        # Fixer Wert — nur vorschlagen wenn abweichend
        if interval_min != override_max:
            proposed_schedule = f"every {override_max}m"
            reason = (
                f"Watchdog-Job muss alle {override_max}m laufen. "
                f"Aktuell: alle {interval_min}m. Systemlast: {system_load_level}"
            )
        # Ansonsten nichts tun
        if proposed_schedule is None:
            return None

    # ── 3) Job läuft zu oft (Intervall < Optimal) ──
    elif interval_min < optimal_interval:
        # Nur vorschlagen wenn mindestens 30% Unterschied oder ≥30min Differenz
        diff = optimal_interval - interval_min
        if diff >= 30:
            # Prüfen ob Quiet-Verschiebung sinnvoll
            move_to_quiet = (
                priority == "low"
                and not any(kw.lower() in job_name.lower() for kw in KEEP_AWAKE_JOBS)
            )

            if move_to_quiet and not is_quiet:
                proposed_schedule = f"every {optimal_interval}m"
                reason = (
                    f"Niedrige Prio läuft alle {interval_min}m → "
                    f"{optimal_interval // 60}h in Quiet Hours reicht. "
                    f"Systemlast: {system_load_level}"
                )
            else:
                proposed_schedule = f"every {optimal_interval}m"
                # Detaillierte Begründung
                savings = interval_min - optimal_interval if interval_min < optimal_interval else interval_min
                reason = (
                    f"Job läuft alle {interval_min}m, "
                    f"Prio {priority} → {optimal_interval // 60}h-Intervall optimal. "
                    f"Systemlast: {system_load_level}"
                )

    # ── 4) Job läuft zu selten (für kritische/hohe/override) ──
    elif interval_min > optimal_interval:
        proposed_schedule = f"every {optimal_interval}m"
        reason = (
            f"Job ({priority}) läuft nur alle {interval_min}m → "
            f"öfter ({optimal_interval // 60}h) empfohlen. "
            f"Systemlast: {system_load_level}"
        )

    if proposed_schedule is None:
        return None

    # Normalisiere auf "every Nm" Format für openamer cron edit
    mins_str = proposed_schedule.replace("every ", "").replace("m", "").strip()
    try:
        mins = int(mins_str.split("~")[0].strip())
    except ValueError:
        mins = optimal_interval
    cron_schedule = f"every {mins}m"

    return {
        "job_id": job_id,
        "job_name": job_name,
        "priority": priority,
        "current_schedule": current_schedule,
        "current_interval_min": interval_min,
        "proposed_schedule": proposed_schedule,
        "proposed_interval_min": parse_schedule_minutes(
            {"kind": "interval", "minutes": optimal_interval}
        ),
        "reason": reason,
        "cron_edit_schedule": cron_schedule,
    }


def analyze_all_jobs(system_load: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analysiert alle Jobs und gibt Optimierungsvorschläge zurück."""
    jobs = read_jobs()
    suggestions = []

    for job in jobs:
        suggestion = analyze_job(job, system_load)
        if suggestion:
            suggestions.append(suggestion)

    return suggestions


# ──────────────────────────────────────────────────────────────────────
# Apply-Modus — Änderungen via CLI umsetzen
# ──────────────────────────────────────────────────────────────────────

def apply_suggestion(suggestion: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """
    Wendet einen Optimierungsvorschlag via 'openamer cron edit' an.
    """
    job_id = suggestion["job_id"]
    new_schedule = suggestion["cron_edit_schedule"]

    if verbose:
        print(f"  → openamer cron edit {job_id} --schedule \"{new_schedule}\"")

    try:
        result = subprocess.run(
            ["openamer", "cron", "edit", job_id, "--schedule", new_schedule],
            capture_output=True, text=True, timeout=30,
        )
        success = result.returncode == 0
        return {
            "job_id": job_id,
            "job_name": suggestion["job_name"],
            "applied": success,
            "schedule": new_schedule,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "job_id": job_id,
            "job_name": suggestion["job_name"],
            "applied": False,
            "schedule": new_schedule,
            "stdout": "",
            "stderr": "Timeout (30s)",
        }
    except FileNotFoundError:
        return {
            "job_id": job_id,
            "job_name": suggestion["job_name"],
            "applied": False,
            "schedule": new_schedule,
            "stdout": "",
            "stderr": "openamer CLI nicht gefunden",
        }


# ──────────────────────────────────────────────────────────────────────
# Hauptprogramm
# ──────────────────────────────────────────────────────────────────────

def build_report(
    system_load: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    apply_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Baut den vollständigen Report als Dict."""
    total_jobs = len(read_jobs())
    now = datetime.now(timezone.utc)

    return {
        "generated_at": now.isoformat(),
        "timestamp_epoch": int(now.timestamp()),
        "summary": {
            "total_jobs": total_jobs,
            "analyzed_jobs": total_jobs,
            "suggestions_count": len(suggestions),
        },
        "system_load": system_load,
        "suggestions": suggestions,
        "apply_results": apply_results or [],
    }


def print_report(report: Dict[str, Any], verbose: bool = False):
    """Gibt den Report formatiert auf der Konsole aus."""
    load = report["system_load"]
    summary = report["summary"]
    suggestions = report["suggestions"]
    apply_results = report.get("apply_results", [])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "─" * 62

    print(f"\n{'=' * 62}")
    print(f"  Smart Cron Scheduler — Report v1.0")
    print(f"  {now_str}")
    print(f"{'=' * 62}")

    # ── System-Auslastung ──
    print(f"\n  ┌─ System Auslastung {'─' * 42}┐")
    print(f"  │ CPU:    {load['cpu_percent']:>5.1f} %{'':>30}│")
    print(f"  │ RAM:    {load['ram_used_percent']:>5.1f} % ({load['ram_free_mb']:>6.0f} MB frei v. {load['ram_total_mb']:>6.0f} MB){'':>6}│")
    print(f"  │ Disk:   {load['disk_used_percent']:>5.1f} % ({load['disk_free_gb']:>6.1f} GB frei v. {load['disk_total_gb']:>6.1f} GB){'':>6}│")
    print(f"  │ Last:   {load['load_level']:>5}{'':>34}│")
    print(f"  │ Uhr:    UTC {load['current_hour_utc']:>2d}:00 {'🔕 Quiet Hours' if load['is_quiet_hours'] else '🌞'}{'':>28}│")
    print(f"  └{'─' * 58}┘")

    # ── Job-Übersicht ──
    print(f"\n  ┌─ Job-Übersicht {'─' * 44}┐")
    print(f"  │ Total: {summary['total_jobs']:>3} Jobs  |  "
          f"Optimierungsvorschläge: {summary['suggestions_count']:>3}     │")
    print(f"  └{'─' * 58}┘")

    # ── Vorschläge ──
    if suggestions:
        print(f"\n  {'─' * 58}")
        print(f"  Optimierungsvorschläge:")
        print(f"  {'─' * 58}\n")
        for i, s in enumerate(suggestions, 1):
            prio_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            icon = prio_icon.get(s["priority"], "⚪")
            print(f"  {icon} [{i:02d}] {s['job_name']}")
            print(f"       ID:    {s['job_id']}")
            print(f"       Prio:  {s['priority']}")
            print(f"       Aktuell:  {s['current_schedule']}")
            print(f"       Vorschlag: {s['proposed_schedule']}")
            print(f"       Grund: {s['reason']}")
            print()
    else:
        print(f"\n  ✅ Keine Optimierungsvorschläge — alle Jobs laufen optimal.\n")

    # ── Apply-Ergebnisse ──
    if apply_results:
        print(f"  {'─' * 58}")
        print(f"  Apply-Ergebnisse:")
        print(f"  {'─' * 58}\n")
        succeeded = sum(1 for r in apply_results if r.get("applied"))
        failed = sum(1 for r in apply_results if not r.get("applied"))
        print(f"  ✅ Erfolgreich: {succeeded}  |  ❌ Fehlgeschlagen: {failed}\n")
        for r in apply_results:
            status = "✅" if r.get("applied") else "❌"
            print(f"  {status} {r['job_name']} ({r['job_id']})")
            if verbose and r.get("stdout"):
                print(f"       → {r['stdout']}")
            if verbose and r.get("stderr"):
                print(f"       ! {r['stderr']}")
        print()

    print(f"{'=' * 62}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Smart Cron Scheduler — Job-Optimierung mit Systemauslastung",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur Vorschläge anzeigen (default)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Optimierte Schedules via 'openamer cron edit' umsetzen",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Ausgabe als JSON (für programmatische Nutzung)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Ausführliche Ausgabe",
    )
    args = parser.parse_args()

    # ── System-Auslastung messen ──
    if args.verbose:
        print("[INFO] Messe System-Auslastung...")

    system_load = get_system_load()

    if args.verbose:
        print(f"[INFO] CPU: {system_load['cpu_percent']}% | "
              f"RAM: {system_load['ram_used_percent']:.0f}% | "
              f"Last-Level: {system_load['load_level']}")

    # ── Jobs analysieren ──
    if args.verbose:
        print("[INFO] Analysiere Cron-Jobs...")

    suggestions = analyze_all_jobs(system_load)

    # ── Apply oder dry-run ──
    apply_results = None
    if args.apply:
        if args.verbose:
            print(f"[INFO] Apply-Modus: Setze {len(suggestions)} Vorschläge um...\n")

        apply_results = []
        for s in suggestions:
            result = apply_suggestion(s, verbose=args.verbose)
            apply_results.append(result)
            if not args.verbose:
                icon = "✅" if result.get("applied") else "❌"
                print(f"  {icon} {s['job_name']}: {s['current_schedule']} → {s['proposed_schedule']}")
    else:
        if args.verbose:
            print("[INFO] Dry-Run-Modus (--apply zum Umsetzen)")

    # ── Report bauen ──
    report = build_report(system_load, suggestions, apply_results)

    # ── Ausgabe ──
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report, verbose=args.verbose)


if __name__ == "__main__":
    main()