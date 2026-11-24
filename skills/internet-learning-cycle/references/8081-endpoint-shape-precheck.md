# Step -1: probe the model endpoint's SHAPE before blaming the cycle (live 13.10.26)

Why this belongs here: `internet_learner.py` talks to `http://localhost:8081/v1/chat/completions`
(module constant `LIVE`), so a *foreign* core on :8081 changes the cycle's outcome without a
single line of learner code being at fault. (SKILL.md itself is at the 100 kB ceiling and cannot
be extended — this file is the pointer target.)

## 1. Judge `/health` by its SHAPE, not by "it answered"

```bash
curl -s -m 8 http://localhost:8081/health
```

| Body | Meaning | Consequence for the cycle |
|---|---|---|
| `{"status":"alive","tools":N,...}` | canonical `tool_server.py` | fine — judge the cycle itself |
| `{"status":"ok"}` | a **foreign llama.cpp core** (the profile's own `/v1` fallback) holds the port | the canonical core is NOT up; `/execute_tool` 404s |

In the second case the cron's "restart tool_server with the training venv if `/health` returns
nothing" branch is a **no-op** — `/health` answers, just with the wrong shape. Do **not** kill the
other listener: it belongs to another profile (`emilija`) and the shape-gated keepalive
(`scripts/tool_server_keepalive.py`) deliberately leaves a foreign non-deprecated core alone.
Full detail: skill `windows-python-service-ops` → `references/8081-port-contention.md`.

## 2. Saturated ≠ dead — read the elapsed time that is already in the log

`scripts/training/internet_learn_log.jsonl` rows are `{ts, source, result, elapsed_s}`.

- **normal cycle:** 30–85 s, `result` = a real `learn:` / `paper-learn:` / `competitor-learn:` line
- **saturated single CPU slot (observed 13.10.26, 06:48–06:54):** **6–14 s** rows with
  `no insight` — or a truncated raw page sentence where a `learn:` should be
  (`cycle_e_competitors`, 6.2 s: *"It was then released alongside the iPad in 2010, [ 3 ] …"*)
- same window, direct probes: `/health` → `{"status":"ok"}` **instantly** (so the HTTP loop is
  alive) while `/v1/chat/completions` → `HTTP:000` at 20 s, 25 s, 30 s and 120 s

**Re-probe before classifying.** A cycle 13 min later took **40 s** and returned a real gate
verdict (`rejected, not trained (shallow + deep read both gated)`) — the endpoint had only been
busy, serialised on one slot. Two probes ≥30 s apart, minutes apart, before calling it stalled.

## 3. Two servers on one port: the stuck duplicate has a numeric signature

```bash
powershell.exe -NoProfile -Command "Get-Process -Id <pid1>,<pid2> -ErrorAction SilentlyContinue | Select-Object Id,CPU,@{n='WS_MB';e={[int](\$_.WorkingSet64/1MB)}},StartTime | Format-Table -AutoSize"
```

| Process | Working set | CPU | Reading |
|---|---|---|---|
| holder (started 06:46) | 3.0–3.1 GB | 643–703 s | loaded, serving |
| duplicate (started 06:47) | 120–152 MB | ~8 s after 14 min | never finished loading — lost the port race, just sits there |

Triage by **working set + CPU seconds**, not PID order or creation time. And do not
"de-duplicate" another profile's process — report it with the numbers.

`netstat -ano | grep -i LISTEN` printing nothing is *not* "port free": the same call showed four
`127.0.0.1:8081 → 127.0.0.1:* … WARTEND` lines (German = WAITING) — connections mid-teardown
toward the port are themselves proof that a listener exists. Use
`Get-NetTCPConnection -LocalPort 8081 -State Listen` for the owner.

## 4. Report form when the cycle learned nothing

Name the source and the gate line, then the dependency evidence — a dependency-blocked cycle is a
finding, so **do NOT answer `[SILENT]`**:

```
cycle_g_security: no insight (9.4 s)
cycle_h_efficiency: rejected, not trained (shallow + deep read both gated) (40.0 s)
— /health {"status":"ok"} without a tools key ⇒ foreign core on :8081, canonical tool_server down
— /v1/chat/completions timed out 20/30/120 s at 06:48–07:00, cycles 6–14 s; recovered at 07:01
```

`[SILENT]` is only for a cycle that ran healthy and genuinely had nothing new to say.
