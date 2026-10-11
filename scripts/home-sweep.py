#!/usr/bin/env python3
"""Native home-hygiene organ — quarantine *provable* junk out of the user's HOME.

Owned by the ASI heartbeat (infra subsystem), not a standalone cron.  It runs
in-process / via ``python home-sweep.py`` and is deliberately narrow: it only
touches classes whose identity is provable from the name, the contents, or a
hard age bound — and it **never deletes**.  Every item is moved into
``<HOME>/_QUARANTAENE-<YYYYMMDD>/<category>/`` and recorded in that folder's
``manifest.json`` so the user can restore anything.

Classes
-------
1. ``uv_leichen`` — a top-level UUID-named directory containing the astral uv
   installer's extracted payload (``uv.exe``/``uvw.exe``/``uvx.exe``/``uv.zip``).
   Extraction scratch, never read at runtime; the producer is pinned in
   ``openamer_cli/managed_uv.py`` and ``scripts/install.ps1`` (TEMP/TMP).
2. ``kaputte_pfadnamen`` — entries whose *name* is a torn shell token: an
   unquoted Windows path (``C:Users...``), a truncated ``AppDat``, a
   heredoc/substring fragment (``({t``, ``t.slice(0``), or the mangled
   ``UsersdamirAppDataLocalTemp…`` duplicate the shell produced.
3. ``session_exports`` — top-level ``*.json``/``*.jsonl`` whose name carries
   ``session`` or ``export`` (agent run dumps; nothing else in a home root is
   named that way).
4. ``agent_screenshots`` — top-level image files older than
   ``--artifact-min-age-days`` (default 14).  Asset-looking names
   (logo/icon/brand/avatar/favicon/wallpaper) are always kept.

Bounds and safety
-----------------
* ``--max-moves`` (default 200) caps how many entries a single run may move.
* ``--min-age-minutes`` (default 60) means an entry younger than that is left
  alone, so a concurrent install/agent run is never raced.
* Windows profile hives (``NTUSER.DAT*``, ``*.regtrans-ms``, ``ntuser.ini``) and
  the standard shell folders are always skipped.

Exit code is 0 even on a no-op — the heartbeat reads ``success`` from the
return code and a green tick must not mean "nothing to do" is a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

UUID_DIR = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
UV_MARKERS = ("uv.exe", "uvw.exe", "uvx.exe", "uv.zip")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
# Names that are assets, not agent output — never swept even when old.
ASSET_HINTS = ("logo", "icon", "brand", "avatar", "favicon", "wallpaper")

# Never touch these (Windows profile / shell folders).
PROTECTED = {
    "desktop", "documents", "downloads", "music", "pictures", "videos",
    "favorites", "links", "contacts", "searches", "saved games", "onedrive",
    "appdata", ".ssh", ".cache", ".config", ".local", ".openamer", ".openamer-secrets",
}
# Broken-path fragments: exact names or prefixes that are unambiguously torn
# shell tokens and never a legitimate user file.
FRAGMENT_EXACT = {"appdat"}
FRAGMENT_PREFIX = ("c:users", "usersdamirappdata", "({", "[h.", "[i+", "slice(",
                   "t.slice(", "json.stringify(", "c.includes(")


def _is_protected(name: str) -> bool:
    low = name.lower()
    if low in PROTECTED:
        return True
    if low.startswith("ntuser.dat") or low == "ntuser.ini":
        return True
    if low.endswith(".regtrans-ms"):
        return True
    if low.startswith("_quarantaene-") or low.startswith("_backups") or low == "_notizen":
        return True
    return False


def _classify(path, mtime: float, now: float,
              artifact_min_age_days: int) -> Optional[str]:
    """Return the category for a provable-junk entry, else None."""
    name = path.name
    low = name.lower()

    # 1) uv installer extraction dir
    if path.is_dir() and UUID_DIR.match(name):
        try:
            inner = {p.name.lower() for p in path.iterdir()}
        except OSError:
            inner = set()
        return "uv_leichen" if any(m in inner for m in UV_MARKERS) else None

    # 2) torn shell token in the NAME
    if low in FRAGMENT_EXACT or any(low.startswith(p) for p in FRAGMENT_PREFIX):
        return "kaputte_pfadnamen"

    # Files only beyond this point.
    if path.is_dir():
        return None

    # 3) agent session/export dumps
    if low.endswith((".json", ".jsonl")) and ("session" in low or "export" in low):
        return "session_exports"

    # 4) agent screenshots — old images that are not obviously an asset
    if low.endswith(IMAGE_SUFFIXES) and not any(h in low for h in ASSET_HINTS):
        age_days = (now - mtime) / 86400.0
        if age_days >= artifact_min_age_days:
            return "agent_screenshots"

    return None


def _load_manifest(qdir: Path) -> dict:
    mf = qdir / "manifest.json"
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def sweep(home: Path, *, min_age_minutes: int = 60, max_moves: int = 200,
          dry_run: bool = False, now: Optional[float] = None,
          artifact_min_age_days: int = 14) -> Dict[str, object]:
    """Quarantine provable junk from *home*. Returns a summary dict."""
    now = time.time() if now is None else now
    stamp = datetime.fromtimestamp(now).strftime("%Y%m%d")
    qdir = home / f"_QUARANTAENE-{stamp}"
    moved: Dict[str, List[str]] = {}
    skipped: List[str] = []
    cutoff = now - min_age_minutes * 60

    try:
        entries = sorted(os.listdir(home))
    except OSError as exc:
        return {"success": False, "error": f"cannot list {home}: {exc}"}

    for name in entries:
        if sum(len(v) for v in moved.values()) >= max_moves:
            break
        path = home / name
        if _is_protected(name) or name == qdir.name:
            continue
        try:
            mtime = path.lstat().st_mtime
        except OSError:
            continue
        category = _classify(path, mtime, now, artifact_min_age_days)
        if category is None:
            continue
        if mtime > cutoff:
            skipped.append(name)              # junk, but too fresh to be safe
            continue
        if dry_run:
            moved.setdefault(category, []).append(name)
            continue
        dest_dir = qdir / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        if dest.exists():
            dest = dest_dir / f"{name}.dup{int(now)}"
        try:
            shutil.move(str(path), str(dest))
        except OSError as exc:
            skipped.append(f"{name} ({exc})")
            continue
        moved.setdefault(category, []).append(name)

    if moved and not dry_run:
        data = _load_manifest(qdir)
        for cat, names in moved.items():
            data.setdefault(cat, []).extend(names)
        data["last_sweep"] = datetime.fromtimestamp(now).isoformat(timespec="seconds")
        (qdir / "manifest.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    total = sum(len(v) for v in moved.values())
    return {
        "success": True,
        "home": str(home),
        "moved_total": total,
        "moved": {k: len(v) for k, v in moved.items()},
        "skipped_fresh_or_locked": len(skipped),
        "dry_run": dry_run,
        "quarantine": str(qdir) if total and not dry_run else None,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Quarantine provable junk from HOME.")
    ap.add_argument("--home", default=os.environ.get("USERPROFILE") or str(Path.home()),
                    help="target home directory (default: the real user home)")
    ap.add_argument("--min-age-minutes", type=int, default=60)
    ap.add_argument("--artifact-min-age-days", type=int, default=14,
                    help="age an image must reach before it counts as a screenshot")
    ap.add_argument("--max-moves", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    summary = sweep(
        Path(args.home),
        min_age_minutes=args.min_age_minutes,
        max_moves=args.max_moves,
        dry_run=args.dry_run,
        artifact_min_age_days=args.artifact_min_age_days,
    )
    # Silent on a no-op (classic watchdog pattern): a cron --no-agent job
    # delivers stdout verbatim, so an empty stdout means the user is not pinged
    # when there was nothing to quarantine.
    if summary.get("moved_total") or args.dry_run:
        print("home-sweep: " + json.dumps(summary, ensure_ascii=False))
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
