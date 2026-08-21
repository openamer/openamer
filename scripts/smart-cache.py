#!/usr/bin/env python3
"""
Smart Cache v1.0 — Cache-Analyse + Auto-Cleanup + Skill-Archivierung + Warm-Cache
=============================================================================
Analysiert Cache-Grössen, löscht veraltete Dateien, archiviert seltene Skills.

CLI:
  --scan       Cache-Grössen anzeigen
  --clean      Veraltete Dateien löschen (tmp>24h, logs>7d, cache>500MB)
  --warm       Seltene Skills (>30 Tage ungenutzt) archivieren (zip)
  --stats      JSON-Report ausgeben
  --dry-run    Nur zeigen, nichts löschen
  --force      Wirklich löschen (ohne --force nur Simulation)

Exit-Codes:
  0 = OK, alles sauber
  1 = Cache > 1 GB (Warnung)
  2 = Kein Cleanup nötig
"""

import argparse
import datetime
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

# ─── Konfiguration ───────────────────────────────────────────────
def _normalize_path(raw: str) -> Path:
    """MSYS-Pfade (/c/Users/…) in Windows-Pfade (C:\\Users\…) umwandeln."""
    raw = raw.strip()
    if raw.startswith("/") and len(raw) > 2 and raw[2] == "/":
        # /c/Users/... → C:\Users\...
        raw = raw[1].upper() + ":" + raw[2:]
    return Path(raw).resolve()


def _detect_openamer_home() -> Path:
    """Ermittelt OPENAMER_HOME zuverlässig, auch unter MSYS/bash."""
    env_path = os.environ.get("OPENAMER_HOME")
    if env_path:
        p = _normalize_path(env_path)
        if p.exists():
            return p
    # Fallback
    return Path(r"C:\Users\damir\AppData\Local\openamer-laptop")

OPENAMER_HOME = _detect_openamer_home()

# Ordner die analysiert/gesäubert werden
CACHE_DIRS = {
    "skills/.hub":       {"max_mb": 500, "max_age_h": 0,    "label": "Skills Hub Cache"},
    "scripts/node_modules": {"max_mb": 500, "max_age_h": 0, "label": "Node Modules"},
    "logs":              {"max_mb": 500, "max_age_h": 168,  "label": "Logs", "glob": "*.log"},
    ".security-cve":     {"max_mb": 500, "max_age_h": 0,    "label": "Security CVE Cache"},
    ".predictive-health": {"max_mb": 500, "max_age_h": 0,   "label": "Predictive Health"},
    "cron/output":       {"max_mb": 500, "max_age_h": 72,   "label": "Cron Output", "glob": "*"},
}

TEMP_GLOBS = ["*.tmp", "*.temp", "*.swp", "*.bak", "~*"]
TEMP_MAX_AGE_H = 24  # tmp-Dateien > 24h löschen
LOG_MAX_AGE_H = 168   # Logs > 7 Tage löschen
SKILL_ARCHIVE_AGE_DAYS = 30  # Skills >30 Tage ungenutzt → archivieren
WARN_THRESHOLD_MB = 1024     # Warnung bei >1 GB


def fmt_size(bytes_: int) -> str:
    """Bytes in lesbares Format."""
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 ** 2:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024 ** 3:
        return f"{bytes_ / 1024 ** 2:.1f} MB"
    return f"{bytes_ / 1024 ** 3:.2f} GB"


def dir_size(path: Path) -> int:
    """Gesamtgrösse eines Verzeichnisses."""
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
    return total


def count_files(path: Path, pattern: str = "*") -> int:
    """Anzahl Dateien in einem Verzeichnis (rekursiv)."""
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob(pattern) if _.is_file())


