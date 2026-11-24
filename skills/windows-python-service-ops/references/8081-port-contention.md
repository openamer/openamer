# :8081 port contention + shape-gated keepalive (live 13.10.26)

Session-specific detail for the correction in SKILL.md. Context: the recurring
`internet-learner-247` cron reported `rejected, not trained (shallow + deep read
both gated)` and the learner's success rate had fallen to **ok% last-10 = 10 /
last-20 = 10 / last-80 = 24 vs all-time 61 %** (n=3284), with `no insight`
spiking (22 of the last 80 vs 72 all-time).

## Diagnosis order that worked

1. **Rate first, before touching gates.** U/V probes were HEALTHY
   (`_search_urls` → 6,6,6; `_fair_share_window` → 4000; `deep_learn` → 5/8
   True), so the plumbing was fine and the *content* was wrong. No gate class.
2. **Junk-reason census** (`buffer_junk.jsonl` last 100): 77 `duplicate`,
   19 `junk`, 4 `writer-gate` → rotation noise, not a new chrome class.
3. **Then** look at what the search actually returned — the German results were
   the tell.
4. **Step -1 from the learner skill still applies:** `git status --porcelain
   scripts/training tests/scripts` in the repo, to rule out a previous cron
   that died mid-fix (it was clean).

## Who owns :8081 — get the command line, not just the PID

```bash
powershell.exe -NoProfile -Command "\$p=(Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue).OwningProcess; foreach(\$id in \$p){ \$c=Get-CimInstance Win32_Process -Filter \"ProcessId=\$id\"; Write-Output ('PID '+\$id+' :: '+\$c.CommandLine) }"
```

Do this from a script/`-Command` that does **not** contain the strings you are
looking for (self-match, see SKILL.md). Parent chain is what identifies the
supervisor:

```bash
powershell.exe -NoProfile -Command "\$l=Get-CimInstance Win32_Process | Where-Object {\$_.CommandLine -match 'llama-server'}; foreach(\$x in \$l){ 'PID '+\$x.ProcessId+' parent='+\$x.ParentProcessId; (Get-CimInstance Win32_Process -Filter \"ProcessId=\$(\$x.ParentProcessId)\").CommandLine }"
```

Measured result: parent =
`python.exe -m openamer_cli.main --profile default serve --host 127.0.0.1 --port 0`
→ the profile's own `openamer serve`, i.e. **not a stray**.

## Hardened keepalive (`scripts/tool_server_keepalive.py`, laptop-local, NOT in the repo)

The original probe was a bare TCP connect; a squatter satisfies it, so the wrong
server survives forever. Two changes:

1. **Shape-gated liveness** — only the canonical `/health` counts:

```python
CANONICAL_HEALTH_KEY = "tools"   # serve_live/serve_mini/llama-server never send it

def _healthy() -> bool:
    if not _port_open():
        return False
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=PROBE_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        return body.get("status") == "alive" and CANONICAL_HEALTH_KEY in body
    except Exception:
        return False
```

2. **Evict ONLY the deprecated python variants; never fight a foreign core:**

```python
DEPRECATED_SCRIPTS = ("serve_live.py", "serve_mini.py")

def main() -> int:
    if _healthy():
        return 0                     # silent while healthy (keep the contract)
    if _port_open():
        reclaimed = _reclaim()       # kills only serve_live.py / serve_mini.py
        if reclaimed:
            time.sleep(2)
        else:
            owners = ", ".join(f"{p}:{c.split(chr(92))[-1]}" for p, c in _owners())
            print(f"cognition-core-keepalive: :{PORT} busy with a non-canonical "
                  f"listener ({owners or 'unknown'}) — not starting the core")
            return 0                 # do NOT war over a port we do not own
```

Verified E2E: healthy → silent, exit 0; foreign core holding the port → one line,
exit 0, nothing killed; port free → starts the canonical core
(`{"status":"alive","tools":10,"swaps":0}`, `GET /tools` = 10,
`POST /execute_tool` works).

## Cost of NOT doing this (why the "just kill the squatter" advice misleads)

