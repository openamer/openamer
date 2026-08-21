#!/usr/bin/env python3
"""
Commander v1.0 — Zentrale CLI-Steuerung für OpenAmer
====================================================
Einheitliche Kommandozentrale für alle 25+ existierenden Skripte:
  Subcommands, Status-Overview, Farben, Tabellen, Fortschrittsbalken.

CLI:
  python commander.py <subcommand> [args...]    # Route zum Skript
  python commander.py --status                  # Status aller Subsysteme
  python commander.py --help <subcommand>       # Spezifische Hilfe
  python commander.py --all                     # Alle --check/--status ausführen
  python commander.py --list                   # Alle Subcommands auflisten
  python commander.py --version                # Version anzeigen

Exit-Codes:
  0 = alles OK
  1 = einige Subsysteme haben Warnungen
  2 = einige Subsysteme haben Fehler
  3 = kritische Fehler
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── ANSI-Farben ──────────────────────────────────────────────────────────────

class Style:
    """ANSI-Farben und Stile kompatibel mit Windows 10+ und allen modernen Terminals."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"

    # 256-Farben-Modus für schöne Paletten
    @staticmethod
    def fg(code: int) -> str:
        return f"\033[38;5;{code}m"
    @staticmethod
    def bg(code: int) -> str:
        return f"\033[48;5;{code}m"

    # Benannte Farben
    RED = fg(196)
    GREEN = fg(82)
    YELLOW = fg(220)       # warmes Goldgelb
    ORANGE = fg(208)
    BLUE = fg(39)
    CYAN = fg(51)
    MAGENTA = fg(201)
    WHITE = fg(255)
    GRAY = fg(245)
    DARK_GRAY = fg(240)
    TEAL = fg(43)
    PINK = fg(205)

    # Hintergründe
    BG_RED = bg(52)
    BG_GREEN = bg(22)
    BG_YELLOW = bg(58)
    BG_BLUE = bg(18)
    BG_DARK = bg(235)

    # Symbole
    CHECK = f"{GREEN}✔{RESET}"
    CROSS = f"{RED}✘{RESET}"
    WARN = f"{YELLOW}⚠{RESET}"
    INFO = f"{BLUE}ℹ{RESET}"
    ARROW = f"{CYAN}→{RESET}"
    STAR = f"{YELLOW}★{RESET}"


# ─── Konfiguration ────────────────────────────────────────────────────────────

OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    str(Path.home() / "AppData" / "Local" / "openamer-laptop")
))
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
REPO_SCRIPTS_DIR = Path(__file__).parent.resolve()

VERSION = "1.0.0"
APP_NAME = f"{Style.BOLD}{Style.CYAN}OpenAmer Commander{Style.RESET}"


# ─── Subcommand-Definitionen ─────────────────────────────────────────────────

