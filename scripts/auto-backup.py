#!/usr/bin/env python3
"""
auto-backup.py — Tägliche Sicherung + Rotation + Wiederherstellung + optional encryption

CLI:
  --now             Backup sofort ausführen
  --list            Alle vorhandenen Backups anzeigen
  --restore DATUM   Backup von DATUM (YYYY-MM-DD) wiederherstellen
  --encrypt         Backup mit Fernet-Verschlüsselung (Key in .backup_key)
  --external PFAD   Backup auf externes Laufwerk/Verzeichnis schreiben
  --dry-run         Nur simulieren, nichts schreiben

Exit-Codes:
  0 = ok
  1 = backup fehlgeschlagen
  2 = kein Platz
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────
# Immer Windows-korrekte Pfade — OPENAMER_HOME kann MSYS-Pfad (/c/...) enthalten
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

BACKUP_SOURCES = [
    ("skills",            HOME / "skills"),
    ("scripts",           HOME / "scripts"),
    ("cron-jobs",         HOME / "cron" / "jobs.json"),
    ("config",            HOME / "config.yaml"),
    ("env",               HOME / ".env"),
    ("security-cve",      HOME / ".security-cve"),
    ("logs",              HOME / "logs"),
]

DEFAULT_TARGET  = Path.home() / "openamer-backups"

RETENTION = {
    "daily":   7,
    "weekly":  4,
    "monthly": 3,
}

KEY_FILE = HOME / ".backup_key"
MANIFEST = "manifest.json"

# Windows-reservierte Namen, die rmtree blockieren
_WINDOWS_RESERVED = {"nul", "con", "prn", "aux", "com1", "com2", "com3", "com4",
                     "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3",
                     "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}

# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _get_target(external: str | None) -> Path:
    """Gib das Zielverzeichnis zurück (default oder external)."""
    base = Path(external) if external else DEFAULT_TARGET
    base.mkdir(parents=True, exist_ok=True)
    return base


def _today_tag() -> str:
    return datetime.date.today().isoformat()


def _now_tag() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup_dir(base: Path, tag: str | None = None) -> Path:
    return base / (tag or _today_tag())


def _walk_backups(base: Path) -> list[tuple[str, Path]]:
    """Alle vorhandenen Backup-Verzeichnisse als (tag, path)."""
    results = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and p.name.count("-") == 2:
            try:
                datetime.date.fromisoformat(p.name)
                results.append((p.name, p))
            except ValueError:
                continue
    return results


def _free_space_gb(path: Path) -> float:
    """Freier Speicherplatz in GB. Nutzt shutil.disk_usage."""
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def _check_space(target: Path, estimated_gb: float = 1.0) -> bool:
    free = _free_space_gb(target)
    if free < estimated_gb:
        print(f"[FEHLER] Nicht genug Speicherplatz: {free:.2f} GB frei, {estimated_gb:.2f} GB benötigt")
        return False
    return True


def _safe_rmtree(path: Path):
    """Entferne Verzeichnisbaum und ignoriere Windows-reservierte Dateien."""
    def _onerror(func, p, exc_info):
        name = Path(p).name.lower()
        if name in _WINDOWS_RESERVED:
            print(f"[WARN] Überspringe Windows-reservierte Datei: {p}")
            return
        print(f"[WARN] Fehler beim Löschen von {p}: {exc_info[1]}")
    shutil.rmtree(path, onerror=_onerror)


def _zip_directory(src: Path, dst_zip: Path, encrypt: bool, key: bytes | None):
    """Packe src in eine ZIP-Datei und verschlüssele optional."""
    tmp_zip = dst_zip.with_suffix(".tmp.zip")
    try:
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in src.rglob("*"):
                if f.is_file() and f.name.lower() not in _WINDOWS_RESERVED:
                    arcname = str(f.relative_to(src))
                    zf.write(f, arcname)
        if encrypt and key:
            _encrypt_file(tmp_zip, dst_zip, key)
            tmp_zip.unlink()
        else:
            tmp_zip.rename(dst_zip)
    except Exception:
        if tmp_zip.exists():
            tmp_zip.unlink()
        raise


def _zip_file(src: Path, dst_zip: Path, encrypt: bool, key: bytes | None):
    """Packe eine einzelne Datei in eine ZIP."""
    tmp_zip = dst_zip.with_suffix(".tmp.zip")
    try:
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(src, src.name)
        if encrypt and key:
            _encrypt_file(tmp_zip, dst_zip, key)
            tmp_zip.unlink()
        else:
            tmp_zip.rename(dst_zip)
    except Exception:
        if tmp_zip.exists():
            tmp_zip.unlink()
        raise


def _encrypt_file(src: Path, dst: Path, key: bytes):
    """Verschlüssele src mit Fernet."""
    from cryptography.fernet import Fernet
    f = Fernet(key)
    data = src.read_bytes()
    encrypted = f.encrypt(data)
    dst.write_bytes(encrypted)


def _decrypt_file(src: Path, key: bytes) -> bytes:
    """Entschlüssele eine Fernet-verschlüsselte Datei."""
    from cryptography.fernet import Fernet
    f = Fernet(key)
    return f.decrypt(src.read_bytes())


def _get_or_create_key() -> bytes:
    """Lese oder erstelle den Fernet-Schlüssel."""
    if KEY_FILE.exists():
        raw = KEY_FILE.read_text().strip()
        return raw.encode() if isinstance(raw, str) else raw
    from cryptography.fernet import Fernet
    fkey = Fernet.generate_key()
    KEY_FILE.write_text(fkey.decode())
    KEY_FILE.chmod(0o600)
    print(f"[INFO] Neuer Backup-Key erstellt: {KEY_FILE}")
    return fkey


def _load_key() -> bytes | None:
    """Lade den Fernet-Schlüssel, falls vorhanden."""
    if not KEY_FILE.exists():
        return None
    raw = KEY_FILE.read_text().strip()
    return raw.encode()


def _is_encrypted(path: Path) -> bool:
    return path.suffix == ".enc"


def _extract_zip(src: Path, dst: Path, key: bytes | None):
    """Entpacke eine ZIP (ggf. entschlüsselt)."""
    if _is_encrypted(src):
        if not key:
            raise RuntimeError("Verschlüsseltes Backup, aber kein Schlüssel gefunden.")
        decrypted = _decrypt_file(src, key)
        tmp = src.with_suffix(".tmp.zip")
        tmp.write_bytes(decrypted)
        try:
            with zipfile.ZipFile(tmp) as zf:
                zf.extractall(dst)
        finally:
            if tmp.exists():
                tmp.unlink()
    else:
        with zipfile.ZipFile(src) as zf:
            zf.extractall(dst)


def _archive_label(tag: str, now: datetime.datetime) -> str:
    """Ermittle ob ein Backup daily/weekly/monthly ist."""
    day_obj = datetime.date.fromisoformat(tag)
    today = now.date()
    if day_obj.day <= 7 and (today - day_obj).days >= 21:
        return "monthly"
    if day_obj.weekday() == 0:
        return "weekly"
    return "daily"


# ── Hauptfunktionen ─────────────────────────────────────────────────────────

def cmd_now(encrypt: bool, external: str | None, dry_run: bool = False) -> int:
    """Führe Backup jetzt aus."""
    target = _get_target(external)
    tag = _today_tag()
    bdir = _backup_dir(target, tag)

    if bdir.exists():
        print(f"[HINWEIS] Backup für {tag} existiert bereits. Überschreibe.")
        if not dry_run:
            _safe_rmtree(bdir)

    if not _check_space(target, 0.5):
        return 2

    if dry_run:
        print(f"[DRY-RUN] Würde Backup nach {bdir} erstellen")
        print(f"[DRY-RUN] Quellen: {[str(s[1]) for s in BACKUP_SOURCES]}")
        return 0

    bdir.mkdir(parents=True, exist_ok=True)

    key = _get_or_create_key() if encrypt else None
    manifest_entries = []
    errors = []

    for name, src in BACKUP_SOURCES:
        if not src.exists():
            print(f"[WARN] Quelle nicht gefunden: {src}")
            manifest_entries.append({"name": name, "status": "skipped", "reason": "not_found"})
            continue

        ext = ".enc" if encrypt else ".zip"
        dst_zip = bdir / f"{name}{ext}"

        try:
            if src.is_dir():
                _zip_directory(src, dst_zip, encrypt, key)
            else:
                _zip_file(src, dst_zip, encrypt, key)
            manifest_entries.append({"name": name, "size": dst_zip.stat().st_size, "encrypted": encrypt, "status": "ok"})
            print(f"[OK] {name} → {dst_zip.name} ({dst_zip.stat().st_size / 1024:.1f} KB)")
        except Exception as e:
            errors.append(str(e))
            manifest_entries.append({"name": name, "status": "error", "error": str(e)})
            print(f"[FEHLER] {name}: {e}")

    # Metadaten
    checksums = {}
    for f in bdir.iterdir():
        if f.is_file() and f.name != MANIFEST:
            checksums[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()

    manifest = {
        "backup_date": tag,
        "backup_time": _now_tag(),
        "openamer_home": str(HOME),
        "target": str(target),
        "encrypted": encrypt,
        "entries": manifest_entries,
        "checksums": checksums,
        "total_size_bytes": sum(e.get("size", 0) for e in manifest_entries),
    }
    (bdir / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n[OK] Manifest: {bdir / MANIFEST}")

    _rotate(target)

    if errors:
        print(f"\n[FEHLER] {len(errors)} Fehler während Backup")
        return 1
    print(f"\n[OK] Backup abgeschlossen: {bdir}")
    return 0


def cmd_list(external: str | None) -> int:
    """Zeige alle vorhandenen Backups."""
    target = _get_target(external)
    backups = _walk_backups(target)

    if not backups:
        print(f"Keine Backups gefunden in: {target}")
        return 0

    print(f"{'DATUM':<14} {'GRÖSSE':>10} {'DATEIEN':>8} {'ENCRYPTED':>10}")
    print("-" * 50)
    for tag, bdir in backups:
        manifest = bdir / MANIFEST
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text())
                size_mb = m.get("total_size_bytes", 0) / (1024 * 1024)
                count = len(m.get("entries", []))
                encrypted = "ja" if m.get("encrypted") else "nein"
                print(f"{tag:<14} {size_mb:>8.1f} MB {count:>6} {encrypted:>10}")
            except (json.JSONDecodeError, KeyError):
                total = sum(f.stat().st_size for f in bdir.iterdir() if f.is_file())
                print(f"{tag:<14} {total / (1024*1024):>8.1f} MB {'?':>6} {'?':>10}")
        else:
            total = sum(f.stat().st_size for f in bdir.iterdir() if f.is_file())
            print(f"{tag:<14} {total / (1024*1024):>8.1f} MB {'?':>6} {'?':>10}")

    print(f"\nGefunden: {len(backups)} Backup(s) in {target}")
    return 0


def cmd_restore(tag: str, external: str | None, key: bytes | None = None, dry_run: bool = False) -> int:
    """Stelle Backup von einem bestimmten Datum wieder her."""
    target = _get_target(external)
    bdir = _backup_dir(target, tag)

    if not bdir.exists():
        print(f"[FEHLER] Kein Backup für {tag} gefunden in {target}")
        return 1

    if not key:
        key = _load_key()

    manifest_file = bdir / MANIFEST
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text())
        encrypted = manifest.get("encrypted", False)
    else:
        encrypted = any(f.suffix == ".enc" for f in bdir.iterdir())
        manifest = {"entries": [{"name": f.stem} for f in bdir.iterdir() if f.suffix in (".zip", ".enc")]}

    if encrypted and not key:
        print("[FEHLER] Backup ist verschlüsselt, aber kein Schlüssel gefunden.\n       Nutze --encrypt-key PFAD oder lege .backup_key an.")
        return 1

    if dry_run:
        print(f"[DRY-RUN] Würde Backup von {tag} wiederherstellen:")
        for entry in manifest.get("entries", []):
            print(f"  - {entry['name']}")
        return 0

    for entry in manifest.get("entries", []):
        name = entry["name"]
        ext = ".enc" if encrypted else ".zip"
        zip_file = bdir / f"{name}{ext}"
        if not zip_file.exists():
            print(f"[WARN] {zip_file} nicht gefunden, überspringe")
            continue

        src_map = {s[0]: s[1] for s in BACKUP_SOURCES}
        if name not in src_map:
            print(f"[WARN] {name} ist keine bekannte Quelle, überspringe")
            continue

        restore_path = src_map[name]

        # Backup existierender Dateien in temp-Verzeichnis
        if restore_path.exists():
            bak_dir = Path(tempfile.mkdtemp(prefix=f".backup_{name}_"))
            bak_path = bak_dir / restore_path.name
            try:
                if restore_path.is_dir():
                    shutil.copytree(restore_path, bak_path)
                else:
                    shutil.copy2(restore_path, bak_path)
                print(f"[INFO] Alte Daten gesichert nach: {bak_path}")
            except Exception as e:
                print(f"[WARN] Konnte alte Daten nicht sichern: {e}")

            # Lösche existierendes Ziel (mit Permission-Handling)
            try:
                if restore_path.is_dir():
                    _safe_rmtree(restore_path)
                else:
                    restore_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"[WARN] Fehler beim Löschen von {restore_path}: {e}")

        # Wiederherstellung
        try:
            if restore_path.suffix:  # einzelne Datei
                restore_path.parent.mkdir(parents=True, exist_ok=True)
                _extract_zip(zip_file, restore_path.parent, key)
            else:  # Verzeichnis
                restore_path.mkdir(parents=True, exist_ok=True)
                _extract_zip(zip_file, restore_path, key)
            print(f"[OK] {name} → {restore_path}")
        except Exception as e:
            print(f"[FEHLER] {name}: {e}")

    print(f"\n[OK] Wiederherstellung von {tag} abgeschlossen")
    return 0


def _rotate(target: Path):
    """Rotiere Backups: behalte 7 tägliche, 4 wöchentliche, 3 monatliche."""
    backups = _walk_backups(target)
    if not backups:
        return

    now = datetime.datetime.now()

    daily = []
    weekly = []
    monthly = []

    for tag, bdir in backups:
        label = _archive_label(tag, now)
        tgt = daily if label == "daily" else weekly if label == "weekly" else monthly
        tgt.append((tag, bdir))

    daily.sort()
    weekly.sort()
    monthly.sort()

    to_delete = []

    if len(daily) > RETENTION["daily"]:
        to_delete.extend(daily[:len(daily) - RETENTION["daily"]])
    if len(weekly) > RETENTION["weekly"]:
        to_delete.extend(weekly[:len(weekly) - RETENTION["weekly"]])
    if len(monthly) > RETENTION["monthly"]:
        to_delete.extend(monthly[:len(monthly) - RETENTION["monthly"]])

    for tag, bdir in to_delete:
        _safe_rmtree(bdir)
        print(f"[ROTATION] Gelöscht: {bdir} ({tag})")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OpenAmer Auto-Backup – Tägliche Sicherung + Rotation + Wiederherstellung"
    )
    parser.add_argument("--now", action="store_true", help="Backup jetzt ausführen")
    parser.add_argument("--list", action="store_true", help="Alle Backups anzeigen")
    parser.add_argument("--restore", metavar="YYYY-MM-DD", help="Backup wiederherstellen")
    parser.add_argument("--encrypt", action="store_true", help="Backup verschlüsseln (Fernet)")
    parser.add_argument("--encrypt-key", metavar="PFAD", help="Pfad zum Fernet-Schlüssel (statt .backup_key)")
    parser.add_argument("--external", metavar="PFAD", help="Externes Zielverzeichnis")
    parser.add_argument("--dry-run", action="store_true", help="Nur simulieren")
    args = parser.parse_args()

    if args.encrypt_key:
        key_path = Path(args.encrypt_key)
        if key_path.exists():
            global KEY_FILE
            KEY_FILE = key_path
        else:
            print(f"[FEHLER] Schlüsseldatei nicht gefunden: {key_path}")
            return 1

    if args.now:
        return cmd_now(encrypt=args.encrypt, external=args.external, dry_run=args.dry_run)
    elif args.list:
        return cmd_list(external=args.external)
    elif args.restore:
        key = _load_key()
        return cmd_restore(args.restore, external=args.external, key=key, dry_run=args.dry_run)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())