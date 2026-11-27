#!/usr/bin/env python3
"""Nightly test-suite watchdog: run the canonical suite, alert only on failure.

Why this exists: "the system works" is not a state that can be asserted once —
the repo moves (cron jobs commit to it daily), so yesterday's green says nothing
about today. This job converts the claim into a *measurement that refreshes
itself*: it runs the canonical runner, records the result, and stays silent
unless something went red.

Deliberately a watchdog, not a reporter: empty stdout means "all green, nothing
to say" and the cron delivers nothing. Silence is the success signal. A message
only arrives when the suite is red, or when the run itself could not complete.

Canonical runner contract (do NOT substitute a bare pytest call): scripts/
run_tests.sh runs under `env -i` with TZ=UTC/LANG=C.UTF-8/PYTHONHASHSEED=0 —
a raw pytest inherits PYTHONPATH and can be green while this is red. On Windows
the wrapper needs OPENAMER_PYTHON because it probes the POSIX .venv/bin layout.

Usage:
    python test-suite-watchdog.py [target]     # target defaults to tests/

Exit codes:
  0 -> suite green                       -> silent (or one "recovered" line)
  1 -> suite red, or run could not complete -> prints the alert
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

def _resolve_repo_root() -> Path:
    """The checkout this script lives in — not one guessed from ``$HOME``.

    The script ships inside the repo at ``scripts/test-suite-watchdog.py``, so
    its own location is the only answer that holds everywhere. Deriving it
    from ``$HOME`` (``~/openamer-repo``) was right on one developer box and
    wrong everywhere else: on CI ``$HOME`` is ``/home/runner`` while the
    checkout is ``/home/runner/work/openamer/openamer``, so ``PYTHON`` and
    ``RUNNER`` pointed at a directory that does not exist and every scheduled
    run alerted ``runner or venv python missing`` instead of watching the
    suite. ``OPENAMER_REPO`` still wins when it is set.
    """
    env = os.environ.get("OPENAMER_REPO", "").strip()
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "run_tests.sh").exists() and (parent / "tests").is_dir():
            return parent
    return Path.home() / "openamer-repo"


REPO = _resolve_repo_root()
# The install home is ``%LOCALAPPDATA%/openamer-laptop`` on Windows and
# ``~/.openamer-laptop`` elsewhere; spelling the Windows layout on Linux put
# the state and log files under a ``~/AppData`` that is never created.
HOME = Path(
    os.environ.get("OPENAMER_HOME")
    or str(Path.home() / "AppData" / "Local" / "openamer-laptop" if os.name == "nt" else Path.home() / ".openamer-laptop")
)
# Repo-local venv: the canonical runner needs a python with the project deps,
# and this is the one that ships with the checkout.


def _venv_python(repo: Path) -> Path:
    """The project venv's interpreter, in whichever layout this platform uses.

    ``uv sync`` / ``python -m venv`` put it in ``Scripts/python.exe`` on Windows
    and ``bin/python`` on POSIX. Hardcoding the Windows spelling made ``main()``
    conclude the venv was missing on Linux and macOS, so the watchdog printed
    "runner or venv python missing" and exited 1 on every single run instead of
    watching the suite. CI installs with ``uv sync`` into ``.venv/bin/python``,
    so this is the layout the runner actually runs under there.
    """
    for parts in (("Scripts", "python.exe"), ("bin", "python")):
        cand = repo / ".venv" / Path(*parts)
        if cand.exists():
            return cand
    # Not created yet: fall back to this platform's own spelling so the alert
    # names the path a human would find.
    sub = Path("Scripts", "python.exe") if os.name == "nt" else Path("bin", "python")
    return repo / ".venv" / sub


PYTHON = Path(os.environ.get("OPENAMER_PYTHON") or _venv_python(REPO))
RUNNER = REPO / "scripts" / "run_tests.sh"


def _posix_bash() -> str:
    """A bash that understands a POSIX-style runner path.

    A bare `bash` on PATH is the WSL shim on Windows
    (AppData/Local/Microsoft/WindowsApps/bash.exe) and it CANNOT read a
    git-bash path such as /c/Users/... — it dies with
    "/bin/bash: /c/...: No such file or directory" (exit 127) while the very
    same runner works under git's own bash. Live 2026-09-22: the nightly
    watchdog had been failing on exactly this, every night.
    Prefer git's bash, derived from `git --exec-path` so this stays portable,
    then any non-WindowsApps bash on PATH.
    """
    exe = "bash.exe" if os.name == "nt" else "bash"
    try:
        out = subprocess.run(
            ["git", "--exec-path"],
            capture_output=True, text=True, errors="replace", timeout=20,
        )
        if out.returncode == 0 and out.stdout.strip():
            core = Path(out.stdout.strip())
            for cand in (
                core.parent.parent / "bin" / exe,   # <git>/mingw64/bin/bash.exe
                core.parent / "bin" / exe,
            ):
                if cand.exists():
                    return str(cand)
    except Exception:
        pass
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if "WindowsApps" in part:
            continue  # the WSL shim — cannot read /c/... paths
        cand = Path(part) / exe
        if cand.exists():
            return str(cand)
    return "bash"


BASH = _posix_bash()
STATE = HOME / "logs" / "test-suite-watchdog.json"
LOG = HOME / "logs" / "test-suite-watchdog.log"

# Whole suite normally; argv[1] narrows it (scoped re-runs, and the only way to
# exercise this watchdog end-to-end without burning 30 minutes per test).
DEFAULT_TARGET = "tests/"

# A hung runner must be killed; a *slow* runner must not be. The suite is
# RAM-aware (scripts/run_tests_parallel.py sizes its worker pool from free
# memory), so on a night where another job holds RAM it legitimately drops to
# 2-3 workers and needs well over an hour. Measured 2026-11-09: 60% at 3000s
# with 3 workers, i.e. ~5000s for a healthy run — the old flat 3000s timeout
# reported that healthy run as a failure. Progress, not wall-clock, decides.
STALL_TIMEOUT_S = 900     # no new output for 15 min => genuinely stuck
TIMEOUT_S = 14400         # absolute ceiling (4h) -- safety net, not the mechanism
LAST_TIMEOUT_REASON = ""  # why the last run was killed, for the alert text
SUMMARY_RE = re.compile(
    r"Summary:\s*(\d+)\s*files,\s*(\d+)\s*tests passed,\s*(\d+)\s*failed"
)
# The runner marks a failing file as "✗ tests\path\file.py"; the same glyph also
# appears as the running counter ("✗ 2]"), so match the path explicitly.
FAILING_FILE_RE = re.compile(r"✗\s+(tests[\\/][^\s(]+\.py)")
# The last progress line of a red run; its trailing "✗ N" is the failure count
# that belongs to the file named earlier in that same line.
FAILED_FILE_LINE_RE = re.compile(r"✗\s+(tests[\\/][^\s(]+\.py)\s+\((\d+)✓\s+(\d+)✗")


def _log(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")


def _load_state(state_path: Path) -> dict:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _env_override(name: str, default: Path) -> Path:
    """Let the test harness redirect a file so it cannot clobber live state."""
    raw = os.environ.get(f"TEST_WATCHDOG_{name}")
    return Path(raw) if raw else default


def _summarize_failures(out: str) -> list[str]:
    """Per-file failure counts, worst first — from the runner's progress lines."""
    counts = {
        path: int(failed)
        for path, _passed, failed in FAILED_FILE_LINE_RE.findall(out)
    }
    if not counts:  # fall back to names without counts
        return sorted(set(FAILING_FILE_RE.findall(out)))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [f"{path}  ({n} failing)" for path, n in ranked]


