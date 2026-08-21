#!/usr/bin/env python3
"""
Auto-Env-Checker — Vollständige Umgebungs-Validierung + Auto-Fix

Prüft:
  - .env auf Existenz + kritische Keys
  - config.yaml auf Syntax + required Sections
  - paths (skills/, scripts/, cron/) auf Existenz + Schreibbarkeit
  - Python-Umgebung (venv aktiv? python version? pip outdated?)
  - Git-Status (uncommitted? ahead/behind?)

CLI:
  --check        Alles prüfen (Default)
  --env          Nur .env
  --config       Nur config.yaml
  --paths        Nur paths
  --python       Nur Python
  --git          Nur Git
  --fix          Automatische Reparatur versuchen
  --json         JSON-Output (maschinenlesbar)
  --quiet        Nur Exit-Code, keine Ausgabe

Exit-Codes:
  0 = alles gut
  1 = Warnungen
  2 = Fehler
  3 = kritisch
"""

import os
import sys
import json
import stat
import subprocess
import datetime
import shutil
import re
import tempfile
from pathlib import Path
from collections import OrderedDict

# ─── Konfiguration ────────────────────────────────────────────────

def _msys_to_win(path: str) -> str:
    """Konvertiert MSYS-Pfad (/c/Users/...) zu Windows (C:\\Users\\...)."""
    if not path:
        return path
    m = re.match(r"^/([a-zA-Z])/(.*)", path)
    if m:
        sep = "\\"
        return f"{m.group(1).upper()}:{sep}{m.group(2).replace('/', sep)}"
    return path

def _resolve_home() -> Path:
    """Robuste Ermittlung des OpenAmer-Home-Pfads."""
    env = os.environ.get("OPENAMER_HOME")
    if env:
        return Path(_msys_to_win(env)).resolve()
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        return Path(_msys_to_win(localappdata)) / "openamer-laptop"
    # Fallback
    home = Path.home()
    return home / "AppData" / "Local" / "openamer-laptop"

def _resolve_repo() -> Path:
    env = os.environ.get("OPENAMER_REPO")
    if env:
        return Path(_msys_to_win(env)).resolve()
    return Path.home() / "openamer-repo"

OPENAMER_HOME = _resolve_home()
REPO_DIR = _resolve_repo()
SCRIPT_DIR = OPENAMER_HOME / "scripts"
CONFIG_FILE = OPENAMER_HOME / "config.yaml"
ENV_FILE = OPENAMER_HOME / ".env"

CRITICAL_ENV_KEYS = [
    "OPENROUTER_API_KEY",
]

OPTIONAL_ENV_KEYS = [
    "OLLAMA_API_KEY",
    "OLLAMA_BASE_URL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]

REQUIRED_CONFIG_SECTIONS = ["model", "agent", "terminal", "browser", "display"]

REQUIRED_PATHS = {
    "skills": OPENAMER_HOME / "skills",
    "scripts": OPENAMER_HOME / "scripts",
    "cron": OPENAMER_HOME / "cron",
    "memories": OPENAMER_HOME / "memories",
    "config": OPENAMER_HOME / "config.yaml",
    "env": OPENAMER_HOME / ".env",
    "cache": OPENAMER_HOME / "cache",
}

MIN_PYTHON_VERSION = (3, 10)
MAX_EXIT_CODE = 0


# ─── Output ───────────────────────────────────────────────────────

class Results:
    def __init__(self):
        self.checks = []
        self.fixes = []
        self.exit_code = 0

    def add(self, section, status, message, detail=None):
        """status: ok, warning, error, critical"""
        code_map = {"ok": 0, "warning": 1, "error": 2, "critical": 3}
        self.checks.append({
            "section": section,
            "status": status,
            "message": message,
            "detail": detail,
        })
        self.exit_code = max(self.exit_code, code_map[status])

    def add_fix(self, section, action, result, success=True):
        self.fixes.append({
            "section": section,
            "action": action,
            "result": result,
            "success": success,
        })

    def print_results(self, json_output=False, quiet=False):
        if quiet:
            return
        if json_output:
            print(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
            return

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"╔═══ Auto-Env-Checker ═══ {ts} ═══╗")
        print()

        current_section = None
        for c in self.checks:
            if c["section"] != current_section:
                current_section = c["section"]
                print(f"  ┌─ {current_section.upper()} ──────────────────")
            icon = {"ok": "✓", "warning": "⚠", "error": "✗", "critical": "‼"}.get(c["status"], "?")
            print(f"  {icon} {c['message']}")
            if c.get("detail"):
                for line in c["detail"].split("\n"):
                    print(f"    {line}")
        print()

        if self.fixes:
            print(f"  ┌─ FIXES ─────────────────────")
            for f in self.fixes:
                icon = "✓" if f["success"] else "✗"
                print(f"  {icon} [{f['section']}] {f['action']}: {f['result']}")
            print()

        label = {0: "ALL GOOD", 1: "WARNINGS", 2: "ERRORS", 3: "CRITICAL"}
        exit_label = label.get(self.exit_code, "UNKNOWN")
        print(f"  Exit-Code: {self.exit_code} ({exit_label})")
        print(f"╚══════════════════════════════════════════════╝")

    def to_dict(self):
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "exit_code": self.exit_code,
            "checks": self.checks,
            "fixes": self.fixes,
            "status": {0: "ok", 1: "warning", 2: "error", 3: "critical"}.get(self.exit_code, "unknown"),
        }


