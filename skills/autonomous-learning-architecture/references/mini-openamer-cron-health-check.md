# Mini-OpenAmer Cron Health Check — Reference

## Purpose

Use this checklist when running a cron health sweep of the Mini-OpenAmer
subsystem: online-learning daemon, ToolServer (:8081), GPU worker (:8082),
episodic memory, world model, brain training, router state.

## Service probes (start here)

| Service | Probe | Healthy signal |
|---|---|---|
| ToolServer: serve_live.py (:8081, Delfin) | `curl -s --max-time 10 http://localhost:8081/health` | `{"status":"ok",...}` — else DOWN |
| ToolServer: serve_mini.py (:8081, Legacy) | `curl -s --max-time 30 -X POST http://localhost:8081/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":5}'` | Gültiges JSON mit `choices[0].message.content` — else DOWN (KEIN /health-Endpoint) |
| GPU Worker (:8082 via SSH) | `ssh damir@192.168.178.23 "curl -s --max-time 5 http://localhost:8082/health"` | `{"status":"ok",...}` — else DOWN |
| Router State | `.router_state.json` `last_refresh` | Must be < 7 days stale (observed 10 days stale on 13.09.26) |

## Online-learning daemon health

### Files to check (all in `OPENAMER_HOME/scripts/training/`)

| File | What it tells you |
|---|---|
| `.online_marker` | Training step counter — increases over time = alive |
| `.brain_count` | Training examples collected — should grow |
| `.last_retrain` | ISO timestamp of last retrain |
| `.daemon_pid.txt` | Daemon PID. MISSING doesn't mean daemon dead — watchdog may have restarted without writing one |
| `_wd_now.txt` | Last watchdog scan output — shows running PIDs + creation dates |
| `_online_daemon.log` | Daemon stdout: cycle logs, mini-step results, swap status |

### Life signs — read-only via file:// (when terminal is WSL-stub)

Read the mtimes of TWO independent per-cycle writers from the directory listing:

1. `online_buffer.jsonl` — appended every cycle (5 min interval)
2. `buffer_junk.jsonl` — also appended every cycle (rejection audit log)

If both advance on the ~300 s cadence, the daemon is alive. A single stale
file can be a paused code path; TWO advancing together is proof.

Cross-check against a known-fresh file (`outcome_analyses.jsonl` mtime) to
confirm the listing itself is not cached.

### Process table (fallback when terminal works)

`Get-CimInstance Win32_Process | Where-Object Name -EQ python.exe` reveals
the daemon twin chain (venv parent + uv child). The parent:child have
IDENTICAL `CreationDate` stamps. If 3+ processes with `online_learning.py`
in CommandLine exist, a duplicate was spawned — kill all but the oldest
pair (by CreationDate).

### Log-tail verdict

`file:///.../logs/online_learning.log` renders as text. Read innerText:

- `[online-learning] loop started` — restarts (should only appear once per daemon lifetime)
- `hot-swap: live-not-reachable` — benign fallback when :8081 is down; NOT a crash
- `mini-step N/3: {'ok': True, ...}` — healthy. Loss magnitudes jumping after fresh examples is normal
- `meta-learn cycle #N` repeating verbatim — ignore if `meta_state.json` mtime is stale; the counter is stuck on dead state

## Episodic memory check

File: `memory/longterm_episodes.jsonl`

```python
# Quick stats (Python on laptop)
total = sum(1 for _ in open('memory/longterm_episodes.jsonl'))
with_embed = sum(1 for l in open(...) if '"embedding"' in l)
print(total, with_embed)
```

**Schema facts (observed 13.09.26):**
- Keys: `ts`, `kind`, `text`, `meta`, `embedding`
- NO `created` field — use `ts` for temporal queries
- NO `indexed` field — `indexed: N` printed by scripts is the TOTAL count, not what was indexed
- `indexed: 0` does NOT mean indexing is broken; it means the schema lacks the `indexed` key
- Backfilled 8 days retrospectively with `--days 8` (the CLI writes the last N days)