SUBCMDS: Dict[str, Dict[str, Any]] = {
    "security": {
        "script": "security-cve-scan.py",
        "desc": "CVE-Scan + Auto-Patching pip-Pakete via OSV.dev",
        "status_flag": "--check",
        "aliases": ["sec", "cve"],
        "color": Style.RED,
        "icon": "🔒",
        "category": "Sicherheit",
    },
    "perf": {
        "script": "perf-optimizer.py",
        "desc": "RAM/Disk/Cron-Performance-Optimierung",
        "status_flag": "--check",
        "aliases": ["performance", "optimize"],
        "color": Style.MAGENTA,
        "icon": "⚡",
        "category": "Optimierung",
    },
    "monitor": {
        "script": "resource-monitor.py",
        "desc": "Live-Monitor: CPU/RAM/DISK/NET + Top-Prozesse",
        "status_flag": "--once",
        "aliases": ["resources"],
        "color": Style.TEAL,
        "icon": "📊",
        "category": "Monitoring",
    },
    "test": {
        "script": "auto-test-runner.py",
        "desc": "Automatischer Test-Runner (Git-Diff + Priorisierung)",
        "aliases": ["tests", "testing"],
        "color": Style.GREEN,
        "icon": "🧪",
        "category": "Entwicklung",
    },
    "heal": {
        "script": "self-healer.py",
        "desc": "Self-Healing-Daemon: Log-Scan + Workarounds",
        "status_flag": "--check",
        "aliases": ["healing", "selfheal"],
        "color": Style.PINK,
        "icon": "🩹",
        "category": "Wartung",
    },
    "graph": {
        "script": "skill-knowledge-graph.py",
        "desc": "Skill-Knowledge-Graph: 630+ Skills + Vorschläge",
        "aliases": ["skillgraph", "knowledge"],
        "color": Style.MAGENTA,
        "icon": "🕸️",
        "category": "Wissen",
    },
    "cron": {
        "script": "smart-cron-scheduler.py",
        "desc": "Cron-Job-Analyse + optimierte Schedules",
        "status_flag": "--json",
        "aliases": ["scheduler", "jobs"],
        "color": Style.BLUE,
        "icon": "⏰",
        "category": "Automatisierung",
    },
    "crew": {
        "script": "crew-manager.py",
        "desc": "Multi-Agent-Crew: Dev/Tester/Reviewer/Architect",
        "aliases": ["agents"],
        "color": Style.CYAN,
        "icon": "👥",
        "category": "Agenten",
    },
    "dashboard": {
        "script": "dashboard-server.py",
        "desc": "Live-Web-Dashboard auf Port 8899 starten",
        "status_flag": "--status",
        "aliases": ["dash", "web"],
        "color": Style.YELLOW,
        "icon": "📈",
        "category": "UI",
    },
    "docs": {
        "script": "auto-docs.py",
        "desc": "Automatische Dokumentation: Git + Skills + Cron",
        "status_flag": "--check",
        "aliases": ["documentation", "doc"],
        "color": Style.BLUE,
        "icon": "📝",
        "category": "Wissen",
    },
    "sync": {
        "script": "cross-profile-sync.py",
        "desc": "Skills/Cron/Config zwischen Profilen syncen",
        "aliases": ["profiles", "crossprofile"],
        "color": Style.CYAN,
        "icon": "🔄",
        "category": "Verwaltung",
    },
    "voice": {
        "script": "voice-assistant.py",
        "desc": "KI-Sprachassistent: STT + TTS + Chat",
        "status_flag": "--list-voices",
        "aliases": ["speech", "audio"],
        "color": Style.PINK,
        "icon": "🎤",
        "category": "Interface",
    },
    "health": {
        "script": "predictive-health.py",
        "desc": "ML-Prädiktiv: Trend + Anomalie + Disk-Prognose",
        "status_flag": "--collect",
        "aliases": ["predict", "predhealth"],
        "color": Style.GREEN,
        "icon": "❤️",
        "category": "Monitoring",
    },
    "mesh": {
        "script": "agent-mesh.py",
        "desc": "Agent-Mesh: Master/Worker + HTTP-Delegation",
        "status_flag": "status",
        "aliases": ["cluster"],
        "color": Style.TEAL,
        "icon": "🌐",
        "category": "Agenten",
    },
    "review": {
        "script": "auto-code-review.py",
        "desc": "Auto-Code-Review: Security-Scan + Code-Qualität",
        "aliases": ["codereview", "audit"],
        "color": Style.ORANGE,
        "icon": "👁️",
        "category": "Entwicklung",
    },
    "backup": {
        "script": "auto-backup.py",
        "desc": "Automatisches Backup: Skills, Config, Cron, DB",
        "status_flag": "--check",
        "aliases": ["backups"],
        "color": Style.GREEN,
        "icon": "💾",
        "category": "Wartung",
    },
    "resource": {
        "script": "resource-monitor.py",
        "desc": "Alias für 'monitor' — auch hier direkt ansprechbar",
        "status_flag": "--once",
        "aliases": ["resources", "system"],
        "color": Style.TEAL,
        "icon": "🖥️",
        "category": "Monitoring",
    },
    "cache": {
        "script": "smart-cache.py",
        "desc": "Cache-Analyse + Cleanup + Skill-Archivierung",
        "status_flag": "--stats",
        "aliases": ["cleancache"],
        "color": Style.YELLOW,
        "icon": "🗄️",
        "category": "Optimierung",
    },
    "abtest": {
        "script": "ab-test-engine.py",
        "desc": "A/B-Test-Engine: Experimente für Skills + Config",
        "status_flag": "--collect",
        "aliases": ["ab", "experiment"],
        "color": Style.MAGENTA,
        "icon": "📊",
        "category": "Entwicklung",
    },
    "logs": {
        "script": "log-analyzer.py",
        "desc": "Log-Analyzer: Error-Rate + Pattern + Trend",
        "status_flag": "--scan",
        "aliases": ["log", "analyze"],
        "color": Style.CYAN,
        "icon": "📋",
        "category": "Wartung",
    },
    "env": {
        "script": "auto-env-checker.py",
        "desc": "Umgebungsprüfung: .env, config.yaml, Pfade, Git",
        "status_flag": "--check",
        "aliases": ["environment", "check"],
        "color": Style.BLUE,
        "icon": "🔧",
        "category": "Setup",
    },
    "traffic": {
        "script": "traffic-cop.py",
        "desc": "API-Key-Health + Rate-Limit-Rotation + Pool",
        "status_flag": "--check",
        "aliases": ["apikey", "ratelimit"],
        "color": Style.ORANGE,
        "icon": "🚦",
        "category": "Sicherheit",
    },
    "sessions": {
        "script": "smart-session-saver.py",
        "desc": "Session-Archivierung + Suche + Wiederherstellung",
        "aliases": ["session", "archive"],
        "color": Style.TEAL,
        "icon": "💬",
        "category": "Verwaltung",
    },
    "updater": {
        "script": "auto-updater.py",
        "desc": "Auto-Updater: Git, pip, Skill-Hub",
        "status_flag": "--status",
        "aliases": ["update", "upgrade"],
        "color": Style.GREEN,
        "icon": "🔄",
        "category": "Wartung",
    },
    "plugin": {
        "script": "plugin-manager.py",
        "desc": "Plugin-Verwaltung: Install, List, Remove, Update",
        "aliases": ["plugins"],
        "color": Style.CYAN,
        "icon": "🔌",
        "category": "Erweiterung",
    },
    "bugbot": {
        "script": "bugbot.py",
        "desc": "Bug-Bot: Issue-Tracking + Triage + Labels",
        "aliases": ["bugs", "issues"],
        "color": Style.RED,
        "icon": "🐛",
        "category": "Entwicklung",
    },
    "pr_approval": {
        "script": "pr_approval.py",
        "desc": "PR-Approval-Workflow: Review + Merge + CI-Check",
        "aliases": ["pr", "approval"],
        "color": Style.GREEN,
        "icon": "✅",
        "category": "Entwicklung",
    },
    "security_agent": {
        "script": "security_agent.py",
        "desc": "Security-Agent: CVE-Daemon + Patching-Workflow",
        "aliases": ["secagent", "secbot"],
        "color": Style.RED,
        "icon": "🛡️",
        "category": "Sicherheit",
    },
}

