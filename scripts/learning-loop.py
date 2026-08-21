#!/usr/bin/env python3
"""
Continuous Learning Loop — Fehler-Capture + Kategorisierung + Memory + Skill-Generierung + Trend

Scannt Logs nach Fehlern, kategorisiert sie, speichert in Memory, schlägt bei
wiederkehrenden Mustern automatisch neue Skills vor und zeigt Trends an.

CLI:
  --capture          Sammelt neue Fehler aus Logs
  --analyze          Kategorisiert + Memory-Update
  --suggest          Zeigt neue Skills/Vorschläge
  --trend            Verbesserungs-Trend
  --report [json|html]  Generiert Bericht (default: html)
  --auto             Full Cycle: capture → analyze → suggest

Exit-Codes:
  0 = alles stabil
  1 = neue Muster erkannt
  2 = neue Skills vorgeschlagen
"""

import os
import sys
import json
import re
import shutil
import hashlib
import datetime
import textwrap
import html as html_mod
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple

# ── Konfiguration ────────────────────────────────────────────────────────────
# HOME = OpenAmer-Installationsverzeichnis
# Auf Windows: C:\Users\<user>\AppData\Local\openamer-laptop
# In MSYS/git-bash: /c/Users/<user>/AppData/Local/openamer-laptop

def _resolve_home() -> Path:
    """Ermittle das OpenAmer-Home-Verzeichnis robust (Windows/MSYS-kompatibel)."""
    # 1. Standard-Pfad aus HOME + AppData
    user_home = Path.home()
    candidates = [
        user_home / "AppData/Local/openamer-laptop",
        Path("C:/Users/damir/AppData/Local/openamer-laptop"),
        Path("/c/Users/damir/AppData/Local/openamer-laptop"),
        Path.home() / "openamer-laptop",
    ]
    # 2. OPENAMER_HOME Umgebungsvariable (MSYS-korrigiert)
    env_home = os.environ.get("OPENAMER_HOME")
    if env_home:
        # MSYS2 gibt /c/... — Path() kann das nicht, also korrigieren
        env_fixed = re.sub(r"^/([a-zA-Z])/", r"\1:/", env_home)
        candidates.insert(0, Path(env_fixed))

    for c in candidates:
        try:
            if c.exists() and (c / "config.yaml").exists():
                return c.resolve()
        except (OSError, RuntimeError):
            continue
    # Fallback: user_home / AppData/Local/openamer-laptop
    return user_home / "AppData/Local/openamer-laptop"

HOME = _resolve_home()
LOGS_DIR = HOME / "logs"
CRON_OUTPUT_DIR = HOME / "cron/output"
SELF_HEALER_DIR = HOME / ".self-healer"
MEMORY_DIR = HOME / ".learning-loop"
MEMORY_FILE = MEMORY_DIR / "memory.json"
TREND_FILE = MEMORY_DIR / "trend.json"
METRICS_FILE = MEMORY_DIR / "metrics.json"
SKILLS_DIR = HOME / "skills"
REPORT_FILE = MEMORY_DIR / "learning-loop-report.html"

# Exit-Codes
EXIT_STABLE = 0
EXIT_NEW_PATTERNS = 1
EXIT_NEW_SKILLS = 2

# Fehler-Kategorien mit Regex-Mustern
ERROR_CATEGORIES = {
    "import_error": [
        r"ImportError", r"ModuleNotFoundError", r"cannot import name",
        r"No module named", r"ModuleNotFound",
    ],
    "connection_failed": [
        r"ConnectionError", r"Connection refused", r"connection refused",
        r"getaddrinfo failed", r"connect_tcp", r"ConnectError",
        r"connection.*failed", r"Network.*unreachable", r"timeout.*connect",
        r"ECONNREFUSED", r"ENETUNREACH", r"ETIMEDOUT",
    ],
    "timeout": [
        r"Timeout", r"timeout", r"timed out", r"ReadTimeout",
        r"TimeoutError", r"DeadlineExceeded", r"Deadline Exceeded",
    ],
    "permission": [
        r"PermissionError", r"Permission denied", r"Access denied",
        r"EACCES", r"EPERM", r"schreibgeschützt", r"zugriff verweigert",
    ],
    "syntax_error": [
        r"SyntaxError", r"JSONDecodeError", r"json.*parse error",
        r"YAML.*error", r"Unexpected token", r"unclosed group",
        r"regex parse error", r"invalid syntax",
    ],
    "file_not_found": [
        r"FileNotFoundError", r"File not found", r"No such file",
        r"cannot find.*path", r"IO error for operation",
        r"kann den angegebenen Pfad nicht finden", r"kann die angegebene Datei nicht finden",
    ],
    "api_error": [
        r"HTTP Error", r"404", r"500", r"502", r"503",
        r"HTTP response", r"API.*error", r"endpoint.*failed",
        r"No endpoints found", r"NotFoundError",
    ],
    "provider_error": [
        r"provider.*unhealthy", r"marking.*unhealthy", r"payment.*error",
        r"credit error", r"authentication failed", r"auth.*failed",
        r"API key", r"no.*provider configured", r"provider",
    ],
    "memory_error": [
        r"MemoryError", r"OutOfMemory", r"CUDA.*out of memory",
        r"not enough memory", r"RAM.*limit",
    ],
    "cua_driver_error": [
        r"cua-driver", r"computer_use.*failed", r"capture failed",
        r"session has ended", r"list_windows failed",
    ],
    "tool_error": [
        r"tool.*returned error", r"Tool.*error", r"tool.*failed",
        r"execute_code.*BLOCKED", r"Refusing.*curator",
    ],
    "lsp_error": [
        r"lsp\[", r"pyright.*error", r"spawn.*failed",
        r"Win32-Anwendung", r"FileNotFoundError",
    ],
    "unknown": [],
}


