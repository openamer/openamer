# False recovery: a pid file is not a lock (live 19.09.26)

Full evidence chain for the "ask the lock, not the pid file" section of SKILL.md. Found while
verifying a growth-cron's claim that a 24/7 guardian (`autonom_watchtower.py`) had respawned a dead
daemon. It had not — it had been *reporting* the same respawn on **871 consecutive runs**.

## 1. The guardian under test

`scripts/autonom_watchtower.py` — a `no_agent` cron (zero LLM tokens), `every 30m`, job
`6d602cd72e74`, `no_agent: true`, `repeat.completed: 871`. It probes local organs and may take
bounded recovery actions:

```
1. session_to_brain daemon      -> respawn if the pid is dead
2. Chrome CDP :9222             -> restart with the persisted profile
                                  (rejects a HeadlessChrome impostor by design)
3. Dashboard serve :9119        -> start `serve --insecure` if the API is refused
4. config model standard        -> is the user's declared provider/model resolvable
5. A2A worker workflow present  -> .github/workflows/a2a-worker.yml
6. reboot-flag.json pending     -> tell the owner a restart is due
```

Design property worth keeping: **silent when healthy.** Every tick writes
`OPENAMER_HOME/autonom-state.json` and prints nothing unless there is a failure or a recovery.
Exit 0 + empty stdout = the cron stays quiet.

```json
{ "ts": ..., "healthy": true, "problems": [], "actions": [] }
```

## 2. The symptom — pid moves, recovery never converges

Two consecutive ticks against the **real** home:
`OPENAMER_HOME='C:\Users\damir\AppData\Local\openamer-laptop'`

```json
{ "ts": 1789784388.8, "healthy": false,
  "problems": ["session_to_brain daemon down"],
  "actions":  ["respawning session_to_brain"] }
```

and one tick later, byte-identical output apart from the timestamp. The tell is the pid file:

```
session_to_brain.pid  =>  30564  ->  31168  ->  33664
```

A converging recovery leaves a *stable* pid. A treadmill writes a new one every run.

> ⚠️ **First-run trap that cost time:** the initial run happened with the shell's inherited
> `OPENAMER_HOME=/c/tmp/oa-home` (a leftover scratch value — the known MSYS phantom-home form). It
> wrote `autonom-state.json` into `C:\c\tmp\oa-home\` and reported the **wrong** problem
> (`config model standard unresolved`). Always export the native path
> (`OPENAMER_HOME='C:\Users\damir\AppData\Local\openamer-laptop'`, single-quoted so bash keeps the
> backslashes) before probing, or you are diagnosing a scratch tree. See `windows-path-resolution`.

## 3. The child explains itself

```
$ cd <home>/openamer-agent && python scripts/session_to_brain.py --watch
  [watch] another session-to-brain watcher is already running — exiting
```

Exit 0. So the daemon is **not** down — the liveness check is wrong.

## 4. Two mechanisms, two answers

| | Mechanism A — the buggy check | Mechanism B — the real truth |
|---|---|---|
| Where | `openamer_cli/session_to_brain_daemon.py :: spawn()` | `scripts/session_to_brain.py :: _watch_singleton_lock()` |
| Test | `int(pid_file.read_text())` + `tasklist /FI "PID eq N"` | `msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)` (Windows) / `fcntl.flock(LOCK_EX\|LOCK_NB)` |
| Artifact | `OPENAMER_HOME/session_to_brain.pid` | `OPENAMER_HOME/session_to_brain.watch.lock` |
| Lifetime | until something rewrites it | held for the process lifetime, released by the OS on death |

`spawn()` reads the pid file, sees a pid that is not alive, concludes "stale", launches a child, and
writes the new pid — never noticing that the **lock** is held by a live watcher. The child then
correctly refuses to start on the lock.

**The blame lands on the watchdog.** The daemon behaves exactly as designed; the pid file is simply
the wrong artifact to interrogate for a lock-guarded singleton.

## 5. Lock proof: the read failure is the positive evidence

```
$ cat AppData/Local/openamer-laptop/session_to_brain.watch.lock
cat: Device or resource busy
```

Python: `PermissionError: [Errno 13] Permission denied` on `Path.read_text()`.

Negative control (three homes checked; each lock's recorded holder pid looked up with `tasklist`):

```
LOCK .openamer/session_to_brain.watch.lock                        -> holder pid= alive=0
LOCK AppData/Local/openamer-laptop/session_to_brain.watch.lock    -> holder pid= alive=0   (busy = live)
LOCK AppData/Local/openamer/session_to_brain.watch.lock           -> holder pid= alive=0
```

Readable lock + dead recorded pid = stale artifact. **Failing to read = live holder.** These two
must not be inverted.

## 6. The `OPENAMER_HOME` split that makes it worse

| Caller | Fallback chain |
|---|---|
| `session_to_brain_daemon.spawn()` | `OPENAMER_HOME \|\| Path.home() / ".openamer"` |
| `session_to_brain.py` helpers (`_state_db`, `_trajectory_file`, `_watch_singleton_lock`) | `OPENAMER_HOME \|\| Path.home() / "AppData" / "Local" / "openamer"` |

All three candidate trees exist on this box:

```
EXISTS: .openamer
EXISTS: AppData/Local/openamer-laptop
EXISTS: AppData/Local/openamer
```

So with `OPENAMER_HOME` unset, the pid file and the lock can land in **different trees** — a third
way for the two mechanisms to disagree, independent of the pid-is-not-a-lock problem. One resolver,
called by both sides.

## 7. Attribution of the process count

Pattern-census of `session_to_brain.py --watch` (scanner's own signature excluded; see SKILL.md
`SELF_MARKERS`):

```
156 live processes      450 MB RSS
  92 x  C:\Users\damir\openamer-repo                       (239 MB)
  32 x  C:\Users\damir\AppData\Local\Temp\oa-verify        ( 84 MB)
  24 x  C:\Users\damir\AppData\Local\openamer-laptop\...   ( 62 MB)
   8 x  C:\Users\damir\AppData\Local\openamer\...          ( 66 MB)
age: min 0.5h  median 7.7h  max 22.2h
```

First run printed `160`; 4 of those were the scanner plus its child. Group by install root before
calling it a leak — only one root is attributable to the watchdog being investigated.

## 8. What to take away

1. **Never treat a pid file as liveness for a lock-guarded daemon.** Ask the lock: try to acquire.
   Failure to acquire = the daemon is up and the pid file is stale.
2. **One source of truth for `OPENAMER_HOME`** — duplicated env fallbacks silently split state.
3. **Make the watchdog assert convergence.** "I took an action" ≠ "the system is healthy" — an
   action taken 871 times is a bug wearing a green light.
4. **Keep the silent healthy path** — it is what makes the guardian free.
