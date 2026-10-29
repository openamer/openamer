#!/usr/bin/env bash
# Canonical test runner for openamer-agent. Run this instead of calling
# `pytest` directly to guarantee your local run matches CI behavior.
#
# What this script enforces:
#   * Per-file isolation via scripts/run_tests_parallel.py — each test
#     file runs in its own freshly-spawned `python -m pytest <file>`
#     subprocess. No xdist, no shared workers, no module-level leakage
#     between files.
#   * TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0 (deterministic)
#   * Env vars blanked (conftest.py also does this, but this
#     is belt-and-suspenders for anyone running pytest outside our
#     conftest path — e.g. on a single file)
#   * Proper venv activation (probes .venv, venv, then ~/.openamer/...)
#
# Usage:
#   scripts/run_tests.sh                            # full suite
#   scripts/run_tests.sh -j 4                       # cap parallelism
#   scripts/run_tests.sh tests/agent/               # discover only here
#   scripts/run_tests.sh tests/agent/ tests/acp/    # multiple roots
#   scripts/run_tests.sh tests/foo.py               # single file
#   scripts/run_tests.sh tests/foo.py -q            # path + bare pytest flag
#   scripts/run_tests.sh tests/foo.py -v --tb=long  # bare flags "just work"
#   scripts/run_tests.sh -k 'pattern'               # value flags pass through too
#   scripts/run_tests.sh tests/foo.py -- --tb=long  # explicit '--' still works
#
# Bare pytest flags (anything starting with '-' that isn't one of this
# runner's own options: -j/--jobs, --paths, --slice, --file-timeout, etc.)
# are forwarded to each per-file pytest invocation automatically — no '--'
# separator required. The explicit '--' form still works and stacks with
# bare flags. Positional path arguments override the default discovery
# root (tests/).

set -euo pipefail

# ── Locate repo root ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Locate python ───────────────────────────────────────────────────────────
# Probe local venvs first; fall back to the Nix devShell's editable venv
# (OPENAMER_PYTHON is exported by the devShell hook and ships [dev] extras:
# pytest, pytest-asyncio, pytest-timeout, ruff, ty).
#
# A candidate must have pytest INSTALLED, not merely exist. The release venv
# at ~/.openamer/openamer-agent/venv has bin/activate but no pytest, so an
# existence-only probe selected it in checkouts/worktrees without a local
# .venv — every file then died with "No module named pytest" and the run
# reported "0 tests passed" (which reads green at a glance even though the
# exit code is 1). Skip such a venv and keep probing instead.
VENV=""
SKIPPED_VENVS=""
for candidate in "$REPO_ROOT/.venv" "$REPO_ROOT/venv" "$HOME/.openamer/openamer-agent/venv"; do
  # A venv can use the POSIX layout (bin/python) or the Windows layout
  # (Scripts/python.exe). Probe both so native Windows checkouts work without
  # requiring OPENAMER_PYTHON to be set manually.
  for py in "$candidate/bin/python" "$candidate/Scripts/python.exe"; do
    if [ -x "$py" ] && "$py" -c 'import pytest' 2>/dev/null; then
      VENV="$candidate"
      VENV_PYTHON="$py"
      break 2
    fi
  done
  # Record a skip only if the venv exists but lacks pytest (so the error
  # message below can point at it).
  if [ -f "$candidate/bin/activate" ] || [ -f "$candidate/Scripts/activate" ]; then
    SKIPPED_VENVS="$SKIPPED_VENVS $candidate"
  fi
done

if [ -n "$SKIPPED_VENVS" ]; then
  for skipped in $SKIPPED_VENVS; do
    echo "▶ skipping venv without pytest: $skipped" >&2
  done
fi

if [ -n "$VENV" ]; then
  PYTHON="$VENV_PYTHON"