def ensure_dirs():
    """Erstelle benötigte Verzeichnisse."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


# ── Capture ──────────────────────────────────────────────────────────────────

def scan_file(path: Path, max_size_mb: int = 50) -> List[Dict]:
    """Scanne eine Log-Datei nach Fehlern."""
    if not path.exists() or not path.is_file():
        return []
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            print(f"  ⚠  {path.name}: {size_mb:.1f} MB — zu groß, überspringe")
            return []
    except OSError:
        return []

    errors = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠  {path.name}: Konnte nicht lesen ({e})")
        return []

    lines = text.split("\n")
    error_block = []
    in_traceback = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Traceback start
        if "Traceback (most recent call last)" in stripped:
            in_traceback = True
            error_block = [line]
            continue

        if in_traceback:
            error_block.append(line)
            # Ende eines Tracebacks: leerzeile, neuer Eintrag oder ...
            is_exception = re.match(
                r"^(?!\s+)(\w+\.)*\w+(Error|Exception|Warning):", stripped
            )
            if is_exception or (not stripped and len(error_block) > 1):
                # Letzte Zeile enthält den Fehler
                if is_exception:
                    error_block.append(line)
                errors.append({
                    "type": "traceback",
                    "lines": error_block,
                    "text": "\n".join(error_block[-5:]),
                    "line": i + 1,
                })
                error_block = []
                in_traceback = False
                continue

        # Einzelne ERROR/WARNING Einträge (ausserhalb Tracebacks)
        if re.search(r"\b(ERROR|WARNING)\b", stripped) and not in_traceback:
            if re.search(r"(error|exception|failed|unhealthy|unavailable)", stripped.lower()):
                errors.append({
                    "type": "log_entry",
                    "lines": [line],
                    "text": stripped,
                    "line": i + 1,
                })

    # Offenen Traceback sichern
    if in_traceback and error_block:
        errors.append({
            "type": "traceback",
            "lines": error_block,
            "text": "\n".join(error_block[-5:]),
            "line": len(lines),
        })

    return errors


def extract_patterns(errors: List[Dict]) -> List[Dict]:
    """Extrahiere wiedererkennbare Fehler-Patterns aus rohen Fehlern."""
    patterns = []

    for err in errors:
        text = err.get("text", "")
        line = err.get("line", 0)
        lines = err.get("lines", [])

        # Kategorie bestimmen
        category = classify_error(text)

        # Fingerprint (normalisierter Hash)
        fingerprint = make_fingerprint(text)

        # Lösung extrahieren (falls bekannt)
        solution = suggest_solution(text, category)

        # Skill-Vorschlag (generic description)
        skill_suggestion = make_skill_suggestion(text, category)

        patterns.append({
            "fingerprint": fingerprint,
            "category": category,
            "raw_text": text[:500],
            "error_line": line,
            "solution": solution,
            "skill_suggestion": skill_suggestion,
            "timestamp": datetime.datetime.now().isoformat(),
        })

    return patterns


def classify_error(text: str) -> str:
    """Klassifiziere einen Fehlertext in eine Kategorie."""
    for category, patterns in ERROR_CATEGORIES.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return category
    # Fallback: Tool-Ergebnis-Fehler erkennen
    if '"error"' in text and '"success": false' in text:
        return "tool_error"
    if "execute_code" in text or "BLOCKED" in text:
        return "tool_error"
    return "unknown"


def make_fingerprint(text: str) -> str:
    """Normalisiere Fehlertext zu einem wiedererkennbaren Fingerprint."""
    # Entferne Zeilennummern, Pfade, Timestamps, IDs
    normalized = re.sub(r"line \d+", "line N", text, flags=re.IGNORECASE)
    normalized = re.sub(r"[A-Z]:\\[^:\s\\]+(?:\\[^:\s\\]+)*", "<PATH>", normalized)
    normalized = re.sub(r"/[^\s:]+/[^\s:]+", "<PATH>", normalized)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<TS>", normalized)
    normalized = re.sub(r"\d{8}_\d{6}_[a-f0-9]+", "<SESSION>", normalized)
    normalized = re.sub(r"[a-f0-9]{8,}", "<HASH>", normalized)
    normalized = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "<IP>", normalized)
    # Nimm nur die ersten 200 Zeichen
    normalized = normalized[:200]
    return hashlib.md5(normalized.encode()).hexdigest()


def suggest_solution(text: str, category: str) -> str:
    """Schlage eine Lösung basierend auf Kategorie und Text vor."""
    solutions = {
        "import_error": (
            "Installiere das fehlende Paket: `uv pip install <package>` "
            "oder `pip install <package>`. Prüfe ob der Import-Pfad stimmt."
        ),
        "connection_failed": (
            "Prüfe Internetverbindung, Firewall und ob der Dienst läuft. "
            "Bei API-Endpunkten: URL und Port prüfen."
        ),
        "timeout": (
            "Erhöhe das Timeout in der Konfiguration. Prüfe ob der Dienst "
            "antwortet oder die Netzwerkverbindung instabil ist."
        ),
        "permission": (
            "Prüfe Dateiberechtigungen (chmod/icacls). Führe ggf. mit Admin-"
            "Rechten aus. Prüfe ob die Datei von einem anderen Prozess gesperrt ist."
        ),
        "syntax_error": (
            "Prüfe JSON/YAML auf Syntax-Fehler. Nutze `python -m json.tool` "
            "oder einen Validator. Bei Regex: Sonderzeichen escapen."
        ),
        "file_not_found": (
            "Prüfe ob der Pfad existiert. Bei relativen Pfaden: Arbeitsverzeichnis "
            "prüfen. Bei OpenAmer: `HOME` Umgebungsvariable prüfen."
        ),
        "api_error": (
            "Prüfe ob der API-Endpunkt erreichbar ist. Bei 404: URL prüfen. "
            "Bei 5xx: Server-Status prüfen, ggf. später wiederholen."
        ),
        "provider_error": (
            "API-Key prüfen und ggf. erneuern. Prüfe Kontostand/Abonnement. "
            "Bei Provider-unhealthy: warte 60s oder wechsle Provider."
        ),
        "memory_error": (
            "Reduziere Speichernutzung (Batch-Größe, Context-Länge). "
            "Schließe andere Anwendungen. Prüfe RAM-Auslastung."
        ),
        "cua_driver_error": (
            "Starte cua-driver neu: `openamer computer-use doctor` für Diagnose. "
            "Prüfe ob der Session-Status gültig ist."
        ),
        "tool_error": (
            "Prüfe die Tool-Parameter. Bei execute_code-Blockade: Cron-Job hat "
            "keine execute_code-Rechte — nutze terminal() stattdessen."
        ),
        "lsp_error": (
            "Prüfe ob pyright/typescript installiert ist. "
            "Bei Win32-Fehlern: node-Version prüfen (x64?). "
            "`pip install pyright` oder `npm install -g pyright`."
        ),
    }
    return solutions.get(category, "Manuelle Analyse erforderlich.")


def make_skill_suggestion(text: str, category: str) -> str:
    """Generiere einen Skill-Namen und eine Beschreibung."""
    base = {
        "import_error": "Fix ImportError für fehlende Python-Pakete",
        "connection_failed": "Diagnose und Behebung von Verbindungsfehlern",
        "timeout": "Timeout-Fehler beheben und Timeout-Werte erhöhen",
        "permission": "Datei- und Berechtigungsprobleme lösen",
        "syntax_error": "JSON/YAML/Regex-Syntax-Fehler validieren und reparieren",
        "file_not_found": "Fehlende Dateien und Pfad-Probleme diagnostizieren",
        "api_error": "API-Endpunkt-Fehler behandeln (HTTP 4xx/5xx)",
        "provider_error": "Provider/API-Key-Probleme diagnostizieren und beheben",
        "memory_error": "Speicher-Engpässe erkennen und optimieren",
        "cua_driver_error": "cua-driver-Fehler diagnostizieren und neu starten",
        "tool_error": "Tool-Ausführungsfehler beheben und Parameter prüfen",
        "lsp_error": "LSP/IDE-Tooling-Fehler diagnostizieren",
    }
    desc = base.get(category, f"Behebung von {category}-Fehlern")
    name = f"fix-{category}"
    return {"name": name, "description": desc}


# ── Memory ───────────────────────────────────────────────────────────────────

def load_memory() -> Dict:
    """Lade Memory aus memory.json."""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"patterns": {}, "solutions": {}, "skills_generated": []}


def save_memory(memory: Dict):
    """Speichere Memory in memory.json."""
    MEMORY_FILE.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def update_memory(memory: Dict, patterns: List[Dict]) -> Dict:
    """Aktualisiere Memory mit neuen Patterns."""
    now = datetime.datetime.now().isoformat()
    new_patterns_detected = 0

    existing = memory.get("patterns", {})
    solutions = memory.get("solutions", {})

    for p in patterns:
        fp = p["fingerprint"]
        cat = p["category"]

        if fp in existing:
            existing[fp]["count"] += 1
            existing[fp]["last_seen"] = now
            existing[fp]["recent_text"] = p["raw_text"]
        else:
            existing[fp] = {
                "fingerprint": fp,
                "category": cat,
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "raw_text": p["raw_text"],
                "solution": p["solution"],
                "skill_suggestion": p["skill_suggestion"],
                "fixed": False,
            }
            new_patterns_detected += 1

        # Lösung speichern falls vorhanden
        if p["solution"] and fp not in solutions:
            solutions[fp] = p["solution"]

    memory["patterns"] = existing
    memory["solutions"] = solutions
    memory["last_analyzed"] = now
    memory["total_errors_seen"] = sum(e["count"] for e in existing.values())
    memory["unique_patterns"] = len(existing)
    memory["new_patterns_last_run"] = new_patterns_detected

    save_memory(memory)
    return memory


# ── Skill-Generierung ────────────────────────────────────────────────────────

def generate_skills(memory: Dict) -> List[Dict]:
    """Generiere Skill-Vorschläge für Patterns mit count > 3."""
    suggestions = []
    skills_dir = SKILLS_DIR / "learning-loop"
    skills_dir.mkdir(parents=True, exist_ok=True)

    patterns = memory.get("patterns", {})
    generated = memory.setdefault("skills_generated", [])
    seen_names = set()

    # Sammle existierende Skill-Namen
    for f in skills_dir.glob("*.md"):
        seen_names.add(f.stem)
    for f in SKILLS_DIR.glob("*/SKILL.md"):
        seen_names.add(f.parent.name)

    for fp, data in patterns.items():
        if data["count"] < 4 or data.get("fixed", False):
            continue
        # Prüfe ob Fingerprint bereits generiert
        if fp in generated:
            continue

        suggestion = data.get("skill_suggestion", {})
        if not suggestion:
            continue

        name = suggestion.get("name", f"fix-{data['category']}")
        # Prüfe ob Skill-Name bereits existiert
        if name in seen_names:
            generated.append(fp)  # als generiert markieren, damit er nicht neu vorgeschlagen wird
            continue

        seen_names.add(name)
        suggestions.append({
            "fingerprint": fp,
            "category": data["category"],
            "name": name,
            "description": suggestion.get("description", f"Behebung von {data['category']}-Fehlern"),
            "solution": data.get("solution", ""),
            "raw_text": data.get("raw_text", ""),
        })

    return suggestions


def write_skill_file(name: str, description: str, solution: str, category: str, raw_text: str):
    """Schreibe eine SKILL.md-Datei."""
    category_dir = SKILLS_DIR / "learning-loop"
    category_dir.mkdir(parents=True, exist_ok=True)

    path = category_dir / f"{name}.md"

    if path.exists():
        return False

    escaped_text = textwrap.shorten(raw_text.replace("`", ""), width=300, placeholder="...")

    content = f"""---
