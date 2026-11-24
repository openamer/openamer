# Online-Learning Watchdog Pattern (07.09.26, updated 08.09.26, 09.09.26, 10.09.26)

## Session recap

The online-learning daemon (`online_learning.py --loop`) accumulates 4+ duplicate instances when multiple cron ticks fire the watchdog simultaneously without a lock check. The `terminal(background=true)` pattern also fails because the bash wrapper kills children on exit 127.

## ⚠️ Parent+Child Twin-Paar — nicht als Duplikat killen (Live 08.09.26)

Der online_learning Daemon spawnt via `subprocess.run([sys.executable, str(MINI_STEP_SCRIPT)])` ein Kind in jedem Zyklus. **Bis zu 2 Prozesse mit `--loop` in der CommandLine sind NORMAL** — Eltern (venv-Python) + Kind (uv-Python). Sie teilen eine Parent-Child-Beziehung.

### Erkennung: Ist es 1 gesunde Instanz oder echte Duplikate?

```powershell
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | 
  Where-Object { $_.CommandLine -like '*online_learning.py --loop*' } |
  Select-Object ProcessId, ParentProcessId
if ($procs.Count -eq 2 -and ($procs[0].ParentProcessId -eq $procs[1].ProcessId -or 
    $procs[1].ParentProcessId -eq $procs[0].ProcessId)) {
  Write-Output "HEALTHY_PAIR: parent+child — OK"
} else {
  Write-Output "DUPLICATES_OR_SINGLE: $($procs.Count) instances"
}
```

**Regel:**
- **2 Treffer + Parent-Child-Beziehung** = 1 gesunder Daemon → NICHT killen, nur silently confirm
- **2 Treffer OHNE Parent-Child-Beziehung** = 2 echte Duplikate → kill-all, restart fresh
- **3+ Treffer** = echte Duplikate → kill-all, restart fresh
- **0 Treffer** = Daemon tot → restart fresh
- **1 Treffer** = Kind überlebt, Eltern tot (orphan) → kill den Orphan, restart fresh

**⚠️ 08.09.26 refinement:** PPID-based matching is FRAGILE because the venv-launcher's parent is bash, not the uv worker. A simpler approach uses `*uv*` in CommandLine to identify the worker (see section below).

### Kill-All Killt immer die gesamte Kette (Bestätigt 08.09.26)

`Stop-Process -Id <child> -Force` auf das uv-Kind beendet **auch** den venv-Elternprozess (Windows Job-Object shared zwischen Launcher + Target). Daher:

```powershell
# RICHTIG — kill-all killt beide synchron
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | 
  Where-Object { $_.CommandLine -like '*online_learning.py --loop*' } | 
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# FALSCH — nur das Kind killen
Stop-Process -Id <child> -Force   # ← Eltern stirbt auch (Job-Object)
```

### Nach dem Restart: erwartetes Bild

Nach einem sauberen Start tauchen nach ~5s zwei Prozesse auf:
```
PID=X | PARENT=<bash> | CMD=venv/Scripts/python.exe online_learning.py --loop    ← Eltern
PID=Y | PARENT=X      | CMD=uv/cpython-3.11/python.exe online_learning.py --loop  ← Kind
```
Diese zwei sind gesund — NICHT killen. Der Watchdog greift nur ein bei:
- 0 Treffer → restart
- 3+ Treffer → kill-all + restart
- 2 Treffer OHNE Parent-Child-Beziehung → kill-all + restart

## Watchdog procedure

```bash
# Step 1: Find all online_learning daemon processes
# (escape $_ with \$ to prevent bash expansion)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*online_learning.py --loop*' } | Select ProcessId, CommandLine"

# Step 2: Kill ALL duplicates (if any)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*online_learning.py --loop*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"

# Step 3: Clean stale lock file
rm -f "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/online_learning.lock"

# Step 4: Verify no instances remain
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*online_learning.py --loop*' } | Select ProcessId"
# Should return empty (no output)

# Step 5: Start fresh detached daemon
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe' -ArgumentList 'C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/online_learning.py --loop' -WindowStyle Hidden"

# Step 6: Verify it's alive after 10s
sleep 10 && powershell -NoProfile -Command "Get-Process -Id (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*online_learning.py --loop*' } | Select-Object -First 1 -ExpandProperty ProcessId) -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, @{Name='MemMB';Expression={[math]::Round(\$_.WorkingSet64/1MB,1)}}, StartTime"
```

