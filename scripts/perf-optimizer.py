#!/usr/bin/env python3
"""
KI-Performance-Optimizer — RAM/Disk/Cron-Monitoring + Optimierungsvorschläge
=============================================================================
Produktionsreifes Monitoring-Skript für OpenAmer auf Windows (Git-Bash/MSYS2).

Funktionen:
  1. RAM-Monitoring  — Auslastung, Top-Verbraucher, Pagefile
  2. Disk-Monitoring  — Speicher, Temp-Dateien, System-Cache
  3. Cron-Timing      — Cron-Job-Laufzeiten, Engpässe
  4. Optimierungen    — Vorschläge + Auto-Cleanup (Temp, Logs, Cache)

Ausgabe: Strukturiertes JSON (stdout) + optionaler Alarm bei Problemen.
"""

import gc
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Konfiguration ────────────────────────────────────────────────────────────

HOME = Path(os.path.expanduser("~"))
OPENAMER_HOME = Path(
    os.environ.get(
        "OPENAMER_HOME",
        str(HOME / "AppData" / "Local" / "openamer-laptop"),
    )
)
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
CRON_DIR = OPENAMER_HOME / "cron"
LOG_DIR = OPENAMER_HOME / "logs"
TEMP_THRESHOLD_MB = 500   # Warnung wenn Temp > 500 MB
RAM_WARN_PCT = 85         # Warnung wenn RAM > 85%
DISK_WARN_PCT = 90        # Warnung wenn Disk > 90%
# Globaler Timeout: max 25s für den gesamten Lauf
_SCRIPT_START = time.time()
_GLOBAL_TIMEOUT_S = 25


def _check_timeout():
    """Prüft ob das globale Zeitlimit erreicht ist."""
    if time.time() - _SCRIPT_START > _GLOBAL_TIMEOUT_S:
        raise RuntimeError(f"Global timeout ({_GLOBAL_TIMEOUT_S}s) reached")


