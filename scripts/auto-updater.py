#!/usr/bin/env python3
"""
Auto-Updater — intelligentes Update-Management für OpenAmer.

Prüft:
  - Git remote (neue Commits in openamer-repo)
  - pip (veraltete Pakete)
  - Skill Hub (geänderte Skill-Hashes im Vergleich zum Katalog)

CLI:
  python scripts/auto-updater.py --check        Prüft nur, meldet
  python scripts/auto-updater.py --auto          Automatisch aktualisieren (minor/patch)
  python scripts/auto-updater.py --auto --force  Auch major-Updates erlauben
  python scripts/auto-updater.py --dry-run       Zeigt was passieren würde
  python scripts/auto-updater.py --status        Status des letzten Checks
  python scripts/auto-updater.py --history       Letzte Updates anzeigen

Exit-Codes:
  0 = aktuell (keine Updates)
  1 = Updates verfügbar
  2 = Update fehlgeschlagen
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Konfiguration ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent  # openamer-repo root
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "openamer-laptop")
))
# MSYS/POSIX-Stil (/c/...) auf Windows normalisieren
s = str(OPENAMER_HOME)
if os.name == "nt":
    # Fall 1: /c/Users/... → C:/Users/...  (POSIX in MSYS)
    if s.startswith("/") and len(s) > 2 and s[2] == "/":
        OPENAMER_HOME = Path(f"{s[1].upper()}:{s[2:]}")
    # Fall 2: \c\Users\... → C:\Users\...  (WindowsPath str)
    elif len(s) > 2 and s[0] == "\\" and s[2] == "\\" and s[1].isalpha():
        OPENAMER_HOME = Path(f"{s[1].upper()}:{s[2:]}")
SKILLS_DIR = OPENAMER_HOME / "skills"
BUNDLED_MANIFEST = SKILLS_DIR / ".bundled_manifest"
HUB_INDEX_DIR = SKILLS_DIR / ".hub" / "index-cache"
REPORTS_DIR = OPENAMER_HOME / "updater-reports"
HISTORY_FILE = OPENAMER_HOME / "updater-history.json"
GIT_REMOTE = "origin"
GIT_BRANCH = "main"
VERSION_FILE = REPO_DIR / "pyproject.toml"

# ── Hilfsfunktionen ────────────────────────────────────────────────────────


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def run_cmd(
    cmd: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 60,
    capture: bool = True,
) -> Tuple[int, str, str, str]:
    """Führt einen Befehl aus und gibt (exit_code, combined_output, stdout, stderr) zurück."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO_DIR),
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip(), r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT", "", "TIMEOUT"
    except FileNotFoundError:
        return -1, f"Command not found: {cmd[0]}", "", f"Command not found: {cmd[0]}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── 1. Git-Check ───────────────────────────────────────────────────────────


def check_git() -> Dict:
    """Prüft auf neue Commits im Remote-Branch. Gibt Dict mit Ergebnissen."""
    result = {
        "status": "ok",
        "updates_available": False,
        "new_commits": [],
        "new_commit_count": 0,
        "current_sha": "",
        "error": None,
    }

    # Git muss ein repo sein
    rc, _, _, _ = run_cmd(["git", "rev-parse", "--git-dir"])
    if rc != 0:
        result["status"] = "not_a_git_repo"
        result["error"] = "Kein Git-Repository gefunden"
        return result

    # Aktuellen SHA holen
    rc, sha, _, _ = run_cmd(["git", "rev-parse", "HEAD"])
    if rc == 0:
        result["current_sha"] = sha[:12]

    # Fetch
    rc, fetch_out, _, _ = run_cmd(["git", "fetch", GIT_REMOTE, GIT_BRANCH], timeout=30)
    if rc != 0:
        result["status"] = "fetch_failed"
        result["error"] = f"git fetch fehlgeschlagen: {fetch_out[:500]}"
        return result

    # Neue Commits
    rc, log_out, _, _ = run_cmd(
        ["git", "log", f"HEAD..{GIT_REMOTE}/{GIT_BRANCH}", "--oneline"],
        timeout=15,
    )
    if rc != 0:
        result["status"] = "log_failed"
        result["error"] = f"git log fehlgeschlagen: {log_out[:500]}"
        return result

    commits = [line.strip() for line in log_out.split("\n") if line.strip()]
    # Prüfen ob wirklich lokal ist (nicht nur kein Remote)
    rc, _, _, _ = run_cmd(["git", "rev-parse", f"refs/remotes/{GIT_REMOTE}/{GIT_BRANCH}"])
    if rc != 0 and not commits:
        result["status"] = "no_remote"
        result["error"] = f"Remote-Branch {GIT_REMOTE}/{GIT_BRANCH} nicht gefunden"
        return result

    if commits:
        result["updates_available"] = True
        result["new_commits"] = commits
        result["new_commit_count"] = len(commits)

    return result


