#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Dokumentation Generator — README, CHANGELOG, Skills-Index, Cron-Status.

Analysiert Git-History, Skills-Verzeichnis und Cron-Konfiguration,
generiert strukturierte Markdown-Dokumentation nach docs/generated/.

CLI:
    python scripts/auto-docs.py --all          # Alles generieren
    python scripts/auto-docs.py --readme       # Nur README
    python scripts/auto-docs.py --changelog    # Nur CHANGELOG
    python scripts/auto-docs.py --skills       # Nur Skills-Index
    python scripts/auto-docs.py --cron         # Nur Cron-Status

Requirements: Python 3.11+, git, Zugriff auf OpenAmer-Skills+Cron.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Pfade ──────────────────────────────────────────────────────────────────
# REPO_ROOT = Arbeitskopie des openamer-repo
REPO_ROOT = Path(__file__).resolve().parent.parent
# OPENAMER_HOME = lokale OpenAmer-Installation (Skills + Cron)
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"),
))
SKILLS_DIR = OPENAMER_HOME / "skills"
CRON_JOBS_FILE = OPENAMER_HOME / "cron" / "jobs.json"
OUTPUT_DIR = REPO_ROOT / "docs" / "generated"

# Hilfsverzeichnisse für README
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
PLUGINS_DIR = REPO_ROOT / "plugins"
SKILLS_REPO_DIR = REPO_ROOT / "skills"
CRON_DIR = REPO_ROOT / "cron"

# Sicherstellen, dass das Output-Verzeichnis existiert
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# 1. README Generator
# ═══════════════════════════════════════════════════════════════════════════

