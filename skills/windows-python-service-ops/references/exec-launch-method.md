# exec() Launch Method — Single-Process Daemon Start

## When to use

When the venv→uv twin chain won't form cleanly (bash-process intermediate, stale locks, watchdog crash recovery), and `Start-Process` is unavailable or overkill. Starts the daemon as a **single raw Python process** with no bash wrapper, no venv launcher, no twin.

## Method

Use the **uv base Python** directly (not the venv wrapper), inject `sys.argv`, and `exec()` the script — no subprocess, no shell intermediate:

```bash
"C:/Users/damir/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe" \
  -c "import sys; sys.argv = ['','--loop']; exec(compile(open(r'C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\online_learning.py').read(), 'online_learning.py', 'exec'))"
```

## Verification

Expect exactly **1** `python.exe` with the `online_learning` pattern in its CommandLine:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*online_learning*' }
```

If the process runs for >10s and `mini_step()` starts cycling (logs observable via `process(action='log')` or file stderr), the single-process launch succeeded.

## Trade-offs

| Aspect | exec() method | Start-Process | Canonical `_cron_check_*.py` |
|---|---|---|---|
| Process count | **1** (no twin) | 2 (twin chain) | 2 (twin chain via venv) |
| Persistence | Till session/reaper | Survives reboot | Survives reboot |
| `mini_step()` subprocess | `sys.executable` = uv Python → spawns uv python (clean) | venv python → spawns uv python (twin) | psutil + DETACHED_PROCESS |
| Dependency | No psutil needed | No psutil needed | Requires psutil |
| Portability | Hardcoded path — needs path update per host | Hardcoded path | OPENAMER_HOME env var |

## Pitfalls

- **Hardcoded path**: the uv Python path differs per install/version. Verify it exists before using this method.
- **`exec()` + `compile()` = no module isolation**: the script runs in the caller's `__main__` namespace. Side effects from the calling `-c` string bleed into the script's globals. Keep the `-c` minimal (only `sys.argv` + `exec`).
- **No lock file**: unlike the canonical watchdog, the exec() method doesn't write `.online_learning.pid` or `online_learning.lockv2`. If another daemon check finds this process, it won't recognize it as "already managed". Pair with the twin-aware detection logic.
- **Argument quoting on German Windows**: passing `--loop` via `-c` with umlauts in the path or arguments causes `UnicodeDecodeError` on cp1252 terminals. Use only ASCII paths and ASCII-only arguments.