# Umgekehrte Alias-Tabelle
_ALIAS_MAP: Dict[str, str] = {}
for cmd, info in SUBCMDS.items():
    _ALIAS_MAP[cmd] = cmd
    for alias in info.get("aliases", []):
        _ALIAS_MAP[alias] = cmd

RESET = Style.RESET


# ─── Terminal-Hilfsfunktionen ────────────────────────────────────────────────

def term_width() -> int:
    """Terminal-Breite ermitteln (mit Fallback 80)."""
    return shutil.get_terminal_size(fallback=(80, 24)).columns


def title(text: str, char: str = "═", color: str = Style.CYAN) -> str:
    """Zentrierter Titel mit Linien."""
    w = term_width()
    available = max(0, w - len(text) - 4)
    left = available // 2
    right = available - left
    return f"{color}{char * left} {Style.BOLD}{text}{Style.RESET}{color} {char * right}{RESET}"


def heading(text: str, color: str = Style.CYAN) -> str:
    """Überschrift mit Terminator-Linie."""
    w = term_width()
    line = "─" * (w - len(text) - 2)
    return f"\n{color}{Style.BOLD}{text}{RESET} {Style.GRAY}{line}{RESET}"


def subheading(text: str) -> str:
    """Unterüberschrift."""
    return f"  {Style.BOLD}{text}{Style.RESET}"


def colored(text: str, color: str, bold: bool = False) -> str:
    """Farbe anwenden."""
    b = Style.BOLD if bold else ""
    return f"{b}{color}{text}{RESET}"


def status_symbol(code: int) -> str:
    """Exit-Code → Symbol."""
    if code == 0:
        return f" {Style.CHECK} "
    elif code == 1:
        return f" {Style.WARN} "
    elif code == 2:
        return f" {Style.CROSS} "
    else:
        return f" {Style.CROSS}{Style.CROSS} "


def status_text(code: int) -> str:
    """Exit-Code → Text."""
    if code == 0:
        return colored("OK", Style.GREEN, bold=True)
    elif code == 1:
        return colored("WARNUNG", Style.YELLOW, bold=True)
    elif code == 2:
        return colored("FEHLER", Style.RED, bold=True)
    else:
        return colored("KRITISCH", Style.RED, bold=True) + " " + colored("!!", Style.RED, bold=True)