def _run_git(cmd: list[str], cwd: Path | None = None) -> str:
    """Führe ein git-Kommando aus und gib stdout zurück."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or REPO_ROOT,
            timeout=30,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"<error: {e}>"


def get_project_stats() -> dict:
    """Sammle Projekt-Kennzahlen."""
    stats = {}
    # Python-Code
    py_files = list(REPO_ROOT.rglob("*.py"))
    stats["py_files"] = len(py_files)
    try:
        loc = subprocess.run(
            ["wc", "-l"] + [str(f) for f in py_files if "node_modules" not in str(f) and ".venv" not in str(f)],
            capture_output=True, text=True, timeout=30,
        )
        stats["py_loc"] = loc.stdout.strip().split("\n")[-1].split()[-2] if loc.stdout else "?"
    except Exception:
        stats["py_loc"] = "?"

    # JSON/JS/TS
    for ext, key in [(".json", "json_files"), (".js", "js_files"), (".ts", "ts_files")]:
        stats[key] = len(list(REPO_ROOT.rglob(f"*{ext}")))

    # Skills
    stats["skills_count"] = sum(1 for _ in SKILLS_DIR.rglob("SKILL.md")) if SKILLS_DIR.exists() else 0
    stats["scripts_count"] = len(list(SCRIPTS_DIR.glob("*.py"))) if SCRIPTS_DIR.exists() else 0

    # Cron
    if CRON_JOBS_FILE.exists():
        try:
            with open(CRON_JOBS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            stats["cron_jobs"] = len(data.get("jobs", []))
        except Exception:
            stats["cron_jobs"] = 0
    else:
        stats["cron_jobs"] = 0

    # Git-Statistiken
    commits_total = _run_git(["git", "rev-list", "--count", "HEAD"])
    stats["commits_total"] = commits_total or "?"
    authors = _run_git(["git", "shortlog", "-sn", "HEAD"])
    stats["authors"] = len([l for l in authors.split("\n") if l.strip()]) if authors else 0

    # Letzter Tag
    last_tag = _run_git(["git", "describe", "--tags", "--abbrev=0"])
    stats["last_tag"] = last_tag or "—"
    stats["version"] = last_tag.lstrip("v") if last_tag and last_tag != "—" else "dev"

    try:
        size_cmd = subprocess.run(
            ["du", "-sh", str(REPO_ROOT)],
            capture_output=True, text=True, timeout=10,
        )
        stats["repo_size"] = size_cmd.stdout.split()[0] if size_cmd.stdout else "?"
    except Exception:
        stats["repo_size"] = "?"

    return stats


def generate_readme(stats: dict) -> str:
    """Generiere README.md mit Projektübersicht, Features, Architektur, Installation, Usage."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    skills_active = stats.get("skills_count", "?")
    scripts_count = stats.get("scripts_count", "?")
    py_loc = stats.get("py_loc", "?")

    readme = f"""# OpenAmer — Auto-Generated README

> *Automatisch generiert am {now}*
> Version: **{stats["version"]}** | Branche: {stats.get("last_tag", "—")}

**OpenAmer** ist ein persönlicher KI-Agent, der auf CLI, Desktop-App, TUI und
über 20 Messaging-Plattformen (Telegram, Discord, Slack u.v.m.) läuft.
Er lernt über Sessions hinweg (Memory + Skills), delegiert an Sub-Agents,
führt geplante Cron-Jobs aus und steuert Terminal und Browser.

---

## 📊 Projekt-Kennzahlen

| Metrik                | Wert                         |
|-----------------------|------------------------------|
| Python-Dateien        | {stats['py_files']}         |
| Python-LOC            | {py_loc}                    |
| JavaScript-Dateien    | {stats['js_files']}         |
| TypeScript-Dateien    | {stats['ts_files']}         |
| Skills (Installation) | {skills_active}             |
| Scripts               | {scripts_count}             |
| Cron-Jobs             | {stats['cron_jobs']}        |
| Git-Commits           | {stats['commits_total']}    |
| Autoren               | {stats['authors']}          |
| Repo-Grösse           | {stats['repo_size']}        |

---

## 🚀 Features

### Core Agent
- **Multi-Plattform**: CLI, Desktop (Electron), TUI, Telegram, Discord, Slack + 20 weitere
- **Modell-Agnostisch**: OpenAI, Anthropic, Google, DeepSeek, OpenRouter, lokale Modelle
- **Prompt-Caching**: Byte-stabiler System-Prompt für effiziente API-Nutzung
- **Kontext-Kompression**: Automatische Reduzierung langer Konversationen
- **Memory-System**: Sessions-übergreifendes Lernen (Brain-Dataset + Memory-Healing)
- **Skill-System**: 630+ Skills für spezialisierte Aufgaben, modular erweiterbar

### Superintelligence
- **Smart Cron Scheduler**: Intelligente Zeitplan-Optimierung mit Auto-Korrektur
- **Self-Healer Daemon**: Automatische Log-Analyse, Mustererkennung und Reparatur
- **Auto-Test-Runner**: Git-Diff-basierte Test-Priorisierung und parallele Ausführung
- **Knowledge Graph**: Skill-Netzwerk mit 630 Skills + Vorschlags-Engine
- **Circuit Breaker**: Selbstzerstörungsschutz für autonome Systeme
- **Swarm Metrics**: Echtzeit-Überwachung des Agent-Schwarms

### A2A (Agent-to-Agent)
- **Swarm-Kommunikation**: Identität, Vertrauen, Node-to-Node Ask
- **Brain Collect**: Automatischer Export von Sessions ins Brain-Dataset
- **Mesh Learning**: Autonomer Lernprozess über mehrere Agenten hinweg
- **GitHub Relay**: A2A über GitHub als Transport (kein Localhost nötig)
- **Autolog**: Automatische Aufzeichnung aller Aktivitäten für das Brain

### Entwicklung
- **IDE-Integration**: VS Code Extension + JetBrains Plugin
- **Plugin-System**: Erweiterbar über Plugins und MCP-Server
- **CI/CD**: Tägliche Releases (CalVer), automatische Tags
- **Bugbot**: Autonome Bug-Erkennung und -Reparatur
- **Security Agent**: Automatischer CVE-Scan und Patching via OSV.dev API

---

## 🏗️ Architektur

```
openamer-repo/
├── cli.py                 # CLI-Dispatcher (Hauptkommando)
├── run_agent.py           # Agent-Core (Konversationsschleife)
├── openamer_state.py      # State-Management
├── openamer_constants.py  # Konstanten
├── openamer_logging.py    # Logging
├── scripts/               # Automatisierungs-Scripts ({scripts_count} Stk.)
├── gateway/               # Multi-Plattform-Gateway
├── plugins/               # Plugin-System
├── providers/             # Modell-Provider
├── tools/                 # Tool-Definitionen
├── skills/                # In-Repo Skills
├── docs/                  # Dokumentation
│   └── generated/         # Auto-generierte Doks (dieses Script)
├── cron/                  # Cron-Konfiguration
├── tests/                 # Python-Tests
├── desktop-plugins/       # Desktop-Plugins
├── website/               # Docusaurus-Website
├── web/                   # Web-App
└── docker/                # Docker-Konfiguration
```

### Datenfluss
1. **Eingabe**: User-Nachricht via CLI/TUI/Desktop/Gateway
2. **Verarbeitung**: Agent-Core mit System-Prompt, Tool-Auswahl, LLM-Call
3. **Aktion**: Tool-Ausführung (Terminal, Browser, Dateien, Skills)
4. **Lernen**: Sessions → Brain-Dataset → Fine-Tuning
5. **Automatisierung**: Cron-Jobs für regelmässige Wartung

---

## 📦 Installation

```bash
# Via pip (empfohlen)
pip install openamer

# Via uv (schneller)
uv pip install openamer

# Von Source
git clone https://github.com/openamer/openamer.git
cd openamer
pip install -e .
```

### Desktop-App (Windows)
Lade das neueste `.exe`-Setup von [Releases](https://github.com/openamer/openamer/releases).

---

## 🚴 Usage

```bash
# CLI starten
openamer

# Skills verwalten
openamer skills list
openamer skills install <name>

# Cron-Jobs verwalten
openamer cron list
openamer cron add --name "my-job" --prompt "..."

# System-Info
openamer system
openamer config show

# A2A (Agent-to-Agent)
openamer a2a swarm ask "Frage an den Schwarm"
openamer a2a brain collect
```

---

## 🔧 Wartung & Cron-Jobs

OpenAmer läuft rund um die Uhr mit {stats["cron_jobs"]} Cron-Jobs:

- **Brain Collect** (alle 4h): Exportiert Sessions ins Brain-Dataset
- **Self-Reflection** (alle 4h): Überprüft System-Gesundheit
- **Auto-Test-Runner** (alle 4h): Führt Tests aus
- **Security Agent** (alle 4h): Scannt auf CVEs
- **Bugbot** (alle 4h): Fixt automatisch gefundene Bugs
- **Self-Healer** (alle 30min): Daemon für automatische Reparaturen
- **Perf-Optimizer** (alle 6h): Optimiert System-Performance
- **Skills Hub Cache** (alle 6h): Wärmt den Skills-Cache

Vollständige Liste: `docs/generated/CRON-STATUS.md`

---

## 🤝 Mitwirken

Beiträge sind willkommen! Siehe [CONTRIBUTING.md](./CONTRIBUTING.md) und [AGENTS.md](./AGENTS.md) für Entwickler-Richtlinien.

### Entwicklungs-Setup
```bash
git clone https://github.com/openamer/openamer.git
cd openamer
pip install -e ".[dev]"
pre-commit install
```

---

## 📄 Lizenz

Apache 2.0 — siehe [LICENSE](./LICENSE).

---

*Generiert von [auto-docs.py](../scripts/auto-docs.py) — letzte Aktualisierung: {now}*
"""
    return readme