def read_skill_usage() -> dict:
    """Liest .usage.json mit Skill-Nutzungsdaten."""
    usage_file = OPENAMER_HOME / "skills" / ".usage.json"
    if not usage_file.exists():
        return {}
    try:
        return json.loads(usage_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def find_rare_skills(days: int = SKILL_ARCHIVE_AGE_DAYS) -> list[dict]:
    """
    Findet Skills die >days Tage nicht benutzt wurden.
    Gibt Liste mit {name, last_used, days_idle, path, size}.
    """
    usage = read_skill_usage()
    now = datetime.datetime.now(datetime.timezone.utc)
    rare = []
    cutoff = now - datetime.timedelta(days=days)

    skills_dir = OPENAMER_HOME / "skills"
    for cat_dir in skills_dir.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        for skill_dir in cat_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            sk = usage.get(skill_name, {})
            last_used_str = sk.get("last_used_at") or sk.get("last_viewed_at")
            last_used = None
            days_idle = 9999

            if last_used_str:
                try:
                    last_used = datetime.datetime.fromisoformat(last_used_str)
                    days_idle = (now - last_used).days
                except (ValueError, TypeError):
                    days_idle = 9999

            if last_used is None or days_idle > days:
                sz = dir_size(skill_dir)
                rare.append({
                    "name": skill_name,
                    "path": str(skill_dir),
                    "last_used": last_used_str or "never",
                    "days_idle": days_idle,
                    "size": sz,
                    "size_fmt": fmt_size(sz),
                    "use_count": sk.get("use_count", 0),
                    "view_count": sk.get("view_count", 0),
                })
    # Sortieren: nie benutzte zuerst, dann längste idle
    rare.sort(key=lambda x: (-x["days_idle"], x["name"]))
    return rare


def archive_skills(rare_skills: list[dict], dry_run: bool = False) -> tuple[int, list[str]]:
    """
    Archiviert seltene Skills als ZIP.
    Gibt (anzahl_archiviert, fehler) zurück.
    """
    archive_dir = OPENAMER_HOME / ".skill-archives"
    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    archived_count = 0
    errors = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    for sk in rare_skills:
        skill_path = Path(sk["path"])
        if not skill_path.exists():
            continue
        name = sk["name"]

        if dry_run:
            print(f"  [DRY-RUN] Würde archivieren: {name} "
                  f"({sk['size_fmt']}, {sk['days_idle']} Tage ungenutzt)")
            archived_count += 1
            continue

        zip_name = f"{name}_{timestamp}.zip"
        zip_path = archive_dir / zip_name

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in skill_path.rglob("*"):
                    if f.is_file():
                        arcname = str(f.relative_to(skill_path))
                        zf.write(f, arcname)
            # Original löschen nach erfolgreicher Archivierung
            shutil.rmtree(skill_path)
            print(f"  → Archiviert: {name} → {zip_path.name} ({sk['size_fmt']})")
            archived_count += 1
        except (OSError, zipfile.BadZipFile) as e:
            errors.append(f"{name}: {e}")
            print(f"  ✗ Fehler bei {name}: {e}")

    return archived_count, errors


def scan_cache() -> dict:
    """Scannt alle Cache-Ordner, gibt Dict mit Ergebnissen."""
    results = {}
    total_size = 0
    total_warn = False

    print("=" * 60)
    print("  SMART CACHE — Analyse")
    print("=" * 60)
    print(f"  Basis: {OPENAMER_HOME}\n")

    for rel_path, config in CACHE_DIRS.items():
        full_path = OPENAMER_HOME / rel_path
        sz = dir_size(full_path)
        fc = count_files(full_path)
        total_size += sz
        max_bytes = config["max_mb"] * 1024 * 1024
        over_limit = sz > max_bytes
        if over_limit:
            total_warn = True

        result = {
            "path": rel_path,
            "label": config["label"],
            "size": sz,
            "size_fmt": fmt_size(sz),
            "files": fc,
            "max_mb": config["max_mb"],
            "over_limit": over_limit,
        }
        results[rel_path] = result

        status = "⚠ OVER LIMIT" if over_limit else "✓ OK"
        print(f"  {config['label']:25s}  {fmt_size(sz):>10s}  {fc:>5d} files  {status}")
        if over_limit:
            print(f"  {'':25s}  Limit: {config['max_mb']} MB, "
                  f"Überschuss: {fmt_size(sz - max_bytes)}")

    # Temp-Dateien scannen
    temp_total = 0
    temp_files_list = []
    for root, _dirs, files in os.walk(OPENAMER_HOME):
        for fn in files:
            for g in TEMP_GLOBS:
                if fn.startswith(g.replace("*", "")) or fn.endswith(g.lstrip("*")):
                    fp = Path(root) / fn
                    try:
                        mtime = fp.stat().st_mtime
                        age_h = (time.time() - mtime) / 3600
                        temp_total += 1
                        temp_files_list.append({"path": str(fp), "size": fp.stat().st_size, "age_h": round(age_h, 1)})
                    except OSError:
                        pass

    results["_temp"] = {
        "path": "verschiedene",
        "label": "Temporäre Dateien",
        "count": temp_total,
        "total_size": sum(f["size"] for f in temp_files_list),
        "total_size_fmt": fmt_size(sum(f["size"] for f in temp_files_list)),
        "files": temp_files_list,
    }
    if temp_total:
        print(f"\n  {'Temporäre Dateien':25s}  {fmt_size(sum(f['size'] for f in temp_files_list)):>10s}  {temp_total:>5d} files")

    total_mb = total_size / (1024 * 1024)
    results["_total"] = {
        "size": total_size,
        "size_fmt": fmt_size(total_size),
        "warn": total_mb > WARN_THRESHOLD_MB,
    }

    print(f"\n  {'GESAMT':25s}  {fmt_size(total_size):>10s}")
    if total_mb > WARN_THRESHOLD_MB:
        print(f"  ⚠ WARNUNG: Cache > {WARN_THRESHOLD_MB} MB ({fmt_size(total_size)})")
    print()

    return results


def clean_temp(dry_run: bool, force: bool) -> tuple[int, int]:
    """
    Löscht temporäre Dateien älter als TEMP_MAX_AGE_H.
    Gibt (gelöscht, bytes) zurück.
    """
    if not force and not dry_run:
        print("  --clean erfordert --force (Sicherheitsbestätigung)")
        return 0, 0

    deleted = 0
    freed_bytes = 0
    cutoff = time.time() - TEMP_MAX_AGE_H * 3600

    print(f"  Temporäre Dateien > {TEMP_MAX_AGE_H}h alt durchsuchen...")
    for root, _dirs, files in os.walk(OPENAMER_HOME):
        for fn in files:
            for g in TEMP_GLOBS:
                if fn.startswith(g.replace("*", "")) or fn.endswith(g.lstrip("*")):
                    fp = Path(root) / fn
                    try:
                        mtime = fp.stat().st_mtime
                        if mtime < cutoff:
                            sz = fp.stat().st_size
                            if dry_run:
                                print(f"  [DRY-RUN] Löschen: {fp} ({fmt_size(sz)})")
                            else:
                                fp.unlink()
                            deleted += 1
                            freed_bytes += sz
                    except OSError:
                        pass

    mode = "[DRY-RUN]" if dry_run else ""
    print(f"  {mode} Temporäre Dateien: {deleted} gelöscht, {fmt_size(freed_bytes)} freigegeben")
    return deleted, freed_bytes


def clean_logs(dry_run: bool, force: bool) -> tuple[int, int]:
    """
    Löscht Logs älter als LOG_MAX_AGE_H.
    """
    if not force and not dry_run:
        return 0, 0

    deleted = 0
    freed_bytes = 0
    cutoff = time.time() - LOG_MAX_AGE_H * 3600
    log_dir = OPENAMER_HOME / "logs"

    if not log_dir.exists():
        return 0, 0

    print(f"  Log-Dateien > {LOG_MAX_AGE_H}h ({LOG_MAX_AGE_H//24}d) alt durchsuchen...")
    for fp in log_dir.rglob("*.log"):
        try:
            mtime = fp.stat().st_mtime
            if mtime < cutoff:
                sz = fp.stat().st_size
                if dry_run:
                    print(f"  [DRY-RUN] Löschen: {fp} ({fmt_size(sz)})")
                else:
                    fp.unlink()
                deleted += 1
                freed_bytes += sz
        except OSError:
            pass

    # Auch cron/output/ Logs
    cron_out = OPENAMER_HOME / "cron" / "output"
    if cron_out.exists():
        for fp in cron_out.iterdir():
            try:
                mtime = fp.stat().st_mtime
                if mtime < cutoff:
                    sz = fp.stat().st_size
                    if dry_run:
                        print(f"  [DRY-RUN] Löschen: {fp} ({fmt_size(sz)})")
                    else:
                        fp.unlink()
                    deleted += 1
                    freed_bytes += sz
            except OSError:
                pass

    mode = "[DRY-RUN]" if dry_run else ""
    print(f"  {mode} Logs/Cron-Output: {deleted} gelöscht, {fmt_size(freed_bytes)} freigegeben")
    return deleted, freed_bytes


def clean_over_limit_caches(dry_run: bool, force: bool) -> tuple[int, int]:
    """
    Leert Cache-Ordner die über ihrem Limit liegen.
    """
    if not force and not dry_run:
        return 0, 0

    deleted_files = 0
    freed_bytes = 0

    for rel_path, config in CACHE_DIRS.items():
        full_path = OPENAMER_HOME / rel_path
        if not full_path.exists():
            continue

        max_bytes = config["max_mb"] * 1024 * 1024
        sz = dir_size(full_path)
        if sz <= max_bytes:
            continue  # unter Limit, nix tun

        overshoot = sz - max_bytes
        print(f"  {config['label']}: {fmt_size(sz)} > Limit {config['max_mb']} MB "
              f"(Überschuss: {fmt_size(overshoot)})")

        if config.get("glob"):
            # Nach Alter löschen (älteste zuerst)
            glob_pattern = config["glob"]
            files = sorted(
                [f for f in full_path.rglob(glob_pattern) if f.is_file()],
                key=lambda x: x.stat().st_mtime,
            )
            freed_here = 0
            for fp in files:
                if freed_here >= overshoot:
                    break
                try:
                    sz_f = fp.stat().st_size
                    if dry_run:
                        print(f"    [DRY-RUN] Löschen: {fp} ({fmt_size(sz_f)})")
                    else:
                        fp.unlink()
                    deleted_files += 1
                    freed_here += sz_f
                    freed_bytes += sz_f
                except OSError:
                    pass
            mode = "[DRY-RUN]" if dry_run else ""
            print(f"    {mode} Gelöscht: {deleted_files} Dateien, {fmt_size(freed_here)} freigegeben")
        else:
            # Kompletten Cache leeren
            if dry_run:
                print(f"    [DRY-RUN] Würde leeren: {full_path}")
            else:
                for fp in full_path.iterdir():
                    try:
                        if fp.is_file():
                            freed_bytes += fp.stat().st_size
                            fp.unlink()
                            deleted_files += 1
                        elif fp.is_dir():
                            sz_d = dir_size(fp)
                            freed_bytes += sz_d
                            shutil.rmtree(fp)
                            deleted_files += 1
                    except OSError:
                        pass
                mode = ""
                print(f"    {mode} Cache geleert: {full_path}")

    return deleted_files, freed_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Smart Cache — Cache-Analyse, Auto-Cleanup & Skill-Archivierung",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit-Codes:\n"
            "  0 = OK, alles sauber\n"
            "  1 = Cache > 1 GB (Warnung)\n"
            "  2 = Kein Cleanup nötig\n"
            "\n"
            "Beispiele:\n"
            "  python smart-cache.py --scan\n"
            "  python smart-cache.py --clean --force\n"
            "  python smart-cache.py --warm\n"
            "  python smart-cache.py --stats --dry-run\n"
        ),
    )
    parser.add_argument("--scan", action="store_true", help="Cache-Grössen anzeigen")
    parser.add_argument("--clean", action="store_true", help="Veraltete Dateien löschen")
    parser.add_argument("--warm", action="store_true", help="Seltene Skills archivieren")
    parser.add_argument("--stats", action="store_true", help="JSON-Report ausgeben")
    parser.add_argument("--dry-run", action="store_true", help="Nur zeigen, nichts löschen")
    parser.add_argument("--force", action="store_true", help="Wirklich löschen")

    args = parser.parse_args()

    # Kein Arg → scan
    if not any([args.scan, args.clean, args.warm, args.stats]):
        args.scan = True

    exit_code = 0
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "openamer_home": str(OPENAMER_HOME),
        "actions": [],
        "warnings": [],
    }

    # ─── SCAN ───
    if args.scan or args.stats:
        scan_result = scan_cache()
        report["scan"] = {
            "caches": {k: v for k, v in scan_result.items() if not k.startswith("_")},
            "temp": scan_result.get("_temp", {"count": 0}),
            "total": scan_result.get("_total", {}),
        }
        if scan_result.get("_total", {}).get("warn"):
            report["warnings"].append("Cache > 1 GB")
            exit_code = 1

    # ─── CLEAN ───
    if args.clean:
        print("─── CLEAN ───")
        action = {"type": "clean", "dry_run": args.dry_run, "force": args.force}

        if args.dry_run or args.force:
            d1, b1 = clean_temp(args.dry_run, args.force)
            d2, b2 = clean_logs(args.dry_run, args.force)
            d3, b3 = clean_over_limit_caches(args.dry_run, args.force)

            action["deleted_files"] = d1 + d2 + d3
            action["freed_bytes"] = b1 + b2 + b3
            action["freed_fmt"] = fmt_size(b1 + b2 + b3)

            if d1 + d2 + d3 == 0:
                action["note"] = "Kein Cleanup nötig"
                if exit_code == 0:
                    exit_code = 2
        else:
            print("  --clean erfordert --force (Sicherheitsbestätigung)")
            action["note"] = "--clean without --force: no action taken"
            exit_code = 2

        report["actions"].append(action)
        print()

    # ─── WARM ───
    if args.warm:
        print("─── WARM (Skill-Archivierung) ───")
        action = {"type": "warm", "dry_run": args.dry_run}

        rare = find_rare_skills()
        print(f"  Gefunden: {len(rare)} seltene Skills (>={SKILL_ARCHIVE_AGE_DAYS} Tage ungenutzt)\n")

        if rare:
            for sk in rare[:10]:
                print(f"  • {sk['name']:35s}  idle: {sk['days_idle']:>3d} Tage  "
                      f"size: {sk['size_fmt']:>10s}  uses: {sk['use_count']}")
            if len(rare) > 10:
                print(f"  ... und {len(rare) - 10} weitere")

            archived, errors = archive_skills(rare, args.dry_run)
            action["found_rare"] = len(rare)
            action["archived"] = archived
            if errors:
                action["errors"] = errors

            if archived and not args.dry_run:
                print(f"\n  ✓ {archived} Skills archiviert in {OPENAMER_HOME / '.skill-archives'}")
        else:
            print("  Keine seltenen Skills gefunden.")
            action["note"] = "Keine seltenen Skills"

        report["actions"].append(action)
        print()

    # ─── STATS (JSON) ───
    if args.stats:
        print(json.dumps(report, indent=2, default=str))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()