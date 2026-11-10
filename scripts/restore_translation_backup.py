"""Restore the translation caches from the pre-update backup.

An `openamer update` replaces the install tree and kills every running process,
including the detached translation workers. The translated keys survive in two
places: the committed files (locales/*.yaml, apps/desktop/src/i18n/*.ts) and the
per-language caches. This script puts the caches back so a restarted worker
resumes from where it stopped instead of re-translating from zero.

Usage:
    python scripts/restore_translation_backup.py --backup <dir>
    python scripts/restore_translation_backup.py --latest
    python scripts/restore_translation_backup.py --latest --dry-run
"""
from __future__ import annotations

import argparse
import os
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(
    os.environ.get("OPENAMER_HOME")
    or (Path.home() / "AppData" / "Local" / "openamer-laptop")
)
BACKUP_ROOT = Path.home() / "openamer-work-backup"


def normalise(raw: str) -> Path:
    """Accept an MSYS path (/c/Users/...) as well as a native one.

    A marker written from a git-bash shell carries the MSYS form, which Windows
    Python resolves relative to the current drive as a literal backslash-c
    directory -- a path that never exists. On POSIX /c/... is a legitimate
    absolute path, so the rewrite stays Windows-only: translating it there
    would turn a working path into a broken one.
    """
    text = raw.strip()
    if (os.name == "nt" and len(text) >= 3 and text[0] == "/"
            and text[2] == "/" and text[1].isalpha()):
        return Path(f"{text[1].upper()}:/{text[3:]}")
    return Path(text)


def latest_backup() -> Path:
    marker = BACKUP_ROOT / "LATEST.txt"
    if marker.exists():
        return normalise(marker.read_text(encoding="utf-8"))
    dirs = sorted(p for p in BACKUP_ROOT.iterdir() if p.is_dir()) if BACKUP_ROOT.exists() else []
    if not dirs:
        raise SystemExit(f"no backup found under {BACKUP_ROOT}")
    return dirs[-1]


def count_entries(path: Path) -> int:
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return -1


def restore(backup: Path, dry_run: bool) -> int:
    targets = [
        (backup / "cli-cache", REPO / "tmp", "i18n_cli_"),
        (backup / "desktop-cache", HOME / "tmp", "desktop_"),
    ]
    total_files = total_keys = 0
    for src_dir, dst_dir, _prefix in targets:
        if not src_dir.is_dir():
            print(f"  skip {src_dir.name}: not in backup")
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_dir.glob("*.json")):
            dst = dst_dir / src.name
            keys = count_entries(src)
            if dst.exists() and count_entries(dst) >= keys:
                print(f"  keep {src.name}: destination already has {count_entries(dst)} keys")
                continue
            print(f"  {'would restore' if dry_run else 'restore'} {src.name} ({keys} keys)"
                  f" -> {dst_dir}")
            if not dry_run:
                shutil.copy2(src, dst)
            total_files += 1
            total_keys += max(keys, 0)
    verb = "would restore" if dry_run else "restored"
    print(f"{verb} {total_files} cache file(s), {total_keys} translated keys")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", type=Path)
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    backup = args.backup or (latest_backup() if args.latest else None)
    if backup is None:
        ap.error("pass --backup <dir> or --latest")
    if not backup.is_dir():
        print(f"not a directory: {backup}", file=sys.stderr)
        return 2
    print(f"backup: {backup}")
    return restore(backup, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