def _no_verdict_files(out: str) -> list[str]:
    match = re.search(r"^=== \d+ files? where no tests ran[^\n]*===", out, re.MULTILINE)
    if match is None:
        return []
    body = out[match.end():].split("\n===", 1)[0]
    return [line.strip().split()[0] for line in body.splitlines()
            if line.strip().split() and line.strip().split()[0].endswith(".py")]


def _run_suite(command: list[str], env: dict, output_path: Path):
    """Stream diagnostics to disk; kill only this run's process tree when stuck.

    Killing only bash (subprocess.run's default timeout handling) leaves pytest
    workers alive. They can keep consuming resources into the next nightly run.
    The runner starts new sessions per file, so killing one POSIX group is not
    enough either: snapshot descendants while the parent still exists.

    The kill condition is *no progress*, not elapsed time: the runner writes a
    progress line per finished file, so a growing output file proves the suite
    is alive even when it is slow (few workers because another job holds RAM).
    """
    import psutil

    global LAST_TIMEOUT_REASON

    def _kill_tree(proc: subprocess.Popen) -> None:
        try:
            children = psutil.Process(proc.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        proc.kill()
        proc.wait(timeout=10)
        psutil.wait_procs(children, timeout=10)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        proc = subprocess.Popen(command, cwd=str(REPO), env=env, stdout=output,
                                stderr=subprocess.STDOUT, start_new_session=True)
        hard_deadline = time.time() + TIMEOUT_S
        last_size = -1
        last_progress = time.time()
        try:
            while True:
                if proc.poll() is not None:
                    break
                try:
                    size = output_path.stat().st_size
                except OSError:
                    size = last_size
                if size != last_size:
                    last_size = size
                    last_progress = time.time()
                now = time.time()
                if now - last_progress > STALL_TIMEOUT_S:
                    _kill_tree(proc)
                    LAST_TIMEOUT_REASON = f"no output for {STALL_TIMEOUT_S}s (runner stalled)"
                    raise subprocess.TimeoutExpired(
                        command, int(now - last_progress),
                        output=LAST_TIMEOUT_REASON)
                if now > hard_deadline:
                    _kill_tree(proc)
                    LAST_TIMEOUT_REASON = f"hard ceiling of {TIMEOUT_S}s reached"
                    raise subprocess.TimeoutExpired(command, TIMEOUT_S,
                                                    output=LAST_TIMEOUT_REASON)
                time.sleep(5)
        except BaseException:
            if proc.poll() is None:
                _kill_tree(proc)
            raise
    return subprocess.CompletedProcess(command, proc.returncode,
                                       output_path.read_text(encoding="utf-8"), "")


def _announce_run(state_path: Path, target: str) -> None:
    """Write an in-flight marker before the suite starts.

    A full run takes over an hour here. If the process is killed from outside
    (gateway restart, `taskkill /F`, machine sleep) nothing gets written at the
    end — and a cron row with no verdict is indistinguishable from "never ran".
    The marker makes the death visible: it stays behind with status "running"
    and a start timestamp, so the next tick can report it.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "status": "running",
        "target": target,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "started_epoch": int(time.time()),
        "pid": os.getpid(),
    }, indent=1), encoding="utf-8")


def _previous_was_killed(state_path: Path) -> dict:
    """Was the last recorded run left mid-flight?"""
    try:
        prev = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(prev, dict) and prev.get("status") == "running":
        return prev
    return {}


def _install_kill_handlers(state_path: Path, log_path: Path, target: str,
                           started: float) -> None:
    """Record an external kill where a handler gets the chance to run.

    On POSIX a SIGTERM arrives before death; on Windows it usually does not,
    which is exactly why `_announce_run` exists as the durable fallback. This
    handler is the polite path, not the guarantee.
    """
    def _handler(signum, _frame):
        elapsed = int(time.time() - started)
        _log(log_path, f"KILLED by signal {signum} after {elapsed}s (target={target})")
        try:
            state_path.write_text(json.dumps({
                "status": "killed",
                "target": target,
                "signal": int(signum),
                "elapsed_s": elapsed,
                "started_epoch": int(started),
            }, indent=1), encoding="utf-8")
        finally:
            raise SystemExit(1)

    for name in ("SIGTERM", "SIGINT", "SIGBREAK", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (OSError, ValueError):
            pass


def _lower_own_priority() -> str:
    """Drop this process (and every child) to a low CPU priority class.

    Inherited by children on both platforms, so one call here covers bash, the
    canonical runner and every per-file pytest subprocess beneath them. Done on
    our own process rather than per child: the watchdog spawns from a single
    thread but the runner it starts is multi-threaded, and ``preexec_fn`` is
    unsafe with threads -- inheritance needs no such trick.

    Never raises: a scheduling nicety must not turn a green suite into an alert.
    """
    if os.environ.get("OPENAMER_TEST_LOW_PRIORITY", "1").strip() == "0":
        return "normal (OPENAMER_TEST_LOW_PRIORITY=0)"
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # Without explicit signatures ctypes truncates the pseudo-handle
            # (-1) to 32 bits and SetPriorityClass fails with err=0 -- the
            # documented shape of "it silently did nothing".
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.SetPriorityClass.restype = wintypes.BOOL
            if kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS):
                return "below-normal (win32)"
            return f"normal (SetPriorityClass failed, err={ctypes.get_last_error()})"
        os.nice(10)
        return f"nice+10 (now {os.nice(0)})"
    except Exception as exc:  # pragma: no cover - platform dependent
        return f"normal (could not lower priority: {exc})"


def main() -> int:
    state_path = _env_override("STATE", STATE)
    log_path = _env_override("LOG", LOG)

    # The nightly run must not make the machine unusable. Measured 2026-11-27:
    # the 04:00 run held the CPU at 96-100% for ~65 minutes, so the desktop and
    # the learning daemon were starved and the growth loop stayed paused the
    # whole time. Lowering our own priority class makes the whole tree (bash ->
    # runner -> pytest) lose every contest against interactive work while still
    # using every free cycle. ``OPENAMER_TEST_LOW_PRIORITY=0`` opts out.
    # Logged, never printed: this watchdog's contract is that empty stdout means
    # "all green", so an informational line on stdout would look like an alert.
    _log(log_path, f"SCHEDULING CLASS -> {_lower_own_priority()}")

    if not RUNNER.exists() or not PYTHON.exists():
        print("TEST-WATCHDOG: runner or venv python missing")
        print(f"  runner: {RUNNER} exists={RUNNER.exists()}")
        print(f"  python: {PYTHON} exists={PYTHON.exists()}")
        return 1

    # Read the previous verdict BEFORE _announce_run writes the in-flight
    # marker to the same path. Measured 2026-11-19: _announce_run (dba562c36,
    # "make a killed test run visible") overwrites state.json with
    # {"status": "running"} and no "failed" key, so the `prev` read after the
    # run always came back empty -- the red -> green recovery line could never
    # fire again, and a green suite said nothing at all. Silence after a red
    # night is the one thing a watchdog must not do.
    prev = _load_state(state_path)

    # Report a run that died without a verdict — otherwise it is invisible.
    stale = _previous_was_killed(state_path)
    if stale:
        age = int(time.time()) - int(stale.get("started_epoch") or 0)
        _log(log_path, f"PREVIOUS RUN DID NOT FINISH (target={stale.get('target')}, "
                       f"started {stale.get('started')}, {age}s ago, pid={stale.get('pid')})")
        print(f"TEST-WATCHDOG: the previous run never finished — it was killed "
              f"after {age}s with no verdict (target={stale.get('target')}, "
              f"pid={stale.get('pid')}). Starting a fresh run.")

    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    env = dict(os.environ)
    env["OPENAMER_PYTHON"] = str(PYTHON)
    started = time.time()
    output_path = state_path.with_suffix(".runner.log")
    timed_out = False
    _announce_run(state_path, target)
    _install_kill_handlers(state_path, log_path, target, started)
    try:
        proc = _run_suite([BASH, str(RUNNER), target, "-q"], env, output_path)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc = subprocess.CompletedProcess([], 124, output_path.read_text(encoding="utf-8"), "")

    elapsed = int(time.time() - started)
    out = (proc.stdout or "") + (proc.stderr or "")
    # Also supports injected runners in tests; the real runner streams here.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(out, encoding="utf-8")
    m = SUMMARY_RE.search(out)
    no_verdict = _no_verdict_files(out)
    counts = {path: int(failed) for path, _passed, failed in FAILED_FILE_LINE_RE.findall(out)}
    n_files, n_passed, n_failed = (int(g) for g in m.groups()) if m else (None, None, None)
    status = ("timeout" if timed_out else "incomplete" if m is None or no_verdict
              or "NO TESTS RAN" in out else "green" if n_failed == 0
              and proc.returncode == 0 else "red")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "target": target, "files": n_files, "passed": n_passed,
            "failed": n_failed, "elapsed_s": elapsed, "status": status,
            "returncode": proc.returncode, "no_verdict_files": no_verdict,
            "failing_files": counts, "output_path": str(output_path),
        }, indent=1), encoding="utf-8",
    )
    if timed_out:
        reason = globals().get("LAST_TIMEOUT_REASON") or f"no progress for {STALL_TIMEOUT_S}s"
        _log(log_path, f"TIMEOUT: {reason} (target={target}, elapsed={elapsed}s)")
        print(f"TEST-WATCHDOG: suite aborted — {reason} "
              f"(after {elapsed}s; partial output in {output_path})")
    elif m is None:
        _log(log_path, f"NO SUMMARY rc={proc.returncode} in {elapsed}s")
        print("TEST-WATCHDOG: could not read a summary from the runner output")
    elif status == "incomplete" or (n_failed == 0 and proc.returncode != 0):
        _log(log_path, f"INCOMPLETE exit={proc.returncode} no_verdict={len(no_verdict)} in {elapsed}s")
        print(f"TEST-WATCHDOG: incomplete run; {len(no_verdict)} file(s) produced NO verdict")
        for path in no_verdict:
            print(f"  {path}")
    else:
        return _report_result(n_files, n_passed, n_failed, elapsed, prev, log_path, out, target)
    print(f"  exit={proc.returncode}  elapsed={elapsed}s  output={output_path}")
    print("--- last 25 lines ---")
    print("\n".join(out.strip().splitlines()[-25:]))
    return 1


def _report_result(n_files, n_passed, n_failed, elapsed, prev, log_path, out, target):
    if n_failed == 0:
        _log(log_path, f"GREEN {n_passed} passed / {n_files} files in {elapsed}s")
        prev_failed = prev.get("failed")
        if prev_failed not in (None, 0):
            # Recovery is worth one message: the previous run was red.
            print(
                f"TEST-WATCHDOG: recovered — suite is green again.\n"
                f"  {n_passed} passed, {n_files} files, {elapsed}s "
                f"(previous run had {prev_failed} failing)"
            )
        return 0  # silent when it was already green

    _log(log_path, f"RED {n_failed} failed / {n_passed} passed in {elapsed}s")
    print(
        f"TEST-WATCHDOG: {n_failed} failing test(s) in the canonical suite\n"
        f"  {n_passed} passed, {n_files} files, {elapsed}s\n"
    )
    failing = _summarize_failures(out)
    if failing:
        print("Affected files:")
        for line in failing[:15]:
            print(f"  {line}")
        if len(failing) > 15:
            print(f"  … and {len(failing) - 15} more")
        print()
    print(f"--- runner tail ({target}) ---")
    print("\n".join(out.strip().splitlines()[-40:]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