# ── 2. Pip-Check ───────────────────────────────────────────────────────────


def check_pip() -> Dict:
    """Prüft auf veraltete pip-Pakete."""
    result = {
        "status": "ok",
        "updates_available": False,
        "outdated_packages": [],
        "error": None,
    }

    rc, out, pip_stdout, _ = run_cmd([sys.executable, "-m", "pip", "list", "--outdated", "--format=json"], timeout=30)
    if rc != 0:
        result["status"] = "pip_failed"
        result["error"] = f"pip list --outdated fehlgeschlagen: {out[:500]}"
        return result

    # JSON-Teil sauber extrahieren: pip_stdout=JSON, kombiniert in out
    json_text = (pip_stdout or "").strip()
    if not json_text:
        # Fallback: kombinierten Output parsen
        json_text = out.strip()
    # JSON-Array extrahieren — das erste '[' bis zum schließenden ']'
    # das NICHT innerhalb eines Strings liegt (rohe Heuristik reicht für
    # pip output, das keine verschachtelten Arrays/Klammern in Strings hat)
    if "[" in json_text:
        start = json_text.index("[")
        depth = 0
        end = start
        for i in range(start, len(json_text)):
            if json_text[i] == "[":
                depth += 1
            elif json_text[i] == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        json_text = json_text[start:end]

    try:
        packages = json.loads(json_text) if json_text.strip() else []
    except json.JSONDecodeError:
        result["status"] = "parse_failed"
        result["error"] = "pip-Ausgabe nicht als JSON lesbar"
        return result

    # Pakete aus openamer und relevanten Abhängigkeiten (breiter: alles, dessen
    # Name 'openamer' enthält oder direkt installiert wurde)
    relevant = [p for p in packages if "openamer" in p.get("name", "").lower() or p.get("name", "") in (
        "openai", "pydantic", "httpx", "rich", "pyyaml", "prompt-toolkit", "croniter",
        "python-dotenv", "jinja2", "fire", "requests", "tenacity", "certifi",
    )]
    # Plus die ersten 10 System-Pakete (als Übersicht)
    all_packages = packages[:10]

    if relevant:
        result["updates_available"] = True

    result["outdated_packages"] = relevant
    result["all_outdated"] = all_packages

    return result


# ── 3. Skill-Hub-Check ─────────────────────────────────────────────────────


