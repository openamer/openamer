# The learning loop dies silently in three ways (2026-10-05, all measured)

The RSI / meta-learning machinery can look alive while doing nothing. Each link
below was broken on this box; each fix was verified with real evidence, never a
green cron status.

The closed loop is: **serve → collect → retrain → hot-swap**. Every link needs a
*supervisor* AND a *measurement*. A link that only has `last_status: ok` is the
broken one.

## 1. The served core has no supervisor

`scripts/training/serve_live.py` (:8081) is the cognition core — Qwen3.5-2B +
LoRA, OpenAI-compatible inference, and **test-time training on every exchange**
(`_learn_inline` runs one gradient step per chat, fire-and-forget). Nothing
restarted it when it died, so the served model and its learning were silently
gone.

**Fix:** a keepalive cron (mirror `scripts/a2a_keepalive.py`): probe the port,
spawn detached only if down, silent while healthy.

- Spawn with the **training venv** `$OPENAMER_HOME/venv` (has torch /
  transformers / peft), NOT the agent venv (`openamer-agent/venv` has pytest but
  no torch). `serve_live.py`'s own default path had the `openamer` vs
  `openamer-laptop` typo — verify `$OPENAMER_HOME` is set.
- Model load is heavy (~90 s wait before the port answers).
- Windows: `creationflags = CREATE_NO_WINDOW | 0x00000008` (DETACHED_PROCESS)
  so the server outlives the cron tick.
- Verify: `curl :8081/health` → `{"status":"alive","learn_steps":N}`.
  `learn_steps` incrementing across chats is the proof test-time training runs;
  `last_loss` non-null means a real gradient step landed.

## 2. The retrain is gated on a path/count that can never fire

`scripts/training/auto_retrain.py` (nightly, watchdog-style: silent exit 0 unless
it trained) was permanently silent. Two independent bugs:

- **Path mismatch.** It read `~/.openamer/a2a/openamer-brain.jsonl` (a **stale**
  Sep-24 copy) while `brain_collect` writes
  `<OPENAMER_HOME>/a2a/openamer-brain.jsonl` (fresh, 7544 vs 2288 lines) — two
  *different files*, **not** a symlink.
- **Non-monotonic counts.** `brain_collect` **regenerates** the brain file (does
  not append), so `new = brain_ct - last_ct` goes **negative** whenever the
  dataset shrinks (observed 7544 → 1417). The old gate `new < MIN_NEW_PAIRS`
  then always tripped.

**Fix:** point `BRAIN` at `<OPENAMER_HOME>/a2a/openamer-brain.jsonl` and gate on
**mtimes**, not counts:

```python
HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData/Local/openamer-laptop")))
T = HOME / "scripts" / "training"
BRAIN = HOME / "a2a" / "openamer-brain.jsonl"
...
if not BRAIN.exists(): return
last = MARKER.stat().st_mtime if MARKER.exists() else 0.0
if BRAIN.stat().st_mtime <= last: return        # nothing freshly collected
if sum(1 for _ in open(BRAIN, encoding="utf-8")) < MIN_NEW_PAIRS: return
```

Verify by printing the resolved `BRAIN` and whether the gate now opens.

## 3. The fitness time-series is frozen and cannot be read

`openamer-agent/scripts/benchmark.py` stores runs under `"history"`, but
`run_full()` read `all_results["runs"]` → `KeyError: 'runs'` crashed every
`--cron` run. So no data point ever landed: the series sat frozen at 4 identical
entries and the weekly benchmark cron could never prove improvement.

**Fix:** normalize the schema on both ends:

```python
def load_results():
    if BENCH_FILE.exists():
        data = json.loads(BENCH_FILE.read_text(encoding="utf-8"))
        data.setdefault("runs", data.get("history", []))
        return data
    return {"runs": [], "best": {}}

def save_results(results):
    results["history"] = results.get("runs", [])   # keep legacy readers working
    BENCH_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
```

After the fix a real run landed and moved the series: **0.401 → 0.483 → 0.757**.

## Detection checklist

- Is the served core up? `curl :8081/health` — a down core makes the rest moot.
- Read the state file's `updated_at`; a frozen timestamp beats any cron status.
- For each retrain/collect job: print the **resolved path** it reads and whether
  its gate opens. A path/count gate is a common silent killer.
- For any metric: confirm a NEW row appears after a run. A frozen series cannot
  show improvement.

## Wiring a keepalive cron correctly

`cronjob action=create` with a bare schedule string (`"5m"`) produces a
**one-shot** job (`schedule.kind="once"`). For a recurring probe, edit
`cron/jobs.json` for that job id:

```json
{"schedule": {"kind":"cron","expr":"*/5 * * * *","display":"*/5 * * * *"},
 "repeat": {"times": null, "completed": 0}}
```

then confirm with `cronjob action=list`.