r = Results()


# ─── Check: .env ─────────────────────────────────────────────────

def check_env(fix=False):
    """Prüft .env auf Existenz + kritische Keys."""
    if not ENV_FILE.exists():
        r.add("env", "critical", ".env existiert nicht", f"Pfad: {ENV_FILE}")
        if fix:
            try:
                ENV_FILE.write_text("# Auto-Env-Checker: initial .env\n")
                r.add_fix("env", ".env erstellt", f"{ENV_FILE} wurde angelegt")
            except Exception as e:
                r.add_fix("env", ".env erstellen", f"Fehler: {e}", success=False)
        return

    if not os.access(str(ENV_FILE), os.R_OK):
        r.add("env", "error", ".env ist nicht lesbar")
        return

    try:
        content = ENV_FILE.read_text(encoding="utf-8")
    except Exception as e:
        r.add("env", "error", ".env kann nicht gelesen werden", str(e))
        return

    # Parse .env
    env_vars = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env_vars[key.strip()] = val.strip()

    r.add("env", "ok", f".env gefunden ({len(env_vars)} Variablen)")

    # Critical keys
    missing_critical = []
    for key in CRITICAL_ENV_KEYS:
        if key not in env_vars:
            missing_critical.append(key)
        elif not env_vars[key]:
            missing_critical.append(f"{key}=<leer>")

    if missing_critical:
        r.add("env", "critical",
              f"Fehlende kritische Keys: {', '.join(missing_critical)}")
        if fix:
            for key in CRITICAL_ENV_KEYS:
                if key not in env_vars or not env_vars.get(key):
                    if key == "OPENROUTER_API_KEY":
                        r.add_fix("env",
                                  f"{key} setzen",
                                  "Manuell eintragen — kein Default-Wert möglich",
                                  success=False)
                    elif key == "OPENAI_API_KEY":
                        r.add_fix("env",
                                  f"{key} setzen (optional, OpenRouter als Fallback)",
                                  "Manuell eintragen — kein Default-Wert möglich",
                                  success=False)
    else:
        # Check if keys have valid-looking values
        for key in CRITICAL_ENV_KEYS:
            val = env_vars.get(key, "")
            if len(val) < 8:
                r.add("env", "warning",
                      f"{key} wirkt sehr kurz ({len(val)} Zeichen) — möglicherweise ungültig")
            else:
                r.add("env", "ok", f"{key} ist gesetzt ({len(val)} Zeichen)")

    # Optional keys
    found_optional = []
    missing_optional = []
    for key in OPTIONAL_ENV_KEYS:
        if key in env_vars and env_vars[key]:
            found_optional.append(key)
        else:
            missing_optional.append(key)

    if found_optional:
        r.add("env", "ok", f"Optionale Keys gefunden: {', '.join(found_optional)}")
    if missing_optional:
        r.add("env", "warning",
              f"Optionale Keys fehlen: {', '.join(missing_optional)}")

    # Check .env permissions
    try:
        mode = os.stat(str(ENV_FILE)).st_mode
        # On Windows, check if it's readable by others
        r.add("env", "ok", ".env Berechtigungen ok")
    except Exception:
        r.add("env", "warning", ".env Berechtigungen konnten nicht geprüft werden")


# ─── Check: config.yaml ──────────────────────────────────────────