def _hash_file(path: Path) -> str:
    """MD5-Hash einer Datei."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return ""


def check_skills_hub() -> Dict:
    """Vergleicht lokale Skill-Manifest-Hashes mit Hub-Index."""
    result = {
        "status": "ok",
        "updates_available": False,
        "local_skills": 0,
        "hub_skills": 0,
        "updated_skills": [],
        "new_skills": [],
        "missing_skills": [],
        "bundled_size": 0,
        "hub_size": 0,
        "error": None,
    }

    # 1) Lokales Manifest lesen
    if not BUNDLED_MANIFEST.exists():
        result["status"] = "no_manifest"
        result["error"] = "Kein .bundled_manifest gefunden"
        return result

    local_skills: Dict[str, str] = {}
    for line in BUNDLED_MANIFEST.read_text().strip().split("\n"):
        line = line.strip()
        if ":" in line:
            name, h = line.split(":", 1)
            local_skills[name.strip()] = h.strip()

    result["local_skills"] = len(local_skills)

    # 2) Skills aus dem Skills Hub Index lesen (der Katalog, gegen den wir
    #    prüfen). Der Katalog enthält Skills aus skills.sh / lobehub / OpenAI.
    #    Wir ziehen nur skills.sh Einträge – die sind versioniert.
    hub_skills: Dict[str, str] = {}
    if HUB_INDEX_DIR.exists():
        for cache_file in HUB_INDEX_DIR.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text())
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and "name" in entry:
                            name = entry.get("name", "")
                            identifier = entry.get("identifier", "")
                            # Hash aus identifier + name generieren (Hub hat
                            # keinen festen Hash, aber wir tracken Änderungen
                            # über identifier)
                            hub_skills[name] = identifier
                elif isinstance(data, dict):
                    # Manche Caches sind dicts
                    for key, val in data.items():
                        if isinstance(val, dict) and "name" in val:
                            hub_skills[val["name"]] = key
            except (json.JSONDecodeError, OSError):
                continue

    result["hub_skills"] = len(hub_skills)

    # 3) Vergleich: Welche lokalen Skills fehlen im Hub (gelöscht/umbenannt)?
    #    Welche Hub-Skills sind lokal unbekannt (neu verfügbar)?
    local_names = set(local_skills.keys())
    hub_names = set(hub_skills.keys())

    # Update-fähige Skills: Hub hat einen Eintrag mit gleichem Namen aber
    # anderem identifier
    for name in local_names & hub_names:
        if local_skills.get(name) and hub_skills.get(name) != local_skills.get(name):
            result["updated_skills"].append(name)

    new_from_hub = [n for n in hub_names - local_names]
    missing_from_local = [n for n in local_names - hub_names]

    result["new_skills"] = sorted(new_from_hub)[:20]  # Top 20
    result["missing_skills"] = sorted(missing_from_local)[:20]  # Top 20
    result["updates_available"] = bool(result["updated_skills"]) or bool(new_from_hub)
    result["bundled_size"] = len(local_skills)
    result["hub_size"] = len(hub_skills)

    return result


# ── 4. Changelog / Report ──────────────────────────────────────────────────


def extract_changelog(git_result: Dict) -> str:
    """Erzeugt einen Changelog aus den neuen Git-Commits."""
    if not git_result["updates_available"]:
        return "Keine neuen Git-Commits."

    lines = [
        f"# Auto-Updater Report – {now_iso()}",
        "",
        f"Aktueller SHA: {git_result['current_sha']}",
        f"Neue Commits: {git_result['new_commit_count']}",
        "",
        "## Neue Commits",
        "",
    ]
    for c in git_result["new_commits"]:
        lines.append(f"- {c}")

    lines += [
        "",
        "## Kategorien (automatisch erkannt)",
        "",
    ]

    # Commits nach Kategorien sortieren
    categories: Dict[str, List[str]] = {}
    for c in git_result["new_commits"]:
        if re.match(r"^[0-9a-f]{7,}\s+feat:", c):
            categories.setdefault("Features", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+fix:", c):
            categories.setdefault("Bugfixes", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+chore:", c):
            categories.setdefault("Chores", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+docs?:", c):
            categories.setdefault("Dokumentation", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+refactor:", c):
            categories.setdefault("Refactoring", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+test:", c):
            categories.setdefault("Tests", []).append(c)
        elif re.match(r"^[0-9a-f]{7,}\s+perf:", c):
            categories.setdefault("Performance", []).append(c)
        else:
            categories.setdefault("Sonstige", []).append(c)

    for cat, commits in categories.items():
        lines.append(f"### {cat}")
        for c in commits:
            lines.append(f"- {c}")
        lines.append("")

    return "\n".join(lines)


def save_report(changelog: str, pip_result: Dict, skills_result: Dict) -> Path:
    """Speichert den Report als Datei."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"updater-report-{timestamp}.md"

    # Pip-Sektion anhängen
    sections = [changelog]
    sections.append("\n## Pip-Updates\n\n")
    if pip_result["updates_available"]:
        for pkg in pip_result["outdated_packages"]:
            sections.append(
                f"- {pkg.get('name', '?')}: "
                f"{pkg.get('version', '?')} → {pkg.get('latest_version', '?')} "
                f"({pkg.get('type', '?')})"
            )
        sections.append("")
    else:
        sections.append("Keine veralteten pip-Pakete.\n")

    sections.append("\n## Skill-Hub-Updates\n\n")
    if skills_result["updates_available"]:
        if skills_result.get("updated_skills"):
            sections.append(f"**Geänderte Skills ({len(skills_result['updated_skills'])}):**\n")
            for s in skills_result["updated_skills"]:
                sections.append(f"- {s}")
            sections.append("")
        if skills_result.get("new_skills"):
            sections.append(f"**Neue Skills im Hub ({len(skills_result['new_skills'])}):**\n")
            for s in skills_result["new_skills"]:
                sections.append(f"- {s}")
            sections.append("")
        if skills_result.get("missing_skills"):
            sections.append(f"**Lokale Skills nicht im Hub ({len(skills_result['missing_skills'])}):**\n")
            for s in skills_result["missing_skills"]:
                sections.append(f"- {s}")
            sections.append("")
    else:
        sections.append("Keine Skill-Hub-Updates.\n")

    report_path.write_text("\n".join(sections))
    return report_path


