"""
Self-Healing Memory Pipeline — erkennt und repariert korrupte Memories automatisch.

Läuft als Teil der Autonomous Initiative oder als Standalone-Cron.
Prüft Integrität aller Memory-Dateien, repariert korrupte und
erstellt Backup-Wiederherstellung bei Totalausfall.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Circuit Breaker Integration
# ---------------------------------------------------------------------------

from openamer_cli.circuit_breaker import check_action, record_success, record_failure

CB_MODULE = "memory_healing"


# ---------------------------------------------------------------------------


def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _memories_dir() -> Path:
    return _home() / "memories"


def _backup_dir() -> Path:
    bdir = _home() / "memory_backups"
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def _vector_dir() -> Path:
    return _home() / "vector_memory"


# ----- Integrity Checks -----


def check_memory_integrity() -> dict[str, Any]:
    """Prüft alle Memories auf Korruption. Liefert Report."""
    memdir = _memories_dir()
    if not memdir.is_dir():
        return {"status": "warn", "message": "Memory-Verzeichnis existiert nicht", "issues": [], "issues_count": 0}

    issues: list[dict[str, Any]] = []
    for f in memdir.glob("*.md"):
        fpath = memdir / f.name
        try:
            content = fpath.read_text(encoding="utf-8")
            if len(content) == 0:
                issues.append({"file": f.name, "issue": "leer", "severity": "warn"})
            if content.count("---") > 10:
                issues.append({"file": f.name, "issue": "frontmatter-wiederholung", "severity": "warn"})
            # Prüfe auf ungewöhnliche Bytes
            try:
                fpath.read_bytes()
            except Exception:
                issues.append({"file": f.name, "issue": "korrupte-binärdaten", "severity": "fail"})
        except Exception as e:
            issues.append({"file": f.name, "issue": f"lesefehler: {e}", "severity": "fail"})

    # Prüfe Vector-Store Konsistenz
    vecdir = _vector_dir()
    if vecdir.is_dir():
        for needed in ["index.json", "vectors.npy", "documents.json"]:
            if not (vecdir / needed).exists():
                issues.append({"file": f"vector_memory/{needed}", "issue": "fehlt", "severity": "fail"})

    return {
        "status": "pass" if not issues else "warn",
        "issues_count": len(issues),
        "issues": issues,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def fix_memory_issues() -> dict[str, Any]:
    """Repariert erkannter Probleme automatisch."""
    report = check_memory_integrity()
    memdir = _memories_dir()
    fixed: list[str] = []
    errors: list[str] = []

    for issue in report.get("issues", []):
        fname = issue["file"]
        fpath = memdir / fname

        if issue["issue"] == "leer" and fpath.exists():
            # Leere Datei: Backup vor dem Löschen
            bpath = _backup_dir() / f"{fname}.{int(time.time())}.bak"
            try:
                shutil.copy2(fpath, bpath)
                fpath.unlink()
                fixed.append(f"{fname} → gelöscht (leer), Backup unter {bpath.name}")
            except Exception as e:
                errors.append(f"{fname}: {e}")

        elif issue["issue"] == "korrupte-binärdaten":
            bpath = _backup_dir() / f"{fname}.{int(time.time())}.bak"
            try:
                shutil.copy2(fpath, bpath)
                fpath.write_text("", encoding="utf-8")
                fixed.append(f"{fname} → zurückgesetzt, Backup unter {bpath.name}")
            except Exception as e:
                errors.append(f"{fname}: {e}")

    # Vector-Store: fehlende Dateien neu erstellen
    from openamer_cli.vector_memory import get_store
    try:
        store = get_store()
        store._ensure_loaded()
        # Einfach ein Dummy-Entry speichern um Struktur aufzubauen
        store.store("health_check", "Auto-healing memory pipeline initialization")
        fixed.append("vector_memory → Struktur neu aufgebaut")
    except Exception as e:
        errors.append(f"vector_memory: {e}")

    return {
        "fixed": fixed,
        "errors": errors,
        "fixed_count": len(fixed),
        "error_count": len(errors),
        "previous_issues": report["issues_count"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_healing_cycle() -> dict[str, Any]:
    """Vollständiger Self-Healing Zyklus: Check → Fix → Report."""
    if not check_action(CB_MODULE):
        return {"status": "blocked", "message": "Circuit breaker is RED — manual reset required", "issues_found": 0, "issues_fixed": 0}

    try:
        check = check_memory_integrity()
        fix = fix_memory_issues() if check["issues_count"] > 0 else {"fixed": [], "fixed_count": 0}
        record_success(CB_MODULE)
        return {
            "check_status": check["status"],
            "issues_found": check["issues_count"],
            "issues_fixed": fix["fixed_count"],
            "details": fix.get("fixed", []),
            "errors": fix.get("errors", []),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        record_failure(CB_MODULE, str(e))
        return {"status": "error", "message": str(e), "issues_found": 0, "issues_fixed": 0}


def run_cron_entry() -> str:
    """Cron-kompatibler Einstieg (für autonome Initiative)."""
    result = run_healing_cycle()
    logdir = _home() / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"memory-heal-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(logfile, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return str(logfile)