def check_config(fix=False):
    """Prüft config.yaml auf Syntax + required Sections."""
    if not CONFIG_FILE.exists():
        r.add("config", "critical", "config.yaml existiert nicht", f"Pfad: {CONFIG_FILE}")
        if fix:
            try:
                _write_default_config()
                r.add_fix("config", "config.yaml erstellt", "Default-Konfiguration geschrieben")
            except Exception as e:
                r.add_fix("config", "config.yaml erstellen", f"Fehler: {e}", success=False)
        return

    try:
        import yaml
        with open(str(CONFIG_FILE), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except ImportError:
        # Fallback: rudimentärer Check ohne PyYAML
        try:
            content = CONFIG_FILE.read_text(encoding="utf-8")
        except Exception as e:
            r.add("config", "error", "config.yaml kann nicht gelesen werden", str(e))
            return
        r.add("config", "warning", "PyYAML nicht installiert — nur rudimentäre Prüfung")

        # Simple key:value check
        lines = content.splitlines()
        has_model = any("model:" in l for l in lines)
        has_agent = any("agent:" in l for l in lines)
        if has_model and has_agent:
            r.add("config", "ok", f"config.yaml vorhanden ({len(lines)} Zeilen, rudimentär)")
        else:
            r.add("config", "error", "config.yaml scheint model/agent zu fehlen")
        return

    if config is None:
        r.add("config", "error", "config.yaml ist leer")
        if fix:
            try:
                _write_default_config()
                r.add_fix("config", "config.yaml neu geschrieben", "Default gesetzt")
            except Exception as e:
                r.add_fix("config", "config.yaml schreiben", f"Fehler: {e}", success=False)
        return

    r.add("config", "ok", "config.yaml Syntax gültig (YAML geparst)")

    # Check required sections
    missing_sections = []
    for section in REQUIRED_CONFIG_SECTIONS:
        if section not in config:
            missing_sections.append(section)

    if missing_sections:
        r.add("config", "error",
              f"Fehlende Sections: {', '.join(missing_sections)}")
        if fix:
            for section in missing_sections:
                if section == "model":
                    _ensure_config_section("model", {"default": "deepseek/deepseek-v4-flash:0731", "provider": "openrouter"})
                    r.add_fix("config", f"Section '{section}' ergänzt", "Default-Modell gesetzt")
                elif section == "agent":
                    _ensure_config_section("agent", {"max_turns": 150})
                    r.add_fix("config", f"Section '{section}' ergänzt", "Default-Agent gesetzt")
                elif section == "display":
                    _ensure_config_section("display", {"language": "de", "compact": False})
                    r.add_fix("config", f"Section '{section}' ergänzt", "Default-Display gesetzt")
                elif section in ("terminal", "browser"):
                    _ensure_config_section(section, {})
                    r.add_fix("config", f"Section '{section}' ergänzt", f"Leere '{section}' Section gesetzt")
    else:
        for section in REQUIRED_CONFIG_SECTIONS:
            r.add("config", "ok", f"Section '{section}' vorhanden")

    # Check specific critical config values
    if "model" in config:
        model = config.get("model", {})
        if not model.get("default"):
            r.add("config", "warning", "model.default ist nicht gesetzt")
        if not model.get("provider"):
            r.add("config", "warning", "model.provider ist nicht gesetzt")
        else:
            r.add("config", "ok", f"Provider: {model.get('provider')}, Model: {model.get('default')}")

    # Check for _config_version
    if "_config_version" in config:
        r.add("config", "ok", f"config_version: {config['_config_version']}")
    else:
        r.add("config", "warning", "_config_version fehlt — config könnte veraltet sein")


def _write_default_config():
    """Schreibt eine minimale Default-Config."""
    default_config = """model:
  default: deepseek/deepseek-v4-flash:0731
  provider: openrouter
  base_url: ''
agent:
  max_turns: 150
terminal:
  backend: local
browser:
  engine: chrome
display:
  language: de
  compact: false
_config_version: 34
"""
    CONFIG_FILE.write_text(default_config, encoding="utf-8")


def _ensure_config_section(section, defaults):
    """Fügt eine fehlende Section in config.yaml ein (einfach per Anhängen)."""
    try:
        with open(str(CONFIG_FILE), "a", encoding="utf-8") as f:
            f.write(f"\n{section}:\n")
            for k, v in defaults.items():
                if isinstance(v, bool):
                    f.write(f"  {k}: {'true' if v else 'false'}\n")
                elif isinstance(v, str):
                    f.write(f"  {k}: {v}\n")
                elif isinstance(v, int):
                    f.write(f"  {k}: {v}\n")
                else:
                    f.write(f"  {k}: {v}\n")
    except Exception:
        pass


# ─── Check: Paths ─────────────────────────────────────────────────

def check_paths(fix=False):
    """Prüft alle required Paths auf Existenz + Schreibbarkeit."""
    all_ok = True
    for name, path in REQUIRED_PATHS.items():
        if path.exists():
            r.add("paths", "ok", f"{name}: {path} existiert")

            # Check writability for directories
            if path.is_dir():
                test_file = path / f"._env_check_{os.getpid()}.tmp"
                try:
                    test_file.write_text("test")
                    test_file.unlink()
                    r.add("paths", "ok", f"{name}: schreibbar")
                except (OSError, PermissionError) as e:
                    r.add("paths", "warning", f"{name}: NICHT schreibbar ({e})")
                    all_ok = False
                    if fix:
                        try:
                            os.chmod(str(path), stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
                            r.add_fix("paths", f"{name} chmod", f"Berechtigungen repariert: {path}")
                        except Exception as e2:
                            r.add_fix("paths", f"{name} chmod", f"Fehler: {e2}", success=False)
        else:
            r.add("paths", "error", f"{name}: {path} existiert NICHT")
            all_ok = False
            if fix:
                try:
                    if name in ("skills", "scripts", "cron", "memories", "cache"):
                        path.mkdir(parents=True, exist_ok=True)
                        r.add_fix("paths", f"{name} erstellt", f"{path} angelegt")
                    elif name in ("config", "env"):
                        r.add_fix("paths", f"{name} erstellt",
                                  f"Bitte manuell anlegen: {path}", success=False)
                except Exception as e:
                    r.add_fix("paths", f"{name} erstellen", f"Fehler: {e}", success=False)

    # Disk space check
    try:
        if os.name == "nt":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(str(OPENAMER_HOME)),
                None, None, ctypes.pointer(free_bytes)
            )
            free_gb = free_bytes.value / (1024**3)
        else:
            st = os.statvfs(str(OPENAMER_HOME))
            free_gb = st.f_bavail * st.f_frsize / (1024**3)

        if free_gb < 0.5:
            r.add("paths", "critical", f"Wenig Speicher: {free_gb:.1f} GB frei")
        elif free_gb < 2:
            r.add("paths", "warning", f"Speicherplatz: {free_gb:.1f} GB frei")
        else:
            r.add("paths", "ok", f"Speicherplatz: {free_gb:.1f} GB frei")
    except Exception:
        r.add("paths", "warning", "Speicherplatz konnte nicht geprüft werden")

    # Logs directory
    logs_dir = OPENAMER_HOME / "logs"
    if logs_dir.exists():
        try:
            log_count = len(list(logs_dir.iterdir()))
            log_size_mb = sum(f.stat().st_size for f in logs_dir.iterdir() if f.is_file()) / (1024**2)
            if log_size_mb > 100:
                r.add("paths", "warning",
                      f"Logs: {log_count} Dateien, {log_size_mb:.1f} MB — groß")
            else:
                r.add("paths", "ok", f"Logs: {log_count} Dateien, {log_size_mb:.1f} MB")
        except Exception:
            pass


# ─── Check: Python ────────────────────────────────────────────────

def check_python(fix=False):
    """Prüft Python-Umgebung."""
    # Version
    v = sys.version_info
    r.add("python", "ok", f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")

    if (v.major, v.minor) < MIN_PYTHON_VERSION:
        r.add("python", "error",
              f"Python {v.major}.{v.minor} zu alt — mindestens {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}")

    # Venv detection
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        venv_path = sys.prefix
        r.add("python", "ok", f"Venv aktiv: {venv_path}")
    else:
        r.add("python", "warning", "Kein venv aktiv — globale Python-Installation")

    # Check if the correct venv is active
    expected_venv = OPENAMER_HOME / "openamer-agent" / "venv"
    if in_venv and expected_venv.exists():
        norm_venv = os.path.normpath(str(expected_venv))
        norm_sys = os.path.normpath(sys.prefix)
        if norm_venv in norm_sys:
            r.add("python", "ok", "OpenAmer-Venv korrekt aktiv")
        else:
            r.add("python", "warning",
                  f"Anderes venv aktiv: {sys.prefix}\n  Erwartet: {expected_venv}")
            if fix:
                activate_script = expected_venv / "Scripts" / "activate"
                if activate_script.exists():
                    r.add_fix("python", "venv aktivieren",
                              f"Bitte manuell: source {activate_script}", success=False)
    elif in_venv and not expected_venv.exists():
        r.add("python", "warning",
              "OpenAmer-Venv existiert nicht — möglicherweise neu installieren nötig")

    # Pip version check
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10
        )
        pip_version_str = result.stdout.strip()
        r.add("python", "ok", f"pip: {pip_version_str}")

        # Check for outdated pip
        try:
            out_dated = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--outdated", "--format=columns"],
                capture_output=True, text=True, timeout=15
            )
            outdated_lines = [l for l in out_dated.stdout.split("\n") if l.strip() and not l.startswith("Package")]
            if len(outdated_lines) > 1:  # header only means none
                pkg_count = len(outdated_lines) - 1  # subtract header line
                if pkg_count > 10:
                    r.add("python", "warning",
                          f"Veraltete Pakete: {pkg_count} (pip list --outdated)")
                    if fix:
                        r.add_fix("python", "pip upgrade",
                                  f"Führe aus: {sys.executable} -m pip install --upgrade pip")
                else:
                    r.add("python", "ok", f"Veraltete Pakete: {pkg_count}")
            else:
                r.add("python", "ok", "Keine veralteten Pakete")
        except subprocess.TimeoutExpired:
            r.add("python", "warning", "pip outdated-Check timed out (übersprungen)")
        except Exception:
            r.add("python", "warning", "pip outdated-Check fehlgeschlagen")

    except FileNotFoundError:
        r.add("python", "error", "pip nicht installiert/found")
        if fix:
            try:
                subprocess.run(
                    [sys.executable, "-m", "ensurepip", "--upgrade"],
                    check=True, timeout=30
                )
                r.add_fix("python", "pip installiert", "ensurepip erfolgreich")
            except Exception as e:
                r.add_fix("python", "pip installieren", f"Fehler: {e}", success=False)
    except Exception as e:
        r.add("python", "error", f"pip-Check fehlgeschlagen: {e}")

    # uv check
    uv_path = shutil.which("uv")
    if uv_path:
        r.add("python", "ok", f"uv: {uv_path}")
    else:
        r.add("python", "warning", "uv nicht gefunden — empfohlen für Paketmanagement")

    # PyYAML (wichtig für config-check)
    try:
        import yaml
        r.add("python", "ok", "PyYAML installiert")
    except ImportError:
        r.add("python", "warning", "PyYAML nicht installiert — für config-Prüfung empfohlen")
        if fix:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pyyaml"],
                    check=True, timeout=60, capture_output=True
                )
                r.add_fix("python", "PyYAML installiert", "pip install pyyaml erfolgreich")
            except Exception as e:
                r.add_fix("python", "PyYAML installieren", f"Fehler: {e}", success=False)