description: Use when {description.lower()}. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# {description}

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `{category}`):

```
{escaped_text}
```

## Lösung

{solution}

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
"""

    path.write_text(content, encoding="utf-8")
    return True


# ── Capture-Module ───────────────────────────────────────────────────────────

def scan_log_files() -> List[Dict]:
    """Scanne alle relevanten Log-Quellen nach Fehlern."""
    all_errors = []
    sources = []

    # 1. errors.log
    if (LOGS_DIR / "errors.log").exists():
        sources.append(LOGS_DIR / "errors.log")
    # 2. agent.log (nur die letzen 5000 Zeilen)
    agent_log = LOGS_DIR / "agent.log"
    if agent_log.exists():
        sources.append(agent_log)
    # 3. desktop.log
    desktop_log = LOGS_DIR / "desktop.log"
    if desktop_log.exists():
        sources.append(desktop_log)
    # 4. gui.log
    gui_log = LOGS_DIR / "gui.log"
    if gui_log.exists():
        sources.append(gui_log)

    # 5. Cron-Outputs (letzte 10)
    if CRON_OUTPUT_DIR.exists():
        cron_files = sorted(CRON_OUTPUT_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)[:10]
        sources.extend(cron_files)

    # 6. self-healer files
    if SELF_HEALER_DIR.exists():
        healer_files = sorted(SELF_HEALER_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)[:5]
        sources.extend(healer_files)

    skipped = 0
    for src in sources:
        try:
            errors = scan_file(src, max_size_mb=20)
            if errors:
                print(f"  ✓ {src.name}: {len(errors)} Fehler gefunden")
            all_errors.extend(errors)
        except Exception as e:
            print(f"  ⚠  {src.name}: Fehler beim Scannen ({e})")
            skipped += 1

    if not all_errors:
        print("  ℹ  Keine neuen Fehler gefunden")
    else:
        print(f"  ℹ  Insgesamt {len(all_errors)} Fehler aus {len(sources)} Quellen")

    return all_errors


# ── Trend / Metriken ─────────────────────────────────────────────────────────

def load_metrics() -> Dict:
    """Lade Metrik-Historie."""
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"snapshots": [], "categories_over_time": {}}


def save_metrics(metrics: Dict):
    """Speichere Metrik-Historie."""
    METRICS_FILE.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def update_metrics(memory: Dict):
    """Aktualisiere Metrik-Historie mit aktuellem Snapshot."""
    metrics = load_metrics()
    now = datetime.datetime.now().isoformat()

    patterns = memory.get("patterns", {})
    by_category = Counter()
    total = 0
    fixed = 0

    for data in patterns.values():
        cat = data.get("category", "unknown")
        by_category[cat] += data.get("count", 0)
        total += data.get("count", 0)
        if data.get("fixed", False):
            fixed += 1

    snapshot = {
        "timestamp": now,
        "total_errors": total,
        "unique_patterns": memory.get("unique_patterns", 0),
        "fixed_patterns": fixed,
        "fix_rate": round(fixed / max(len(patterns), 1), 3),
        "by_category": dict(by_category),
        "new_patterns": memory.get("new_patterns_last_run", 0),
    }

    # Snapshot an Metrik-Historie anhängen
    metrics["snapshots"].append(snapshot)

    # Kategorien über Zeit
    for cat, count in by_category.items():
        if cat not in metrics["categories_over_time"]:
            metrics["categories_over_time"][cat] = []
        metrics["categories_over_time"][cat].append({
            "timestamp": now,
            "count": count,
        })

    # Max 100 Snapshots behalten
    if len(metrics["snapshots"]) > 100:
        metrics["snapshots"] = metrics["snapshots"][-100:]

    save_metrics(metrics)
    return metrics


def compute_trend(metrics: Dict) -> Dict:
    """Berechne Trend-Daten aus Metrik-Historie."""
    snapshots = metrics.get("snapshots", [])
    if len(snapshots) < 2:
        return {"status": "insufficient_data", "data_points": len(snapshots)}

    first = snapshots[0]
    last = snapshots[-1]

    total_change = last["total_errors"] - first["total_errors"]
    fix_rate_change = last["fix_rate"] - first["fix_rate"]

    # Fehler pro Stunde (letzten 24h)
    recent = [s for s in snapshots if s["timestamp"] > (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()]
    errors_per_hour = len(recent) / max(24, 1)

    # Top-Kategorien
    by_category = Counter()
    for s in snapshots[-10:]:
        for cat, count in s.get("by_category", {}).items():
            by_category[cat] += count

    top_categories = by_category.most_common(5)

    return {
        "status": "ok",
        "data_points": len(snapshots),
        "total_error_change": total_change,
        "fix_rate_change": fix_rate_change,
        "current_fix_rate": last["fix_rate"],
        "errors_per_hour_last_24h": round(errors_per_hour, 2),
        "top_categories": [{"name": c, "count": n} for c, n in top_categories],
        "last_snapshot": last,
        "first_snapshot": first,
    }


# ── Report ───────────────────────────────────────────────────────────────────

def generate_html_report(memory: Dict, trend: Dict) -> str:
    """Generiere einen HTML-Report."""
    patterns = memory.get("patterns", {})
    total = memory.get("total_errors_seen", 0)
    unique = memory.get("unique_patterns", 0)
    fixed = sum(1 for d in patterns.values() if d.get("fixed", False))
    fix_rate = round(fixed / max(len(patterns), 1) * 100, 1)
    last_analyzed = memory.get("last_analyzed", "nie")

    # Top-Patterns
    sorted_patterns = sorted(patterns.values(), key=lambda x: x.get("count", 0), reverse=True)[:20]

    by_category = Counter()
    for d in patterns.values():
        by_category[d.get("category", "unknown")] += d.get("count", 0)

    category_rows = "".join(
        f"<tr><td>{cat}</td><td>{cnt}</td></tr>"
        for cat, cnt in by_category.most_common()
    )

    pattern_rows = "".join(
        f"""<tr>
            <td>{p.get('category', '?')}</td>
            <td>{p.get('count', 0)}</td>
            <td>{'✓' if p.get('fixed') else '○'}</td>
            <td><code>{html_mod.escape(p.get('raw_text', '')[:100])}</code></td>
            <td><small>{p.get('first_seen', '')[:10]}</small></td>
        </tr>"""
        for p in sorted_patterns
    )

    trend_text = ""
    if trend.get("status") == "ok":
        trend_text = f"""
        <tr><td>Fix-Rate (aktuell)</td><td>{trend['current_fix_rate'] * 100:.1f}%</td></tr>
        <tr><td>Fix-Rate Änderung</td><td>{trend['fix_rate_change']:+.1%}</td></tr>
        <tr><td>Fehler Änderung gesamt</td><td>{trend['total_error_change']:+d}</td></tr>
        <tr><td>Fehler/h (24h)</td><td>{trend['errors_per_hour_last_24h']}</td></tr>
        <tr><td>Datenpunkte</td><td>{trend['data_points']}</td></tr>
        """
        if trend.get("top_categories"):
            trend_text += "<tr><td colspan='2'><b>Top-Kategorien:</b></td></tr>" + "".join(
                f"<tr><td>&nbsp;&nbsp;{t['name']}</td><td>{t['count']}</td></tr>"
                for t in trend["top_categories"]
            )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Learning Loop Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 20px; }}
  h1, h2, h3 {{ color: #58a6ff; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
  th {{ background: #161b22; color: #8b949e; }}
  tr:nth-child(even) {{ background: #161b22; }}
  code {{ background: #1f2937; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; color: #f0c674; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; text-align: center; }}
  .card h3 {{ margin: 0 0 8px 0; font-size: 0.9em; color: #8b949e; }}
  .card .value {{ font-size: 2em; font-weight: bold; color: #f0c674; }}
  .card .good {{ color: #3fb950; }}
  .card .warn {{ color: #d29922; }}
  .card .bad {{ color: #f85149; }}
  .footer {{ margin-top: 20px; font-size: 0.8em; color: #484f58; }}
</style>
</head>
<body>
<h1>🔄 Learning Loop Report</h1>
<p>Letzte Analyse: {last_analyzed}</p>

<div class="summary">
  <div class="card">
    <h3>Fehler Gesamt</h3>
    <div class="value">{total}</div>
  </div>
  <div class="card">
    <h3>Einzigartige Patterns</h3>
    <div class="value">{unique}</div>
  </div>
  <div class="card">
    <h3>Fix-Rate</h3>
    <div class="value {'good' if fix_rate >= 50 else 'warn' if fix_rate >= 25 else 'bad'}">{fix_rate}%</div>
  </div>
  <div class="card">
    <h3>Gefixt</h3>
    <div class="value good">{fixed}</div>
  </div>
</div>

<h2>📊 Trend</h2>
<table>
  {trend_text or '<tr><td colspan="2">Noch nicht genug Daten für Trend-Analyse (min. 2 Snapshots)</td></tr>'}
</table>

<h2>📂 Kategorien</h2>
<table>
  <tr><th>Kategorie</th><th>Fehler</th></tr>
  {category_rows}
</table>

<h2>🔍 Top-Patterns</h2>
<table>
  <tr><th>Kategorie</th><th>Count</th><th>Fixed</th><th>Pattern</th><th>Erstmals</th></tr>
  {pattern_rows if pattern_rows else '<tr><td colspan="5">Keine Patterns erfasst</td></tr>'}
</table>

<div class="footer">
  Generiert von learning-loop.py am {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>
</body>
</html>"""
    return html


