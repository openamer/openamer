# Online-Learning Daemon: Startup & Path Quoting

Git-bash (MSYS) on Windows mangles POSIX paths when starting the daemon.
Observations from the watchdog cron (live 10.09.26):

## The correct startup command

```bash
# WORKS — native Windows path, quoted script path:
C:/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/python.exe \
  "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/online_learning.py" \
  --loop
```

## What FAILS (and why)

```bash
# FAILS — MSYS mangles /c/ → C:/c/...:
/c/Users/damir/.../online_learning.py --loop
# → "can't open file 'C:\\c\\Users\\...': No such file or directory"
```

`/c/...` in git-bash gets a `C:/` prepended by the shell, yielding `C:/c/Users/...`
which is a doubled mount point.

## The twin-pair startup sequence

1. Venv python starts, becomes PID X (parent)
2. `mini_step()` calls `sys.executable` → venv python wrapper → uv python
3. uv python child (PID Y) appears with the same `--loop` arg, PPID = X
4. Both share `CreationDate` to the same second

Result: 2 processes, same cmdline, PPID child-of-other = 1 healthy daemon.

## Recovery after a mistaken twin-kill

When a watchdog mistakenly kills the child (the uv python, seeing it as a
"duplicate"), both processes disappear because the child is the actual worker
and the venv parent exits when its child dies:

1. Remove stale lock files:
   - `online_learning.pid` (the venv daemon wrote this)
   - `online_learning.lockv2` (the mini_step mutex)
   Only these two files exist on this host — `online_learning.lock` is a
   different mechanism and should NOT be removed.

2. Start fresh with the correct command above.

3. Verify the twin pair forms: check `cmdline *online_learning* --loop`
   returns 2 processes, one with PPID matching the other's PID.

## Canonical watchdog (preferred)

Use `_cron_check_online_learning.py` (Python/psutil) instead of a
PowerShell script — the psutil version handles twin detection and
DETACHED_PROCESS spawning correctly.