def _shell_escape(s):
    """Einfaches Shell-Escaping für Bash-Aufrufe unter Windows."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _run(cmd, timeout=10, use_bash=False):
    """Führt Shell-Befehl aus, robust gegen Encoding-Probleme."""
    _check_timeout()
    if use_bash:
        cmd = f'bash -c {_shell_escape(cmd)}'
    try:
        # binary mode + manuelles Decoding mit Fallback
        r = subprocess.run(
            cmd, shell=True, capture_output=True, timeout=timeout
        )
        for enc in ("utf-8", "cp1252", "cp850", "latin-1"):
            try:
                out = r.stdout.decode(enc, errors="strict").strip()
                err = r.stderr.decode(enc, errors="strict").strip()
                return out, err, r.returncode
            except (UnicodeDecodeError, LookupError):
                continue
        # Fallback: replace errors
        out = r.stdout.decode("utf-8", errors="replace").strip()
        err = r.stderr.decode("utf-8", errors="replace").strip()
        return out, err, r.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT ({timeout}s)", -1
    except Exception as e:
        return "", str(e), -1


def _to_mb(val_str):
    """Konvertiert '1024 KB' oder '1.5 GB' zu MB."""
    val_str = val_str.strip().upper().replace(",", "").replace(".", ".")
    m = re.match(r"([\d.]+)\s*(MB|GB|KB|B)?", val_str)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2) or "B"
    if unit == "GB":
        return num * 1024
    elif unit == "KB":
        return num / 1024
    elif unit == "B":
        return num / (1024 * 1024)
    return num  # MB


def _size_str(mb):
    """Gibt MB-Wert hübsch formatiert aus."""
    if mb >= 1024:
        return f"{mb/1024:.1f} GB"
    return f"{mb:.0f} MB"


def _dir_size_mb_fast(path, max_depth=2):
    """Schnelle Verzeichnisgrößen-Schätzung (nicht rekursiv bei großen Bäumen)."""
    _check_timeout()
    try:
        p = Path(path)
        if not p.exists():
            return -1

        total = 0
        try:
            # Nur eine Ebene tief für Temp/Cache — ausreichend für Bewertung
            for entry in os.scandir(str(p)):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
        except PermissionError:
            return -1

        return total / (1024 * 1024)
    except Exception:
        return -1


# ── RAM-Monitoring ──────────────────────────────────────────────────────────

def check_ram():
    """Ermittelt RAM-Auslastung und Top-Prozesse."""
    _check_timeout()
    result = {
        "total_mb": 0, "used_mb": 0, "free_mb": 0,
        "usage_pct": 0, "pagefile_total_mb": 0, "pagefile_used_mb": 0,
        "top_processes": [], "status": "ok",
    }

    # WMIC RAM
    out, _, _ = _run('wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv 2>nul')
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Node"):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                total_kb = int(parts[-2].strip())
                free_kb = int(parts[-1].strip())
                result["total_mb"] = round(total_kb / 1024, 1)
                result["free_mb"] = round(free_kb / 1024, 1)
                result["used_mb"] = round(result["total_mb"] - result["free_mb"], 1)
                result["usage_pct"] = round(
                    (result["used_mb"] / result["total_mb"]) * 100, 1
                ) if result["total_mb"] > 0 else 0
            except (ValueError, IndexError):
                pass

    # WMIC Pagefile
    out3, _, _ = _run('wmic OS get TotalVirtualMemorySize,FreeVirtualMemory /format:csv 2>nul')
    for line in out3.splitlines():
        line = line.strip()
        if not line or line.startswith("Node"):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                pf_total_kb = int(parts[-2].strip())
                pf_free_kb = int(parts[-1].strip())
                result["pagefile_total_mb"] = round(pf_total_kb / 1024, 1)
                result["pagefile_used_mb"] = round(
                    (pf_total_kb - pf_free_kb) / 1024, 1
                )
            except (ValueError, IndexError):
                pass

    # Top-Prozesse (PowerShell, encoding-sicher)
    out2, _, _ = _run(
        'powershell -NoProfile -Command "'
        'Get-Process | Sort-Object WorkingSet64 -Descending | '
        'Select-Object -First 10 Name,Id,@{N=\'WS_MB\';E={[math]::Round($_.WorkingSet64/1MB,1)}} | '
        'ConvertTo-Csv -NoTypeInformation" 2>nul',
        timeout=8,
    )
    procs = []
    for line in out2.splitlines():
        line = line.strip()
        if not line or line.startswith('"Name"'):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                name = parts[0].strip('"')
                pid = parts[1].strip('"')
                ws_mb = float(parts[2].strip('"'))
                procs.append({"name": name, "pid": pid, "mem_mb": ws_mb})
            except (ValueError, IndexError):
                pass

    result["top_processes"] = procs[:10]

    # Status
    if result["usage_pct"] >= RAM_WARN_PCT:
        result["status"] = "critical"
    elif result["usage_pct"] >= RAM_WARN_PCT - 10:
        result["status"] = "warning"

    return result


# ── Disk-Monitoring ─────────────────────────────────────────────────────────

def check_disk():
    """Analysiert Speicherplatz und Temp-Dateien."""
    _check_timeout()
    result = {"drives": [], "temp_analysis": {}, "cache_analysis": {}, "status": "ok"}

    # Laufwerke via PowerShell
    out, _, _ = _run(
        'powershell -NoProfile -Command "'
        'Get-CimInstance Win32_LogicalDisk -Filter DriveType=3 | '
        'Select-Object DeviceID,Size,FreeSpace | '
        'ConvertTo-Csv -NoTypeInformation"',
        timeout=5,
    )
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith('"DeviceID"'):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                drive = parts[0].strip('"')
                total_b = int(float(parts[1].strip('"')))
                free_b = int(float(parts[2].strip('"')))
                used_b = total_b - free_b
                used_pct = round((used_b / total_b) * 100, 1) if total_b > 0 else 0
                result["drives"].append({
                    "drive": drive,
                    "total_gb": round(total_b / (1024**3), 1),
                    "used_gb": round(used_b / (1024**3), 1),
                    "free_gb": round(free_b / (1024**3), 1),
                    "used_pct": used_pct,
                })
            except (ValueError, IndexError):
                pass

    # Temp-Analyse (schnell: scandir, nur flache Größe)
    temp_paths = {}
    windows_temp = Path("C:\\Windows\\Temp")
    if windows_temp.exists():
        temp_paths["Windows Temp"] = windows_temp
    user_temp = HOME / "AppData" / "Local" / "Temp"
    if user_temp.exists():
        temp_paths["User Temp"] = user_temp
    if LOG_DIR.exists():
        temp_paths["OpenAmer Logs"] = LOG_DIR

    temp_total = 0
    for label, p in temp_paths.items():
        if p.exists():
            mb = _dir_size_mb_fast(str(p), max_depth=1)
            if mb >= 0:
                result["temp_analysis"][label] = {
                    "path": str(p),
                    "size_mb": round(mb, 1),
                    "size_str": _size_str(mb),
                    "cleanable": mb > 10,
                }
                temp_total += mb

    result["temp_analysis"]["_total_mb"] = round(temp_total, 1)
    result["temp_analysis"]["_total_str"] = _size_str(temp_total)

    # Status
    for d in result["drives"]:
        if d["used_pct"] >= DISK_WARN_PCT:
            result["status"] = "critical"
        elif d["used_pct"] >= DISK_WARN_PCT - 10 and result["status"] != "critical":
            result["status"] = "warning"

    return result


# ── Cron-Timing ──────────────────────────────────────────────────────────────

def check_cron_timing():
    """Analysiert Cron-Jobs: Laufzeiten, Exit-Codes, Engpässe."""
    _check_timeout()
    result = {
        "cron_jobs": [], "total_cron_jobs": 0,
        "slow_jobs": [], "failed_jobs": [], "status": "ok",
    }

    if not CRON_DIR.exists():
        result["status"] = "no_data"
        return result

    for cron_file in sorted(CRON_DIR.iterdir()):
        if cron_file.suffix in (".log", ".json", ".txt"):
            try:
                mtime = cron_file.stat().st_mtime
                age_h = (time.time() - mtime) / 3600
                size_kb = cron_file.stat().st_size / 1024

                job_info = {
                    "name": cron_file.stem,
                    "path": str(cron_file),
                    "size_kb": round(size_kb, 1),
                    "age_hours": round(age_h, 1),
                }

                # Nur lesen wenn klein genug
                if size_kb < 100:
                    content = cron_file.read_text(encoding="utf-8", errors="replace")
                    job_info["has_error"] = "error" in content.lower() or "traceback" in content.lower()
                    job_info["has_exception"] = "exception" in content.lower()

                    for line in content.strip().splitlines()[-5:]:
                        m = re.search(r"exit.code[:\s]+(\d+)", line, re.IGNORECASE)
                        if m:
                            job_info["last_exit_code"] = int(m.group(1))
                            break

                result["cron_jobs"].append(job_info)

                if job_info.get("last_exit_code", 0) != 0 and job_info.get("last_exit_code") is not None:
                    result["failed_jobs"].append(job_info)
                if age_h > 26:
                    result["slow_jobs"].append(job_info)

            except Exception:
                continue

    result["total_cron_jobs"] = len(result["cron_jobs"])
    if result["failed_jobs"]:
        result["status"] = "warning"
    if result["slow_jobs"]:
        for s in result["slow_jobs"]:
            s["_warn"] = f"Job '{s['name']}' seit {s['age_hours']}h unverändert"

    return result


# ── Optimierungsvorschläge ───────────────────────────────────────────────────

def generate_optimizations(ram_data, disk_data, cron_data):
    """Generiert Optimierungsvorschläge basierend auf den Messdaten."""
    suggestions = []
    auto_actions = []

    # RAM
    if ram_data["usage_pct"] > 80:
        suggestions.append({
            "category": "ram",
            "severity": "high" if ram_data["usage_pct"] > RAM_WARN_PCT else "medium",
            "title": "Hohe RAM-Auslastung",
            "detail": f"{ram_data['usage_pct']}% RAM belegt ({_size_str(ram_data['used_mb'])} / {_size_str(ram_data['total_mb'])})",
            "actions": [
                "Nicht benötigte Programme schließen",
                "Browser-Tabs reduzieren",
                "RAM-Limit für OpenAmer prüfen: openamer config set max_memory <MB>",
                "Python-Garbage-Collection forcieren",
            ],
        })

    if ram_data["top_processes"]:
        top_ram = ram_data["top_processes"][0]
        if top_ram["mem_mb"] > 2000:
            suggestions.append({
                "category": "ram",
                "severity": "medium",
                "title": f"Speicherfresser: {top_ram['name']}",
                "detail": f"{top_ram['name']} (PID {top_ram['pid']}) verbraucht {_size_str(top_ram['mem_mb'])} RAM",
                "actions": [
                    f"Prozess prüfen: Get-Process -Id {top_ram['pid']}",
                    "Falls unbekannt: Stop-Process -Id <PID> -Force",
                ],
            })

    # Disk
    for d in disk_data.get("drives", []):
        if d["used_pct"] > 85:
            suggestions.append({
                "category": "disk",
                "severity": "high" if d["used_pct"] > DISK_WARN_PCT else "medium",
                "title": f"Laufwerk {d['drive']} fast voll",
                "detail": f"{d['used_pct']}% belegt ({d['used_gb']} GB / {d['total_gb']} GB)",
                "actions": [
                    "Datenträgerbereinigung: cleanmgr.exe",
                    "Alte Downloads löschen",
                    "Papierkorb leeren: rd /s /q %systemdrive%\\$Recycle.Bin",
                ],
            })

    # Temp
    ta = disk_data.get("temp_analysis", {})
    temp_total = ta.get("_total_mb", 0)
    if temp_total > TEMP_THRESHOLD_MB:
        items = []
        for k, v in ta.items():
            if k.startswith("_"):
                continue
            if v.get("cleanable"):
                items.append(f"{k}: {v['size_str']}")
        suggestions.append({
            "category": "temp",
            "severity": "medium",
            "title": f"Temp-Dateien: {ta.get('_total_str', '?')}",
            "detail": " | ".join(items),
            "actions": [
                "Automatische Bereinigung ausführen (s.u.)",
                "Manuell: %TEMP% leeren",
            ],
        })
        auto_actions.append({
            "action": "temp_cleanup",
            "detail": "Temporäre Dateien bereinigen",
        })

    # Cron
    if cron_data.get("status") == "warning":
        if cron_data.get("failed_jobs"):
            names = [j["name"] for j in cron_data["failed_jobs"]]
            suggestions.append({
                "category": "cron",
                "severity": "high",
                "title": "Cron-Jobs mit Fehlern",
                "detail": f"Fehlgeschlagen: {', '.join(names)}",
                "actions": [
                    "Logs prüfen: openamer cron log <job>",
                    "Job neu starten: openamer cron run <job>",
                ],
            })
        if cron_data.get("slow_jobs"):
            for j in cron_data["slow_jobs"]:
                suggestions.append({
                    "category": "cron",
                    "severity": "low",
                    "title": f"Cron-Job '{j['name']}' hängt?",
                    "detail": j.get("_warn", f"Seit {j['age_hours']}h ohne Änderung"),
                    "actions": [
                        f"Log prüfen: cat '{j['path']}'",
                        "Cron-Timing optimieren oder Job parallelisieren",
                    ],
                })

    if not suggestions:
        suggestions.append({
            "category": "info",
            "severity": "low",
            "title": "System läuft sauber",
            "detail": "Keine Optimierungsbedarf erkannt.",
            "actions": [],
        })

    return suggestions, auto_actions


# ── Auto-Cleanup ─────────────────────────────────────────────────────────────

def auto_cleanup(actions, dry_run=False):
    """Führt leichte Optimierungen automatisch durch."""
    results = []

    for action in actions:
        kind = action.get("action")
        if kind == "temp_cleanup":
            cleaned = []

            # User-Temp — schnell mit scandir
            temp_dir = HOME / "AppData" / "Local" / "Temp"
            if temp_dir.exists():
                count = 0
                freed_mb = 0.0
                try:
                    for entry in os.scandir(str(temp_dir)):
                        try:
                            if entry.is_file(follow_symlinks=False):
                                fs = entry.stat().st_size
                                if not dry_run:
                                    os.unlink(entry.path)
                                freed_mb += fs
                                count += 1
                            elif entry.is_dir(follow_symlinks=False):
                                # nur leere Ordner löschen, keine riesigen Bäume
                                pass
                        except (OSError, PermissionError):
                            pass
                except PermissionError:
                    pass

                if count > 0:
                    cleaned.append({
                        "target": "User Temp",
                        "path": str(temp_dir),
                        "freed_mb": round(freed_mb / (1024 * 1024), 1),
                        "freed_str": _size_str(freed_mb / (1024 * 1024)),
                        "files_removed": count,
                        "dry_run": dry_run,
                    })

            # OpenAmer Logs > 7 Tage
            if LOG_DIR.exists():
                freed_mb = 0.0
                count = 0
                cutoff = time.time() - (7 * 86400)
                try:
                    for entry in os.scandir(str(LOG_DIR)):
                        try:
                            if entry.is_file(follow_symlinks=False):
                                mtime = entry.stat().st_mtime
                                if mtime < cutoff:
                                    fs = entry.stat().st_size
                                    if not dry_run:
                                        os.unlink(entry.path)
                                    freed_mb += fs
                                    count += 1
                        except (OSError, PermissionError):
                            pass
                except PermissionError:
                    pass

                if count > 0:
                    cleaned.append({
                        "target": "Alte Logs (>7 Tage)",
                        "path": str(LOG_DIR),
                        "freed_mb": round(freed_mb / (1024 * 1024), 1),
                        "freed_str": _size_str(freed_mb / (1024 * 1024)),
                        "files_removed": count,
                        "dry_run": dry_run,
                    })

            results.append({
                "action": "temp_cleanup",
                "detail": f"Temp-Bereinigung {'(Dry-Run)' if dry_run else ''}",
                "cleaned": cleaned,
            })

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    started_at = datetime.now(timezone.utc)

    print(json.dumps({"tool": "perf-optimizer", "version": "2.0.0", "started_at": started_at.isoformat()}, indent=2))
    print()

    # 1. RAM
    try:
        ram = check_ram()
        print(json.dumps({"phase": "ram", "data": ram}, indent=2))
    except Exception as e:
        ram = {"error": str(e)}
        print(json.dumps({"phase": "ram", "error": str(e)}, indent=2))
    print()

    _check_timeout()

    # 2. Disk
    try:
        disk = check_disk()
        print(json.dumps({"phase": "disk", "data": disk}, indent=2))
    except Exception as e:
        disk = {"error": str(e)}
        print(json.dumps({"phase": "disk", "error": str(e)}, indent=2))
    print()

    _check_timeout()

    # 3. Cron
    try:
        cron = check_cron_timing()
        print(json.dumps({"phase": "cron_timing", "data": cron}, indent=2))
    except Exception as e:
        cron = {"error": str(e)}
        print(json.dumps({"phase": "cron_timing", "error": str(e)}, indent=2))
    print()

    _check_timeout()

    # 4. Optimierungsvorschläge
    suggestions, auto_actions = generate_optimizations(
        ram if "error" not in ram else {"usage_pct": 0, "used_mb": 0, "total_mb": 0, "top_processes": []},
        disk if "error" not in disk else {"drives": [], "temp_analysis": {}, "cache_analysis": {}},
        cron if "error" not in cron else {"status": "ok", "cron_jobs": [], "failed_jobs": [], "slow_jobs": []},
    )
    print(json.dumps({"phase": "suggestions", "data": suggestions}, indent=2))
    print()

    _check_timeout()

    # 5. Auto-Cleanup
    cleanup_results = []
    if auto_actions and not dry_run:
        cleanup_results = auto_cleanup(auto_actions, dry_run=False)
        print(json.dumps({"phase": "cleanup_executed", "data": cleanup_results}, indent=2))
    elif auto_actions and dry_run:
        cleanup_results = auto_cleanup(auto_actions, dry_run=True)
        print(json.dumps({"phase": "cleanup_dry_run", "data": cleanup_results}, indent=2))
    else:
        print(json.dumps({"phase": "cleanup", "data": {"note": "Keine Auto-Cleanups erforderlich"}}, indent=2))
    print()

    # 6. Zusammenfassung
    has_issues = False
    if "status" in ram:
        has_issues = ram["status"] != "ok"
    if "status" in disk and disk["status"] != "ok":
        has_issues = True
    if "status" in cron and cron["status"] not in ("ok", "no_data"):
        has_issues = True

    severity_count = {"high": 0, "medium": 0, "low": 0}
    for s in suggestions:
        sev = s.get("severity", "low")
        severity_count[sev] = severity_count.get(sev, 0) + 1

    summary = {
        "phase": "summary",
        "data": {
            "has_issues": has_issues,
            "severity_summary": severity_count,
            "suggestion_count": len(suggestions),
            "auto_cleanups_done": len(cleanup_results),
            "alarm": has_issues and severity_count.get("high", 0) > 0,
            "recommendation": (
                "⚠️ KRITISCH: Hohe Priorität — sofortige Optimierung empfohlen"
                if has_issues and severity_count.get("high", 0) > 0
                else (
                    "⚠️ Auffälligkeiten erkannt — Optimierung empfohlen"
                    if has_issues
                    else "✅ System läuft sauber — keine Optimierung nötig"
                )
            ),
        },
    }
    print(json.dumps(summary, indent=2))

    # Exit-Code
    if has_issues and severity_count.get("high", 0) > 0:
        sys.exit(2)
    elif has_issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        if "timeout" in str(e).lower():
            print(json.dumps({"phase": "error", "error": str(e)}, indent=2))
            sys.exit(3)
        raise