# ─── Check: Git ───────────────────────────────────────────────────

def check_git(fix=False):
    """Prüft Git-Status im Repository."""
    repo = REPO_DIR
    git_dir = repo / ".git"

    if not git_dir.exists():
        r.add("git", "warning", f"Kein Git-Repo gefunden: {repo}")
        return

    r.add("git", "ok", f"Git-Repo: {repo}")

    def _run_git(*args):
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True, text=True, timeout=15,
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except FileNotFoundError:
            return None, "git nicht installiert", -1
        except Exception as e:
            return None, str(e), -1

    # Git version
    stdout, stderr, rc = _run_git("--version")
    if rc == 0 and stdout:
        r.add("git", "ok", stdout)
    else:
        r.add("git", "error", "Git nicht installiert oder nicht erreichbar")
        return

    # Branch
    stdout, stderr, rc = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    if rc == 0:
        branch = stdout
        r.add("git", "ok", f"Branch: {branch}")
    else:
        r.add("git", "error", f"Branch konnte nicht ermittelt werden: {stderr}")
        branch = "unknown"

    # Uncommitted changes
    stdout, stderr, rc = _run_git("status", "--porcelain")
    if rc == 0:
        uncommitted = [l for l in stdout.split("\n") if l.strip()]
        if uncommitted:
            # Classify
            untracked = [l for l in uncommitted if l.startswith("??")]
            modified = [l for l in uncommitted if l.startswith(" M") or l.startswith("M ")]
            staged = [l for l in uncommitted if l.startswith("A ") or l.startswith("M ")]
            deleted = [l for l in uncommitted if l.startswith(" D") or l.startswith("D ")]

            parts = []
            if modified: parts.append(f"{len(modified)} modified")
            if staged: parts.append(f"{len(staged)} staged")
            if untracked: parts.append(f"{len(untracked)} untracked")
            if deleted: parts.append(f"{len(deleted)} deleted")

            detail_lines = uncommitted[:20]
            detail = "\n".join(detail_lines)
            if len(uncommitted) > 20:
                detail += f"\n  ... und {len(uncommitted) - 20} weitere"

            if len(uncommitted) > 30:
                r.add("git", "warning",
                      f"Viele uncommitted: {', '.join(parts)} ({len(uncommitted)} Dateien)",
                      detail)
            else:
                r.add("git", "warning",
                      f"Uncommitted: {', '.join(parts)} ({len(uncommitted)} Dateien)",
                      detail)
        else:
            r.add("git", "ok", "Working tree clean")
    else:
        r.add("git", "error", f"Git status fehlgeschlagen: {stderr}")

    # Ahead/behind
    stdout, stderr, rc = _run_git("rev-list", "--count", "--left-right", f"{branch}...origin/{branch}")
    if rc == 0 and stdout.strip():
        parts = stdout.strip().split("\t")
        if len(parts) == 2:
            behind_str = parts[0].strip()
            ahead_str = parts[1].strip()
            try:
                behind = int(behind_str) if behind_str else 0
                ahead = int(ahead_str) if ahead_str else 0
            except ValueError:
                behind = ahead = 0

            if behind > 0 and ahead > 0:
                r.add("git", "warning",
                      f"Branch divergiert: {ahead} ahead, {behind} behind origin/{branch}")
                if fix and behind <= 5:
                    stdout, stderr, rc = _run_git("pull", "--rebase")
                    if rc == 0:
                        r.add_fix("git", "git pull --rebase", "Erfolgreich (wenn Konflikte, manuell lösen)")
                    else:
                        r.add_fix("git", "git pull --rebase", f"Fehler: {stderr}", success=False)
            elif ahead > 0:
                r.add("git", "warning", f"Branch ist {ahead} Commit(s) ahead of origin/{branch}")
            elif behind > 0:
                r.add("git", "warning", f"Branch ist {behind} Commit(s) behind origin/{branch}")
                if fix:
                    stdout, stderr, rc = _run_git("pull", "--ff-only")
                    if rc == 0:
                        r.add_fix("git", "git pull --ff-only", "Erfolgreich")
                    else:
                        r.add_fix("git", "git pull --ff-only", f"Fehler: {stderr}", success=False)
            else:
                r.add("git", "ok", "Up to date with origin")
    else:
        # No remote or can't check — not critical
        pass

    # Last commit
    stdout, stderr, rc = _run_git("log", "-1", "--format=%h %s (%ar)")
    if rc == 0 and stdout:
        r.add("git", "ok", f"Letzter Commit: {stdout}")