elif [ -n "${OPENAMER_PYTHON:-}" ] && [ -x "$OPENAMER_PYTHON" ] \
    && "$OPENAMER_PYTHON" -c 'import pytest' 2>/dev/null; then
  # Guard with an import check: OPENAMER_PYTHON may point at the RELEASE
  # venv (no pytest) when inherited from a wrapped `openamer` binary rather
  # than the devShell hook.
  PYTHON="$OPENAMER_PYTHON"
  echo "▶ no local venv — using Nix dev venv via OPENAMER_PYTHON: $PYTHON"
else
  echo "error: no virtualenv with pytest found in $REPO_ROOT/.venv or $REPO_ROOT/venv," >&2
  echo "       and OPENAMER_PYTHON is not a python with pytest (enter the Nix devShell or create a venv)" >&2
  if [ -n "$SKIPPED_VENVS" ]; then
    echo "       (skipped for missing pytest:$SKIPPED_VENVS — install dev extras there, or create $REPO_ROOT/.venv)" >&2
  fi
  exit 1
fi


# ── Live-gateway plugin (computed before we drop env) ───────────────────────
EXTRA_PYTHONPATH=""
EXTRA_PYTEST_PLUGINS=""
if [ -f "$HOME/.openamer/pytest_live_guard.py" ]; then
  EXTRA_PYTHONPATH="$HOME/.openamer"
  EXTRA_PYTEST_PLUGINS="pytest_live_guard"
fi


# ── SystemRoot for the hermetic env (captured BEFORE env -i) ────────────────
# env -i drops SystemRoot. On Windows the SSL module cannot build a default
# context without it: `ssl.SSLError: [SSL] unknown error (_ssl.c:3108)`. That
# surfaces as aiohttp failing to import, which breaks any test that empties
# os.environ itself (e.g. test_setup_feishu's @patch.dict(clear=True)) —
# 3 failures attributed to the wrong cause.
# MSYS bash does NOT expose SystemRoot as a shell variable (verified: empty in
# bash, "C:\\WINDOWS" via Python), so ask the OS through the interpreter.
NATIVE_SYSROOT="$("$PYTHON" -c 'import os;print(os.environ.get("SystemRoot") or r"C:\Windows")' 2>/dev/null)"
# LOCALAPPDATA is a system variable every Windows process has, and the product
# (and tests for it) read it to locate ~/AppData/Local/openamer. env -i drops it,
# which turned a documented-default test into KeyError: 'LOCALAPPDATA' under the
# runner while passing in a normal shell (measured 2026-10-25).
NATIVE_LOCALAPPDATA="$("$PYTHON" -c 'import os;print(os.environ.get("LOCALAPPDATA") or "")' 2>/dev/null)"
# PROCESSOR_ARCHITECTURE: platform.machine() returns "" without it on Windows, and
# platform caches uname() on first call -- so a dashboard arch field read under
# env -i was empty while passing in a shell (measured 2026-10-25).
NATIVE_PROCESSOR_ARCH="$("$PYTHON" -c 'import os;print(os.environ.get("PROCESSOR_ARCHITECTURE") or "")' 2>/dev/null)"
# PATHEXT: without it Windows/PowerShell cannot resolve a bare command name to an
# .exe, so install.ps1 died with rc=1 and an EMPTY stderr (PowerShell writes the
# error record to stdout) -- which looked like a broken installer rather than a
# stripped variable (measured 2026-10-25, reproduced by deleting PATHEXT alone).
NATIVE_PATHEXT="$("$PYTHON" -c 'import os;print(os.environ.get("PATHEXT") or "")' 2>/dev/null)"
if [ -z "$NATIVE_SYSROOT" ]; then
  NATIVE_SYSROOT='C:\Windows'
fi

