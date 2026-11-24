# Adding a tool to the OpenAmer tool server (`:8081`)

Live 21.09.26. Adding a 10th tool (`group_state`) that exposes a trained
group-state tracker over HTTP. Everything below was measured, not assumed.

## The three edits

A handler must appear in **both** `TOOLS` and `EXECUTORS`. Registering only in
`TOOLS` makes the model *see* the tool while `/execute_tool` answers HTTP 400
`unknown tool` — a confusing split.

```python
# 1. TOOLS — the schema the 2B core is shown
TOOLS = [
    # ... existing 9 ...
    {"name": "group_state",
     "desc": "Exact composed state over a long sequence of group operations. "
             "Use when state must be tracked perfectly across many steps.",
     "params": {"group": "S5|S6|A5|D12|Z10",
                "moves": "list of generator indices"}},
]

# 2. EXECUTORS — the dispatch dict
EXECUTORS = {
    # ... existing 9 ...
    "listen": t_listen, "group_state": t_group_state,
}

# 3. the handler
def t_group_state(params):
    ...
```

## Handler design rules (both learned the hard way)

### Never do unbounded work inside a request

The first version trained a model on demand when no artifact existed. For one
group that is **~161 s**. The HTTP client timed out and the symptom was
indistinguishable from a hang — the caller sees nothing, the server is fine.

Correct shape: **load** a persisted artifact; if it is missing, return an error
naming the fix:

```python
p = model_path(name)
if not os.path.exists(p):
    return {"error": f"no trained model for {name}",
            "fix": f"python scripts/<engine>.py --train {name}",
            "note": "training on demand would exceed the request timeout"}
```

Guard with a test asserting the refusal returns in < 2 s (so the trap cannot
come back).

### Measure your own share of the latency

| component | measured |
|---|---|
| handler's actual computation | **0.22 ms** |
| full HTTP round trip | **~2050 ms** |

~10,000x. The overhead is the server's own per-request work (2B-model status,
security analyzer) and **every tool pays it** — `see` and `run_python` included.
Do not report this as your tool being slow; do report it, so a future reader
does not misattribute it.

## Restarting so the change is live

A running server keeps the code it loaded. The proof your edit landed is the
**tool count**, not liveness:

```bash
curl -s localhost:8081/health          # {"status":"alive","tools":9,"swaps":N}
curl -s localhost:8081/tools | python -c "import sys,json;print(len(json.load(sys.stdin).get('tools',[])))"
```

`tools: 9` → `tools: 10` and `GET /tools` length 10. Then a real
`POST /execute_tool` to confirm behaviour.

### Let the watchdog do the restart

`OpenAmer Laptop Stack Watchdog` is a scheduled task on a **one-minute**
repetition:

```bash
schtasks /query /tn "OpenAmer Laptop Stack Watchdog" /fo LIST /v
#   Status: Bereit | Letztes Ergebnis: 0 | Zeitplantyp: Einmal, Minute
```

Kill the listener and wait. Observed twice: **65 s** (and once 85 s) until
`/health` answered with the new tool count — no manual start required.

Finding the listener PID without MSYS/UTF-16 pain (run the netstat parse from
Python; `netstat` output is UTF-16 and `grep` sees it as binary):

```python
import subprocess
r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                   encoding="cp850", errors="replace")
pids = {l.split()[-1] for l in r.stdout.splitlines()
        if ":8081" in l and ("LISTEN" in l.upper() or "ABH" in l.upper())}
for pid in pids:
    subprocess.run(["taskkill", "/PID", pid, "/F"])
```

Then poll `/health` in a 5 s loop for up to ~2 min.

**Prefer this over starting a second instance by hand** — the watchdog already
owns that job, and a manual start can race it for the port (see the
port-hijack / duplicate-instance sections in the parent skill).

## Error shapes worth copying

A tool that returns a *useful* refusal is far easier to debug than one that
returns a generic failure. The bounds are read from the loaded object, never
assumed:

```python
VALID = f"0..{g.num_gens - 1}"
bad = [k for k in moves if not (0 <= k < g.num_gens)]
if bad:
    return {"error": f"move index out of range: {bad}",
            "group": name, "valid_indices": VALID,
            "note": f"{name} has {g.num_gens} generator(s)"}
```

Live proof that this matters: a test sent index `2` to a group that has exactly
**2** generators (valid indices 0–1). The tool rejected it correctly, and the
test mis-flagged the *correct rejection* as a failure. **Read bounds from the
object; do not encode them in tests either.**

## Conventions in this file

- **Function-local imports are the house style.** 13 other handlers import
  optional deps inside the function body (`from longterm_memory import query`,
  `from reasoning_loop import recursive_ask`, `import websocket`). A lazy import
  for a heavy or optional module follows convention and keeps server start-up
  unchanged. Do not "fix" it into a module-level import.
- Keep gate names under the column width used by the runner's `stage()` helper,
  or the name runs into `PASS` (`...grads (6 groups)PASS`). Centralise the width
  in one variable if the runner pads with `printf`.

## DRY in the persisted-artifact schema

A format tag written by `save()` and asserted by `load()` must be ONE constant —
otherwise the two drift and every old artifact becomes unreadable (or worse,
silently acceptable):

```python
FORMAT = "openamer-group-state-v1"   # written by save(), asserted by load()
```

Repeat JSON *schema keys* (`"param_shapes"`, `"num_generators"`) are fine as
literals — turning them into constants is noise, not DRY.