# ═══════════════════════════════════════════════════════════════════════════
# 2. CHANGELOG Generator
# ═══════════════════════════════════════════════════════════════════════════

def parse_git_log(raw: str) -> list[dict]:
    """Parst das raw git log in strukturierte Dicts."""
    commits = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            hash_, date, author, message = parts
            date_dt = datetime.strptime(date[:19], "%Y-%m-%d %H:%M:%S") if len(date) >= 19 else None
            # Typ erkennen (feat, fix, docs, chore, etc.)
            type_match = re.match(r"^(feat|fix|docs|chore|test|refactor|ci|style|perf|revert|build|stealth)(\([^)]+\))?:\s*(.*)", message)
            if type_match:
                commit_type = type_match.group(1)
                scope = type_match.group(2).strip("()") if type_match.group(2) else ""
                desc = type_match.group(3)
            else:
                commit_type = "other"
                scope = ""
                desc = message
            commits.append({
                "hash": hash_[:8],
                "date": date,
                "author": author,
                "message": message,
                "type": commit_type,
                "scope": scope,
                "description": desc,
            })
    return commits


def get_tags() -> list[dict]:
    """Hole alle Tags mit Datum."""
    raw = _run_git(["git", "tag", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:iso-strict)"])
    tags = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 1)
        if len(parts) == 2:
            tags.append({"name": parts[0], "date": parts[1]})
    return tags