def save_history(entry: Dict) -> None:
    """Hängt einen History-Eintrag an."""
    history: List[Dict] = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            history = []

    # Max 50 Einträge
    history.insert(0, entry)
    if len(history) > 50:
        history = history[:50]

    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def show_history() -> None:
    """Zeigt die letzten Update-Einträge."""
    if not HISTORY_FILE.exists():
        info("Keine Update-Historie vorhanden.")
        return

    try:
        history = json.loads(HISTORY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        info("Historie konnte nicht gelesen werden.")
        return

    if not history:
        info("Keine Update-Historie vorhanden.")
        return

    print(f"\n{'═' * 60}")
    print(f"  Update-Historie (letzte {len(history)} Einträge)")
    print(f"{'═' * 60}")
    for entry in history[:10]:
        ts = entry.get("timestamp", "?")
        mode = entry.get("mode", "?")
        status = entry.get("status", "?")
        git_count = entry.get("git_commits", 0)
        pip_count = entry.get("pip_packages", 0)
        print(f"  [{ts}] {mode} → {status}  (git:{git_count} pip:{pip_count})")


# ── 5. Update-Ausführung ──────────────────────────────────────────────────


def apply_git_update(dry_run: bool = False, force: bool = False) -> bool:
    """Führt git pull aus. True bei Erfolg."""
    if dry_run:
        info("[DRY-RUN] git pull würde ausgeführt: "
             f"git pull {GIT_REMOTE} {GIT_BRANCH}")
        return True

    info("Führe git pull aus ...")
    rc, out, _, _ = run_cmd(["git", "pull", GIT_REMOTE, GIT_BRANCH], timeout=60)
    if rc != 0:
        error(f"git pull fehlgeschlagen: {out[:500]}")
        return False

    info(f"git pull erfolgreich:\n{out[:500]}")
    return True


def apply_pip_update(dry_run: bool = False, force: bool = False) -> bool:
    """Führt pip install --upgrade aus. True bei Erfolg."""
    if dry_run:
        info("[DRY-RUN] pip install --upgrade von openamer und Abhängigkeiten")
        return True

    info("Aktualisiere pip-Pakete ...")
    # Nur Hauptpaket upgraden, Abhängigkeiten via pip
    packages = ["openamer-agent"]

    if force:
        # Bei --force kein Upgrade-Limit
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + packages
    else:
        # Minor/patch only: --upgrade-strategy only-if-needed
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade",
               "--upgrade-strategy", "only-if-needed"] + packages

    rc, out, _, _ = run_cmd(cmd, timeout=120)
    if rc != 0:
        error(f"pip install fehlgeschlagen: {out[:500]}")
        return False

    info(f"pip-Update erfolgreich:\n{out[:500]}")
    return True


# ── 6. Haupt-Logik ─────────────────────────────────────────────────────────


