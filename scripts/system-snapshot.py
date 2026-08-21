#!/usr/bin/env python3
"""
system-snapshot.py — Vollständiger Systemzustand auf einen Blick

Erfasst KOMPLETTEN Systemzustand als JSON:
  a) OS: Windows-Version, Python-Version, OpenAmer-Version, Git-Commit
  b) Skripte: scripts/ — Liste + Größe + letzte Änderung
  c) Skills: alle Skills + Kategorie + Größe
  d) Cron: alle Jobs + Schedule + letzter Run + Exit-Code
  e) Health: RAM, Disk, CPU aktuell
  f) Security: letzter CVE-Scan, CVEs gefunden
  g) Backup: letztes Backup existiert?
  h) Sessions: Anzahl Sessions, archiviert, komprimiert

CLI:
  --now               Einmaligen Snapshot erstellen
  --diff              Unterschied zum letzten Snapshot anzeigen
  --list              Alle Snapshots auflisten
  --compare A B       Zwei Snapshots (IDs oder Datumsangaben) vergleichen
  --serve             HTTP-Server auf Port 8898 (liefert aktuellen Snapshot als JSON)
  --port PORT         Port für --serve (default: 8898)
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────
_default_home = Path.home() / "AppData" / "Local" / "openamer-laptop"
_env_home = os.environ.get("OPENAMER_HOME", "")
if _env_home and _env_home.startswith("/"):
    if _env_home.startswith("/c/"):
        _env_home = "C:/" + _env_home[3:]
    elif _env_home.startswith("/d/"):
        _env_home = "D:/" + _env_home[3:]
    HOME = Path(_env_home)
elif _env_home:
    HOME = Path(_env_home)
else:
    HOME = _default_home

SNAPSHOT_DIR = HOME / ".system-snapshot" / "snapshots"
REPO_DIR = Path(os.environ.get("OPENAMER_REPO", str(Path.home() / "openamer-repo")))

EXIT_OK = 0
EXIT_ERR = 1


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def ensure_snapshot_dir():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd, timeout=10):
    """Run a shell command and return (stdout, stderr, exit_code)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=True, cwd=str(REPO_DIR) if REPO_DIR.exists() else None
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except FileNotFoundError:
        return "", "not found", -1


def get_size_str(path):
    """Return human-readable file size."""
    try:
        size = path.stat().st_size
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except (OSError, FileNotFoundError):
        return "0 B"


def get_mtime_iso(path):
    """Return ISO mtime string."""
    try:
        mtime = path.stat().st_mtime
        return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()
    except (OSError, FileNotFoundError):
        return None


