#!/usr/bin/env python3
"""Publish translated desktop locales — the step the pipeline never had.

Measured 2026-11-18: `scripts/i18n_converge.py` (cron `i18n Converge to 100%`)
delivers finished translations into the **working tree** and stops there. No
git, no PR. The result was 9,612 finished strings across 38 locales sitting
unpublished until someone noticed, while users kept reading English. The same
gap refilled within the hour (gl/ii/nv, 188 strings).

This script closes it: gate, branch, commit, push, PR — idempotent, so every run
adds a commit to the same rolling PR instead of opening a new one.

    python scripts/i18n_publish.py                 # publish every dirty locale
    python scripts/i18n_publish.py --dry-run       # show the plan, change nothing
    python scripts/i18n_publish.py --locales gl,ii # restrict

Exit codes: 0 published or nothing to do, 3 refused by the quality gate,
1 anything else.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("OPENAMER_REPO", str(Path.home() / "openamer-repo")))
I18N_REL = Path("apps") / "desktop" / "src" / "i18n"
BRANCH = "i18n/rolling"
WORKTREE = Path(os.environ.get("OPENAMER_I18N_WT", r"C:\Users\damir\oa_i18n_wt"))
GH = shutil.which("gh") or "gh"


def log(msg: str) -> None:
    print(f"[i18n-publish] {msg}", flush=True)


def git(*args: str, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def dirty_locales() -> list[str]:
    """Locale files the pipeline has written but nobody published."""
    st = git("status", "--porcelain", "--", str(I18N_REL))
    out = []
    for line in st.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path.endswith(".ts") and ".test." not in path:
            out.append(Path(path).stem)
    return sorted(set(out))


def judge(rows: list[dict]) -> tuple[bool, str]:
    """Decide from the verifier's JSON whether a batch may be published.

    Pure on purpose: the decision is the part that must be testable without a
    live git remote, node, or 186 locale files.
    """
    bad = []
    for row in rows:
        if "fatal" in row:
            bad.append(f"{row.get('locale')}: {str(row['fatal'])[:80]}")
            continue
        problems = []
        if row.get("parse_errors"):
            problems.append("parse")
        if row.get("broken_placeholders"):
            problems.append(f"{len(row['broken_placeholders'])} broken placeholders")
        if row.get("brand"):
            problems.append("brand")
        if row.get("missing_sections"):
            problems.append(f"{len(row['missing_sections'])} missing")
        if row.get("extra"):
            problems.append(f"{len(row['extra'])} extra")
        if row.get("wrong_script"):
            problems.append(f"{len(row['wrong_script'])} in the wrong "
                            "writing system (mistranslation)")
        if problems:
            bad.append(f"{row['locale']}: {', '.join(problems)}")
    if bad:
        return False, "; ".join(bad[:6])
    return True, f"{len(rows)} locale(s) clean"


def gate(locales: list[str]) -> tuple[bool, str]:
    """Refuse to publish a locale the verifier rejects.

    The gate is `i18n_verify_locales.py` with the 2026-11-18 fix (variables, not
    translated words). Publishing without it is how wrong-script translations
    reached main before.
    """
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "i18n_verify_locales.py"),
                        *locales, "--json"], cwd=str(REPO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0 and not r.stdout.strip():
        return False, f"verifier failed: {(r.stderr or '')[-200:]}"
    try:
        rows = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, "verifier produced no JSON"
    return judge(rows)


def open_pr() -> str:
    r = subprocess.run([GH, "pr", "list", "--head", BRANCH, "--state", "open",
                        "--json", "number,url"], cwd=str(REPO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        rows = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return ""
    return rows[0]["url"] if rows else ""


def publish(locales: list[str], dry: bool) -> int:
    ok, why = gate(locales)
    log(f"gate: {'pass' if ok else 'REFUSED'} — {why}")
    if not ok:
        return 3
    if dry:
        log(f"dry run — would publish {len(locales)} locale(s): {', '.join(locales)}")
        return 0

    git("fetch", "-q", "origin", "main", timeout=180)
    git("worktree", "unlock", str(WORKTREE))
    git("worktree", "remove", "--force", "--force", str(WORKTREE))
    git("worktree", "prune")
    add = git("worktree", "add", "--detach", "--force", str(WORKTREE), "origin/main")
    if add.returncode != 0:
        log(f"worktree add failed: {(add.stderr or add.stdout)[-300:]}")
        return 1

    try:
        base = git("-C", str(WORKTREE), "rev-parse", "HEAD").stdout.strip()
        # Continue the rolling branch ONLY while its PR is still open. Once that
        # PR merges, the branch tip is already inside main: appending to it would
        # base the next PR on an older main for no reason. Measured 2026-11-18:
        # PR #437 merged, the branch stayed behind, and the next batch needed a
        # fresh branch instead of a commit on the merged one.
        url = open_pr()
        branch = BRANCH if url else f"{BRANCH}-{datetime.now(timezone.utc):%Y%m%d-%H%M}"
        existing = git("ls-remote", "--heads", "origin", branch).stdout.split()
        if existing and url:
            git("-C", str(WORKTREE), "fetch", "-q", "origin", branch, timeout=180)
            git("-C", str(WORKTREE), "checkout", "-q", "-B", branch, "FETCH_HEAD")

        copied = 0
        for loc in locales:
            src = REPO / I18N_REL / f"{loc}.ts"
            dst = WORKTREE / I18N_REL / f"{loc}.ts"
            if not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1

        if not git("-C", str(WORKTREE), "status", "--porcelain").stdout.strip():
            log("nothing to publish — origin already carries these bytes")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        msg = (f"feat(i18n): publish translated catalogs ({stamp})\n\n"
               f"{copied} locale file(s) produced by the converge pipeline and\n"
               f"verified by scripts/i18n_verify_locales.py before publishing.\n"
               f"Locales: {', '.join(locales)}\n")
        git("-C", str(WORKTREE), "add", "--", *[str(I18N_REL / f"{l}.ts") for l in locales])
        commit = git("-C", str(WORKTREE), "commit", "-q", "-m", msg)
        if commit.returncode != 0:
            log(f"commit failed: {(commit.stderr or commit.stdout)[-300:]}")
            return 1

        sha = git("-C", str(WORKTREE), "rev-parse", "HEAD").stdout.strip()
        push = git("-C", str(WORKTREE), "push", "-q", "origin",
                   f"HEAD:refs/heads/{branch}", timeout=300)
        if push.returncode != 0:
            log(f"push failed: {(push.stderr or push.stdout)[-300:]}")
            return 1
        log(f"pushed {sha[:10]} ({copied} file(s), base {base[:10]}) to {branch}")

        if not url:
            created = subprocess.run(
                [GH, "pr", "create", "--base", "main", "--head", branch,
                 "--title", "feat(i18n): publish translated catalogs (rolling)",
                 "--body", "Rolling PR written by `scripts/i18n_publish.py`.\n\n"
                           "Each commit is one converge batch that already passed\n"
                           "`scripts/i18n_verify_locales.py` (placeholder variables,\n"
                           "leaf set, brand names, parse). Nothing here is hand-edited."],
                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300)
            url = (created.stdout or "").strip().splitlines()[-1] if created.stdout else ""
            log(f"opened PR {url or '? ' + (created.stderr or '')[-200:]}")
        else:
            log(f"updated PR {url}")
        return 0
    finally:
        git("worktree", "remove", "--force", str(WORKTREE))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Publish verified locale translations.")
    ap.add_argument("--locales", default="", help="comma list; default = every dirty locale")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    locales = [x for x in args.locales.split(",") if x.strip()] or dirty_locales()
    if not locales:
        log("no dirty locale files — nothing to publish")
        return 0
    return publish([l.strip() for l in locales], args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