## Exit-15 + PID-Switching Trap (07.09.26)

`terminal(background=true)` starts the daemon, but the process manager kills it with SIGTERM (exit 15) after ~59s. **Surviving PIDs after exit 15 are from a DIFFERENT source** (cron, self-healer) — the background process truly died.

- **Verification**: compare `process(action='poll')` PID with PowerShell CIM results. If they differ, the background start died.
- **Fix**: use `Start-Process -WindowStyle Hidden` via PowerShell for persistent daemons.
- **Live evidence**: background PID=44432 exited 15 after 59s; live PIDs=42896/47704 were a different chain.

## Health check after restart

The daemon logs to `scripts/training/_ol_stdout.log`. Expected output after 30-60s:

```
[online-learning] loop started: cycle=300s, steps/cycle=3, swap-every=6, replay-mode=on
[online-learning] buffer trimmed to 300
[online-learning] replay: +2 old episodes re-injected (buffer=300)
[online-learning] mini-step 1/3: {'ok': True, 'examples': 2, 'avg_loss': <float>, 'fresh_adapter': False}
[online-learning] mini-step 2/3: {'ok': True, 'examples': 2, 'avg_loss': <float>, 'fresh_adapter': False}
[online-learning] mini-step 3/3: {'ok': True, 'examples': 2, 'avg_loss': <float>, 'fresh_adapter': False}
[meta-learn] cycle #4: next strategy: replay (not enough data yet — exploring)
[online-learning] analogy extraction: {"added": 0, "total": 31}
[online-learning] hot-swap: OK: swap queued (#N) — applied on next request
```

Loss values bouncing between 0.08–2.2 are normal (replay mode re-injects old episodes, causing gradient noise). Hot-swap every 6 cycles (~30 min) confirms the adapter is live-queued.

## 🆕 08.09.26: uv-path Twin Detection (simpler, verified)

**Kernerkenntnis:** Der online-learning Daemon erzeugt ein **venv→uv Twin-Paar**: 
- **venv Launcher** (`venv/Scripts/python.exe`) → erkannt via `*uv*` NICHT in CommandLine
- **uv Worker** (`uv/python/cpython-3.11/python.exe`) → erkannt via `*uv*` IN CommandLine

PPID-basierte Erkennung ist **fragil**, weil der venv-Launcher unter bash läuft (PID des bash-Wrappers, nicht des uv-Kinds). Die zuverlässige Methode ist CommandLine-Matching auf `*uv*`.

### Vereinfachte Erkennung (statt PPID-Vergleich)

```powershell
function Get-OnlineProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*online_learning.py*' }
}
function Get-UvProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*online_learning.py*' -and $_.CommandLine -like '*uv*' }
}

$all = @(Get-OnlineProcesses)
$uv = @(Get-UvProcesses)

# Twin = genau 2 total + davon 1 uv
if ($all.Count -eq 2 -and $uv.Count -eq 1) { "TWIN_OK" }
# Single = 1 Instanz (rare, wenn venv crashed)
elseif ($all.Count -eq 1) { "SINGLE" }
# 0 oder >2 → kill-all + restart
else { /* kill all, then restart fresh */ }
```

### "Keep Oldest" ist unsicher → Kill-All-Then-Start ist die Lösung

Der "keep oldest"-Ansatz (alle killen bis auf den ältesten Twin) scheitert, weil **Windows Job Objects** Kill-Signale über die gesamte venv→uv-Kette teilen. `Stop-Process -Id <child>` killt auch den Elternprozess. Stattdessen:

```
1. Erkenne ob Twin (2 Prozesse = genau 1 gesunder Daemon) → nichts tun, OK ausgeben
2. Erkenne ob Single (1 Prozess = möglicher Orphan) → kill-all + restart
3. Erkenne ob tot (0 Prozesse) → start
4. Erkenne ob echte Duplikate (>2 oder 2 ohne UV) → kill-all + restart
```

### Canonical Watchdog-Script

Das Script befindet sich unter der Skill `windows-python-service-ops` als `scripts/watchdog-online-learning.ps1`. Lokale Kopie ebenfalls in OpenAmer-Laptop: `scripts/_watchdog_online_learning.ps1`.

**Usage:**
```bash
powershell -NoProfile -ExecutionPolicy Bypass -File \
  "C:/Users/damir/AppData/Local/openamer-laptop/scripts/_watchdog_online_learning.ps1"
```

**Output-Formate:**
| Output | Bedeutung | Aktion |
|---|---|---|
| `STATUS=TWIN_OK\nVENV_PID=...\nUV_PID=...` | 1 gesunder Daemon | Nichts tun |
| `STATUS=RUNNING\nPID=...` | 1 Instanz (selten) | Nichts tun |
| `STATUS=DUPLICATES:N\n...\nSTARTED_UV_PID=...` | Duplikate → gekillt → neugestartet | OK |
| `STATUS=NOT_RUNNING\n...\nSTARTED_UV_PID=...` | War tot → gestartet | OK |

### Idempotenz bestätigt (Live 08.09.26)

Zweiter Aufruf innerhalb derselben Minute gibt `TWIN_OK` zurück. Kein Flapping.

### Twin-Detail: venv PID → uv PID (Live 08.09.26)

```
ProcessId       : 13084      (venv Launcher)
CommandLine     : "...\venv\Scripts\python.exe" "...online_learning.py" --loop
ParentProcessId : 21668      (bash wrapper)

ProcessId       : 5344       (uv Worker — der, der wirklich Loopt)
CommandLine     : "...\uv\python\cpython-3.11...\python.exe" "...online_learning.py" --loop
ParentProcessId : 13084      (venv Launcher)
```

Der uv-Worker (PID 5344) ist der eigentliche Arbeiter. Der venv-Launcher (PID 13084) startet ihn per `subprocess.run`. Die `*uv*`-Filterung identifiziert den Worker zuverlässig.

### Health-Check auf aktive Log-Produktion

Nach einem Restart prüft man nicht nur Prozess-Existenz, sondern auch Logging:

```bash
cat "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/internet_learn_log.jsonl" | tail -3
```

Ein gesunder Daemon produziert alle 5 Minuten frische Logs mit cycle-Labeln (`cycle_a_papers`, `cycle_b_papers`, etc.). Timeout der letzten Logs > 15 Min = Daemon läuft zwar, tut aber nichts → trotzdem Restart.

## 🆕 09.09.26: Start-Process parameter fix + refined TWIN_OK

### Bug: -NoNewWindow + -WindowStyle sind inkompatibel

```powershell
# FEHLER (exit 1, InvalidOperationException)
Start-Process -FilePath $venv -ArgumentList "$script --loop" -WindowStyle Hidden -NoNewWindow

# RICHTIG
Start-Process -FilePath $venv -ArgumentList "$script --loop" -WindowStyle Hidden
```

Fehler beim ersten Watchdog-Lauf: Der Daemon wurde mit dem inkorrekten Parameter-Paar gestartet, sodass der Start in PowerShell fehlschlug und kein uv-Child entstand. Beim zweiten Aufruf war kein Prozess mehr da → Watchdog startete einen sauberen, der dann TWIN_OK erreichte.

### Refined TWIN_OK: $TWIN_OK = 2 Variable statt festem Count-Check

Das alte Script hatte `$allCount -eq 2` fest einprogrammiert. Das neue verwendet `$TWIN_OK = 2` als Variable, sodass die Logik strukturiert ist:

| Zustand | Action |
|---|---|
| `Count -eq 0` | Start |
| `Count -gt $TWIN_OK` | Kill Duplikate, behalte älteste $TWIN_OK |
| `Count -eq $TWIN_OK` | TWIN_OK (silent confirm) |
| else (Count -eq 1) | OK (single, rare degraded state) |

Exit-Codes:
- **0**: Alles gut (TWIN_OK oder Single Instanz)
- **1**: Daemon war tot → wurde gestartet
- **2**: Duplikate gefunden → älteste $TWIN_OK behalten, Rest gekillt
- **3**: Fehler (Pfad nicht gefunden)

### Verifikation (3 Runs, 09.09.26)

| Run | Zustand | Exit | Ergebnis |
|---|---|---|---|
| 1 | 2 online_learning Prozesse (vor altem Script) | 2 | Duplikat PID 13364 beendet, PID 2896 behalten |
| 2 | 0 Prozesse → Start (alter Bug) | 1 | Fix: -NoNewWindow entfernt |
| 3 | 0 Prozesse → Start (gefixt) | 1 | Start erfolgreich → TWIN_OK PIDs 27692, 7408 |
| 4 | TWIN_OK (2 Prozesse) | 0 | ✅ Stabil: PIDs 27692, 7408 |

Gelernt: `$all = @(...)` garantiert immer ein Array → `.Count` funktioniert für 0, 1 und N ohne Null-Check.

### 🆕 09.09.26 (late): Inline-twin-kill re-confirmed — canonical script is the ONLY safe path

A cron watchdog run later the same day re-confirmed the twin-kill hazard despite having the FULL decision table at hand. Sequence:

1. **Initial check**: 0 processes → daemon started via `terminal(background=true)`
2. **5s later**: 2 processes found (venv PID 21404 + uv PID 16280, same CreationDate)
3. **Naive response**: identified uv child (16280) as "duplicate" → `Stop-Process -Id 16280 -Force`
4. **Result**: BOTH processes died instantly (Job Object killed the chain). Verified via `Get-CimInstance` → empty output.
5. **Restart via `terminal(background=true)`**: another twin pair formed, again at the same CreationDate (12028 + 9312)
6. **Correct verification**: `CommandLine` check showed venv (`venv/Scripts/python.exe`) + uv (`uv/python/cpython-3.11.../python.exe`) — healthy pair.
7. **Process logs confirmed**: daemon running stable with mini-steps, replay mode active, avg_loss=1.055.

**Key lesson re-confirmed:** even with the twin-detection logic known, the agent's natural response to "2 processes" is to kill one — and the chain dies. The canonical `_cron_check_online_learning.py` script (Python/psutil, DETACHED_PROCESS) is the ONLY reliably safe approach. The .ps1 scripts under `scripts/` are for diagnostic/debug use only, not for cron monitoring.

## 🆕 10.09.26: Cron-spec "keep oldest" trap — verified worked recovery recipe

The cron watchdog job itself instructed "Falls MEHRERE Instanzen laufen, beende alle außer der ältesten PID" (if multiple instances, kill all but the oldest PID). Executing that literally produced the following sequence:

1. **Initial state**: 4 matches = 2 full duplicate daemons (venv 13820 + uv 15412 paired; venv 13100 + uv 6916 paired).
2. **Naive keep-oldest**: killed uv 15412, venv 13100, uv 6916 — kept venv 13820. Result: **0 processes** (killing uv 15412 destroyed its own venv 13820 via Job Object). Oldest PID survived nothing.
3. **Restart (terminal background, fully-quoted absolute paths)**: new pair appeared within ~3s (venv 13536 + uv 13216). The naive kill-again struck: killed uv 13216 → chain died → 0 processes.
4. **Second restart**: pair (venv 2008 + uv 20892), killed uv 20892 → 0 processes again.
5. **Third restart**: pair (venv 4324 + uv 5088, uv PPID = 4324 ✓). **This time verified with ParentProcessId + process log before touching anything** — daemon healthy, mini-steps running (avg_loss 0.44 → 0.168 → 0.082), analogy engine total=31. Left untouched. Final: STATUS=TWIN_OK.