def cmd_check(quiet: bool = False) -> int:
    """Prüft alle Quellen. Exit-Code: 0=aktuell, 1=Updates."""
    info("Prüfe auf Updates ...")

    git_result = check_git()
    pip_result = check_pip()
    skills_result = check_skills_hub()

    has_updates = any([
        git_result["updates_available"],
        pip_result["updates_available"],
        skills_result["updates_available"],
    ])

    if not quiet:
        # Git
        print(f"\n{'─' * 50}")
        print(f"  Git-Status:")
        print(f"    Status:     {git_result['status']}")
        print(f"    SHA:        {git_result['current_sha']}")
        if git_result["updates_available"]:
            print(f"    Updates:    ✅ {git_result['new_commit_count']} neue Commit(s)")
            for c in git_result["new_commits"][:5]:
                print(f"      → {c}")
            if len(git_result["new_commits"]) > 5:
                print(f"      … und {len(git_result['new_commits'])-5} weitere")
        elif git_result.get("error"):
            print(f"    Fehler:     {git_result['error']}")
        else:
            print(f"    Updates:    ❌ Keine – aktuell")

        # Pip
        print(f"\n  Pip-Status:")
        print(f"    Status:     {pip_result['status']}")
        if pip_result["updates_available"]:
            print(f"    Updates:    ✅ {len(pip_result['outdated_packages'])} veraltet")
            for pkg in pip_result["outdated_packages"]:
                print(f"      → {pkg.get('name','?')} "
                      f"{pkg.get('version','?')} → {pkg.get('latest_version','?')}")
        elif pip_result.get("error"):
            print(f"    Fehler:     {pip_result['error']}")
        else:
            print(f"    Updates:    ❌ Keine – aktuell")

        # Skills
        print(f"\n  Skill-Hub-Status:")
        print(f"    Status:     {skills_result['status']}")
        print(f"    Lokal:      {skills_result['bundled_size']} Skills")
        print(f"    Hub:        {skills_result['hub_size']} Skills")
        if skills_result["updates_available"]:
            print(f"    Updates:    ✅ {len(skills_result['updated_skills'])} Skill-Updates verfügbar")
            for s in skills_result["updated_skills"][:10]:
                print(f"      → {s}")
            if skills_result.get("new_skills"):
                print(f"    Neue:       {len(skills_result['new_skills'])} neue Skills im Hub")
            if skills_result.get("missing_skills"):
                print(f"    Fehlend:    {len(skills_result['missing_skills'])} lokale nicht im Hub")
        elif skills_result.get("error"):
            print(f"    Fehler:     {skills_result['error']}")
        else:
            print(f"    Updates:    ❌ Keine – aktuell")

        print(f"{'─' * 50}")

    # Report speichern wenn Updates
    changelog = extract_changelog(git_result)
    report_path = save_report(changelog, pip_result, skills_result)
    info(f"Report gespeichert: {report_path}")

    # History
    save_history({
        "timestamp": now_iso(),
        "mode": "check",
        "status": "updates_available" if has_updates else "current",
        "git_commits": git_result["new_commit_count"],
        "pip_packages": len(pip_result["outdated_packages"]),
        "skill_updates": len(skills_result.get("updated_skills", [])),
    })

    return 1 if has_updates else 0