**Shared-store caution (live 12.09.26):** Other crons write foreign-schema
records (`{timestamp, type, summary, action_needed}` with no `text` key)
into the same JSONL. Loaders must filter on required keys:
```python
if isinstance(e, dict) and "text" in e and "embedding" in e:
    out.append(e)
```
Never index blindly. Audit any shared store with `scripts/check_store_schema.py`.

## World model

File: `memory/world_model.jsonl`

| Metric | What to look for |
|---|---|
| Total entries | Should grow slowly (observed 303 facts + 35 predictions = 338) |
| Latest errors | Scroll to last entries — HTTP 402 (Token Harbor quota) is EXPECTED benign |
| Timeouts | `Cron job '...' idle for 60N s` - recurrent pattern |
| `embed_ok: False` edges | Should be 0 after `repair_store()` runs in nightly consolidation |

## Router state freshness

File: `scripts/training/.router_state.json`

```json
{"free_chain": [...], "last_refresh": "2026-09-03T16:24..."}
```

The free model chain can go stale (observed 10 days stale on 13.09.26).
Free models come and go (e.g. `z-ai/glm-5.2:free` went paid 404). Refresh
by running `smart_router.py --refresh` or re-running the tool_server.

## Brain training pipeline

| File | Signal |
|---|---|
| `.brain_count` | Integer — training examples collected (observed 2862) |
| `.last_retrain` | ISO datetime — should be < 48h old if retrain cron runs (observed 06:12 previous day) |
| `lora_out/adapter/` | Directory listing — should have `adapter_model.safetensors` + `adapter_config.json` |

## Quick verdict template

```markdown
### 🩺 Mini-OpenAmer Health — <DATE>

| Service | Status |
|---|---|
| ToolServer (:8081) | 🟢/🔴 |
| GPU Worker (:8082 via SSH) | 🟢/🔴 |
| Online Learning Daemon | 🟢/🔴 (marker, mtime cadence) |
| Episodic Memory | N episodes, latest: <DATE> |
| World Model | N entries, latest error: <TYPE> |
| Disk | N GB free |
| Router State | <N> days stale |
```

## Pitfalls

- **serve_mini.py startup time: ~2.5 min on CPU** — nach dem Start zeigt der Process-Table-Status `running`, aber Port :8081 ist erst nach dem `MODEL_READY`-Log belegt. Ein Health-Check <30s schlägt falsch fehl. Erstversuch braucht `--max-time 180`; Kurzprobe <30s ist kein Server-Crash, sondern Modell-Ladezeit. Der korrekte erste Check ist POST /v1/chat/completions mit langem Timeout.
- **No `tool_server.py` found to restart** — the server is part of the main
  OpenAmer process tree; there is no standalone restart script. Report DOWN
  honestly rather than fabricating a restart path.
- **GPU worker SSH works but server doesn't respond** — check whether the
  `frontier_server.py` (or `serve_live.py`) is actually bound to :8082 on
  the PC. Windows Firewall may block LAN connections even when `0.0.0.0` is
  the bind address. Verify ON the PC (`curl localhost:8082/health`).
- **24+ Python processes is normal** — Mini-OpenAmer runs 7 parallel learning
  loops + tool_server + agent processes. Investigate only if one PID holds
  >4 GB RAM or has run >4h CPU time.
- **`meta_learn.py` PATH failure on Windows** — when called from outside the
  training dir, `PYTHONPATH` / `cd` context matters. Always `cd` to
  `OPENAMER_HOME/scripts/training/` first, or use the absolute venv python.
- **`created` field is EMPTY on episodes** — the schema uses `ts`, not
  `created`. Sorting by `ts` works; `created` won't.
- **Evolution events file may not exist** — the memory claim "2400+ evolution
  events" may be aspirational (from identity.md text). Check `ls memory/evolution*`
  before reporting the count.
- **Never report a stale identity.md number** — always re-measure the raw
  store line count before stating episodic/world-model totals.