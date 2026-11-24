# Consumer-side liveness: the producer's own report is not evidence (live 21.09.26)

A cron job that runs `internet_learner.py --once` and prints
`rejected, not trained (shallow + deep read both gated)` looks like a stall.
It is not one. Three independent things must be told apart before you touch
anything, and **none of them is visible from the learner's own log line**:

| Claim | Producer-side evidence (insufficient) | Consumer-side evidence (required) |
|---|---|---|
| "the learner is alive" | a log row with a fresh timestamp | ≥1 row that is `learned:` / `*‑learn:` among **≥3** cycles |
| "the pipeline is not stalled" | `online_buffer.jsonl` size | adapter file **mtime** on disk |
| "the daemon runs" | a pid file / `ps` count | twin pair via psutil `ParentProcessId` |

## The full-buffer trap

`buffer_store.MAX_BUF == 300` and `enforce_cap` trims on **every** append. An
accepted row therefore leaves the line count **unchanged** at 300 — a pinned
300/300 buffer is the *normal* steady state, not a symptom. Judge throughput by
artifact mtime, never by row count:

```bash
ls -la --time-style=+%H:%M \
  C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/lora_out/adapter_rolling/adapter_model.safetensors
```

Live 21.09.26: `adapter_model.safetensors` rewritten **11:33:11**, probed at
**11:35:36** — training steps landing while every other cycle logged
"rejected". Compare the mtime against `date +%H:%M:%S`, in the same call.

## Daemon liveness on this host — which probe actually returns data

- `ps -W | grep -ci online_learning` → **0**, with `ps -W` producing nothing
  usable. A **silent zero is not proof of absence** (same trap as `rg` with no
  matches). Never conclude "daemon down" from it.
- `tasklist //FI "IMAGENAME eq python.exe" //FO CSV` → printed nothing.
- `wmic process where ... get CommandLine` → nothing (wmic is gone on this host).
- **What worked:** drive `Get-CimInstance` from *inside* a Python script with
  `subprocess.run(..., capture_output=True)`, so bash/MSYS never sees `$_`:

```python
import subprocess
out = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
     "Select-Object -ExpandProperty CommandLine"],
    capture_output=True, text=True, timeout=60)
lines = [l for l in out.stdout.splitlines() if l.strip()]
hits = [l for l in lines if "online_learning" in l]
print("python procs:", len(lines), "hits:", len(hits))
```

Result 21.09.26: 29 python processes, **2** matching `online_learning` — the
venv launcher plus its uv child, i.e. **one healthy daemon** (twin rule, see
SKILL.md). Killing either one kills both; report `TWIN_OK` and stop.

Also verify the daemon's own mode: with `--loop` the loop logs to **stdout**,
not to `logs/online_learning.log` — a days-old log mtime says nothing.

## Rate-first rule (applies to any gated learner)

A single rejected cycle is a coin flip at the observed reject rates. Before
attributing anything to the gates, count the day:

```bash
awk 'match($0,/"ts": "(2026-09-[0-9][0-9])/,m){d=m[1]; tot[d]++; if($0 ~ /rejected/) rej[d]++}
     END{for(k in tot) printf "%s tot=%d rej=%d rate=%.1f%%\n", k, tot[k], rej[k]+0,
         100*(rej[k]+0)/tot[k]}' scripts/training/internet_learn_log.jsonl | sort
```

21.09.26: 112 cycles / 70 rejects = **62.5 %** — inside the documented healthy
band 32–72 % (13.–20.09. measured 32.4 / 51.6 / 37.3 / 36.3 / 54.3 / 44.8 /
64.6 / 72.2 %). Inside the band ⇒ the rejection warrants **no gate change**;
run 3 cycles and report honestly. Only a rate outside the band, or a ≥3-in-a-row
reject streak, justifies opening the gate code. The dedicated gate-attribution
recipe (frozen-string probe of `IL._is_junk` / `BS.is_junk` /
`BS._is_serp_snippet`) and the class-BC NON-FIX verdict live in
`internet-learner-stall-fix` (user-owned — read it, do not patch it).

## Cleanup

Probe files are scratch: `rm -f <file>` works in a cron session, only
`rm -rf` is blocked. Delete them at the end of the session.
