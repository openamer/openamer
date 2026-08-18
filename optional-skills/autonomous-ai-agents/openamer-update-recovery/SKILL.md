---
name: openamer-update-recovery
description: Recover from a failed or broken `openamer update`.
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [openamer, update, recovery, troubleshooting, self-update, windows]
    related_skills: [openamer-agent]
---

# OpenAmer Update Recovery Skill

Recover from a failed or interrupted `openamer update`. The update is a
multi-stage process (git pull → dependency install → optional ZIP fallback),
and any stage can fail partway, leaving the install in a half-updated state
that then misbehaves on every subsequent launch. This skill diagnoses the
marker lifecycle and walks through a clean reinstall.

## When to Use

- `openamer update` printed `✗ ZIP update failed` / `Git update failed` / a
  non-zero exit.
- Every `openamer` launch now prints `⚠ A previous openamer update was
  interrupted mid-install — finishing dependency installation now...` and then
  `✗ Could not auto-recover the interrupted install.`
- `openamer --version` shows "Up to date" but the recovery warning still fires.

## Prerequisites

- A working `git` checkout of the install (the git stage usually succeeds even
  when deps fail).
- The managed `uv` binary at `~/.openamer/bin/uv.exe` (or `$OPENAMER_HOME/bin/uv.exe`).
- Shell access to the install directory (`~/.openamer/openamer-agent`, or
  `$OPENAMER_HOME/openamer-agent`).

## How to Run

Run the recovery steps below with the `terminal` tool. On Windows the venv
Python lives at `venv/Scripts/python.exe` (NOT `venv/bin/`). The `VIRTUAL_ENV`
env var is required so `uv` targets the project venv instead of creating a new
one.

## Quick Reference

```bash
cd ~/.openamer/openamer-agent   # or $OPENAMER_HOME/openamer-agent
VIRTUAL_ENV="$(pwd)/venv" ~/.openamer/bin/uv.exe pip install -e ".[all]"
rm -f .update-incomplete .update-incomplete.lock .lazy-refresh-incomplete
rm -rf apps.openamer-update-staging apps.openamer-update-old
openamer --version   # must print version with NO ⚠ warning
```

## Procedure

### The marker lifecycle (root cause of the "stuck" symptom)

A failed update writes a breadcrumb file at the project root
(`~/.openamer/openamer-agent/.update-incomplete`, or under `$OPENAMER_HOME`).
On every launch, `openamer_cli/main.py::_recover_from_interrupted_install()`
sees the marker and tries to finish the install. If that recovery itself
fails, it **leaves the marker in place**, so the next launch tries again —
forever. The fix is to make the install actually succeed, THEN delete the
marker.

Key facts (from `openamer_cli/main.py` and `_early_recovery.py`):

- `.update-incomplete` → core `.[all]` install was interrupted. Recovered ONLY
  by a full `.[all]` reinstall; narrow import-probe repair never clears it.
- `.lazy-refresh-incomplete` → lazy-backend refresh may have corrupted
  packages; recovered by import-probe repair.
- `.update-incomplete.lock` → single-flight guard (O_EXCL); a stale lock is
  broken after 1 hour.
- The marker is intentionally NOT cleared by the stdlib-only early-recovery
  pass — only the full recovery in `main.py` clears it, and only on success.

### Recovery steps

1. **Confirm the code is actually current** — the git stage often succeeds even
   when deps fail:
   ```bash
   cd ~/.openamer/openamer-agent   # or $OPENAMER_HOME/openamer-agent
   git log --oneline -3
   openamer --version              # shows "Up to date" if git pulled fine
   ```

2. **Run the full `.[all]` reinstall manually** (this is what the auto-recovery
   tries and fails at). Use the managed uv binary, not a bare `pip`:
   ```bash
   cd ~/.openamer/openamer-agent
   VIRTUAL_ENV="$(pwd)/venv" ~/.openamer/bin/uv.exe pip install -e ".[all]"
   # fallback if uv is missing:
   ./venv/Scripts/python.exe -m pip install -e ".[all]"
   ```

3. **Delete the marker** once the install succeeds:
   ```bash
   rm -f .update-incomplete .update-incomplete.lock .lazy-refresh-incomplete
   ```

4. **Clean up update leftovers** (staging/old dirs the ZIP fallback leaves):
   ```bash
   rm -rf apps.openamer-update-staging apps.openamer-update-old
   ```

## Pitfalls

- **`openamer update` says "Already up to date!" but the marker is still there** —
  when git has no new commit, the update path skips the dependency reinstall
  entirely and does NOT clear `.update-incomplete`. The marker then keeps
  firing the recovery warning on every launch. Fix: run the manual `.[all]`
  reinstall yourself (step 2), then delete the marker. Do NOT rely on
  `openamer update` to clear it when there's nothing to pull.
- **The agent is running INSIDE the desktop app it needs to kill** — you
  cannot `taskkill` the app from your own session without killing yourself
  mid-turn. Solution: write a detached PowerShell script that (a) sleeps a few
  seconds, (b) kills `OpenAmer.exe` + `openamer.exe`, (c) runs the manual
  reinstall with `VIRTUAL_ENV` set, (d) deletes the markers on success, (e)
  restarts `openamer desktop`, and launch it with
  `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',... -WindowStyle Hidden`.
  The script survives your session's death and finishes the job. Log every
  step to a file so you can verify afterward (PowerShell `Out-File` writes
  UTF-16 — read it back with `iconv -f UTF-16LE -t UTF-8` or `tr -d '\000'`).
- **`[WinError 5] Zugriff verweigert` on the `apps` folder** — the running
  desktop app (or another OpenAmer window) holds file locks on `apps/`, so the
  ZIP fallback can't rename it. This is why the ZIP path fails on Windows. The
  git path is the primary path and works fine; the ZIP failure is non-fatal.
  To avoid it entirely, close the desktop app before updating, or run
  `openamer update` from a separate terminal.
- **`Failed to inspect Python interpreter ... venv\Scripts\python.exe`** — this
  error is often a red herring: the interpreter exists and works. The real
  blocker is usually the file-lock or a missing `VIRTUAL_ENV`. Test the
  interpreter directly (`./venv/Scripts/python.exe -c "print('ok')"`) before
  assuming the venv is broken.
- **Don't just delete the marker without a successful reinstall.** The marker
  exists because the install is genuinely incomplete. Deleting it first can
  leave a half-installed venv that fails later. Reinstall → verify → then
  delete.
- **`uv pip install -e .` (base only) is not enough** — the recovery path
  requires `.[all]` (extras). A base-only install leaves the marker's
  condition unmet.
- **The `openamer update` command restarts the gateway and kills running
  agents** — it's flagged for approval. Expect the running session to be
  affected.

## Verification

```bash
openamer --version   # should print version + "Up to date" with NO ⚠ warning
ls .update-incomplete .update-incomplete.lock .lazy-refresh-incomplete
# → "No such file or directory" for all three means the recovery is complete
```

## Related

The bundled `openamer-agent` skill (protected) is the umbrella for general
OpenAmer usage; this skill is the focused companion for the self-update
failure mode. If `openamer-agent` gains a troubleshooting section for this,
this skill can be absorbed into it.