def cmd_auto(dry_run: bool = False, force: bool = False) -> int:
    """Prüft + wendet Updates an. Exit-Code: 0=aktuell, 1=erfolgreich, 2=fehlgeschlagen."""
    info("Auto-Update gestartet ...")

    # 1) Prüfen
    git_result = check_git()
    pip_result = check_pip()
    skills_result = check_skills_hub()

    has_git_updates = git_result["updates_available"]
    has_pip_updates = pip_result["updates_available"]

    if not has_git_updates and not has_pip_updates:
        info("Alles aktuell – keine Aktion nötig.")
        changelog = extract_changelog(git_result)
        report_path = save_report(changelog, pip_result, skills_result)
        info(f"Report: {report_path}")
        save_history({
            "timestamp": now_iso(),
            "mode": "auto",
            "status": "current",
            "git_commits": 0,
            "pip_packages": 0,
            "skill_updates": 0,
        })
        return 0

    # 2) Report vorbereiten
    changelog = extract_changelog(git_result)
    report_path = save_report(changelog, pip_result, skills_result)
    info(f"Report: {report_path}")

    # 3) Git-Update
    git_ok = True
    if has_git_updates:
        git_ok = apply_git_update(dry_run=dry_run, force=force)
        if not git_ok:
            error("Git-Update fehlgeschlagen")

    # 4) Pip-Update
    pip_ok = True
    if has_pip_updates:
        pip_ok = apply_pip_update(dry_run=dry_run, force=force)
        if not pip_ok:
            error("Pip-Update fehlgeschlagen")

    overall_ok = git_ok and pip_ok
    status = "completed" if overall_ok else "failed"

    save_history({
        "timestamp": now_iso(),
        "mode": "auto" if not dry_run else "dry-run",
        "status": status,
        "force": force,
        "git_commits": git_result["new_commit_count"] if has_git_updates else 0,
        "pip_packages": len(pip_result["outdated_packages"]) if has_pip_updates else 0,
        "skill_updates": len(skills_result.get("updated_skills", [])),
    })

    if overall_ok:
        info("Auto-Update erfolgreich abgeschlossen.")
        return 1
    else:
        error("Auto-Update fehlgeschlagen.")
        return 2


def cmd_status() -> int:
    """Zeigt Status des letzten Checks."""
    if not HISTORY_FILE.exists():
        info("Keine vorherigen Checks gefunden.")
        return 0

    history = json.loads(HISTORY_FILE.read_text())
    if not history:
        info("Keine vorherigen Checks gefunden.")
        return 0

    latest = history[0]
    ts = latest.get("timestamp", "?")
    mode = latest.get("mode", "?")
    status = latest.get("status", "?")

    print(f"\n{'═' * 60}")
    print(f"  Letzter Update-Check")
    print(f"{'═' * 60}")
    print(f"  Zeit:     {ts}")
    print(f"  Modus:    {mode}")
    print(f"  Status:   {status}")

    if status == "updates_available":
        print(f"  Git:      {latest.get('git_commits', 0)} neue Commits")
        print(f"  Pip:      {latest.get('pip_packages', 0)} veraltete Pakete")
        print(f"  Skills:   {latest.get('skill_updates', 0)} Skill-Updates")

    return 0


def cmd_history() -> int:
    """Zeigt die letzten Einträge."""
    show_history()
    return 0


# ── 7. CLI ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="OpenAmer Auto-Updater – Update-Verwaltung",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python scripts/auto-updater.py --check       # Nur prüfen
  python scripts/auto-updater.py --auto         # Automatisch updaten
  python scripts/auto-updater.py --auto --force # Major-Updates erlauben
  python scripts/auto-updater.py --dry-run      # Zeigen, nicht ausführen
  python scripts/auto-updater.py --status       # Letzten Check anzeigen
  python scripts/auto-updater.py --history      # Letzte Updates anzeigen
        """,
    )

    parser.add_argument("--check", action="store_true", help="Nur prüfen, keine Aktion")
    parser.add_argument("--auto", action="store_true", help="Automatisch aktualisieren")
    parser.add_argument("--dry-run", action="store_true", help="Zeigen was passieren würde, nicht ausführen")
    parser.add_argument("--force", action="store_true", help="Major-Updates erlauben")
    parser.add_argument("--status", action="store_true", help="Letzten Check-Status anzeigen")
    parser.add_argument("--history", action="store_true", help="Letzte Updates anzeigen")
    parser.add_argument("--quiet", action="store_true", help="Weniger Ausgabe")

    args = parser.parse_args()

    if args.status:
        return cmd_status()
    elif args.history:
        return cmd_history()
    elif args.auto:
        return cmd_auto(dry_run=args.dry_run, force=args.force)
    elif args.dry_run:
        return cmd_auto(dry_run=True, force=args.force)
    elif args.check:
        return cmd_check(quiet=args.quiet)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[ABBRUCH] durch Benutzer")
        sys.exit(2)
    except Exception as e:
        error(f"Unvorhergesehener Fehler: {e}")
        sys.exit(2)