# ── SystemDrive for the hermetic env (captured BEFORE env -i) ──────────────
# env -i drops SystemDrive too, and on Windows `taskkill` HANGS (does not
# fail) when SystemDrive is missing: it needs the drive to build the job
# object path. The canonical runner kills every timed-out test file via
# `taskkill /F /T` in run_tests_parallel._kill_tree, so without SystemDrive
# each timeout burned the full 10s taskkill timeout instead of ~1s.
# That silently stretched every timeout by ~10s and pushed CI slices over
# the job timeout with the offending file never named.
# Verified deterministically: 5/5 hangs without SystemDrive, 0/5 with it.
NATIVE_SYSDRIVE="$("$PYTHON" -c 'import os;print(os.environ.get("SystemDrive") or os.environ.get("SYSTEMDRIVE") or "")' 2>/dev/null)"
if [ -z "$NATIVE_SYSDRIVE" ]; then
  # Derive it from SystemRoot (usually "C:\Windows" -> "C:") as a fallback.
  NATIVE_SYSDRIVE="${NATIVE_SYSROOT%%:*}:"
fi


# ── Run in hermetic env ──────────────────────────────────────────────────────
# env -i: start with empty environment, opt-in only what we need.
# No credential var can leak — you'd have to explicitly add it here.
echo "▶ running per-file parallel test suite via run_tests_parallel.py"
echo "  (TZ=UTC LANG=C.UTF-8 PYTHONHASHSEED=0; clean env)"

cd "$REPO_ROOT"

# ── Pre-compile .pyc bytecode cache ─────────────────────────────────────────
# Each test file runs in its own subprocess via run_tests_parallel.py.
# Pre-building the bytecode cache once here (instead of each subprocess
# compiling on first import) avoids redundant work across ~2000 processes.
# Uses git to list tracked .py files (skips venv, node_modules, etc).
echo "▶ pre-compiling bytecode cache"
"$PYTHON" -m compileall -q -j 0 -- $(git ls-files '*.py') >/dev/null 2>&1 || true

echo "▶ launching test runner"
# PYTHONUTF8=1 is not cosmetic: LANG/LC_ALL are only advisory to CPython on
# Windows, where the default text encoding comes from the ANSI code page
# (cp1252 here) no matter what the locale says. On Linux CI the same code runs
# with a UTF-8 default encoding, so a test that does a bare open("cli.py")
# passes there and dies here with
#   UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f
# the moment the file contains a non-ASCII glyph (→, ✓, —). Measured
# 2026-10-25: 96 of the 392 failing files read repo sources without
# encoding=, and every one of them failed on that decode. PEP 540 UTF-8 mode
# makes this runner reproduce CI's default encoding instead of the host's --
# which is exactly the promise this script already makes for TZ/LANG/hashseed.
exec env -i \
  PATH="$PATH" \
  HOME="$HOME" \
  ${USERPROFILE:+USERPROFILE="$USERPROFILE"} \
  ${HOMEDRIVE:+HOMEDRIVE="$HOMEDRIVE"} ${HOMEPATH:+HOMEPATH="$HOMEPATH"} \
  SystemRoot="$NATIVE_SYSROOT" \
  SystemDrive="$NATIVE_SYSDRIVE" \
  ${NATIVE_LOCALAPPDATA:+LOCALAPPDATA="$NATIVE_LOCALAPPDATA"} \
  ${NATIVE_PROCESSOR_ARCH:+PROCESSOR_ARCHITECTURE="$NATIVE_PROCESSOR_ARCH"} \
  ${NATIVE_PATHEXT:+PATHEXT="$NATIVE_PATHEXT"} \
  TZ=UTC \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONHASHSEED=0 \
  PYTHONUTF8=1 \
  PYTHONIOENCODING=utf-8 \
  ${OPENAMER_RUN_SLOW_PET_TESTS:+OPENAMER_RUN_SLOW_PET_TESTS="$OPENAMER_RUN_SLOW_PET_TESTS"} \
  ${EXTRA_PYTHONPATH:+PYTHONPATH="$EXTRA_PYTHONPATH"} \
  ${EXTRA_PYTEST_PLUGINS:+PYTEST_PLUGINS="$EXTRA_PYTEST_PLUGINS"} \
  "$PYTHON" "$SCRIPT_DIR/run_tests_parallel.py" "$@"
