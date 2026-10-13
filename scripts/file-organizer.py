#!/usr/bin/env python3
"""
File Organizer – Desktop/Downloads/Documents Scan + Temp-Cleanup + Duplikaterkennung + Typ-Organizer + Undo

Usage:
  python file-organizer.py --scan              # Zeige eine Zusammenfassung
  python file-organizer.py --dry-run            # Zeige alle Aktionen ohne auszuführen
  python file-organizer.py --clean              # Lösche temporäre Dateien
  python file-organizer.py --dedupe             # Merge Duplikate (behalte eine, verlinke/verschiebe Rest)
  python file-organizer.py --organize           # Sortiere Dateien in Typ-Ordner
  python file-organizer.py --report             # Erstelle HTML-Report
  python file-organizer.py --undo               # Letzte Aktion rückgängig machen

State: ~/.file-organizer/state.json (History + Undo)
"""

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import sys
import time
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ─── Konfiguration ────────────────────────────────────────────────────────────

HOME = Path.home()
STATE_DIR = HOME / ".file-organizer"
STATE_FILE = STATE_DIR / "state.json"

SCAN_DIRS = [
    HOME / "Desktop",
    HOME / "Downloads",
    HOME / "Documents",
]

TEMP_EXTENSIONS = {".tmp", ".log", ".dmp", ".bak", ".temp", ".~tmp", ".cache", ".swp", ".swo"}
LARGE_FILE_THRESHOLD_MB = 100
ORGANIZE_EXTENSIONS = {
    # category -> set of extensions
    "Bilder":      {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".raw", ".heic"},
    "Dokumente":   {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".txt", ".rtf", ".md", ".csv", ".tsv"},
    "Archive":     {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst"},
    "Audio":       {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"},
    "Video":       {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "Code":        {".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".java", ".rs", ".go", ".rb", ".php", ".sh", ".bat", ".ps1", ".sql", ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg"},
    "Installers":  {".exe", ".msi", ".dmg", ".iso", ".appimage", ".deb", ".rpm", ".pkg"},
    "Fonts":       {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "Sonstiges":   set(),
}

# ─── State-Management ──────────────────────────────────────────────────────────

def load_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"actions": [], "scans": []}
    return {"actions": [], "scans": []}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def push_action(state, action_type, details):
    """Speichere eine Aktion im Undo-Stack."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": action_type,
        "details": details,
    }
    state["actions"].append(entry)
    # Begrenze den Stack auf 20 Einträge
    if len(state["actions"]) > 20:
        state["actions"] = state["actions"][-20:]
    save_state(state)
    return entry


def push_scan(state, scan_data):
    state["scans"].append(scan_data)
    if len(state["scans"]) > 50:
        state["scans"] = state["scans"][-50:]
    save_state(state)


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

def md5_hash(filepath: Path, chunk_size=65536):
    """Berechne MD5-Hash einer Datei."""
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def get_category(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in ORGANIZE_EXTENSIONS.items():
        if ext in exts:
            return cat
    return "Sonstiges"


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} GB"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def collect_files(dirs: list[Path]) -> list[dict]:
    """Sammle alle Dateien aus den angegebenen Verzeichnissen (flach — nur eine Ebene)."""
    files = []
    for d in dirs:
        if not d.is_dir():
            continue
        try:
            for entry in sorted(d.iterdir()):
                if entry.is_file() and not entry.name.startswith("."):
                    try:
                        stat = entry.stat()
                        files.append({
                            "path": entry,
                            "name": entry.name,
                            "size": stat.st_size,
                            "ext": entry.suffix.lower(),
                            "mtime": stat.st_mtime,
                            "dir": str(d),
                        })
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
    return files


# ─── Scan ─────────────────────────────────────────────────────────────────────

def run_scan(dirs=None, verbose=True) -> dict:
    """Führe einen vollständigen Scan durch."""
    if dirs is None:
        dirs = SCAN_DIRS

    files = collect_files(dirs)

    result = {
        "timestamp": datetime.now().isoformat(),
        "scanned_dirs": [str(d) for d in dirs],
        "total_files": len(files),
        "total_size": sum(f["size"] for f in files),
        "temp_files": [],
        "large_files": [],
        "duplicates": [],       # list of groups
        "similar_files": [],    # list of groups
        "by_category": defaultdict(list),
    }

    # a) Temporäre Dateien
    for f in files:
        if f["ext"] in TEMP_EXTENSIONS:
            result["temp_files"].append(f)

    # b) Große Dateien
    for f in files:
        if f["size"] >= LARGE_FILE_THRESHOLD_MB * 1_048_576:
            result["large_files"].append(f)

    # c) Duplikate (gleiche Größe + MD5)
    size_groups = defaultdict(list)
    for f in files:
        size_groups[f["size"]].append(f)

    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        hash_groups = defaultdict(list)
        for f in group:
            h = md5_hash(f["path"])
            if h:
                hash_groups[h].append(f)
        for h, hg in hash_groups.items():
            if len(hg) >= 2:
                result["duplicates"].append({
                    "hash": h,
                    "size": size,
                    "files": hg,
                })

    # d) Ähnliche Dateien (gleicher Name, ähnliche Größe ±10%)
    name_groups = defaultdict(list)
    for f in files:
        stem = Path(f["name"]).stem.lower()
        name_groups[stem].append(f)

    for stem, group in name_groups.items():
        if len(group) < 2:
            continue
        # Prüfe ähnliche Größe: alle Paare mit max 10% Abweichung
        sorted_by_size = sorted(group, key=lambda x: x["size"])
        similar_group = [sorted_by_size[0]]
        for f in sorted_by_size[1:]:
            prev = similar_group[-1]
            if prev["size"] > 0:
                ratio = max(f["size"], prev["size"]) / min(f["size"], prev["size"])
                if ratio <= 1.10:
                    similar_group.append(f)
                else:
                    if len(similar_group) >= 2:
                        result["similar_files"].append({
                            "stem": stem,
                            "files": list(similar_group),
                        })
                    similar_group = [f]
            else:
                similar_group.append(f)
        if len(similar_group) >= 2:
            result["similar_files"].append({
                "stem": stem,
                "files": list(similar_group),
            })

    # Kategorien
    for f in files:
        cat = get_category(f["ext"])
        result["by_category"][cat].append(f)

    if verbose:
        print_scan_report(result)

    return result


def print_scan_report(result: dict):
    print("=" * 60)
    print(f"  📋 FILE ORGANIZER – SCAN REPORT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"  Scan-Verzeichnisse: {len(result['scanned_dirs'])}")
    for d in result["scanned_dirs"]:
        print(f"    • {d}")
    print(f"  ─────────────────────────────────────────")
    print(f"  Gesamt: {result['total_files']} Dateien, {format_size(result['total_size'])}")
    print(f"  ─────────────────────────────────────────")

    # Temporäre Dateien
    if result["temp_files"]:
        temp_size = sum(f["size"] for f in result["temp_files"])
        print(f"\n  🗑️  TEMPORÄRE DATEIEN: {len(result['temp_files'])} ({format_size(temp_size)})")
        for f in sorted(result["temp_files"], key=lambda x: -x["size"])[:10]:
            print(f"    ⚠ {f['name']:45s} {format_size(f['size']):>10s}")
        if len(result["temp_files"]) > 10:
            print(f"    ... und {len(result['temp_files']) - 10} weitere")
    else:
        print(f"\n  ✅ Keine temporären Dateien gefunden.")

    # Große Dateien
    if result["large_files"]:
        large_size = sum(f["size"] for f in result["large_files"])
        print(f"\n  🐘 GROSSE DATEIEN >{LARGE_FILE_THRESHOLD_MB}MB: {len(result['large_files'])} ({format_size(large_size)})")
        for f in sorted(result["large_files"], key=lambda x: -x["size"])[:10]:
            print(f"    💾 {f['name']:45s} {format_size(f['size']):>10s}")
        if len(result["large_files"]) > 10:
            print(f"    ... und {len(result['large_files']) - 10} weitere")
    else:
        print(f"\n  ✅ Keine großen Dateien (>={LARGE_FILE_THRESHOLD_MB} MB) gefunden.")

    # Duplikate
    if result["duplicates"]:
        wasted = sum((len(g["files"]) - 1) * g["size"] for g in result["duplicates"])
        print(f"\n  🔁 DUPLIKATE: {len(result['duplicates'])} Gruppen (verschwendet: {format_size(wasted)})")
        for g in result["duplicates"][:5]:
            print(f"    📄 Hash={g['hash'][:12]}... ({format_size(g['size'])})")
            for f in g["files"]:
                print(f"      └ {f['path']}")
        if len(result["duplicates"]) > 5:
            print(f"    ... und {len(result['duplicates']) - 5} weitere Gruppen")
    else:
        print(f"\n  ✅ Keine Duplikate gefunden.")

    # Ähnliche Dateien
    if result["similar_files"]:
        print(f"\n  📁 ÄHNLICHE DATEIEN (gleicher Name, ähnliche Größe): {len(result['similar_files'])} Gruppen")
        for g in result["similar_files"][:5]:
            print(f"    🔀 Stammname: '{g['stem']}'")
            for f in g["files"]:
                print(f"      └ {os.path.basename(f['dir']):15s}/{f['name']:35s} {format_size(f['size']):>10s}")
        if len(result["similar_files"]) > 5:
            print(f"    ... und {len(result['similar_files']) - 5} weitere Gruppen")
    else:
        print(f"\n  ✅ Keine ähnlichen Dateigruppen gefunden.")

    # Kategorien
    print(f"\n  🗂️  KATEGORIEN:")
    for cat in sorted(result["by_category"].keys()):
        files = result["by_category"][cat]
        total = sum(f["size"] for f in files)
        print(f"    {cat:15s} {len(files):5d} Dateien, {format_size(total)}")
    print(f"{'='*60}\n")


# ─── Clean (Temp-Dateien löschen) ─────────────────────────────────────────────

def action_clean(dry_run=False):
    state = load_state()
    scan_result = run_scan(verbose=not dry_run)
    
    if not scan_result["temp_files"]:
        print("✅ Keine temporären Dateien zum Löschen.")
        return

    deleted = []
    for f in scan_result["temp_files"]:
        path = f["path"]
        if not dry_run:
            try:
                path.unlink()
                deleted.append({
                    "path": str(path),
                    "name": f["name"],
                    "size": f["size"],
                })
                print(f"  🗑️  Gelöscht: {path.name} ({format_size(f['size'])})")
            except (OSError, PermissionError) as e:
                print(f"  ❌ Fehler beim Löschen von {path}: {e}")
        else:
            print(f"  [DRY-RUN] Würde löschen: {path.name} ({format_size(f['size'])})")
            deleted.append({
                "path": str(path),
                "name": f["name"],
                "size": f["size"],
            })

    if not dry_run and deleted:
        push_action(state, "clean", {
            "deleted_files": deleted,
            "count": len(deleted),
            "freed_bytes": sum(d["size"] for d in deleted),
        })
        print(f"\n✅ {len(deleted)} temporäre Dateien gelöscht ({format_size(sum(d['size'] for d in deleted))} frei).")

    return deleted


# ─── Dedupe (Duplikate mergen) ────────────────────────────────────────────────

def action_dedupe(dry_run=False):
    state = load_state()
    scan_result = run_scan(verbose=not dry_run)

    if not scan_result["duplicates"]:
        print("✅ Keine Duplikate zum Zusammenführen.")
        return

    merged = []
    for group in scan_result["duplicates"]:
        files = group["files"]
        # Behalte die erste Datei, entferne den Rest
        keeper = files[0]
        for duplicate in files[1:]:
            dup_path = duplicate["path"]
            if not dry_run:
                try:
                    # Lösche das Duplikat (shallow — nur Datei, nicht Ordner)
                    dup_path.unlink()
                    merged.append({
                        "keeper": str(keeper["path"]),
                        "deleted": str(dup_path),
                        "size": duplicate["size"],
                        "hash": group["hash"],
                    })
                    print(f"  🔗 Behalten: {keeper['path'].name}")
                    print(f"     Gelöscht: {dup_path.name} ({format_size(duplicate['size'])})")
                except (OSError, PermissionError) as e:
                    print(f"  ❌ Fehler beim Löschen von {dup_path}: {e}")
            else:
                print(f"  [DRY-RUN] Würde Duplikat löschen: {dup_path}")
                print(f"            Behalten: {keeper['path']}")
                merged.append({
                    "keeper": str(keeper["path"]),
                    "deleted": str(dup_path),
                    "size": duplicate["size"],
                    "hash": group["hash"],
                })

    if not dry_run and merged:
        push_action(state, "dedupe", {
            "merged_groups": merged,
            "count": len(merged),
            "freed_bytes": sum(m["size"] for m in merged),
        })
        print(f"\n✅ {len(merged)} Duplikat(e) entfernt ({format_size(sum(m['size'] for m in merged))} frei).")

    return merged


# ─── Organize (Dateien nach Typ sortieren) ────────────────────────────────────

def action_organize(dry_run=False):
    state = load_state()
    scan_result = run_scan(verbose=not dry_run)

    if scan_result["total_files"] == 0:
        print("❌ Keine Dateien zum Organisieren.")
        return

    organized = []
    cat_count = defaultdict(int)

    for f in scan_result["by_category"]["Sonstiges"]:
        # Auch Sonstiges hat eine Extension-basierte Kategorie
        cat = get_category(f["ext"])
        cat_count[cat] += 1

    for cat, files in scan_result["by_category"].items():
        if cat == "Sonstiges":
            continue
        cat_count[cat] = len(files)

    for f in collect_files(SCAN_DIRS):
        cat = get_category(f["ext"])
        target_dir = f["path"].parent / cat
        target_path = target_dir / f["name"]

        if f["path"].parent.name == cat:
            continue  # bereits im richtigen Ordner

        if not dry_run:
            try:
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(f["path"]), str(target_path))
                organized.append({
                    "from": str(f["path"]),
                    "to": str(target_path),
                    "category": cat,
                    "size": f["size"],
                })
                print(f"  📦 {f['name']:40s} → {cat}/")
            except (OSError, shutil.Error) as e:
                # Ziel existiert bereits – überspringe
                print(f"  ⏭️  {f['name']:40s} existiert bereits in {cat}/ ({e})")
        else:
            print(f"  [DRY-RUN] {f['name']:40s} → {cat}/")
            organized.append({
                "from": str(f["path"]),
                "to": str(target_path),
                "category": cat,
                "size": f["size"],
            })

    if not dry_run and organized:
        push_action(state, "organize", {
            "moved_files": organized,
            "count": len(organized),
        })
        print(f"\n✅ {len(organized)} Dateien organisiert.")

    return organized


# ─── Undo ─────────────────────────────────────────────────────────────────────

def action_undo():
    state = load_state()
    if not state["actions"]:
        print("❌ Keine Aktionen zum Rückgängigmachen.")
        return

    last = state["actions"].pop()
    print(f"\n{'='*60}")
    print(f"  ↩️  UNDO – Letzte Aktion rückgängig machen")
    print(f"  Typ: {last['type']}")
    print(f"  Zeit: {last['timestamp']}")
    print(f"{'='*60}")

    details = last["details"]

    if last["type"] == "clean":
        # Gelöschte Temp-Dateien können nicht wiederhergestellt werden
        print(f"  ⚠️  Gelöschte temporäre Dateien können nicht wiederhergestellt werden.")
        print(f"  {details.get('count', 0)} Dateien ({format_size(details.get('freed_bytes', 0))})")
        print(f"  ── Keine Aktion möglich ──")

    elif last["type"] == "dedupe":
        restored = 0
        for m in details.get("merged_groups", []):
            # Das Duplikat wurde gelöscht – können es nicht wiederherstellen
            print(f"  ⚠️  Gelöschtes Duplikat '{Path(m['deleted']).name}' kann nicht wiederhergestellt werden.")
            restored += 1
        print(f"  ── Keine Wiederherstellung möglich (Dateien wurden endgültig gelöscht) ──")

    elif last["type"] == "organize":
        restored = 0
        for m in details.get("moved_files", []):
            src = Path(m["from"])
            dst = Path(m["to"])
            if dst.exists():
                try:
                    dst_dir = dst.parent
                    # Verschiebe zurück
                    shutil.move(str(dst), str(src))
                    restored += 1
                    print(f"  ↩️  {dst.name:40s} ← {dst.parent.name}/")
                    # Leere Ordner aufräumen
                    if dst_dir.exists() and not any(dst_dir.iterdir()):
                        try:
                            dst_dir.rmdir()
                            print(f"     🧹 Leeren Ordner '{dst_dir.name}/' entfernt.")
                        except OSError:
                            pass
                except (OSError, shutil.Error) as e:
                    print(f"  ❌ Fehler: {e}")
            else:
                print(f"  ⚠️  {dst.name} existiert nicht mehr ({dst.parent.name}/).")
        save_state(state)
        print(f"\n✅ {restored} Dateien zurückverschoben.")

    else:
        print(f"  ⚠️  Unbekannter Aktionstyp: {last['type']}")

    # Entferne die Aktion aus dem Stack (wir haben sie bereits gepoppt)
    save_state(state)
    return last


# ─── HTML Report ──────────────────────────────────────────────────────────────

def generate_html_report(result: dict, output_path: Path = None) -> Path:
    """Generiere einen HTML-Report."""
    if output_path is None:
        output_path = STATE_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    cat_rows = ""
    for cat in sorted(result["by_category"].keys()):
        files = result["by_category"][cat]
        total = sum(f["size"] for f in files)
        cat_rows += f"<tr><td>{cat}</td><td>{len(files)}</td><td>{format_size(total)}</td></tr>\n"

    temp_rows = ""
    for f in sorted(result["temp_files"], key=lambda x: -x["size"])[:20]:
        temp_rows += f"<tr class='warn'><td>{f['name']}</td><td>{os.path.basename(f['dir'])}</td><td>{format_size(f['size'])}</td></tr>\n"

    large_rows = ""
    for f in sorted(result["large_files"], key=lambda x: -x["size"])[:20]:
        large_rows += f"<tr class='warn'><td>{f['name']}</td><td>{os.path.basename(f['dir'])}</td><td>{format_size(f['size'])}</td></tr>\n"

    dup_rows = ""
    for g in result["duplicates"][:10]:
        wasted = (len(g["files"]) - 1) * g["size"]
        dup_rows += f"<tr><td>{g['hash'][:12]}...</td><td>{format_size(g['size'])}</td><td>{len(g['files'])}×</td><td>{format_size(wasted)}</td><td>"
        for f in g["files"]:
            dup_rows += f"{os.path.basename(f['dir'])}/{f['name']}<br>"
        dup_rows += "</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>File Organizer Report</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 1000px; margin: 2em auto;
         background: #1a1a2e; color: #e0e0e0; padding: 0 1em; }}
  h1 {{ color: #e94560; border-bottom: 2px solid #e94560; padding-bottom: .3em; }}
  h2 {{ color: #0f3460; margin-top: 2em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ text-align: left; padding: .5em .8em; border-bottom: 1px solid #16213e; }}
  th {{ background: #0f3460; color: #e94560; }}
  tr:hover {{ background: #16213e; }}
  .warn td {{ color: #ffa726; }}
  .ok {{ color: #66bb6a; }}
  .summary {{ display: flex; gap: 1em; flex-wrap: wrap; margin: 1em 0; }}
  .card {{ background: #16213e; border-radius: 8px; padding: 1em 1.5em; flex: 1; min-width: 140px; }}
  .card .num {{ font-size: 1.8em; font-weight: bold; color: #e94560; }}
  .card .label {{ font-size: .85em; color: #aaa; }}
  footer {{ margin-top: 3em; font-size: .85em; color: #666; text-align: center; }}
</style>
</head>
<body>
<h1>📋 File Organizer Report</h1>
<p>Erstellt: {result['timestamp']}</p>

<div class="summary">
  <div class="card"><div class="num">{result['total_files']}</div><div class="label">Dateien gesamt</div></div>
  <div class="card"><div class="num">{format_size(result['total_size'])}</div><div class="label">Gesamtgröße</div></div>
  <div class="card"><div class="num">{len(result['temp_files'])}</div><div class="label">Temp-Dateien</div></div>
  <div class="card"><div class="num">{len(result['large_files'])}</div><div class="label">Große Dateien</div></div>
  <div class="card"><div class="num">{len(result['duplicates'])}</div><div class="label">Duplikat-Gruppen</div></div>
</div>

<h2>🗂️ Kategorien</h2>
<table><tr><th>Kategorie</th><th>Anzahl</th><th>Größe</th></tr>{cat_rows}</table>

<h2>🗑️ Temporäre Dateien</h2>
{"<table><tr><th>Datei</th><th>Ordner</th><th>Größe</th></tr>" + temp_rows + "</table>" if temp_rows else "<p class='ok'>✅ Keine temporären Dateien gefunden.</p>"}

<h2>🐘 Große Dateien (>={LARGE_FILE_THRESHOLD_MB} MB)</h2>
{"<table><tr><th>Datei</th><th>Ordner</th><th>Größe</th></tr>" + large_rows + "</table>" if large_rows else "<p class='ok'>✅ Keine großen Dateien gefunden.</p>"}

<h2>🔁 Duplikate</h2>
{"<table><tr><th>Hash</th><th>Größe</th><th>Kopien</th><th>Verschwendet</th><th>Pfade</th></tr>" + dup_rows + "</table>" if dup_rows else "<p class='ok'>✅ Keine Duplikate gefunden.</p>"}

<footer>File Organizer · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</footer>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"📄 HTML-Report erstellt: {output_path}")
    return output_path


# ─── Haupt ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="File Organizer – Desktop/Downloads/Documents verwalten")
    parser.add_argument("--scan", action="store_true", help="Scan durchführen und Bericht anzeigen")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ausführen")
    parser.add_argument("--clean", action="store_true", help="Temporäre Dateien löschen")
    parser.add_argument("--dedupe", action="store_true", help="Duplikate entfernen")
    parser.add_argument("--organize", action="store_true", help="Dateien nach Typ in Ordner sortieren")
    parser.add_argument("--report", action="store_true", help="HTML-Report erstellen und öffnen")
    parser.add_argument("--undo", action="store_true", help="Letzte Aktion rückgängig machen")
    parser.add_argument("--output", type=str, help="Report-Ausgabepfad (nur mit --report)")
    args = parser.parse_args()

    if args.scan:
        result = run_scan()
        state = load_state()
        push_scan(state, {
            "timestamp": result["timestamp"],
            "total_files": result["total_files"],
            "total_size": result["total_size"],
            "temp_count": len(result["temp_files"]),
            "large_count": len(result["large_files"]),
            "dup_groups": len(result["duplicates"]),
        })
        return

    if args.clean:
        action_clean(dry_run=args.dry_run)
        return

    if args.dedupe:
        action_dedupe(dry_run=args.dry_run)
        return

    if args.organize:
        action_organize(dry_run=args.dry_run)
        return

    if args.undo:
        action_undo()
        return

    if args.report:
        result = run_scan(verbose=False)
        output = Path(args.output) if args.output else None
        path = generate_html_report(result, output)
        # Öffne im Browser
        try:
            webbrowser.open(str(path))
        except Exception:
            pass
        return

    # Kein Argument → zeige Hilfe
    parser.print_help()
    print("\n💡 Tipp: Verwende --scan für einen ersten Überblick oder --dry-run --organize um zu sehen, was passieren würde.")


if __name__ == "__main__":
    main()