# ── CLI-Dispatch ─────────────────────────────────────────────────────────────

def cmd_capture():
    """--capture: Sammle neue Fehler aus Logs."""
    print("┌─────────────────────────────────────────────────┐")
    print("│  🔍 Learning Loop — Capture                      │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    errors = scan_log_files()
    patterns = extract_patterns(errors)

    if patterns:
        print(f"\n  → {len(patterns)} Patterns extrahiert")
        # Zeige Top-Kategorien
        cats = Counter(p["category"] for p in patterns)
        print("\n  Kategorien:")
        for cat, cnt in cats.most_common():
            print(f"    {cat}: {cnt}")
    else:
        print("\n  → Keine neuen Patterns")

    # In temporäre Datei für analyze
    capture_file = MEMORY_DIR / "last_capture.json"
    capture_file.write_text(
        json.dumps({"patterns": patterns, "timestamp": datetime.datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )

    return patterns


def cmd_analyze():
    """--analyze: Kategorisiere und aktualisiere Memory."""
    print("┌─────────────────────────────────────────────────┐")
    print("│  📊 Learning Loop — Analyze                      │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    # Lade letzten Capture
    capture_file = MEMORY_DIR / "last_capture.json"
    if not capture_file.exists():
        print("  ⚠  Keine Capture-Daten gefunden. Führe zuerst --capture aus.")
        return []

    try:
        capture_data = json.loads(capture_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("  ⚠  Capture-Daten beschädigt. Führe erneut --capture aus.")
        return []

    patterns = capture_data.get("patterns", [])
    if not patterns:
        print("  ℹ  Keine neuen Patterns zum Analysieren.")
        return []

    memory = load_memory()
    memory = update_memory(memory, patterns)

    # Metriken aktualisieren
    update_metrics(memory)

    print(f"  ✓ Memory aktualisiert: {memory['total_errors_seen']} Fehler, {memory['unique_patterns']} Patterns")
    print(f"  ✓ {memory['new_patterns_last_run']} neue Patterns erkannt")

    return patterns


def cmd_suggest():
    """--suggest: Zeige neue Skills/Vorschläge."""
    print("┌─────────────────────────────────────────────────┐")
    print("│  💡 Learning Loop — Suggest                      │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    memory = load_memory()
    suggestions = generate_skills(memory)

    if not suggestions:
        print("  ℹ  Keine neuen Skill-Vorschläge. Entweder alle Patterns haben")
        print("     count < 3 oder es wurden bereits Skills generiert.")
        print()
        print("  Patterns mit count > 3:")
        patterns = memory.get("patterns", {})
        for fp, data in sorted(patterns.items(), key=lambda x: x[1].get("count", 0), reverse=True):
            if data["count"] >= 3:
                fixed = "✓" if data.get("fixed") else "○"
                print(f"    {fixed} [{data['category']:20s}] count={data['count']:3d}  {data.get('raw_text', '')[:80]}")
        return []

    print(f"  → {len(suggestions)} neue Skill-Vorschläge:\n")

    written = 0
    for s in suggestions:
        print(f"    📄 {s['name']}")
        print(f"       Beschreibung: {s['description']}")
        print(f"       Kategorie:    {s['category']}")
        print(f"       Lösung:       {s['solution'][:80]}...")
        print()

        if write_skill_file(s["name"], s["description"], s["solution"], s["category"], s["raw_text"]):
            written += 1
            print(f"       ✅ Skill geschrieben: skills/learning-loop/{s['name']}.md")
        else:
            print(f"       ℹ  Skill existiert bereits")

        # Als generiert markieren
        memory["skills_generated"].append(s["fingerprint"])

    # Pattern als fixed markieren
    for s in suggestions:
        fp = s["fingerprint"]
        if fp in memory.get("patterns", {}):
            memory["patterns"][fp]["fixed"] = True

    save_memory(memory)

    print(f"\n  📝 {written} neue Skills geschrieben")
    return suggestions


def cmd_trend():
    """--trend: Zeige Verbesserungs-Trend."""
    print("┌─────────────────────────────────────────────────┐")
    print("│  📈 Learning Loop — Trend                        │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    metrics = load_metrics()
    trend = compute_trend(metrics)

    if trend["status"] == "insufficient_data":
        print(f"  ⚠  Nicht genug Daten (nur {trend['data_points']} Snapshot(s)).")
        print("     Führe --auto mindestens 2x aus.")
        return

    print(f"  Datenpunkte:     {trend['data_points']}")
    print(f"  Fix-Rate:        {trend['current_fix_rate']*100:.1f}%")
    print(f"  Fix-Rate Δ:      {trend['fix_rate_change']:+.1%}")
    print(f"  Fehler Δ:        {trend['total_error_change']:+d}")
    print(f"  Fehler/h (24h):  {trend['errors_per_hour_last_24h']}")
    print()

    if trend.get("top_categories"):
        print("  Top-Kategorien:")
        for t in trend["top_categories"]:
            bar = "█" * min(t["count"], 40)
            print(f"    {t['name']:20s} {bar} {t['count']}")
    print()

    # Bewertung
    fix_rate = trend["current_fix_rate"]
    direction = ""

    if fix_rate >= 0.7:
        direction = "🟢 System stabilisiert sich — hohe Lösungsrate"
    elif fix_rate >= 0.4:
        direction = "🟡 Mittlere Lösungsrate — Verbesserungspotential"
    else:
        direction = "🔴 Niedrige Lösungsrate — viele ungelöste Muster"

    if trend["total_error_change"] > 0:
        direction += ", Fehler nehmen zu ⬆"
    elif trend["total_error_change"] < 0:
        direction += ", Fehler nehmen ab ⬇"
    else:
        direction += ", Fehler stabil ➡"

    print(f"  → {direction}")


def cmd_report(format="html"):
    """--report: Generiere Report."""
    print("┌─────────────────────────────────────────────────┐")
    print(f"│  📋 Learning Loop — Report ({format})               │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    memory = load_memory()
    metrics = load_metrics()
    trend = compute_trend(metrics)

    if format == "json":
        report = {
            "memory": {
                "total_errors_seen": memory.get("total_errors_seen", 0),
                "unique_patterns": memory.get("unique_patterns", 0),
                "last_analyzed": memory.get("last_analyzed", "nie"),
                "patterns": len(memory.get("patterns", {})),
                "fixed": sum(1 for d in memory.get("patterns", {}).values() if d.get("fixed")),
            },
            "trend": trend,
            "generated_at": datetime.datetime.now().isoformat(),
        }
        json_path = MEMORY_DIR / "learning-loop-report.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✓ JSON-Report: {json_path}")
    else:
        html = generate_html_report(memory, trend)
        REPORT_FILE.write_text(html, encoding="utf-8")
        print(f"  ✓ HTML-Report: {REPORT_FILE}")

    print(f"  ✓ Memory: {memory.get('total_errors_seen', 0)} Fehler, {memory.get('unique_patterns', 0)} Patterns")


def cmd_auto():
    """--auto: Full Cycle capture → analyze → suggest."""
    print("┌─────────────────────────────────────────────────┐")
    print("│  🔄 Learning Loop — Auto Cycle                    │")
    print(f"│  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          │")
    print("└─────────────────────────────────────────────────┘")
    print()

    # Phase 1: Capture
    print("Phase 1/3: Capture")
    errors = scan_log_files()
    patterns = extract_patterns(errors)
    capture_file = MEMORY_DIR / "last_capture.json"
    capture_file.write_text(
        json.dumps({"patterns": patterns, "timestamp": datetime.datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )
    new_patterns = len(patterns)
    print(f"  → {new_patterns} Patterns extrahiert\n")

    # Phase 2: Analyze
    print("Phase 2/3: Analyze")
    if patterns:
        memory = load_memory()
        memory = update_memory(memory, patterns)
        update_metrics(memory)
        print(f"  ✓ Memory: {memory['total_errors_seen']} Fehler, {memory['unique_patterns']} Patterns")
        new_seen = memory['new_patterns_last_run']
    else:
        new_seen = 0
        memory = load_memory()
    print()

    # Phase 3: Suggest (nur wenn neue Muster erkannt)
    print("Phase 3/3: Suggest")
    suggestions = generate_skills(memory)
    if suggestions:
        written = 0
        for s in suggestions:
            if write_skill_file(s["name"], s["description"], s["solution"], s["category"], s["raw_text"]):
                written += 1
                print(f"  ✓ Skill: {s['name']}")
            memory["skills_generated"].append(s["fingerprint"])
            fp = s["fingerprint"]
            if fp in memory.get("patterns", {}):
                memory["patterns"][fp]["fixed"] = True
        save_memory(memory)
        print(f"  → {written} neue Skills generiert")
    else:
        print("  ℹ  Keine neuen Skill-Vorschläge")
    print()

    # Report generieren
    cmd_report("html")

    # Exit-Code bestimmen
    has_new_patterns = new_seen > 0
    has_new_skills = len(suggestions) > 0

    print(f"  Resultat: Patterns={'✓' if new_patterns > 0 else '–'} Neu={'✓' if has_new_patterns else '–'} Skills={'✓' if has_new_skills else '–'}")

    if has_new_skills:
        sys.exit(EXIT_NEW_SKILLS)
    if has_new_patterns:
        sys.exit(EXIT_NEW_PATTERNS)

    sys.exit(EXIT_STABLE)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--capture":
        cmd_capture()
    elif arg == "--analyze":
        cmd_analyze()
    elif arg == "--suggest":
        cmd_suggest()
    elif arg == "--trend":
        cmd_trend()
    elif arg == "--report":
        fmt = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in ("json", "html") else "html"
        cmd_report(fmt)
    elif arg == "--auto":
        cmd_auto()
    elif arg in ("-h", "--help"):
        print(__doc__)
    else:
        print(f"Unbekanntes Argument: {arg}")
        print("Verwendung: python learning-loop.py [--capture|--analyze|--suggest|--trend|--report|--auto]")
        sys.exit(1)


if __name__ == "__main__":
    main()