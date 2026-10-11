#!/usr/bin/env python3
"""Native home-hygiene organ — quarantine *provable* junk out of the user's HOME.

Owned by the ASI heartbeat (infra subsystem), not a standalone cron.  It runs
in-process / via ``python home-sweep.py`` and is deliberately narrow: it only
touches two classes whose identity is provable from the name and contents, and
it **never deletes** — every item is moved into
``<HOME>/_QUARANTAENE-<YYYYMMDD>/<category>/`` and recorded in that folder's
``manifest.json`` so the user can restore anything.

Classes handled
---------------
1. ``uv_leichen`` — a top-level UUID-named directory containing the astral uv
   installer's extracted payload (``uv.exe``/``uvw.exe``/``uvx.exe``/``uv.zip``).
   Those are extraction scratch dirs, never read by uv at runtime.  The
   producer is pinned in ``openamer_cli/managed_uv.py`` and
   ``scripts/install.ps1`` (TEMP/TMP); this organ is the belt-and-braces sweep.
2. ``kaputte_pfadnamen`` — entries whose *name* is a torn shell token: an
   unquoted Windows path (``C:Users...``), a truncated ``AppDat``, or a
   heredoc/substring fragment (``({t``, ``t.slice(0``, ``JSON.stringify((j.data``).

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
from typing import Dict, List

UUID_DIR = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
UV_MARKERS = ("uv.exe", "uvw.exe", "uvx.exe", "uv.zip")

# Never touch these (Windows profile / shell folders).
PROTECTED = {
    "desktop", "documents", "downloads", "music", "pictures", "videos",
    "favorites", "links", "contacts", "searches", "saved games", "onedrive",
    "appdata", ".ssh", ".cache", ".config", ".local", ".openamer", ".openamer-secrets",
}
# Broken-path fragments: exact names or prefixes that are unambiguously torn
# shell tokens and never a legitimate user file.
FRAGMENT_EXACT = {"appdat"}
FRAGMENT_PREFIX = ("c:users", "({", "[h.", "[i+", "slice(", "t.slice(",
                   "json.stringify(", "c.includes(")


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


def _classify(path: Path) -> str | None:
    """Return the category for a provable-junk entry, else None."""
    name = path.name
    if path.is_dir() and UUID_DIR.match(name):
        try:
            inner = {p.name.lower() for p in path.iterdir()}
        except OSError:
            inner = set()
        if any(m in inner for m in UV_MARKERS):
            return "uv_leichen"
        return None
    low = name.lower()
    if low in FRAGMENT_EXACT or any(low.startswith(p) for p in FRAGMENT_PREFIX):
        return "kaputte_pfadnamen"
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
          dry_run: bool = False, now: float | None = None) -> Dict[str, object]:
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
        if _is_protected(name):
            continue
        if name == qdir.name:
            continue
        try:
            mtime = path.lstat().st_mtime
        except OSError:
            continue
        category = _classify(path)
        if category is None:
            continue
        if mtime > cutoff:
            skipped.append(name)          # too fresh — a run may be mid-flight
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


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Quarantine provable junk from HOME.")
    ap.add_argument("--home", default=os.environ.get("USERPROFILE") or str(Path.home()),
                    help="target home directory (default: the real user home)")
    ap.add_argument("--min-age-minutes", type=int, default=60)
    ap.add_argument("--max-moves", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    summary = sweep(
        Path(args.home),
        min_age_minutes=args.min_age_minutes,
        max_moves=args.max_moves,
        dry_run=args.dry_run,
    )
    # Silent on a no-op (classic watchdog pattern): a cron --no-agent job
    # delivers stdout verbatim, so an empty stdout means the user is not pinged
    # when there was nothing to quarantine.
    if summary.get("moved_total") or args.dry_run:
        print("home-sweep: " + json.dumps(summary, ensure_ascii=False))
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
