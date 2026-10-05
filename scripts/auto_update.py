#!/usr/bin/env python3
"""Keep OpenAmer on the newest release — SAFE auto fast-forward.

OpenAmer sat at v2026.10.04 while upstream had v2026.10.05: nothing ever ran an
update, so it drifted. A stale install is a mortality risk (missed fixes).

SAFETY FIRST — this does NOT run `openamer update`. That path quarantines
`venv/Scripts/openamer.exe`, which the running Desktop holds open, and can
strand the install half-updated (see the `openamer-update-recovery` skill).
Instead it does exactly the sync that skill proved safe:

  1. `git fetch --depth=150 origin main`   (deepen a shallow clone first)
  2. `git merge --ff-only origin/main`     (fast-forward ONLY)

and it refuses to touch anything when the fast-forward would not be trivial:

  * a dirty tracked file also changes upstream  -> report, do not touch
  * pyproject.toml / uv.lock changes beyond version literals -> needs a real
    dependency install -> report "manual update needed", do not touch

Watchdog output: silent when current; one line when it advanced or when it
refused. Always exits 0.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
AGENT = HOME / "openamer-agent"
DEP_FILES = ("pyproject.toml", "uv.lock")
# a dependency-file line that is ONLY a version bump (safe for a fast-forward)
_VERSION_ONLY = re.compile(r'version\s*=\s*"?[\d.]+"?\s*$')


def _git(args, timeout=180):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          timeout=timeout, cwd=str(AGENT))


def _dirty_files() -> set[str]:
    r = _git(["status", "--short"])
    out = set()
    for line in (r.stdout or "").splitlines():
        if len(line) > 3 and not line.startswith("??"):
            out.add(line[3:].strip())
    return out


def main() -> int:
    if not (AGENT / ".git").exists():
        print(f"auto-update: no git checkout at {AGENT}")
        return 0

    # 1) deepen a shallow clone and fetch
    try:
        _git(["fetch", "--depth=150", "origin", "main"], timeout=300)
    except subprocess.TimeoutExpired:
        print("auto-update: fetch timed out")
        return 0

    behind = _git(["rev-list", "--count", "HEAD..origin/main"]).stdout.strip()
    if behind in ("", "0"):
        return 0  # up to date -> silent

    # 2) refuse if a dirty tracked file is also incoming (stash required -> risky)
    incoming = {f for f in _git(["diff", "--name-only", "HEAD", "origin/main"]).stdout.split("\n") if f}
    clash = _dirty_files() & incoming
    if clash:
        print(f"auto-update: {behind} behind but local edits would be overwritten "
              f"({', '.join(sorted(clash)[:3])}) — leaving untouched")
        return 0

    # 3) refuse if real dependencies changed (needs a full install, not a FF)
    depdiff = _git(["diff", "HEAD", "origin/main", "--", *DEP_FILES]).stdout
    changed = [ln for ln in depdiff.splitlines()
               if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    if any(not _VERSION_ONLY.search(ln) for ln in changed):
        print(f"auto-update: {behind} behind but dependencies changed — run "
              f"'openamer update' manually (close the Desktop first)")
        return 0

    # 4) the safe sync: fast-forward only
    ff = _git(["merge", "--ff-only", "origin/main"], timeout=180)
    if ff.returncode != 0:
        tail = (ff.stderr or ff.stdout or "").strip().splitlines()[-1:] or ["unknown error"]
        print(f"auto-update: fast-forward refused — {tail[0][:160]}")
        return 0

    ver = _git(["--no-pager", "log", "-1", "--format=%h", "HEAD"]).stdout.strip()
    print(f"auto-update: fast-forwarded {behind} commit(s) -> {ver}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