def get_file_hash(path):
    """SHA-256 hash of file content."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, FileNotFoundError):
        return None


# ── Datenerfassung ─────────────────────────────────────────────────────────

def collect_snapshot():
    """Collect complete system state and return as dict."""
    data = {
        "snapshot_meta": {
            "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "tool_version": "1.0.0",
        },
        "os": collect_os_info(),
        "scripts": collect_scripts_info(),
        "skills": collect_skills_info(),
        "cron": collect_cron_info(),
        "health": collect_health_info(),
        "security": collect_security_info(),
        "backup": collect_backup_info(),
        "sessions": collect_sessions_info(),
    }
    return data


def collect_os_info():
    info = {}

    # Windows version — use Python's platform module (reliable in all shells)
    try:
        import platform
        info["windows_version"] = platform.platform(terse=True)
        info["windows_version_full"] = platform.version()
        info["system"] = platform.system()
        info["release"] = platform.release()
    except Exception:
        pass

    # Fallback: try PowerShell
    if "windows_version" not in info:
        stdout, _, _ = run_cmd('powershell.exe -Command "(Get-CimInstance Win32_OperatingSystem).Caption"', timeout=10)
        info["windows_version"] = stdout or "unknown"

    # Python version
    info["python_version"] = sys.version
    info["python_executable"] = sys.executable

    # OpenAmer version — from pyproject.toml
    pyproject_path = REPO_DIR / "pyproject.toml"
    if pyproject_path.exists():
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                pyproj = tomllib.load(f)
            info["openamer_version"] = pyproj.get("project", {}).get("version", "unknown")
        except Exception:
            # fallback: grep
            stdout, _, _ = run_cmd(f'grep "^version" "{pyproject_path}"', timeout=5)
            if not stdout:
                stdout, _, _ = run_cmd(f'grep -m1 "version =" "{pyproject_path}"', timeout=5)
            info["openamer_version"] = stdout.split("=")[-1].strip().strip('"').strip("'") if stdout else "unknown"
    else:
        info["openamer_version"] = "unknown"

    # Git commit
    stdout, _, rc = run_cmd("git rev-parse HEAD", timeout=5)
    info["git_commit"] = stdout if rc == 0 else "no repo"
    if rc == 0:
        stdout2, _, _ = run_cmd('git log --oneline -1', timeout=5)
        info["git_commit_msg"] = stdout2 or ""
        # check for tags
        stdout3, _, _ = run_cmd("git tag --points-at HEAD", timeout=5)
        info["git_tags"] = [t.strip() for t in stdout3.split("\n") if t.strip()] if stdout3 else []

    # Hostname
    info["hostname"] = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
    info["username"] = os.environ.get("USERNAME", "unknown")

    return info


def collect_scripts_info():
    scripts_dir = HOME / "scripts"
    if not scripts_dir.is_dir():
        return {"count": 0, "items": [], "total_size": "0 B", "error": "scripts dir not found"}

    items = []
    total_size = 0
    for f in sorted(scripts_dir.iterdir()):
        if f.is_file() and f.name != "__pycache__":
            size = f.stat().st_size if f.is_file() else 0
            total_size += size
            items.append({
                "name": f.name,
                "size": get_size_str(f),
                "size_bytes": size,
                "modified": get_mtime_iso(f),
                "hash": get_file_hash(f),
            })

    return {
        "count": len(items),
        "items": items,
        "total_size": get_size_str(scripts_dir),
        "total_size_bytes": total_size,
        "directory": str(scripts_dir),
    }


def collect_skills_info():
    skills_dir = HOME / "skills"
    if not skills_dir.is_dir():
        return {"count": 0, "categories": {}, "error": "skills dir not found"}

    categories = {}
    total_skills = 0

    for cat_dir in sorted(skills_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        cat_name = cat_dir.name
        skills = []
        cat_size = 0
        for skill_dir in sorted(cat_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                size = skill_md.stat().st_size
                cat_size += size
                skills.append({
                    "name": skill_dir.name,
                    "size": get_size_str(skill_md),
                    "size_bytes": size,
                    "modified": get_mtime_iso(skill_md),
                })

        if skills:
            categories[cat_name] = {
                "count": len(skills),
                "skills": skills,
                "total_size_bytes": cat_size,
            }
            total_skills += len(skills)

    return {
        "count": total_skills,
        "categories": categories,
        "directory": str(skills_dir),
    }


def collect_cron_info():
    jobs_file = HOME / "cron" / "jobs.json"
    if not jobs_file.exists():
        return {"count": 0, "jobs": [], "error": "cron jobs.json not found"}

    try:
        with open(jobs_file) as f:
            cron_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"count": 0, "jobs": [], "error": "invalid jobs.json"}

    jobs = cron_data.get("jobs", [])
    simplified = []
    for job in jobs:
        simplified.append({
            "id": job.get("id"),
            "name": job.get("name"),
            "enabled": job.get("enabled", False),
            "state": job.get("state"),
            "schedule": job.get("schedule_display", job.get("schedule", {})),
            "last_run_at": job.get("last_run_at"),
            "last_status": job.get("last_status"),
            "last_error": job.get("last_error"),
            "next_run_at": job.get("next_run_at"),
            "completed_count": job.get("repeat", {}).get("completed", 0),
            "script": job.get("script"),
            "skill": job.get("skill"),
        })

    return {
        "count": len(simplified),
        "jobs": simplified,
    }


def collect_health_info():
    info = {}

    # RAM via Python (avoid MSYS shell quoting issues)
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_mb"] = round(mem.total / (1024**2), 1)
        info["ram_used_mb"] = round(mem.used / (1024**2), 1)
        info["ram_free_mb"] = round(mem.available / (1024**2), 1)
        info["ram_used_pct"] = round(mem.percent, 1)
    except ImportError:
        # Fallback: read /proc/meminfo (WSL/MSYS2)
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                        info["ram_total_mb"] = total_kb // 1024
                    elif line.startswith("MemFree:"):
                        free_kb = int(line.split()[1])
                        info["ram_free_mb"] = free_kb // 1024
                if "ram_total_mb" in info and "ram_free_mb" in info:
                    info["ram_used_mb"] = info["ram_total_mb"] - info["ram_free_mb"]
                    info["ram_used_pct"] = round(info["ram_used_mb"] / info["ram_total_mb"] * 100, 1)
        except (FileNotFoundError, OSError):
            pass

    # Alternative /proc/meminfo
    if "ram_total_mb" not in info:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        info["ram_total_kb"] = int(line.split()[1])
                        info["ram_total_mb"] = info["ram_total_kb"] // 1024
                    elif line.startswith("MemFree:"):
                        info["ram_free_kb"] = int(line.split()[1])
                        info["ram_free_mb"] = info["ram_free_kb"] // 1024
            if "ram_total_mb" in info and "ram_free_mb" in info:
                info["ram_used_mb"] = info["ram_total_mb"] - info["ram_free_mb"]
                info["ram_used_pct"] = round(info["ram_used_mb"] / info["ram_total_mb"] * 100, 1)
        except (FileNotFoundError, OSError):
            pass

    # Disk via psutil
    try:
        import psutil
        du = psutil.disk_usage("C:/")
        info["disk_total_gb"] = round(du.total / (1024**3), 1)
        info["disk_free_gb"] = round(du.free / (1024**3), 1)
        info["disk_used_gb"] = round(du.used / (1024**3), 1)
        info["disk_used_pct"] = du.percent
    except (ImportError, PermissionError, FileNotFoundError):
        pass

    # CPU load via psutil
    try:
        import psutil
        info["cpu_pct"] = psutil.cpu_percent(interval=0.5)
    except ImportError:
        pass

    if "cpu_pct" not in info:
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().strip().split()
                if len(parts) >= 3:
                    info["cpu_load_1min"] = float(parts[0])
                    info["cpu_load_5min"] = float(parts[1])
                    info["cpu_load_15min"] = float(parts[2])
        except (FileNotFoundError, OSError):
            pass

    # Uptime via psutil
    try:
        import psutil
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_secs = (datetime.datetime.now() - boot_time).total_seconds()
        info["uptime_days"] = round(uptime_secs / 86400, 1)
        info["uptime_seconds"] = int(uptime_secs)
    except ImportError:
        pass

    return info


def collect_security_info():
    report_file = HOME / ".security-cve" / "last-report.json"
    if not report_file.exists():
        return {"last_scan": None, "cves_found": 0, "scan_exists": False, "error": "no scan data"}

    try:
        with open(report_file) as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"last_scan": None, "cves_found": 0, "scan_exists": True, "error": "invalid report"}

    summary = report.get("summary", {})
    return {
        "last_scan": report.get("timestamp"),
        "duration_seconds": report.get("duration_seconds"),
        "packages_scanned": report.get("packages_scanned"),
        "cves_found": summary.get("total_cves", 0),
        "critical": summary.get("critical", 0),
        "high": summary.get("high", 0),
        "medium": summary.get("medium", 0),
        "patches_applied": summary.get("patches_applied", 0),
        "scan_exists": True,
    }


def collect_backup_info():
    backups_dir = HOME / ".backups"
    if not backups_dir.exists():
        return {"backup_exists": False}

    # Look for latest backup
    backups = sorted(backups_dir.iterdir()) if backups_dir.is_dir() else []

    # Also check auto-backup pattern
    latest_backup = None
    for item in reversed(backups):
        if item.is_dir() or item.suffix == ".zip":
            latest_backup = {
                "name": item.name,
                "size": get_size_str(item) if item.is_file() else None,
                "modified": get_mtime_iso(item),
            }
            break

    return {
        "backup_exists": len(backups) > 0,
        "backup_count": len(backups),
        "backup_directory": str(backups_dir),
        "latest_backup": latest_backup,
    }


def collect_sessions_info():
    session_archive = HOME / ".session-archive"
    context_compressor = HOME / "context-compressor"
    state_db = HOME / "state.db"

    info = {}

    # Total archived sessions
    if session_archive.is_dir():
        count = 0
        for month_dir in session_archive.iterdir():
            if month_dir.is_dir():
                count += len([f for f in month_dir.iterdir() if f.suffix == ".json"])
        info["archived_sessions"] = count

    # Context compressor archives
    if context_compressor.is_dir():
        archives_dir = context_compressor / "archives"
        if archives_dir.is_dir():
            info["compressed_archives"] = len([f for f in archives_dir.iterdir() if f.suffix == ".json"])

    # State DB size
    if state_db.exists():
        info["state_db_size"] = get_size_str(state_db)
        info["state_db_size_bytes"] = state_db.stat().st_size

    # Recent sessions count from state db (SQLite query)
    if state_db.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(state_db))
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM sessions")
            info["total_sessions"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM messages")
            info["total_messages"] = c.fetchone()[0]
            conn.close()
        except Exception:
            pass

    return info


# ── Snapshot I/O ───────────────────────────────────────────────────────────

def save_snapshot(data):
    """Save snapshot to disk and return the filename."""
    ensure_snapshot_dir()
    now = datetime.datetime.now()
    filename = now.strftime("%Y-%m-%d_%H%M.json")
    path = SNAPSHOT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def load_snapshot(name_or_path):
    """Load snapshot by name (e.g., 'latest', filename, id, or full path)."""
    # If full path
    p = Path(name_or_path)
    if p.exists() and p.suffix == ".json":
        with open(p) as f:
            return json.load(f), p

    ensure_snapshot_dir()

    # Try as datetime prefix
    candidates = sorted(SNAPSHOT_DIR.glob(f"{name_or_path}*.json"))
    if candidates:
        with open(candidates[-1]) as f:
            return json.load(f), candidates[-1]

    # Try exact filename
    candidates = list(SNAPSHOT_DIR.glob(f"*{name_or_path}*.json"))
    if candidates:
        with open(candidates[0]) as f:
            return json.load(f), candidates[0]

    # "latest" → most recent
    all_snaps = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)
    if name_or_path == "latest" and all_snaps:
        with open(all_snaps[0]) as f:
            return json.load(f), all_snaps[0]

    raise FileNotFoundError(f"Snapshot '{name_or_path}' not found in {SNAPSHOT_DIR}")


def list_snapshots():
    """Return sorted list of snapshots."""
    ensure_snapshot_dir()
    snaps = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)
    result = []
    for s in snaps:
        name = s.stem  # YYYY-MM-DD_HHMM
        size = get_size_str(s)
        mtime = get_mtime_iso(s)
        result.append({
            "filename": s.name,
            "name": name,
            "size": size,
            "modified": mtime,
        })
    return result


# ── Diff / Compare ─────────────────────────────────────────────────────────

def compute_diff(snap_a, snap_b):
    """Compare two snapshot dicts, return structured diff."""
    diffs = {
        "changed_sections": [],
        "changes": {},
    }

    for section in ["os", "scripts", "skills", "cron", "health", "security", "backup", "sessions"]:
        a_val = snap_a.get(section, {})
        b_val = snap_b.get(section, {})
        if a_val != b_val:
            diffs["changed_sections"].append(section)
            section_diff = {}
            # Compare top-level keys
            all_keys = set(a_val.keys()) | set(b_val.keys())
            for key in sorted(all_keys):
                va = a_val.get(key)
                vb = b_val.get(key)
                if va != vb:
                    section_diff[key] = {"old": va, "new": vb}
            diffs["changes"][section] = section_diff

    # Compare snapshot timestamps
    diffs["snapshot_a"] = snap_a.get("snapshot_meta", {}).get("timestamp")
    diffs["snapshot_b"] = snap_b.get("snapshot_meta", {}).get("timestamp")
    diffs["total_changes"] = sum(len(v) for v in diffs["changes"].values())

    return diffs


# ── HTTP Server ────────────────────────────────────────────────────────────

def run_http_server(port=8898):
    """Simple HTTP server serving the latest snapshot as JSON."""
    import http.server

    class SnapshotHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                data, path = load_snapshot("latest")
                body = json.dumps(data, indent=2, default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Snapshot-File", path.name)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no snapshot yet — run --now first"}).encode("utf-8"))

        def log_message(self, format, *args):
            sys.stderr.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}\n")

    server = http.server.HTTPServer(("0.0.0.0", port), SnapshotHandler)
    print(f"[system-snapshot] HTTP server listening on http://0.0.0.0:{port}")
    print(f"[system-snapshot] GET / → latest snapshot JSON")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[system-snapshot] server stopped")
        server.server_close()


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="system-snapshot.py — Vollständiger Systemzustand auf einen Blick",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python system-snapshot.py --now          Einmaligen Snapshot erstellen
  python system-snapshot.py --diff         Unterschied zum letzten Snapshot
  python system-snapshot.py --list         Alle Snapshots auflisten
  python system-snapshot.py --compare A B  Zwei Snapshots vergleichen
  python system-snapshot.py --serve        HTTP-Server Port 8898
  python system-snapshot.py --serve --port 9999
        """,
    )

    parser.add_argument("--now", action="store_true", help="Einmaligen Snapshot erstellen")
    parser.add_argument("--diff", action="store_true", help="Unterschied zum letzten Snapshot")
    parser.add_argument("--list", action="store_true", help="Alle Snapshots auflisten")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Zwei Snapshots vergleichen")
    parser.add_argument("--serve", action="store_true", help="HTTP-Server (Port 8898)")
    parser.add_argument("--port", type=int, default=8898, help="Port für --serve (default: 8898)")

    args = parser.parse_args()

    # ── --serve ──
    if args.serve:
        run_http_server(args.port)
        return

    # ── --list ──
    if args.list:
        snaps = list_snapshots()
        if not snaps:
            print("Keine Snapshots vorhanden. Verwende --now für den ersten Snapshot.")
            return
        print(f"{'Snapshot':<22} {'Größe':<10} {'Letzte Änderung':<30}")
        print("-" * 62)
        for s in snaps:
            mtime = s["modified"][:19] if s["modified"] else "?"
            print(f"{s['name']:<22} {s['size']:<10} {mtime:<30}")
        print(f"\nTotal: {len(snaps)} Snapshots")
        return

    # ── --now ──
    if args.now:
        print("[system-snapshot] Erfasse Systemzustand...")
        data = collect_snapshot()
        path = save_snapshot(data)
        print(f"[system-snapshot] ✅ Snapshot gespeichert: {path}")
        print(f"[system-snapshot] OS: {data['os'].get('windows_version', '?')}")
        print(f"[system-snapshot] OpenAmer: {data['os'].get('openamer_version', '?')} | Commit: {data['os'].get('git_commit', '?')[:12]}")
        print(f"[system-snapshot] Skripte: {data['scripts'].get('count', 0)} | Skills: {data['skills'].get('count', 0)}")
        print(f"[system-snapshot] Cron-Jobs: {data['cron'].get('count', 0)} | RAM: {data['health'].get('ram_used_pct', '?')}%")
        print(f"[system-snapshot] CVEs: {data['security'].get('cves_found', '?')} | Sessions: {data['sessions'].get('total_sessions', '?')}")
        return

    # ── --diff ──
    if args.diff:
        snaps = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)
        if len(snaps) < 2:
            print("Wenigstens 2 Snapshots nötig für --diff. Erstelle zuerst mehrere mit --now.")
            return
        print(f"[system-snapshot] Vergleiche {snaps[0].stem} ↔ {snaps[1].stem}")
        data_a = json.load(open(snaps[1]))
        data_b = json.load(open(snaps[0]))
        diff = compute_diff(data_a, data_b)
        print(f"\nGeänderte Sektionen ({len(diff['changed_sections'])}): {', '.join(diff['changed_sections'])}")
        print(f"Total Einzeländerungen: {diff['total_changes']}")
        print()
        for section, changes in diff["changes"].items():
            if changes:
                print(f"  ── {section.upper()} ──")
                for key, change in sorted(changes.items()):
                    old_str = json.dumps(change["old"], default=str) if change["old"] is not None else "None"
                    new_str = json.dumps(change["new"], default=str) if change["new"] is not None else "None"
                    if len(old_str) > 60:
                        old_str = old_str[:57] + "..."
                    if len(new_str) > 60:
                        new_str = new_str[:57] + "..."
                    print(f"    {key}:")
                    print(f"      - {old_str}")
                    print(f"      + {new_str}")
                print()
        return

    # ── --compare A B ──
    if args.compare:
        a_name, b_name = args.compare
        try:
            data_a, path_a = load_snapshot(a_name)
            data_b, path_b = load_snapshot(b_name)
        except FileNotFoundError as e:
            print(f"Fehler: {e}")
            sys.exit(EXIT_ERR)

        print(f"[system-snapshot] Vergleiche {path_a.stem} ↔ {path_b.stem}")
        diff = compute_diff(data_a, data_b)
        print(f"\nGeänderte Sektionen ({len(diff['changed_sections'])}): {', '.join(diff['changed_sections'])}")
        print(f"Total Einzeländerungen: {diff['total_changes']}")
        print()
        for section, changes in diff["changes"].items():
            if changes:
                print(f"  ── {section.upper()} ──")
                for key, change in sorted(changes.items()):
                    old_str = json.dumps(change["old"], default=str) if change["old"] is not None else "None"
                    new_str = json.dumps(change["new"], default=str) if change["new"] is not None else "None"
                    if len(old_str) > 60:
                        old_str = old_str[:57] + "..."
                    if len(new_str) > 60:
                        new_str = new_str[:57] + "..."
                    print(f"    {key}:")
                    print(f"      - {old_str}")
                    print(f"      + {new_str}")
                print()
        return

    # Kein Argument → Hilfe
    parser.print_help()


if __name__ == "__main__":
    main()