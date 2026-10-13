# Repo hygiene: the cron report backlog now closes itself

**Date:** 2026-09-15
**Trigger:** `openamer desktop` build run left 59 dirty entries in the work tree.

## What was wrong

The learning cron fleet (darwin, trend-scout, punkt, growth, bugbot, …) writes
artifacts into this repo on every tick, but nothing ever committed them. Two
consequences:

1. `git status` stopped being a signal. With 55 generated files permanently
   dirty, a real hand edit was invisible — you cannot spot the one line that
   matters among five dozen touched report files.
2. The artifacts sat unbacked-up for days. `trend-scout` files from Sep 11-13
   existed in exactly one place on one disk.

## What shipped

* **`.gitignore`** now covers the local scratch a Windows tool dropped into the
  repo root: an embedded Python install (`/Python/`), its installer logs
  (`python_install_*.log`), and the task-queue daemon state (`/.task-queue/`).
  None of it is project source; all of it was showing up as untracked noise.
* **`scripts/cron-repo-autocommit.py`** (lives in `OPENAMER_HOME/scripts/`, not
  in the repo) sweeps `reports/` and `.bugbot/` every 6 hours, commits them on
  the current branch, and pushes.
* Backlog committed once by hand as `e3fe16e29`.

## Design decisions worth keeping

**Scoped staging, not `git add -A`.** The sweep stages only the two generated-
artifact directories. A broad add would sweep another cron's in-flight *code*
edits into a `chore(reports):` commit — silent damage, and exactly what this is
meant to prevent. Anything dirty outside the scope is left alone and reported.

**Silent on success, loud on failure.** As a `no_agent` watchdog its stdout is
delivered verbatim, so emptiness is the success signal: nothing to commit,
nothing to say. It speaks up only for a failed push, a detached HEAD, or dirty
paths outside its scope.

**Detached HEAD refuses to commit.** A commit made on a detached HEAD is not
pushable and easy to lose. The script reports the condition instead of quietly
creating orphaned objects.

**Ledger outside the repo.** Telemetry goes to
`memory/repo-autocommit.json`, not into the repo — a ledger inside it would be
dirty on every run and would re-create the exact problem being fixed.