def generate_changelog() -> str:
    """Generiere CHANGELOG.md aus Git-Commit-Messages."""
    tags = get_tags()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    changelog = f"""# Changelog

> *Automatisch generiert am {now}*

"""

    # Format: Jeder Tag + Commits dazwischen
    if tags:
        # Commits seit HEAD (ungreleasted)
        head_log = _run_git(["git", "log", f"{tags[0]['name']}..HEAD", "--format=%H|%ai|%an|%s"])
        if head_log.strip():
            commits = parse_git_log(head_log)
            if commits:
                changelog += "## Unreleased\n\n"
                changelog += _format_commits(commits)
                changelog += "\n"

        # Für jeden Tag: Commits seit letztem Tag
        for i, tag in enumerate(tags):
            changelog += f"## [{tag['name']}](https://github.com/openamer/openamer/releases/tag/{tag['name']})\n\n"
            changelog += f"> {tag['date'][:10]}\n\n"

            if i < len(tags) - 1:
                log = _run_git(["git", "log", f"{tags[i+1]['name']}..{tag['name']}", "--format=%H|%ai|%an|%s"])
            else:
                log = _run_git(["git", "log", f"{tag['name']}", "--format=%H|%ai|%an|%s", "--reverse"])

            commits = parse_git_log(log)
            if commits:
                changelog += _format_commits(commits)
            else:
                changelog += "- Keine Änderungen\n"
            changelog += "\n"
    else:
        # Kein Tag: alle Commits
        raw = _run_git(["git", "log", "--format=%H|%ai|%an|%s", "--reverse"])
        commits = parse_git_log(raw)
        changelog += "## Alle Commits\n\n"
        changelog += _format_commits(commits)

    return changelog


def _format_commits(commits: list[dict]) -> str:
    """Formatiere Commit-Liste als Markdown."""
    # Gruppiere nach Typ
    groups = defaultdict(list)
    type_labels = {
        "feat": "🚀 Features",
        "fix": "🐛 Bug Fixes",
        "docs": "📝 Dokumentation",
        "chore": "🔧 Wartung",
        "test": "🧪 Tests",
        "refactor": "♻️ Refactoring",
        "ci": "⚙️ CI/CD",
        "style": "🎨 Styling",
        "perf": "⚡ Performance",
        "revert": "↩️ Reverts",
        "build": "📦 Build",
        "stealth": "🕶️ Stealth",
        "other": "📌 Sonstiges",
    }
    type_order = ["feat", "fix", "docs", "refactor", "perf", "test", "ci", "chore", "stealth", "style", "build", "revert", "other"]

    for c in commits:
        groups[c["type"]].append(c)

    output = ""
    for t in type_order:
        if t not in groups:
            continue
        output += f"### {type_labels.get(t, t)}\n\n"
        for c in groups[t]:
            scope = f"**{c['scope']}:** " if c["scope"] else ""
            output += f"- {scope}{c['description']} ({c['hash']})\n"
        output += "\n"

    return output


# ═══════════════════════════════════════════════════════════════════════════
# 3. Skills-Index Generator
# ═══════════════════════════════════════════════════════════════════════════

def scan_skills() -> list[dict]:
    """Scannt das Skills-Verzeichnis nach allen Skills."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for cat_dir in sorted(SKILLS_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        category = cat_dir.name
        for skill_dir in sorted(cat_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            # Lese SKILL.md oder DESCRIPTION.md
            md_file = skill_dir / "SKILL.md"
            if not md_file.exists():
                md_file = skill_dir / "DESCRIPTION.md"
            desc = ""
            tags = []
            if md_file.exists():
                try:
                    content = md_file.read_text(encoding="utf-8", errors="replace")
                    # Extrahiere description aus Frontmatter
                    fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                    if fm_match:
                        fm = fm_match.group(1)
                        for line in fm.split("\n"):
                            line = line.strip()
                            if line.startswith("description:"):
                                desc = line[len("description:"):].strip().strip('"').strip("'")
                            elif line.startswith("tags:"):
                                tag_match = re.findall(r'"([^"]+)"', line)
                                if tag_match:
                                    tags = tag_match
                    # Fallback: erste Zeile nach Frontmatter
                    if not desc:
                        body = content[fm_match.end():] if fm_match else content
                        for line in body.strip().split("\n"):
                            line = line.strip()
                            if line and not line.startswith("#") and not line.startswith(">"):
                                desc = line[:150]
                                break
                except Exception:
                    desc = ""
            skills.append({
                "name": skill_dir.name,
                "category": category,
                "description": desc,
                "tags": tags,
            })
    return skills


def generate_skills_index() -> str:
    """Generiere SKILLS-INDEX.md."""
    skills = scan_skills()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Zähle nach Kategorie
    cat_counts = defaultdict(int)
    for s in skills:
        cat_counts[s["category"]] += 1

    index = f"""# Skills-Index

