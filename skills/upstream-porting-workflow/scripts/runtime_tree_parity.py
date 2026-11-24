#!/usr/bin/env python3
"""Prove which files differ between the repo (SoT) and the RUNTIME agent tree.

Why this exists
---------------
After porting/fixing in `openamer-repo`, the running install at
`$OPENAMER_HOME/openamer-agent` is a *separate* git repo with a divergent history
root. It lags silently, so green repo tests do NOT mean the running agent has the
fix. Syncing scoped paths is easy; knowing WHICH paths to sync is the hard part.

Naive comparison lies two ways:

  * `git hash-object` on a working file differs purely because the two checkouts
    applied different EOL policy (repo CRLF vs runtime LF). That is a false alarm.
  * A file can be present, importable, and still MISS the hunk you care about —
    a silent false negative if you only diff file *lists*.

So: compare bytes with CRLF/CR normalised away, and when they really differ,
print the first differing line from both sides. That names the missing hunk.

Usage
-----
    python runtime_tree_parity.py <file> [<file> ...]
    python runtime_tree_parity.py --from-git <sha> [<sha> ...]   # files a commit touched

    # typical: check everything my commits touched
    python runtime_tree_parity.py --from-git HEAD~7..HEAD

Exit code 1 when a REAL (non-EOL) difference remains, so it gates a DONE claim.

Override the tree locations with --repo / --live if your layout differs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = Path(r"C:\Users\damir\openamer-repo")
DEFAULT_LIVE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent")

# Files whose absence/drift is expected (generated, cron-written, per-profile).
IGNORE_SUBSTRINGS = (
    "reports/",
    ".bugbot/",
    "skills/auto-generated/",
    "package-lock.json",
    "test_durations.json",
)


def normalise(path: Path) -> bytes | None:
    """Read bytes with all line-ending flavours collapsed to \\n."""
    try:
        return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    except FileNotFoundError:
        return None


def files_from_git(repo: Path, revspec: str) -> list[str]:
    """Paths touched by a revspec (e.g. 'HEAD~7..HEAD' or a single sha)."""
    r = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", revspec],
        capture_output=True, text=True, errors="replace",
    )
    if r.returncode != 0:
        print(f"git diff failed: {r.stderr.strip()[:200]}", file=sys.stderr)
        return []
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def compare(repo: Path, live: Path, rel: str) -> str:
    a = normalise(repo / rel)
    b = normalise(live / rel)

    if a is None:
        return "MISSING_IN_REPO"
    if b is None:
        return "NOT_IN_LIVE"          # real: the runtime tree never got the file
    if a == b:
        return "SAME"

    la, lb = a.split(b"\n"), b.split(b"\n")
    diff = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y),
                min(len(la), len(lb)))
    print(f"      line {diff + 1}:")
    if diff < len(la):
        print(f"        repo: {la[diff][:100]!r}")
    if diff < len(lb):
        print(f"        live: {lb[diff][:100]!r}")
    return "REAL_DIFF"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="repo-relative paths to check")
    ap.add_argument("--from-git", metavar="REVSPEC",
                    help="derive the file list from git (e.g. HEAD~7..HEAD)")
    ap.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    ap.add_argument("--live", type=Path, default=DEFAULT_LIVE)
    args = ap.parse_args()

    files = list(args.files)
    if args.from_git:
        files += files_from_git(args.repo, args.from_git)
    files = [f for f in dict.fromkeys(files)
             if not any(s in f for s in IGNORE_SUBSTRINGS)]

    if not files:
        print("no files to check (pass paths, or --from-git REVSPEC)")
        return 0

    print(f"repo: {args.repo}")
    print(f"live: {args.live}\n")

    real = []
    for rel in sorted(files):
        verdict = compare(args.repo, args.live, rel)
        flag = "" if verdict == "SAME" else "  <-- SYNC THIS"
        print(f"  {verdict:<14} {rel}{flag}")
        if verdict != "SAME":
            real.append((rel, verdict))

    print()
    if not real:
        print(f"ALL {len(files)} FILES IDENTICAL (CRLF-normalised) — runtime is in sync")
        return 0

    print(f"{len(real)} of {len(files)} need syncing:")
    for rel, verdict in real:
        print(f"   [{verdict}] {rel}")
    print()
    print("Sync with (applies the repo's EOL policy — better than cp):")
    print(f"  cd {args.live} && git fetch origin main")
    print("  git status --short <the paths above>   # MUST be empty first")
    print("  git checkout origin/main -- " + " ".join(r for r, _ in real))
    return 1


if __name__ == "__main__":
    sys.exit(main())