Killing the llama-server freed the port only briefly; the supervisor respawned it
(01:28, 01:33, 01:43, 01:46 …), so ownership flip-flopped and several 4B model
loads ended up resident at once — free RAM fell to ~7.7 GB of 22.3 GB. The port
then sat FREE/unowned while two orphaned `tool_server.py` instances held loaded
models but no socket.

## Second measurement, same day (13.10.26, cron) — stuck duplicate + learner-side signature

A cron `internet_learner.py --once` run hit the same contention from the OTHER
side (this time the learner, not the keepalive):

- **Two `llama-server.exe … --port 8081 --n-gpu-layers 0 --threads 8` alive at
  once**, both from `C:/Users/damir/.emilija/workspace/llama.cpp`, model
  `Qwen3.5-4B-Q4_K_M.gguf`. The **holder**: 3.0–3.1 GB working set, ~650–700 s
  CPU, started 06:46:04. The **duplicate**: 120–152 MB WS, **~8 s CPU after 14
  minutes**, started 06:47:10 → it never finished loading, lost the port race and
  just sits there. Triage by **working set + CPU seconds**, never by PID order or
  creation time alone (same rule as the venv/uv twin pair in SKILL.md).

```bash
powershell.exe -NoProfile -Command "Get-Process -Id <pid1>,<pid2> -ErrorAction SilentlyContinue | Select-Object Id,CPU,@{n='WS_MB';e={[int](\$_.WorkingSet64/1MB)}},StartTime | Format-Table -AutoSize"
```

- **Learner-side failure signature (cheap, log-only):** entries in
  `scripts/training/internet_learn_log.jsonl` collapse from the normal **30–85 s**
  to **6–14 s** with `no insight`, or a truncated raw page sentence where a
  `learn:` should be (06:48:26 docs `no insight` 13.9 s, 06:48:39 competitors
  garbage sentence 6.2 s, 06:48:53 multi-domain `no insight` 13.3 s, 06:54:42
  security `no insight` 9.4 s).
- **Same window, direct probes:** `/health` → `{"status":"ok"}` **instantly**
  (no `tools` key ⇒ foreign core owns the port); `/v1/chat/completions` →
  `HTTP:000` at 20 s, 25 s, 30 s and 120 s. So the model endpoint was
  **saturated/serialized on one CPU slot**, not dead.
- **It self-heals — do not classify on the first timeout.** 13 min later a cycle
  took **40 s** and returned a real gate verdict (`rejected, not trained
  (shallow + deep read both gated)`), i.e. the LLM answered again. Re-probe
  (a real chat completion, ≥30 s timeout, twice) before calling it a stall.
- **The first `curl /health` is already the whole diagnosis**: no `tools` key ⇒
  the canonical `tool_server.py` is NOT up, so the cron's "restart it with the
  training venv if `/health` returns nothing" branch is a **no-op** here —
  `/health` answers, just with the wrong shape.
- **`netstat -ano | grep -i LISTEN` printing nothing is not "port free".** The
  same call showed four `127.0.0.1:8081 → 127.0.0.1:* … WARTEND` lines (German
  `WARTEND` = WAITING): connections mid-teardown toward :8081 are themselves proof
  that a listener exists. Use `Get-NetTCPConnection -LocalPort 8081 -State Listen`
  for the owner instead.

**Verdict for this class: report, don't kill.** Both remedies — killing the
foreign listener, or repointing the learner at another port/endpoint — are
cross-profile interference or a local workaround, and the keepalive deliberately
leaves a foreign non-deprecated core alone. Report the port-split decision to the
user with the evidence (PIDs, WS/CPU, the log timestamps, the probe results)
instead of forcing a winner.

## Residual (needs a human decision — NOT resolved)

`:8081` should be split: `tool_server.py` (Mini-OpenAmer `/execute_tool`) vs the
profile's llama.cpp `/v1` fallback (config.yaml `- base_url:
http://127.0.0.1:8081/v1`). Also, `internet_learner.py`'s browser search path is
structurally dead — Bing's current SERP exposes source *names*, not `https://`
links, so the `host › path` DOM extractor yields 0 and the HTTP fallback is what
actually runs (hence a Bing market pin is what matters:
`&setmkt=en-US&setlang=en&cc=US`; A/B proof in the learner skill's
`references/root-causes-archive.md`, class 165 — that skill is user-owned, do not
edit it from a curator session).