def format_duration(seconds: float) -> str:
    """Sekunden → hh:mm:ss oder mm:ss."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}:{s:02d}"


# ─── Progress-Bar ────────────────────────────────────────────────────────────

class ProgressBar:
    """Terminal-Progress-Bar mit Farbe, Text, und ETA."""

    def __init__(self, total: int, prefix: str = "", width: int = 40):
        self.total = max(total, 1)
        self.prefix = prefix
        self.width = min(width, term_width() - 30)
        self.start_time = time.time()

    def update(self, current: int, suffix: str = ""):
        """Fortschritt aktualisieren und anzeigen."""
        elapsed = time.time() - self.start_time
        fraction = min(current / self.total, 1.0)
        filled = int(self.width * fraction)
        bar = "█" * filled + "░" * (self.width - filled)

        # ETA berechnen
        if current > 0:
            eta = elapsed / current * (self.total - current)
            eta_str = format_duration(eta)
        else:
            eta_str = "--:--"

        pct = fraction * 100
        elapsed_str = format_duration(elapsed)

        # Farbiger Bar-Text
        if fraction < 0.5:
            bar_color = Style.YELLOW
        elif fraction < 0.9:
            bar_color = Style.GREEN
        else:
            bar_color = Style.CYAN

        line = (
            f"\r{Style.DIM}{self.prefix}{RESET} "
            f"{bar_color}{bar}{RESET} "
            f"{Style.BOLD}{pct:5.1f}%{RESET} "
            f"{Style.GRAY}| {elapsed_str} | ETA {eta_str}{RESET}"
            f"  {Style.ITALIC}{suffix}{RESET}  "
        )
        # Rechts auffüllen für saubere Überschreibung
        w = term_width()
        if len(line) < w:
            line += " " * (w - len(line))
        sys.stdout.write(line)
        sys.stdout.flush()

    def finish(self, suffix: str = "Fertig!"):
        """Progress-Bar abschliessen."""
        self.update(self.total, suffix)
        sys.stdout.write("\n")


# ─── Tabellen ─────────────────────────────────────────────────────────────────

def table(rows: List[List[str]], headers: Optional[List[str]] = None,
          col_colors: Optional[List[Optional[str]]] = None) -> str:
    """Kompakte Tabelle mit variabler Spaltenbreite."""
    if not rows:
        return ""

    # Farben-Konfiguration
    if col_colors is None:
        col_colors = [None] * (len(headers) if headers else len(rows[0]))
    col_colors = col_colors + [None] * (max(0, len(rows[0]) - len(col_colors)))

    # Alle Zeilen + Header einbeziehen
    all_rows = []
    if headers:
        all_rows.append([colored(h, Style.WHITE, bold=True) for h in headers])
    all_rows.extend(rows)

    # Spaltenbreiten berechnen
    col_count = max(len(r) for r in all_rows)
    # Strip ANSI für Breitenberechnung
    def strip_ansi(s: str) -> str:
        return re.sub(r'\033\[[0-9;]*m', '', s)

    widths = [0] * col_count
    for r in all_rows:
        padded = r + [''] * (col_count - len(r))
        for i, cell in enumerate(padded):
            w = len(strip_ansi(cell))
            if w > widths[i]:
                widths[i] = w

    # Term-Breite begrenzen
    max_total = term_width() - col_count - 1
    total_width = sum(widths)
    if total_width > max_total:
        # Proportional schrumpfen, aber min 15 pro Spalte
        ratio = max_total / total_width
        widths = [max(15, int(w * ratio)) for w in widths]
        # Nachjustieren
        diff = max_total - sum(widths)
        if diff > 0:
            widths[-1] += diff

    # Trennzeile
    sep = " " + Style.GRAY + "─" * (sum(widths) + col_count - 1) + RESET

    lines = []
    for i, r in enumerate(all_rows):
        padded = r + [''] * (col_count - len(r))
        cells = []
        for j, cell in enumerate(padded):
            stripped = strip_ansi(cell)
            ansi_part = cell[:len(cell) - len(stripped)]
            w = widths[j]
            if j == 0 and i == 0:
                # Header: linksbündig
                cells.append(f" {ansi_part}{stripped.ljust(w)}")
            elif j == 0:
                cells.append(f" {colored(stripped.ljust(w), Style.WHITE) if col_colors[j] else ' ' + stripped.ljust(w)}")
            elif j >= len(col_colors) or col_colors[j] is None:
                cells.append(f" {stripped.rjust(w)}")
            elif col_colors[j]:
                cells.append(f" {colored(stripped.rjust(w), col_colors[j])}")
            else:
                cells.append(f" {stripped.rjust(w)}")
        line = "│".join(cells)
        lines.append(line)
        if i == 0 and headers:
            lines.append(sep)

    return "\n".join(lines)


# ─── Skript-Routing ──────────────────────────────────────────────────────────

def resolve_command(name: str) -> Optional[str]:
    """Alias → kanonischer Subcommand-Name."""
    return _ALIAS_MAP.get(name.lower())


def find_script_path(script_name: str) -> Optional[Path]:
    """Skript entweder in OPENAMER_HOME/scripts/ oder im Repo-Skripts-Ordner finden."""
    candidates = [
        SCRIPTS_DIR / script_name,
        REPO_SCRIPTS_DIR / script_name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def run_script(script_path: Path, args: List[str], timeout: int = 120) -> Tuple[int, str, float]:
    """Ein Skript ausführen und Exit-Code + Output zurückgeben."""
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return result.returncode, output.strip(), elapsed
    except subprocess.TimeoutExpired:
        return 124, f"⏱️ Timeout nach {timeout}s", time.time() - start
    except FileNotFoundError:
        return 127, f"📁 Skript nicht gefunden: {script_path}", time.time() - start
    except Exception as e:
        return 1, f"❌ Fehler: {e}", time.time() - start


def run_subcommand(cmd: str, extra_args: List[str]) -> int:
    """Ein Subcommand ausführen und Exit-Code zurückgeben."""
    info = SUBCMDS.get(cmd)
    if not info:
        print(f"{Style.CROSS} Unbekannter Befehl: {cmd}", file=sys.stderr)
        return 2

    script_name = info["script"]
    script_path = find_script_path(script_name)
    if not script_path:
        print(f"{Style.CROSS} Skript nicht gefunden: {script_name}", file=sys.stderr)
        print(f"  {Style.INFO} Gesucht in: {SCRIPTS_DIR} oder {REPO_SCRIPTS_DIR}")
        return 2

    # Subcommand-Header
    icon = info.get("icon", "⚙️")
    desc = info.get("desc", "")
    print(f"\n{title(f'{icon} {cmd.upper()} — {desc}', '─', info.get('color', Style.CYAN))}")

    exit_code, output, elapsed = run_script(script_path, extra_args)

    # Output anzeigen (gekürzt bei sehr langem Output)
    if output:
        lines = output.split("\n")
        MAX_LINES = 80
        if len(lines) > MAX_LINES:
            print("\n".join(lines[:MAX_LINES]))
            print(f"{Style.GRAY}... ({len(lines) - MAX_LINES} weitere Zeilen, gekürzt){RESET}")
        else:
            print(output)

    print(f"\n  {Style.GRAY}⏱️  {format_duration(elapsed)}  |  Exit: {exit_code}{RESET}")

    return exit_code


# ─── Status-Overview ──────────────────────────────────────────────────────────

def cmd_status() -> int:
    """--status: Übersicht über alle Subsysteme."""
    print(f"\n{title(f'{Style.STAR}  OpenAmer System-Status  {Style.STAR}', '═', Style.CYAN)}")
    print(f"  {Style.GRAY}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
          f"{len(SUBCMDS)} Subsysteme  |  v{VERSION}{RESET}\n")

    # Status-fähige Subcommands (haben --check, --status, oder ähnlich)
    status_cmds = [name for name, info in SUBCMDS.items() if info.get("status_flag")]

    if not status_cmds:
        print(f"  {Style.WARN} Keine Status-fähigen Subsysteme definiert.\n")
        return 0

    pb = ProgressBar(len(status_cmds), prefix="Status-Scan", width=30)

    results: List[Dict[str, Any]] = []
    for i, name in enumerate(status_cmds):
        info = SUBCMDS[name]
        flag = info["status_flag"]
        script_path = find_script_path(info["script"])

        pb.update(i + 1, f"{info['icon']} {name}")

        if not script_path:
            results.append({
                "name": name,
                "icon": info["icon"],
                "color": info.get("color", Style.WHITE),
                "exit_code": 127,
                "output": "Skript nicht gefunden",
                "elapsed": 0.0,
                "summary": "⚠️ Nicht gefunden",
            })
            continue

        exit_code, output, elapsed = run_script(script_path, [flag])

        # Summary extrahieren (letzte relevante Zeilen)
        summary = extract_summary(output, exit_code)

        results.append({
            "name": name,
            "icon": info["icon"],
            "color": info.get("color", Style.WHITE),
            "exit_code": exit_code,
            "output": output,
            "elapsed": elapsed,
            "summary": summary,
        })

    pb.finish("Analyse abgeschlossen")

    # ── Gesamt-Tabelle ──────────────────────────────────────────────────────
    print(f"\n{heading('Status-Übersicht', Style.CYAN)}\n")

    term_w = term_width()
    # Tabellenspalten: Icon + Name | Exit-Code | Summary | Dauer
    table_rows = []
    max_exit_code = 0
    for r in results:
        sym = status_symbol(r["exit_code"])
        status_txt = status_text(r["exit_code"])
        name_str = f"{r['icon']} {colored(r['name'], r['color'])}"
        dur = format_duration(r["elapsed"])
        table_rows.append([name_str, f"{sym} {status_txt}", r["summary"], dur])
        if r["exit_code"] > max_exit_code:
            max_exit_code = r["exit_code"]

    print(table(table_rows,
                headers=["Subsystem", "Status", "Letzte Meldung", "Dauer"],
                col_colors=[None, None, Style.GRAY, Style.GRAY]))
    print()

    # ── Zusammenfassung ────────────────────────────────────────────────────
    ok_count = sum(1 for r in results if r["exit_code"] == 0)
    warn_count = sum(1 for r in results if r["exit_code"] == 1)
    err_count = sum(1 for r in results if r["exit_code"] >= 2)
    not_found = sum(1 for r in results if r["exit_code"] == 127)

    total = len(results)
    summary_line = (
        f"  {Style.CHECK} {colored(str(ok_count), Style.GREEN, bold=True)} OK  "
        f"{Style.WARN} {colored(str(warn_count), Style.YELLOW, bold=True)} Warnungen  "
        f"{Style.CROSS} {colored(str(err_count), Style.RED, bold=True)} Fehler  "
    )
    if not_found:
        summary_line += f" {Style.WARN} {not_found} nicht gefunden"
    summary_line += f"  {Style.GRAY}| {Style.BOLD}{total}{RESET}{Style.GRAY} Subsysteme geprüft{RESET}"

    print(summary_line)

    # Gesamt-Exit-Code
    if err_count > 0 or not_found > 0:
        overall = 2
    elif warn_count > 0:
        overall = 1
    else:
        overall = 0

    print(f"  {Style.GRAY}Gesamtstatus: {status_text(overall)}{RESET}")
    print(f"\n{title('', '═', Style.DARK_GRAY)}")

    return overall


def extract_summary(output: str, exit_code: int) -> str:
    """Intelligente Summary aus Skript-Output extrahieren."""
    if not output:
        return status_text(exit_code)

    lines = output.strip().split("\n")

    # Letzte 3 Zeilen nach relevanten Infos durchsuchen
    tail = "\n".join(lines[-5:])

    # Nach JSON-Status suchen
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("{") and '"status"' in stripped:
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    s = data.get("status", "")
                    if s:
                        return s[:60]
            except (json.JSONDecodeError, ValueError):
                pass

    # Exit-Code-basierte Summary
    summaries = {
        0: "✅ Alles OK",
        1: "⚠️ Warnungen vorhanden",
        2: "❌ Fehler gefunden",
        3: "🚨 Kritisch!",
        124: "⏱️ Timeout",
        127: "📁 Nicht gefunden",
    }
    return summaries.get(exit_code, f"Exit-Code {exit_code}")


# ─── Hilfe ────────────────────────────────────────────────────────────────────

def cmd_help(subcommand: Optional[str] = None) -> int:
    """Hilfe anzeigen."""
    if subcommand:
        # Subcommand-spezifische Hilfe
        cmd = resolve_command(subcommand)
        if not cmd:
            print(f"{Style.CROSS} Unbekannter Subcommand: {subcommand}")
            print(f"  {Style.INFO} Verfügbare Subcommands: {', '.join(sorted(SUBCMDS.keys()))}")
            return 2

        info = SUBCMDS[cmd]
        icon = info.get("icon", "⚙️")
        print(f"\n{title(f'{icon} {cmd}', '─', info.get('color', Style.CYAN))}")
        print(f"  {Style.BOLD}{info['desc']}{Style.RESET}")
        print(f"  {Style.GRAY}Skript: {info['script']}{RESET}")
        aliases = info.get("aliases", [])
        if aliases:
            print(f"  {Style.GRAY}Aliase: {', '.join(aliases)}{RESET}")
        cat = info.get("category", "Allgemein")
        print(f"  {Style.GRAY}Kategorie: {cat}{RESET}")
        flag = info.get("status_flag")
        if flag:
            print(f"  {Style.GRAY}Status-Flag: {flag}{RESET}")
        print(f"\n  {Style.INFO}  Verwendung:")
        print(f"    {Style.BOLD}python commander.py {cmd}{RESET}  # Standard-Ausführung")
        for alias in aliases:
            print(f"    {Style.DIM}python commander.py {alias}{RESET}  # via Alias")
        print(f"    {Style.DIM}python commander.py --status{RESET}  # Alle Subsysteme prüfen")
        print(f"    {Style.DIM}python commander.py --all{RESET}     # Alle --check/--status ausführen")
        print()
    else:
        # Allgemeine Hilfe
        print(f"\n{title(APP_NAME, '═', Style.CYAN)}")
        print(f"  {Style.GRAY}Version {VERSION} — Zentrale CLI-Steuerung für OpenAmer{RESET}")
        print(f"  {Style.GRAY}Mehr als 25 Subcommands, farbige Tabellen, Fortschrittsbalken{RESET}\n")

        print(f"  {Style.BOLD}VERWENDUNG:{RESET}")
        print(f"    python commander.py <subcommand> [args...]")
        print(f"    python commander.py --status")
        print(f"    python commander.py --all")
        print(f"    python commander.py --help <subcommand>")
        print(f"    python commander.py --list")
        print(f"    python commander.py --version\n")

        # Subcommands nach Kategorie gruppiert
        print(f"  {Style.BOLD}SUBCOMMANDS:{RESET}\n")

        categories: Dict[str, List[Tuple[str, str, str]]] = {}
        for cmd, info in sorted(SUBCMDS.items()):
            cat = info.get("category", "Allgemein")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((cmd, info["desc"], info.get("color", Style.WHITE)))

        for cat in sorted(categories.keys()):
            cmds = categories[cat]
            cat_color = {
                "Sicherheit": Style.RED,
                "Optimierung": Style.MAGENTA,
                "Monitoring": Style.TEAL,
                "Entwicklung": Style.GREEN,
                "Wartung": Style.PINK,
                "Wissen": Style.BLUE,
                "Automatisierung": Style.BLUE,
                "Agenten": Style.CYAN,
                "UI": Style.YELLOW,
                "Verwaltung": Style.CYAN,
                "Interface": Style.PINK,
                "Setup": Style.BLUE,
                "Erweiterung": Style.CYAN,
            }.get(cat, Style.WHITE)

            print(f"  {cat_color}{Style.UNDERLINE}{cat}{RESET}")
            for cmd, desc, color in cmds:
                icon = SUBCMDS[cmd].get("icon", " ")
                print(f"    {color}{icon}{RESET}  {Style.BOLD}{cmd:<18}{RESET}  {Style.GRAY}{desc}{RESET}")
            print()

        print(f"  {Style.BOLD}OPTIONEN:{RESET}")
        print(f"    {Style.BOLD}--status{RESET}        Status aller Subsysteme auf einen Blick")
        print(f"    {Style.BOLD}--all{RESET}           Alle --check/--status Befehle nacheinander")
        print(f"    {Style.BOLD}--help <cmd>{RESET}    Detail-Hilfe für einen Subcommand")
        print(f"    {Style.BOLD}--list{RESET}          Alle Subcommands auflisten")
        print(f"    {Style.BOLD}--version{RESET}       Version anzeigen\n")

        print(f"  {Style.BOLD}BEISPIELE:{RESET}")
        print(f"    python commander.py env --check")
        print(f"    python commander.py security --check")
        print(f"    python commander.py status")
        print(f"    python commander.py --all")
        print(f"    python commander.py dashboard start")
        print(f"    python commander.py --help updater")
        print(f"\n{title('', '═', Style.DARK_GRAY)}")

    return 0


# ─── Alle ausführen ──────────────────────────────────────────────────────────

def cmd_all() -> int:
    """--all: Alle --check/--status Subcommands nacheinander ausführen."""
    print(f"\n{title(f'{Style.STAR}  Kompletter System-Check  {Style.STAR}', '═', Style.CYAN)}")
    print(f"  {Style.GRAY}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
          f"Führe alle Status-fähigen Subsysteme aus...{RESET}\n")

    status_cmds = sorted(
        (name for name, info in SUBCMDS.items() if info.get("status_flag")),
        key=lambda n: SUBCMDS[n].get("category", "")
    )

    if not status_cmds:
        print(f"  {Style.WARN} Keine Status-fähigen Subsysteme definiert.\n")
        return 0

    total = len(status_cmds)
    results: List[Dict[str, Any]] = []
    exit_codes = []

    for i, name in enumerate(status_cmds):
        info = SUBCMDS[name]
        flag = info["status_flag"]
        script_path = find_script_path(info["script"])
        icon = info.get("icon", "⚙️")

        # Fortschritt anzeigen
        print(f"\n{Style.DARK_GRAY}[{i+1}/{total}]{RESET} {icon} {colored(name.upper(), info.get('color', Style.WHITE), bold=True)} ...")

        if not script_path:
            print(f"  {Style.CROSS} Skript nicht gefunden: {info['script']}")
            results.append({"name": name, "icon": icon, "color": info.get("color", Style.WHITE),
                          "exit_code": 127, "output": "", "elapsed": 0.0, "summary": "Nicht gefunden"})
            exit_codes.append(2)
            continue

        exit_code, output, elapsed = run_script(script_path, [flag])
        exit_codes.append(exit_code)

        # Output (gekürzt)
        if output:
            lines = output.strip().split("\n")
            MAX_OUT = 20
            if len(lines) > MAX_OUT:
                print("\n".join(lines[:MAX_OUT]))
                print(f"  {Style.GRAY}... ({len(lines) - MAX_OUT} weitere Zeilen){RESET}")
            else:
                print(output)

        sym = status_symbol(exit_code)
        print(f"  {sym} Exit: {exit_code}  |  {format_duration(elapsed)}")

        results.append({"name": name, "icon": icon, "color": info.get("color", Style.WHITE),
                      "exit_code": exit_code, "output": output, "elapsed": elapsed,
                      "summary": extract_summary(output, exit_code)})

    # ── Abschluss-Table ─────────────────────────────────────────────────────
    print(f"\n{heading('Endergebnis', Style.CYAN)}\n")
    table_rows = []
    for r in results:
        name_str = f"{r['icon']} {colored(r['name'], r['color'])}"
        sym = status_symbol(r["exit_code"])
        st = status_text(r["exit_code"])
        table_rows.append([name_str, f"{sym} {st}", r["summary"], format_duration(r["elapsed"])])

    print(table(table_rows,
                headers=["Subsystem", "Status", "Letzte Meldung", "Dauer"],
                col_colors=[None, None, Style.GRAY, Style.GRAY]))
    print()

    # Gesamt
    ok = sum(1 for r in results if r["exit_code"] == 0)
    warn = sum(1 for r in results if r["exit_code"] == 1)
    err = sum(1 for r in results if r["exit_code"] >= 2)
    overall = 2 if err > 0 else (1 if warn > 0 else 0)

    print(f"  {Style.CHECK} {colored(str(ok), Style.GREEN)} OK  "
          f"{Style.WARN} {colored(str(warn), Style.YELLOW)} Warnungen  "
          f"{Style.CROSS} {colored(str(err), Style.RED)} Fehler  "
          f"| {total} geprüft")

    print(f"  Gesamtstatus: {status_text(overall)}")
    print(f"\n{title('', '═', Style.DARK_GRAY)}")

    return overall


# ─── Liste ────────────────────────────────────────────────────────────────────

def cmd_list() -> int:
    """--list: Alle Subcommands auflisten."""
    print(f"\n{title('Verfügbare Subcommands', '─', Style.CYAN)}\n")

    categories: Dict[str, List[Tuple[str, str, str]]] = {}
    for cmd, info in sorted(SUBCMDS.items()):
        cat = info.get("category", "Allgemein")
        if cat not in categories:
            categories[cat] = []
        icon = info.get("icon", " ")
        categories[cat].append((cmd, info["desc"], info.get("color", Style.WHITE), icon))

    for cat in sorted(categories.keys()):
        cmds = categories[cat]
        cat_color = Style.CYAN
        print(f"  {cat_color}{Style.UNDERLINE}{cat}{RESET}")
        for cmd, desc, color, icon in cmds:
            aliases = SUBCMDS[cmd].get("aliases", [])
            alias_str = f" ({', '.join(aliases[:3])})" if aliases else ""
            print(f"    {color}{icon}{RESET}  {Style.BOLD}{cmd:<18}{RESET}  {Style.GRAY}{desc}{RESET}{Style.DIM}{alias_str}{RESET}")
        print()

    print(f"  {Style.GRAY}Total: {len(SUBCMDS)} Subcommands{RESET}")
    print(f"\n{title('', '─', Style.DARK_GRAY)}")
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OpenAmer Commander — Zentrale CLI-Steuerung",
        add_help=False,
    )
    parser.add_argument("command", nargs="*", help="Subcommand oder Option")
    parser.add_argument("--status", action="store_true", help="Status aller Subsysteme")
    parser.add_argument("--all", action="store_true", help="Alle --check/--status ausführen")
    parser.add_argument("--help", nargs="?", const=None, default=None,
                        dest="help_cmd", metavar="SUBCOMMAND", help="Hilfe zu einem Subcommand")
    parser.add_argument("--list", action="store_true", help="Alle Subcommands auflisten")
    parser.add_argument("--version", action="store_true", help="Version anzeigen")

    args, extra = parser.parse_known_args()

    # ── Flags auswerten ────────────────────────────────────────────────────
    if args.version:
        print(f"{APP_NAME} v{VERSION}")
        return 0

    if args.list:
        return cmd_list()

    if args.help_cmd is not None:
        return cmd_help(args.help_cmd)

    if args.status:
        return cmd_status()

    if args.all:
        return cmd_all()

    # ── Subcommand? ────────────────────────────────────────────────────────
    if args.command:
        raw_cmd = args.command[0]
        cmd_args = args.command[1:] + extra

        cmd = resolve_command(raw_cmd)
        if cmd:
            return run_subcommand(cmd, cmd_args)
        else:
            print(f"{Style.CROSS} Unbekannter Befehl: {raw_cmd}")
            print(f"  {Style.INFO} 'python commander.py --list' zeigt alle Befehle")
            print(f"  {Style.INFO} 'python commander.py --help' zeigt Hilfe")
            return 2

    # ── Kein Argument → Hilfe ──────────────────────────────────────────────
    return cmd_help(None)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Style.WARN} Abgebrochen durch Benutzer{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Style.CROSS} Unerwarteter Fehler: {e}", file=sys.stderr)
        sys.exit(3)