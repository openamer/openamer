#!/usr/bin/env python3
"""OpenAmer Daily Release — bump the version to today's date and publish a GitHub
release with a compact calendar tag (vYYMMDD).

Runs every day (see .github/workflows/release-daily.yml). Idempotent: if today's
tag already exists it does nothing and exits 0, so a re-run on the same day is a
no-op rather than a duplicate release.

Version scheme: v + YY MM DD, e.g. 2026-08-16 -> v260816. This deliberately
diverges from the punctuated CalVer (v2026.8.16) used by scripts/release.py for
the primary weekly release; the daily tag is purely a rolling build number.

Usage:
    python scripts/daily-release.py            # preview (dry run)
    python scripts/daily-release.py --publish  # update files, tag, create release
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "openamer_cli" / "__init__.py"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
DESKTOP_PKG = REPO_ROOT / "apps" / "desktop" / "package.json"
REPO_URL = "https://github.com/openamer/openamer"


def today_compact() -> str:
    """'v260816' from 2026-08-16 (UTC)."""
    now = datetime.utcnow()
    return f"v{now.year % 100:02d}{now.month:02d}{now.day:02d}"


def today_date_str() -> str:
    return datetime.utcnow().strftime("%Y.%m.%d")


def current_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    return m.group(1) if m else ""


def update_version_files(vernum: str, date_str: str) -> None:
    """Stamp every version field with valid, punctuated CalVer.

    ``vernum`` is the bare compact build id (e.g. 260816) used only for the
    tag; ``date_str`` is YYYY.M.D. The *version written into files is always
    ``date_str``* — a bare id (e.g. "260816") is not valid semver
    (electron-builder rejects it with `Invalid version`) nor PEP-440. If a
    caller passes a non-dotted id we defensively fall back to the dotted date
    so the published version can never be malformed.
    """
    import re as _re

    version = date_str if _re.fullmatch(r"\d+\.\d+\.\d+", date_str) else vernum
    content = VERSION_FILE.read_text(encoding="utf-8")
    content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', content)
    content = re.sub(
        r'__release_date__\s*=\s*"[^"]+"',
        f'__release_date__ = "{date_str}"',
        content,
    )
    VERSION_FILE.write_text(content, encoding="utf-8")

    py = PYPROJECT_FILE.read_text(encoding="utf-8")
    py = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{version}"', py, flags=re.MULTILINE)
    PYPROJECT_FILE.write_text(py, encoding="utf-8")

    if DESKTOP_PKG.exists():
        dkg = DESKTOP_PKG.read_text(encoding="utf-8")
        dkg = re.sub(r'("version"\s*:\s*)"[^"]+"', rf'\g<1>"{version}"', dkg, count=1)
        DESKTOP_PKG.write_text(dkg, encoding="utf-8")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true", help="Actually create + push the release")
    args = ap.parse_args()

    tag = today_compact()          # v260816
    vernum = tag[1:]               # 260816
    date_str = today_date_str()    # 2026.8.16

    # Already released today? No-op.
    r = git("tag", "-l", tag)
    if tag in r.stdout.splitlines():
        print(f"Tag {tag} already exists — nothing to do.")
        return 0

    if not args.publish:
        print(f"[dry-run] Would set version to v{vernum} ({date_str}) and create release {tag}")
        return 0

    # Update version files, commit, tag, push, release.
    # Version uses the dotted CalVer date_str (valid semver + PEP-440);
    # vernum stays the compact tag id.
    update_version_files(vernum, date_str)

    git("add", "-u")
    cr = git("commit", "-m", f"chore: daily release v{vernum} ({date_str})")
    if cr.returncode != 0 and cr.stderr and "nothing to commit" not in cr.stderr:
        print(f"commit failed: {cr.stderr.strip()}")
        return 1

    git("push", "origin", "main")
    gt = git("tag", "-a", tag, "-m", f"OpenAmer daily release v{vernum}")
    git("push", "origin", tag)

    rel = subprocess.run(
        ["gh", "release", "create", tag,
         "--title", f"OpenAmer Agent v{vernum} ({date_str})",
         "--notes", f"Daily release v{vernum} — {date_str}."],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if rel.returncode != 0:
        print(f"gh release create failed: {rel.stderr.strip()}")
        return 1

    print(f"🎉 Released v{vernum} as {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())