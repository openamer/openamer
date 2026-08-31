# Windows A2A Brain-Data Pitfalls (observed on Damir's machine)

## meshlearn auto — npm install timeout

`openamer a2a meshlearn auto "<lesson>" --topic <topic>` triggers a full
`npm install` in the background before the insight pipeline runs. On Windows
this can take 20+ seconds. If the insight text is over ~200 characters, the
CLI command timeout (default ~15s) fires and the command appears to fail.

**However:** the insight IS still written to memory. Verify with:
```
grep "<topic>" ~/.openamer/MEMORY-official-mesh.md
```

Short insights (<200 chars) complete normally. Long summaries trigger the
timeout.

## Dual brain files (pre-v1.2 artifact)

Before commit 92ead087d (v1.2), the `session_to_brain.py --watch` daemon wrote
to `~/.openamer/trajectories/` while `a2a brain collect` wrote to
`~/.openamer/a2a/`. This caused confusion — the daemon output was invisible
unless `brain collect` was run manually.

**Now (v1.2+):** both write to the same file:
```
~/.openamer/a2a/openamer-brain.jsonl    ← LIVE (daemon + collect both write here)
```

A stale copy may still exist at:
```
$OPENAMER_HOME/a2a/openamer-brain.jsonl ← STALE (pre-v1.2 artifact)
```

Ignore the app-data copy — it's not updated anymore.

## Session-to-brain daemon on Windows

The daemon (`openamer_cli/session_to_brain_daemon.py → scripts/session_to_brain.py --watch`)
is spawned at every `openamer` startup (main.py line 15146-15148). On Windows:

- It spawns as a silent subprocess (`CREATE_NO_WINDOW` flag)
- PID is written to `~/.openamer/session_to_brain.pid`
- Stale PID files are cleaned up on next spawn
- The daemon dies when the parent process (CLI or desktop app) is killed
- It respawns automatically on next startup

**Diagnostic:**
```powershell
# Check if running:
Get-Content ~\.openamer\session_to_brain.pid
# Or grep logs for daemon start message
```

## Daemon dies with desktop app

When using the desktop app, killing the app process (e.g. via taskkill or
closing the window) also kills the daemon. This is expected — it's a child
process. The daemon starts fresh on next launch.

If the daemon wasn't running and you need to export immediately:
```bash
python "C:\Users\<user>\AppData\Local\openamer-laptop\openamer-agent\scripts\session_to_brain.py"
```

## Real-world numbers (Damir's machine, v1.2)

- ~12h development + conversation BEFORE daemon fix → 9 records, ~900 KB
- ~20h total AFTER daemon fix + manual export → **35 records, ~9 MB**
- After 1 week at current usage → ~150-200 records, ~20-30 MB
- Session DB (state.db): 29 MB after ~2 days of use
- Node fingerprint: cf971ad884b74297@openamer