**Durable lessons (10.09.26):**
- **Even with real duplicates (4 procs = 2 pairs), "keep the oldest pair" by selective Stop-Process is unsafe**: any kill of a uv child kills its own venv parent. The ONLY safe duplicate remediation is kill-ALL (venv+uv of every pair) then start exactly one fresh instance — matching the decision table's "3+ → kill-all + restart".
- **`terminal(background=true)` with fully-quoted absolute paths DID work 3/3 restarts** on this host (each restart formed a healthy venv→uv pair within ~3s). This contradicts the earlier blanket "do NOT use fully-quoted absolute paths" advice — treat exit 127 as the failure signal and fall back to `Start-Process -WindowStyle Hidden`; do not pre-emptively refuse the working form.
- **Recovery verification order that ends the kill-loop**: (a) after restart, wait 3–5s, (b) count matches AND check ParentProcessId (uv child's PPID must equal the venv launcher PID), (c) confirm health via the daemon's own log output (mini-step avg_loss lines) — process existence alone is not enough to break the habit of killing.
- **Guard against the cron-spec itself**: a watchdog prompt saying "kill all but oldest" is the trap; bank the twin-pair classification (2 procs + exactly 1 uv child with venv parent = healthy, do nothing) into the cron text or use `_cron_check_online_learning.py`.

## ✅ 10.09.26 (late): Correct TWIN_OK verification — proven working

A cron watchdog run later the same day (separate execution) PROVES the learnt pattern works when followed correctly.

**State found:**
```
PID=17108|PPID=26476|CREATION=09/10/2026 15:02:50
  CMD=C:\...\venv\Scripts\python.exe scripts/training/online_learning.py --loop
PID=18424|PPID=17108|CREATION=09/10/2026 15:02:50
  CMD="C:\...\uv\python\cpython-3.11-windows-x86_64-none\python.exe" scripts/training/online_learning.py --loop
```

**Verification chain:**
1. `Count = 2` → potential twin pair, not zero/one
2. `ParentProcessId 18424 = 17108` → child's parent IS the venv launcher ✓
3. Same `CreationDate` (both `09/10/2026 15:02:50`) → spawned as one atomic unit, not independent starts
4. CommandLine signature: one without `*uv*` (venv), one WITH `*uv*` (worker) ✓
5. **Conclusion: TWIN_OK → did NOTHING.** No processes killed, no restart triggered. The daemon continued running uninterrupted.

**Key takeaway:** the `.ps1` → `write_file` → `powershell -File` approach (avoiding inline `-Command` with `$_` MSYS mangling) produced clean, parseable output. The structured format `PID=N|PPID=N|CREATION=...|CMD=...` enabled reliable classification without PowerShell noise. The PPID check is the DIFFERENTIATOR between "healthy twin" and "two independent duplicates" — both produce `Count=2` but only twins share a direct parent-child relationship (`uv_child.PPID == venv_pid`).

**Contrast with the cron-spec trap (earlier 10.09.26):** earlier that day, literal execution of "kill all but oldest" destroyed the daemon 3 times in a row. This run proves that replacing the naive instruction with the PPID-based twin check prevents the destruction. The fix is not in the tooling — the tooling (`_cron_check_online_learning.py`) was already canonical — the fix is in HOW the cron agent interprets "2 matches". If the watchdog prompt says "kill all but oldest", the agent MUST override with the twin-pair classification.

## References

- `windows-python-service-ops` SKILL.md — main umbrella, "Daemon persistence via Start-Process" section
- `windows-python-service-ops/scripts/watchdog-online-learning.ps1` — canonical .ps1 script (curator-managed)
- `windows-python-service-ops/references/online-learning-watchdog.md` — this reference file (complete session history)
- `cron-job-repair` → `references/psutil-daemon-watchdog.md` — alternative psutil-based watchdog approach