> *Automatisch generiert am {now}*
> **{len(skills)} Skills** in **{len(cat_counts)} Kategorien**

---

## Übersicht nach Kategorie

| Kategorie | Anzahl |
|-----------|-------:|
"""
    for cat in sorted(cat_counts):
        index += f"| {cat} | {cat_counts[cat]} |\n"

    index += f"\n---\n\n## Vollständiger Index\n\n"

    current_cat = ""
    for s in skills:
        if s["category"] != current_cat:
            current_cat = s["category"]
            index += f"### {current_cat}\n\n"

        desc = s["description"][:120] if s["description"] else "*Keine Beschreibung*"
        tags_str = f" `{', '.join(s['tags'][:3])}`" if s["tags"] else ""
        index += f"- **{s['name']}**{tags_str} — {desc}\n"

    return index


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cron-Status Generator
# ═══════════════════════════════════════════════════════════════════════════

def load_cron_jobs() -> list[dict]:
    """Lade Cron-Jobs aus jobs.json."""
    if not CRON_JOBS_FILE.exists():
        return []
    try:
        with open(CRON_JOBS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("jobs", [])
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Fehler beim Lesen von {CRON_JOBS_FILE}: {e}", file=sys.stderr)
        return []


def _status_icon(status: str | None) -> str:
    """Status-Icon für Cron-Job."""
    if status is None:
        return "🆕"
    match status.lower():
        case "ok":
            return "✅"
        case "error" | "failed":
            return "❌"
        case "scheduled":
            return "⏳"
        case "running":
            return "🔄"
        case "paused":
            return "⏸️"
        case _:
            return "❓"


def _job_type(job: dict) -> str:
    """Menschlicher Job-Typ."""
    if job.get("skill"):
        return f"Skill: `{job['skill']}`"
    if job.get("script"):
        return f"Script: `{job['script']}`"
    if job.get("prompt"):
        return "Agent (Prompt)"
    return "Unbekannt"


def generate_cron_status() -> str:
    """Generiere CRON-STATUS.md."""
    jobs = load_cron_jobs()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    enabled = [j for j in jobs if j.get("enabled", False)]
    disabled = [j for j in jobs if not j.get("enabled", False)]
    ok_jobs = [j for j in jobs if j.get("last_status") == "ok"]
    error_jobs = [j for j in jobs if j.get("last_status") in ("error", "failed")]

    cron_text = f"""# Cron-Status

> *Automatisch generiert am {now}*
> **{len(jobs)} Jobs** davon **{len(enabled)} aktiv**, **{len(disabled)} deaktiviert**
> Letzter Lauf: ✅ **{len(ok_jobs)} OK** | ❌ **{len(error_jobs)} Fehler**

---

## Job-Übersicht