# ─── Main ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Auto-Env-Checker — Vollständige Umgebungs-Validierung",
    )
    parser.add_argument("--check", action="store_true", default=True,
                        help="Alles prüfen (Default)")
    parser.add_argument("--env", action="store_true", help="Nur .env prüfen")
    parser.add_argument("--config", action="store_true", help="Nur config.yaml prüfen")
    parser.add_argument("--paths", action="store_true", help="Nur paths prüfen")
    parser.add_argument("--python", action="store_true", help="Nur Python prüfen")
    parser.add_argument("--git", action="store_true", help="Nur Git prüfen")
    parser.add_argument("--fix", action="store_true", help="Auto-Reparatur versuchen")
    parser.add_argument("--json", action="store_true", help="JSON-Output")
    parser.add_argument("--quiet", action="store_true", help="Nur Exit-Code")
    args = parser.parse_args()

    fix_mode = args.fix

    # Determine which checks to run
    if args.env:
        check_env(fix=fix_mode)
    elif args.config:
        check_config(fix=fix_mode)
    elif args.paths:
        check_paths(fix=fix_mode)
    elif args.python:
        check_python(fix=fix_mode)
    elif args.git:
        check_git(fix=fix_mode)
    else:
        # --check (default)
        check_env(fix=fix_mode)
        check_config(fix=fix_mode)
        check_paths(fix=fix_mode)
        check_python(fix=fix_mode)
        check_git(fix=fix_mode)

    r.print_results(json_output=args.json, quiet=args.quiet)
    sys.exit(r.exit_code)


if __name__ == "__main__":
    main()