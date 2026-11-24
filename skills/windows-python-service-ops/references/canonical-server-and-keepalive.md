# Canonical :8081 server vs. deprecated squatters — and the keepalive they need

Live 05.10.26. Cost a session: a keepalive was written and pointed at a
**deprecated** server variant whose `/health` looked completely plausible. The
port was up, the JSON was valid, and the core was the WRONG core.

## The three files that can own :8081

| File | Status | What it serves |
|---|---|---|
| `scripts/training/tool_server.py` | **CANONICAL** | 2B model (base derived from the active adapter) + 10 tools, `security_analyzer` gate, smart routing, lazy LoRA hot-swap via a `.swap_request` file, `IDLE_TIMEOUT = 1800` |
| `scripts/training/serve_live.py` | **DEPRECATED** | Qwen3.5-2B + test-time training. Different endpoint set, no security gate. **Do not start.** |
| `scripts/training/serve_mini.py` | **DEPRECATED** | older variant, adapter path typo |

## How to tell which is right WITHOUT guessing

Do not trust a docstring or a `--help`. Two independent, machine-readable
tie-breakers:

1. **The retrain cron's own prompt** names the canonical file explicitly (the
   `mini-openamer-retrain` job says: *"The ONLY canonical :8081 server is
   tool_server.py … DO NOT start serve_mini.py or serve_live.py — they are
   DEPRECATED legacy variants that squat port 8081 with no /health endpoint"*).

2. **The active adapter decides the base model.** `tool_server.py` calls
   `_base_for_adapter()` and loads whatever the adapter was trained on:

   ```bash
   python -c "import json;print(json.load(open('scripts/training/lora_out/adapter/adapter_config.json'))['base_model_name_or_path'])"
   ```

   If a candidate server hardcodes a *different* base than the adapter's, LoRA
   load size-mismatches and crashes at startup (`hidden=960` adapter on a
   `hidden=2048` base). So the adapter is the tie-breaker, not the file's prose.

`GET /tools` is the positive proof of the canonical server: `tool_server.py`
answers `{"status":"alive","tools":10}` and lists
`web_search, pc_action, browser_action, speak, see, read_memory, reason_deep,
run_python, listen, group_state`.

## Mark the losers (so the next session cannot repeat the mistake)

Add an explicit banner to the top docstring of every variant you find:

```python
"""DEPRECATED — do NOT use as the :8081 server.

The CANONICAL Mini-OpenAmer server on :8081 is scripts/training/tool_server.py
(...). This file is an old variant that SQUATS :8081 with a different endpoint
set and breaks the service-watchdog. Kept for reference only.
"""
```

Future-you reads the docstring of the file in front of them, not this skill.

## The idle shutdown needs a keepalive, not just a watchdog

`tool_server.py` self-terminates after 30 min idle (`os._exit(0)` to free RAM) —
a healthy energy design on a CPU-only box. The consequence: **the port goes cold
on its own**, and with nothing to restart it the cognition core is silently dead
while every cron still reports green.

Use the standing keepalive pattern already proven for the A2A server
(`scripts/a2a_keepalive.py`): probe → start if down → **silent while healthy**.

```python
PORT, PROBE_TIMEOUT, READY_WAIT_S = 8081, 3, 90

def _alive() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=PROBE_TIMEOUT):
            return True
    except OSError:
        return False

def main() -> int:
    if _alive():
        return 0                      # healthy: print NOTHING (watchdog pattern)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x00000008  # DETACHED
    subprocess.Popen(
        [_interpreter(), str(SERVER)],            # training venv, see below
        stdin=subprocess.DEVNULL, stdout=log_f, stderr=subprocess.STDOUT,
        creationflags=flags, close_fds=True,
        env={**os.environ, "OPENAMER_HOME": str(HOME)},
    )
    deadline = time.time() + READY_WAIT_S
    while time.time() < deadline:
        if _alive():
            print(f"core was down — started on :{PORT}"); return 0
        time.sleep(3)
    print(f"core did NOT come up on :{PORT} within {READY_WAIT_S}s — see {LOG}")
    return 0
```

Two things it MUST get right, both bit this session:

1. **Spawn with the TRAINING venv** (`$OPENAMER_HOME/venv/Scripts/python.exe`,
   `torch 2.14.0+cpu`), not the agent venv. A cron runs under the agent venv
   (no torch); spawning the server with it dies instantly with
   `ModuleNotFoundError: No module named 'torch'`. Fall back to
   `sys.executable` only if the training venv is missing.
2. **Readiness wait ≥ 90 s.** The 2B model load is slow on CPU; a 12 s probe
   false-positives as "never came up" and the watchdog reports a failure it
   caused itself.

Register as a `no_agent` script cron, `*/5 * * * *`. Reference impl:
`scripts/tool_server_keepalive.py`. Verify end-to-end: kill the listener, run the
keepalive, then `curl -s localhost:8081/health` → `{"status":"alive","tools":10}`.

## Also: `taskkill //F //PID` is rejected under git-bash

The double-slash form errors `Argument/Option ungültig`. Use
`powershell -NoProfile -Command "Stop-Process -Id <pid> -Force"`, or the
single-dash `taskkill /F /PID <pid>`.