| Status | Name | Typ | Schedule | Letzter Lauf | Nächster Lauf | Ergebnis |
|--------|------|-----|----------|-------------|---------------|----------|
"""
    for job in jobs:
        icon = _status_icon(job.get("last_status"))
        name = job.get("name", job.get("id", "—"))
        jobtype = _job_type(job)
        schedule = job.get("schedule_display", job.get("schedule", {}).get("display", "—"))
        last_run = job.get("last_run_at", "—")[:19] if job.get("last_run_at") else "—"
        next_run = job.get("next_run_at", "—")[:19] if job.get("next_run_at") else "—"
        last_error = job.get("last_error", "")
        if last_error:
            status_text = f"⚠ {last_error[:50]}"
        else:
            status_text = job.get("last_status") or "🆕 noch nie"

        if not job.get("enabled", False):
            icon = "⏸️"

        cron_text += f"| {icon} | {name} | {jobtype} | {schedule} | {last_run} | {next_run} | {status_text} |\n"

    # Fehler-Highlights
    if error_jobs:
        cron_text += "\n## ❌ Fehlerhafte Jobs\n\n"
        for j in error_jobs:
            cron_text += f"### {j.get('name', j.get('id', '—'))}\n\n"
            cron_text += f"- **Letzter Lauf**: {j.get('last_run_at', '—')[:19]}\n"
            cron_text += f"- **Fehler**: {j.get('last_error', 'Unbekannt')}\n"
            cron_text += f"- **Schedule**: {j.get('schedule_display', '—')}\n\n"

    # Schedule-Übersicht (Intervalle)
    intervals = defaultdict(list)
    cron_exprs = defaultdict(list)
    for j in jobs:
        sched = j.get("schedule", {})
        kind = sched.get("kind", "unknown")
        if kind == "interval":
            mins = sched.get("minutes", 0)
            intervals[mins].append(j)
        elif kind == "cron":
            expr = sched.get("expr", "?")
            cron_exprs[expr].append(j)

    cron_text += "\n## ⏱ Schedule-Übersicht\n\n"
    if intervals:
        cron_text += "### Intervall-Jobs\n\n"
        for mins in sorted(intervals):
            job_names = ", ".join(j.get("name", "?") for j in intervals[mins])
            cron_text += f"- **Alle {mins} min**: {job_names}\n"

    if cron_exprs:
        cron_text += "\n### Cron-Jobs\n\n"
        for expr in sorted(cron_exprs):
            job_names = ", ".join(j.get("name", "?") for j in cron_exprs[expr])
            cron_text += f"- `{expr}` — {job_names}\n"

    return cron_text


# ═══════════════════════════════════════════════════════════════════════════
# 5. CLI + Main
# ═══════════════════════════════════════════════════════════════════════════

def write_doc(filename: str, content: str, title: str):
    """Schreibe generiertes Dokument."""
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    size = len(content.encode("utf-8"))
    print(f"  ✅ {filename} ({size:,} Bytes) → {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Dokumentation Generator für OpenAmer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python scripts/auto-docs.py --all          # Alles generieren
  python scripts/auto-docs.py --readme       # Nur README
  python scripts/auto-docs.py --changelog    # Nur CHANGELOG
  python scripts/auto-docs.py --skills       # Nur Skills-Index
  python scripts/auto-docs.py --cron         # Nur Cron-Status
        """,
    )
    parser.add_argument("--readme", action="store_true", help="README.md generieren")
    parser.add_argument("--changelog", action="store_true", help="CHANGELOG.md generieren")
    parser.add_argument("--skills", action="store_true", help="SKILLS-INDEX.md generieren")
    parser.add_argument("--cron", action="store_true", help="CRON-STATUS.md generieren")
    parser.add_argument("--all", action="store_true", help="Alle Dokumente generieren")
    parser.add_argument("--quiet", action="store_true", help="Nur Fehler ausgeben")

    args = parser.parse_args()

    # Wenn kein Argument, zeige Hilfe
    if not any([args.readme, args.changelog, args.skills, args.cron, args.all]):
        parser.print_help()
        sys.exit(0)

    generate_all = args.all
    if not args.quiet:
        print(f"\n🔧 OpenAmer Auto-Dokumentation Generator")
        print(f"   Repo:      {REPO_ROOT}")
        print(f"   Output:    {OUTPUT_DIR}")
        print(f"   Skills:    {SKILLS_DIR}")
        print(f"   Cron:      {CRON_JOBS_FILE}")
        print()

    # Projekt-Statistiken (einmal sammeln)
    stats = None
    if generate_all or args.readme:
        if not args.quiet:
            print("📊 Sammle Projekt-Statistiken...")
        stats = get_project_stats()

    # README
    if generate_all or args.readme:
        if not args.quiet:
            print("\n📄 Generiere README.md...")
        content = generate_readme(stats)
        write_doc("README.md", content, "README")

    # CHANGELOG
    if generate_all or args.changelog:
        if not args.quiet:
            print("📋 Generiere CHANGELOG.md...")
        content = generate_changelog()
        write_doc("CHANGELOG.md", content, "CHANGELOG")

    # Skills-Index
    if generate_all or args.skills:
        if not args.quiet:
            print("🧠 Generiere SKILLS-INDEX.md...")
        content = generate_skills_index()
        write_doc("SKILLS-INDEX.md", content, "Skills-Index")

    # Cron-Status
    if generate_all or args.cron:
        if not args.quiet:
            print("⏱ Generiere CRON-STATUS.md...")
        content = generate_cron_status()
        write_doc("CRON-STATUS.md", content, "Cron-Status")

    if not args.quiet:
        print(f"\n✅ Fertig! Alle Dokumente in {OUTPUT_DIR}")
        print(f"   ├── README.md")
        print(f"   ├── CHANGELOG.md")
        print(f"   ├── SKILLS-INDEX.md")
        print(f"   └── CRON-STATUS.md")


if __name__ == "__main__":
    main()