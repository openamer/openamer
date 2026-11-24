---
name: autonomous-learning-architecture
description: Use for Mini-OpenAmer learning loops and GPU worker work.
---

# Autonomous Learning Architecture (Mini-OpenAmer ASI-Pfad)

Class-level patterns for Damir's self-improving agent architecture on local hardware
(Qwen3.5-2B, RTX 3060 Ti worker, 0 € running cost, <1 kWh/day). Component detail lives
in the user-owned `mini-openamer` skill (not curator-managed).

## Die 4 Evolutions-Stufen (the core design)
1. **Fähigkeiten** — `darwin_engine.py --autopilot`, 15-min cron, mutation+crossover top-2
2. **Werkzeuge** — 9 tools on :8081, Smart Router (complex→free cloud, simple→local)
3. **Self-code** — `self_improve.py` 30-min: analyze → sandbox → live only if green → rollback
4. **Meta-learning** — `meta_learn.py`: dynamic LR (bandit), replay-vs-fresh by avg_drop
   KTA `knowledge_to_action.py`: keyword-first, rr-fallback; log `kta_log.jsonl`.
   `no usable insight`=exit 0, no log. Verify `scripts/kta_cycle_probe.py` (stdout≠proof).
   Pitfalls + matrix + lexicon-gap fix for `competitor_gap` "signal NOT mappable"
   (3-copy sync): `references/kta-cycle-verification.md` — now opens with the trap
   that OUTRANKS the lexicon fix: verify the input row is real prose first, since
   buffered chrome reports the same message.

## Lern-Loops (24/7 daemons + crons)
- `online_learning.py --loop`: 5-min cycle, 3 mini-steps, replay cap 300, hot-swap every 6 cycles
- `active_learn.py`: */7-min cron, 8 rotating self-driven actions (see `references/active-learn-actions-observed.md` for per-action timing and chat() dependency matrix)
- `internet_learner.py`: 5-min cron, **8 internet sources** (tech news / arxiv / GitHub trending / docs / competitors / multi-domain / **security** (prompt-injection, guardrails, jailbreak prevention) / **efficiency** (energy, quantization, edge AI)). Intensified live 08.09 (was 10-min/6-sources) on the user's "lerne weiter 24/7 extra intensiv" mandate.
- `dream_cycle.py` (03:30): replay day, nightmare motifs → 3x weighting in next SFT
- `auto_retrain.py` (04:00): GPU batch when enough new data
- `session_outcome.py` (hourly): failure-pattern analysis of all cron jobs → playbooks → world model (see "Session outcome analysis" section)

## Critical pitfalls (hard-won, verified)

- **serve_mini.py hat KEIN `/health`-Endpoint, nur `serve_live.py` (live 13.09.26)**: Der Legacy-Server (`serve_mini.py`) akzeptiert ausschließlich `POST /v1/chat/completions`. `GET /health` gibt es dort nicht — ein Health-Check per `curl http://localhost:8081/health` timeouted IMMER, das ist kein Server-Down sondern ein fehlender Endpoint. Der Delfin-Server (`serve_live.py`) hat dagegen `/health` mit uptime + swap-count. Korrekter Liveness-Check für den Mini-Server: `curl -s --max-time 30 -X POST http://localhost:8081/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":5}'`. Antwortet gültiges JSON → läuft. **Startup-Zeit auf CPU**: ~2.5 min (Qwen3.5-2B laden). Der Process-Table-Status zeigt `running`, aber Port :8081 ist erst nach `MODEL_READY`-Log belegt. First-Call-Probe braucht `--max-time 180`; Kurzprobe <30s schlägt falsch fehl. **Launch-Pfad**: `venv/Scripts/python.exe` (torch/transformers/peft nur im Training-Venv). Das `mini-openamer`-Skill (user-owned) dokumentiert beide Server; der Health-Check in diesem Skill muss je nach aktivem Server unterscheiden.

- **LoRA config match**: rolling + batch adapters must have IDENTICAL r/targets (r=16, 4 modules). Mismatch = swap crash (`size mismatch for lora_A.weight`).
- **Laptop = CPU-only torch**: never `.cuda()` in laptop-side code (AssertionError). PC has CUDA torch; keep versions separate.
- **GPU OOM on 8GB**: use fp16 + `gradient_checkpointing_enable()` + batch=1 + grad_accum=4 + maxlen=512 + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- **Windows OpenSSH keys**: admin users need `C:/ProgramData/ssh/administrators_authorized_keys` + `icacls` fix + sshd restart — NOT `~/.ssh/authorized_keys`.
- **Remote process persistence via SSH**: use `powershell Start-Process -WindowStyle Hidden`; `start /b` dies with the SSH session.
- **GPU worker network latency**: live inference over LAN is SLOWER than local CPU (52s vs 5s). PC = training only, not live inference.
- **web_search CDP**: `websocket.create_connection(..., suppress_origin=True)` or Chrome rejects with 403. Full chain when it silently returns nothing (live 06.09): (1) `websocket-client` must be installed in the interpreter actually serving :8081 (uv base python needs `--break-system-packages`), (2) CDP-Chrome on :9222 must be running (`--remote-debugging-port=9222` — dead after every restart), (3) suppress_origin. Verify with a real `execute_tool web_search`, not just `/health` — health stays green while search is broken. Also beware dual tool_server instances (venv + uv-base) racing for :8081: kill ALL, restart ONE.
- **Port 8081 hijack by other local servers (live 06.09)**: `llama-server.exe` (Emilija workspace, llama.cpp) silently took :8081. Symptom: `/health` still responds (with the WRONG server) but `/execute_tool` returns an OpenAI-style `404 not_found_error` and every `internet_learner.py` cycle prints "no results". `/health` alone proves nothing — always verify with a real `POST /execute_tool web_search`. Check the true owner: `powershell "Get-NetTCPConnection -LocalPort 8081 -State Listen | Select -ExpandProperty OwningProcess"` → `Get-Process -Id <pid>`. Non-destructive fix (don't kill the user's other project): start a fresh instance on a free port (`TOOL_SERVER_PORT=8083`) and point clients at it with `TOOL_SERVER_URL=http://localhost:8083` — `internet_learner.py` and `tool_server.py` both honor these env vars. Doing this repeatedly = should be pinned permanently (env-var override or fixed port).
- **Search-result parsing**: format `Title :: snippet || ...` — extract titles directly, don't route through an LLM (2B/nemotron produce template artifacts: `<sentence>`, "Here's a thinking process:").
- **Regex \b corruption in heredoc-written Python**: `\b` in raw strings becomes `\x08` when written via `python -c "..."` heredocs. Use `chr(92)+'b'` or full-file `write_file`.
- **free-model quirks**: `thinkingmachines/inkling:free` → 403; nemotron free models emit reasoning preambles that must be skipped when parsing.
- **Cron exit codes**: a monitor script exiting 1 on threshold-breach marks the cron job as erroring — wrapper should exit 0 and keep alert data in stdout.
- **Sprach-Regel (user, firm)**: Chat = always German; every produced file (reports, posts, commits, skills, HTML, code comments) = English.
- **`tool_server.py` architecture changed 18.10.26 — the 2B model is NO LONGER loaded in-process.** The server is now a pure orchestrator: it imports `from gguf_backend import chat as gguf_chat` and forwards `/v1/chat/completions` to `llama-server` on **:18080** (`gguf_backend.py`, `mini-openamer-2b-q4.gguf`, Q4_K_M, 1.2 GB). The old in-process path (`AutoTokenizer` + `AutoModelForCausalLM` + `PeftModel` from `Qwen/Qwen3.5-2B` + `lora_out/adapter`) loaded **SmolLM2-360M** (the adapter's training base per `adapter_config.json`), not Qwen3.5-2B, and crashed the server on every start. **This invalidates every pitfall below that assumes the model lives in the :8081 process** — in particular the "2B CPU inference >60s" and "model lock starvation" entries, and the "restart-ts capped at 60s because tool_server loads the 2B before binding :8081" claim. Measured 18.10: tool_server starts in **~10 s** (no model load), a tool-decision chat completes in **~6.7 s** at 28–30 tok/s, and `/admin/swap` is now a **no-op** (no in-process PEFT model to swap) that still answers 200 so cron steps don't break.
  - **`enable_thinking=False` is mandatory on the GGUF path.** Qwen3.5-2B-Base is a BASE model, not an Instruct model. With thinking enabled it generates reasoning tokens but **never emits content** (`finish_reason: "length"`, `content: ""`). `gguf_backend.chat()` already sends `chat_template_kwargs: {"enable_thinking": False}`; do not override it.
  - **Liveness proof for :8081 is still the `tools` key** in `/health` (`{"status":"alive","tools":9,"swaps":0}`) — but the inference path is now :18080, so verify the backend too: `GET http://localhost:18080/health` → `{"status":"ok"}`. If :18080 is down, every `/v1/chat/completions` on :8081 returns a 503 with `gguf backend: <error>`.
  - **Full migration write-up + the `NameError: ADAPTER` pitfall:** `references/tool-server-gguf-migration.md`.

- **Invocation arg parsing `--once` vs `once` across training scripts (live 07.09, rediscovered on internet_learner)**: Both `active_learn.py` and `internet_learner.py` originally checked `sys.argv[1] == "once"`, which fails when cron passes `--once` (the argument has a leading dash). `internet_learner.py` was fixed 07.09 with `sys.argv[1].lstrip("-")` — the canonical pattern for ALL `scripts/training/*.py` scripts accepting `once`/`loop` or `--once`/`--loop`. Never use `== "once"`; always `.lstrip("-")` the argument before comparing. Same fix for `--loop` vs `loop`. **Verification**: `python script.py --once` must run one cycle, not all; `python script.py` (no args) must run the else/test branch.

- **Invocation modes on `active_learn.py` (live 07.09 — the script's three modes)**: (1) NO args — triggers the `else` branch (line 239), runs ALL 5 actions sequentially, up to 5×60s+ = 300s+ on CPU; this is a test/debug mode, NOT for cron. (2) `once` — runs exactly ONE rotation action via `run_one()`; completes in ~10s when the action doesn't need `chat()`. This is the correct cron invocation. (3) `loop` — runs forever at 600s interval. The cron command `python active_learn.py` (no args) triggers the `else` branch and always times out at the default 120s terminal timeout. Fix: always use `python active_learn.py once` for cron schedules.

- **`self_improve.py` prints NOTHING on `no-proposal` (live 09.09 — cron run)**: exit code 0, stdout empty. The `improve_once()` function only calls `print(f"[self-improve] ...")` inside the `for proposal in proposals:` loop — if `proposals` is empty (the common case for an already-optimal target), the function returns at line 129 with zero output. For cron monitoring this means: green exit but no way to tell it actually ran vs didn't start. Fix: always print at least `[self-improve] no-proposal: <target>` before returning from the `no-proposal` branch. The log entry is written to `improvements.jsonl` either way, so cron-check can `tail -1 improvements.jsonl` as a workaround. **FIX LANDED — verified live 11.09 (growth cron)**: the script now prints `[self-improve] no-proposal: <file> — already optimal or no safe pattern` with exit 0, so cron stdout alone distinguishes ran-but-no-proposal from didn't-start. For terminal-outage crons capture stdout anyway via `*>><log>` + `"EXIT:$LASTEXITCODE"` append (see `windows-computer-use` `references/shared-terminal-cron-internet-learn.md` §6).
- **`self_improve.py` fallback path: `"openamer"` instead of `"openamer-laptop"` in `OPENAMER_HOME` default (line 20)**: `str(Path.home() / "AppData" / "Local" / "openamer")` — note `openamer`, not `openamer-laptop`. When `OPENAMER_HOME` is NOT set (e.g. fresh install, different launch context), the fallback resolves to a non-existent directory, and `improve_once()` silently skips targets because none of the `SAFE_TARGETS` files are found under the wrong base. This is a latent bug waiting for an env-var-less execution path. Fix: change the fallback to `... / "openamer-laptop"` to match the real install path.
- **Model lock starvation on tool_server — orphaned `model.generate()` blocks all future requests (live 07.09, rediscovered)**: `tool_server.py` uses a `threading.Lock` around `model.generate()` (line 385-386). If a client disconnects mid-generation (timeout or crash), the model thread keeps running with the lock held but no one reads the output. Every subsequent `/v1/chat/completions` request **blocks forever** waiting for the lock. **Diagnostic ladder (never stop at health green):** (1) `/health` returns `alive` — HTTP server threadpool is separate from the model lock. (2) `POST /execute_tool` works fine — no model lock needed. (3) `curl -X POST /v1/chat/completions` returns empty body (exit 0, no JSON) or hangs — confirms lock held. (4) `tasklist /V` shows the tool_server python PID with **3.5-3.9 GB RAM** (expected: ~2.5 GB) and **>2h CPU time** (expected: minutes after restart) — classic lock starvation signature. **Fix ladder**: (1) `taskkill /F /PID <hung_PID>`. (2) Restart via `terminal(background=true): python "C:/.../tool_server.py"`. (3) Wait 15-20s for `MODEL_READY` + `TOOL_SERVER_READY` logs. (4) Verify: `/health` alive, then `curl -X POST /v1/chat/completions` with a simple prompt returns actual content. **Probe-timeout caveat (live 09.09.26)**: the verification probe needs `--max-time 30` minimum (60 for the FIRST call on a fresh instance). A 10s probe false-positives a hang on CPU (cold 2B inference alone can take 30–60s) → needless kill+restart. Do NOT kill a fresh instance on a short-probe timeout alone; retry once with a longer probe first — lock starvation is only conclusive on an instance that has previously served requests and suffered a client disconnect. **Note**: once the lock was cleared and the model freshly loaded, `active_learn.py` completed all 5 actions in ~4s — proving the earlier 120s+ timeouts were PRIMARILY lock starvation, not pure inference slowness. **Root cause fix needed**: add a timeout wrapper around `model.generate()` (e.g. `lock.acquire(timeout=30)`) so a stuck generation releases the lock after 30s instead of blocking indefinitely. Without this, the server has an unbounded failure window after any client-side timeout.

## The closed learning loop (insight → ACTION → skill)

Stages 1–4 above cover learning; three more components close the loop so insights don't rot in the buffer:

- **`knowledge_to_action.py`** (30-min cron): picks the latest buffer insight, maps keywords → one of 5 concrete experiments (LoRA baseline, world-model PREDICTION edges, buffer tuning, competitor gap analysis, meta-RL exploration boost), RUNS it, logs `kta_log.jsonl`. Round-robin via `.kta_rotation` file (otherwise the same "latest insight" triggers the same experiment every time).
  **State observation (live 10.09, re-measured 12.09)**: see `references/kta-cycle-observed-behavior.md` for the stagnation analysis — 4 of 5 experiments are currently static/hardcoded and only `experiment_predict_world` produces new state. The KTA loop is a scaffolding placeholder; real closed-loop experiments need GPU capacity and adaptive insight parsing.
  **Lexicon-gap misreported as an upstream defect (found + fixed live 12.09.26)**: `experiment_competitor_gap` printed `signal NOT mappable: 'Kiro helps developers and teams do their best work' … upstream competitor pipeline produces junk`. The quote was truncated at a *value proposition*, not the capability text — the full snippet ("turn prompts into executable specs, validate code correctness to find bugs unit tests miss, build across large codebases with parallel agents") is a **real capability description**. The `hints` lexicon simply had no token for any of it, so a miss on OUR side was reported as a defect in the upstream producer. **Rule: a claim about someone else's pipeline needs evidence about someone else's pipeline** — "our lexicon has no token" is not that evidence. Fix: grew `hints` with the tokens the live signal actually carries (`parallel agent`, `spec-driven`, `executable spec`, `unit test`, `validate code`, `code correctness`) and reworded the unmappable branch to name the real cause + fix ("grow the capability lexicon"), and **verified in-place**: the same buffer signal now yields `identified_gap: 'parallel multi-agent execution'`, `measurable: true`. When you add a lexicon token, add a REGRESSION test using the verbatim live snippet (`test_real_capability_snippet_maps_instead_of_being_called_junk`) — an honesty branch that is only exercised by a "non-answer" fixture will happily keep blaming upstream. 111 tests green.
  **The `cp` trap is real and I walked into it (live 12.09.26)**: the SoT rule above says "never copy AppData → repo", and I still ran `cp <appdata>/knowledge_to_action.py <repo>/…` after patching the AppData copy. It was harmless *only* because that one file happens to carry the identical `OPENAMER_HOME` header (verified by `grep OPENAMER_HOME` + a hardcoded-path grep returning none) — the next file would not be so lucky, and a blind `cp` reverts the repo's portability convention silently. Correct order: **patch the REPO file first, then `cp` repo → AppData** (running copy). Always finish with `grep -n "C:/Users/damir" <repo-file>` == empty. Also note the two trees are NOT mirrors: some training `test_*.py` files exist only in the repo (`test_competitor_gap.py` was missing from AppData) — a repo→AppData sync is additive, never assume a `cp` loop covered everything.
  **Verifying a cycle ran (live 12.09 — don't count log lines)**: read `.kta_rotation` BEFORE the run, predict the experiment from `n % 5` (0 lora, 1 predict_world, 2 tune_buffer, 3 competitor_gap, 4 meta_insight — verified against two live cycles), then `tail -1 kta_log.jsonl` and assert the `experiment` field matches. Rotation increments BEFORE the try/except, so rotation = attempts while the log = results; an error is swallowed into `result` (`error: …`) and still prints a normal-looking line. Two traps: the `EXPERIMENTS` keyword→function list is **dead code** (selection ignores the insight text entirely and is pure rotation by index), and `meta_lesson` rows added by `experiment_meta_insight` carry **no `ts` field** — never assert "log grew by exactly 1" or key a consumer on `ts` alone. Full recipe + the predict_world dedupe-amplification mechanism in the reference file. **Re-confirmed live 16.09.26** (rotation 1 → `experiment_predict_world`, log tail matched): the recipe above is reliable as written — one run, one JSONL line, `exit_code 0`. Note the log lives at `<OPENAMER_HOME>/scripts/training/kta_log.jsonl` (710 entries live), **not** under `memory/` — `ls memory/ | grep kta` finding nothing proves nothing.
  **`predict_world` happily predicts FROM a stale system-error fact (live 16.09.26)**: the newest observed fact was `System error: brain-collect: cannot import name 'reset_delay_from_message' …` with `dup_count: 3`, so the cycle emitted `If '…' recurs, expect Needs investigation and root-cause fix`. The 12.09 honesty fix (predict from the newest FACT, never from a previous prediction) works — but a *healed* error class that nothing re-observes stays the newest fact and keeps getting re-wrapped, while `dup_count` climbs on the same edge. Consequence: when you audit the world model, a `kind: fact` system-error edge with a rising `dup_count` is a **stale-fact signal, not a live incident** — always disprove it against the current log before acting on it (see `cron-fleet-health` → `references/stale-last-error-verification.md`). Candidate fix (not yet built): have `observe()` stop re-adding a system-error fact whose cause has had 0 occurrences in the last N cycles, or let `predict_world` skip facts already carrying a prediction *and* a stale error signature.
- **Verifying the internet learner's cycle — ground truth, not self-reports (live 12.09.26)**:
  each cycle appends one JSONL line `{ts, source, result, elapsed_s}` to
  `<OPENAMER_HOME>/scripts/training/internet_learn_log.jsonl` (~905 lines live). Read the
  tail via file:// navigation — in the same session `read_file` returned "File not found"
  for the byte-identical path (wrong-FS VM), so file:// is the reliable reader in cron.
  Cross-check `cron/jobs.json`: `internet-learner-247` shows `completed` (cumulative run
  count), `last_run_at`, `last_status` — the fleet-level proof the rotation is alive.
  **Diagnostic trap: "cycle ok" does NOT imply :8081 is up.** `search()` wraps
  `:8081/execute_tool` in a bare try/except returning `""`, while the real sources
  (arXiv/HN/GitHub/docs) are fetched directly over HTTP — cycles complete in ~10 s with
  the tool server dead; only the search-tool route silently degrades. Never infer
  :8081 health from learner success; the dedicated watchdog separates them (mini-openamer
  down: "no answer after 90s" — 90s already being the model-load grace period, so that
  signature means a startup crash, not slowness).
  **Second ground-truth axis: capture QUALITY (live 12.09.26, cron via :8900 webhook)** —
  a green `run-script ... OK` + `success:true` proves the script RAN, not that it LEARNED.
  The captured `result` text can be an error page (live: GitHub returned "You switched
  accounts on another tab or window." — an auth-error page, not trending content; also
  seen: "no insight"). Remedy: fire the webhook ONE more time — the a→h rotation advances
  to the next source and the retry usually captures real content (verified: cycle_c_github
  garbage → cycle_d_docs real capture, both persisted in the log). Garbage captures still
  feed the buffer/skill pipeline, so judge the capture TEXT, not just the log append.
  **Cron exec-path facts when terminal is dead (live 12.09.26)**: `browser_navigate
  http://localhost:8900/` renders plain JSON (`{"error": "Not found"}`) = brick-safe anchor
  (no SPA JS, no prompt()) — use it instead of :8901/api/status, which bricks. In-page
  fetch() to :8900 can fail repeatedly ("Failed to fetch") while GET NAVIGATION still
  works: read the full action log via `browser_navigate http://localhost:8900/state`
  (events/actions/errors arrays as plain JSON). Two awaited POSTs in one IIFE blow the
  ~30 s transport cap, but the server side still executes — poll `window.__x` afterwards.
  restart-ts spawns are capped at 60 s ("Action timed out after 60s") because
  tool_server.py loads the 2B model BEFORE binding :8081; on 12.09 SIX spawns fired across
  the day and none ever bound :8081 (still `ERR_CONNECTION_REFUSED` 7 min after spawn) —
  the spawn path reliably starts a model-load process that dies (likely RAM race with
  online_learning on 22 GB). Fire AT MOST one restart-ts per run, wait-and-probe ≤7 min,
  then report honestly; never re-spawn per retry. **One-call exec+proof (re-verified live
  12.09 ~15:44, cron)**: POST /webhook/internet-learn returns `matched_rules:1` +
  `success:true` + result/elapsed snippet IN THE RESPONSE BODY — no GET /state round-trip;
  the snippet is truncated, so verify the FULL learned content by navigating
  `internet_learn_log.jsonl` + `online_buffer.jsonl` (file:// + innerText tail, zero exec).
  Bridge-cap nuance: a restart-ts fetch can abort client-side at ~30 s ("Command timed
  out") while the server action keeps running — poll with 22-25 s sleeps + 5-8 s-abort
  /health fetches; instant `Failed to fetch` = refused, `TimeoutError` = accepted-but-busy.
  Full recipe: `references/internet-learn-cron-exec-path.md`.
- **Run training scripts from the training dir, or export `OPENAMER_HOME` first (live 12.09)**: every `scripts/training/*.py` resolves its data dir as `OPENAMER_HOME` **from the environment**, with a `Path.home()/AppData/Local/openamer` fallback. An inherited shell has it set (verified: `OPENAMER_HOME=C:\Users\damir\AppData\Local\openamer-laptop`), but the *literal* path still has to be written exactly as `AppData/Local/openamer-laptop` — a wrong-cased or abbreviated path silently resolves to the fallback and the script writes its state/logs to a **different directory while exit code 0 and stdout look completely normal**. Symptom seen live: `.kta_rotation` stuck and `kta_log.jsonl` apparently unappended (the writes went to a stale `AppData/Local/*.jsonl`-shaped dir). Cheap deterministic fix for any training-script run: `cd <OPENAMER_HOME>/scripts/training && env -u PYTHONPATH <python> <script>.py` — cwd-relative resolution removes the whole class of mistake. When state looks frozen, `find <HOME> -maxdepth 6 -name "<statefile>"` for a second copy before concluding the script is broken.
- **`self_model.py`** (hourly cron): gathers live metrics (darwin events, buffer, world-model edges, KTA cycles, dynamic LR) into a persistent identity doc (`memory/self_model/identity.md`). Hash-compare marks it `evolved` vs `stable`; every version archived in `identity_history.jsonl` = proof of identity drift. This is functional selfhood (self-observation, persistence, goal-generation), NOT consciousness — keep the honest boundary in the doc itself.
- **`auto_skill_creation.py`** (30-min cron): converts KTA results + internet insights into NEW draft skills under `skills/auto-generated/` (SKILL.md from template, `status: draft`). Darwin picks drafts up as fresh genetic material; promotion only via arena wins. Full observed behaviour, the "0 new skills" decision table, and the in-process replay diagnostic: `references/auto-skill-creation-observed-behavior.md`.
  **The dedupe guard is the skill NAME, not the description (corrected live 16.09.26).** The old note here ("dedupe by description[:50] — second run must yield 0 new skills") is WRONG on both halves. `dedupe_check()` returns True if `os.path.isdir(AUTO_SKILLS/<name>)` OR any registry entry has the same `name` OR the same `description[:50]`; the docstring is explicit that **name-match is the primary guard** because the same insight question always slugifies to the same name while the answer TEXT drifts run-to-run — a description-only check once let every run re-create and overwrite a known skill (live 11.09: 195 registry entries across just 33 unique names). So: "second run yields 0" is not the success criterion, and a 0 is not automatically good news.
  **A `Total: 0 new skills created` is ambiguous — three different causes, only one benign.** Read the cause before reporting, using the decision table + replay diagnostic in the reference. Causes seen live: (a) genuinely exhausted — every candidate slug already exists (benign); (b) **race with `internet_learner`** — both crons fire at minute `:30`, so the insight can land in `kta_log.jsonl` *after* auto-skill already read it, giving a legitimate 0 followed by a 1 on immediate re-run (verified live 16.09.26: first run 0, second run created `auto-security-learning-how-are` from the `01:30:47` insight). Nothing is lost — the scan window is the **last 10 kta lines** (and last 30 buffer lines), so a late insight is picked up next tick or on re-run. **Never "fix" the race, and never report the 0 as a failure**; (c) filter stall — an unconverted candidate exists because a filter in front of it refuses (buffer keyword gate, readability gate). Distinguish (a)/(b) from (c) by replaying the script's own predicates over the same tail windows (see reference) — per-line reject reasons, not a guess.
  **`OPENAMER_HOME` fallback is the same wrong-default bug as `self_improve.py`** (`.../AppData/Local/openamer`, missing `-laptop`), but here it is *contained*: the `isdir(T)` guard at the top exits 2 with `[auto-skill] ABORT: … refusing to write into a throwaway env`. Consequence: with the env var unset this script fails loudly (correct) instead of writing into a throwaway tree — so an `ABORT` means "OPENAMER_HOME not set in this shell", not a broken script. Check `echo $OPENAMER_HOME` before diagnosing anything else.

The full cycle is now: **internet → insight → experiment → new skill → Darwin → arena → better**. No stage ends at "collected" — every insight must land in an action or a skill, or it's hoarding, not learning.

## Memory consolidation (the missing sleep phase — live 06.09)

The memory scripts each covered a slice but left the core gap open: `longterm_memory.py` stores episodes (grows forever, 49MB+), `memory_hierarchy.py` CLASSIFIES into tiers but never compresses, `forgetting_curve.py` only touches the small `MEMORY.md`, `dream_cycle.py` replays sessions (REM) but doesn't consolidate. Nothing verdichtet the episodic store. Fix: `scripts/training/memory_consolidation.py` — nightly deep-sleep consolidation, wired into `dream_cron.py` to run AFTER the dream cycle (REM replays, then deep sleep consolidates — same order as human sleep):

1. **SCORE** every episode: usefulness (retrievals / led_to_fix from `meta_state.json` `memory_usefulness`) × recency (age in days).
2. **PROMOTE** high-usefulness (`fixes>0 or retrievals>=3`) → `tier=permanent`, never touched.
3. **COMPRESS** old (`>=30d`) + zero-retrieval → one-line summary via `_summarize()` (regex first-sentence, strips `[System note:...]` noise — NO LLM call, cheap + deterministic).
4. **ARCHIVE** originals to `memory/compressed_episodes.jsonl` (append, NEVER delete) + keep a slim `kind=compressed` pointer in the active store so recall still finds the topic.
5. **BOUND** the active store under `MAX_ACTIVE_EPISODES` (8000) so recall stays fast/cheap.

Key invariants (test-guarded in `test_memory_consolidation.py`): never-delete (archive, don't drop), recent episodes never compressed, useful episodes never compressed, system-noise stripped from summaries. **Honest-statistics pitfall**: the result dict must report `kept_after = permanent + active`, NOT just `active` — otherwise a promotion-only run prints a misleading "N → 0" (the permanent episode is still there). Caught and fixed live; the test asserts `kept_after`. Note the real store showed `0 compressed` on first dry-run because all 3012 episodes were only 5 days old (born 01.09) — the 30-day threshold hadn't been reached yet; that's correct behavior, not a bug. Test with artificially-aged episodes in a TEMP store (monkeypatch `mc.EPISODES`/`mc.ARCHIVE`/`mc.META_STATE` to a `tempfile.mkdtemp()`), never against the real 49MB store.

### Shared JSONL stores break on foreign-schema records — load defensively (live 12.09.26)

`longterm_episodes.jsonl` is a **shared append target**: other crons have written
records with a completely different schema into it (observed: a Discord-blocker
event `{timestamp, type, summary, action_needed}` — no `text`, no `embedding`).
`longterm_memory.py`'s `_load()` returned every parsed dict, so `index_brain()`'s
dedupe line `have = {e["text"][:200] for e in eps}` raised `KeyError: 'text'` and
the `index` cron died with exit 1.

The durable rule for any store you don't exclusively own: **`_load()` filters by
required keys, callers never index blindly.**

```python
if isinstance(e, dict) and "text" in e and "embedding" in e:
    out.append(e)
```
and `have = {e.get("text", "")[:200] for e in eps}`.

Repair procedure (never delete — quarantine + back up + harden), the real
traceback, and the regression test that proves the fix are in
`references/longterm-store-foreign-record-repair.md`. Audit any store for
foreign/partial records with the re-runnable `scripts/check_store_schema.py
[store.jsonl]`.

**Read the exit value honestly: `indexed: N` prints the TOTAL episode count, not
what was added** — a run that adds nothing looks identical to a full run. Confirm
real progress by comparing the store's line count / the source file's mtime, not
by the printed number.

**Verifying a script that has no test harness (do this instead of asserting
"not applicable"):** grep the repo `tests/` tree for the module name — 0 hits
means no unit suite exists, so the correct evidence is (a) `py_compile`, (b) a
linter diff **against the pre-edit version** (run ruff on the backup/`git show`
copy too — pre-existing E401/E741 are NOT yours to fix or to count),
(c) a real functional call (`index` / `stats` / `query`), and (d) a targeted
regression: inject the exact bad record into a COPY of the store, assert no
crash, then restore the byte-identical original. Say plainly that the
harness-suggested command (`npm run test`) has no such script here — run it and
quote the real `Missing script: "test"` output rather than just claiming it
doesn't apply.

## Syncing training fixes into the repo (SoT) — live 06.09

The training scripts live in TWO places: `AppData/Local/openamer-laptop/scripts/training/` (the RUNNING copy, NOT a git repo) and `C:/Users/damir/openamer-repo/scripts/training/` (the git Source of Truth, remote `github.com/openamer/openamer`). They drift. Correct workflow when you fix a training script:

1. **The repo is SoT — port fixes INTO the repo, never copy AppData → repo.** The repo may be NEWER than the AppData copy (a fresh commit can have replaced hardcoded paths with `OPENAMER_HOME`). Blindly copying AppData files over the repo would REVERT that improvement. Always `diff` first to see which side is ahead.
2. **Honor the `OPENAMER_HOME` convention.** The repo uses `os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer"))` everywhere; the AppData copy still has hardcoded `C:/Users/damir/...` paths. When porting a fix, rewrite paths to the `OPENAMER_HOME` form. **NEVER `cp` the AppData file over the repo file** — the AppData copy has hardcoded paths, so a blind `cp` silently reverts the repo's `OPENAMER_HOME` convention (this happened live 06.09: I `cp`-ed `world_model.py` AppData→repo, then had to re-patch the `_HOME`/`pathlib` block back in). Always `patch` the repo file in place (or `cp` then immediately re-apply the `OPENAMER_HOME` header), and grep the result for `C:/Users/damir` to confirm no hardcoded path leaked in.
3. **`Path` NameError bug (found live)**: the repo commit that introduced `OPENAMER_HOME` used `Path.home()` in `active_learn.py`, `internet_learner.py`, `reasoning_loop.py`, `knowledge_to_action.py`, `online_learning.py` but only imported `pathlib` (or nothing) — `Path` was never imported, so every run without `OPENAMER_HOME` set throws `NameError: name 'Path' is not defined`. Fix: add `from pathlib import Path` to each. **This bug is NOT limited to the 5 files you touched — a grep sweep found it in 9 MORE files** (`memory_hierarchy.py`, `meta_learn.py`, `mini_step.py`, `self_model.py`, `serve_live.py`, `serve_mini.py`, `smart_router.py`, `swarm_intelligence.py`, `tool_server.py`). The durable check is a grep, not a mental list: every file where `grep -oE "[^a-zA-Z_.]Path\."` (bare `Path.`, excluding `pathlib.Path`) has a hit MUST also have `from pathlib import Path`. Run it over the WHOLE `scripts/training/` tree, not just the files you edited — the bug is latent (only fires when `OPENAMER_HOME` is unset, so it hides in normal runs).
4. **Commit only your files.** `git add` the specific changed paths; the repo has unrelated dirty files (`.bugbot/`, `reports/`, `skills/auto-generated/`, `assets/`) that are NOT yours — leave them unstaged.
5. **`dream_cron.py` / `dream_cycle.py` exist only in AppData, not the repo** — if you wire consolidation into the dream cycle, the repo copy of `dream_cron.py` may not exist yet; create it there too.
6. **Sync the WHOLE tree, not just the files you edited (live 06.09).** After porting your fixes, a grep sweep found the RUNNING copy (`AppData/.../scripts/training/`) still had 17 files with hardcoded `C:/Users/damir` paths that the repo had already made portable — because I only synced the 11 files I'd touched, not the 6 others the earlier commit had fixed. The correct sync is a bulk loop over EVERY `.py` that exists in BOTH trees: `for f in <repo>/scripts/training/*.py; do cp "$f" <appdata>/scripts/training/$(basename "$f"); done`. Then re-grep the running copy for `C:/Users/damir` — the only remaining hit should be `test_no_hardcoded_paths.py` (the guard's own search pattern, an expected false-positive). Two laptop-only files (`finetune_cpu.py`, `verify_tuned.py`) exist in AppData but NOT the repo — fix their hardcoded paths in place (they're CPU-finetuning scripts, not part of the SoT).
7. **`open(buf_path)[-50:]` on a file object is a TypeError (live 06.09).** `predict_validate.py` had `for line in open(buf_path, encoding="utf-8")[-50:]:` — slicing a `TextIOWrapper` raises `TypeError: '_io.TextIOWrapper' object is not subscriptable`. Fix: `.readlines()[-50:]`. This is a latent bug that only fires when the buffer path exists AND a prediction is unmatched — so it hid until a real validation run. When you touch a file for one reason (schema fix), smoke-test its OTHER code paths too, not just the line you changed.

## Verifying training scripts on Windows (pytest) — live 06.09

- **`scripts/run_tests.sh` does NOT hang — it fails with `ModuleNotFoundError: No module named 'pygments'`.** The earlier "hangs on Windows / `env -i` is POSIX-only" diagnosis was WRONG (disproven live 06.09 by actually reproducing it). The real root cause is a **`PYTHONPATH` leak**: the shell env has `PYTHONPATH=C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\venv\Lib\site-packages` pointing at the WRONG venv, which happens to contain `pygments`/`colorama`/`packaging`/`typing-extensions`. So a direct `.venv/Scripts/python.exe -m pytest` call "looks green" (imports resolve via the leaked PYTHONPATH), but `run_tests.sh` runs under `env -i` (clears PYTHONPATH) and then pytest's deps are genuinely missing from the repo `.venv` → `ModuleNotFoundError`. **Fix**: install the missing pytest deps into the repo venv with the leak suppressed: `env -u PYTHONPATH .venv/Scripts/python.exe -m pip install pygments colorama packaging typing-extensions`. Then `bash scripts/run_tests.sh scripts/training/` runs green (14/14). Verify the deps import under the clean env: `env -i PATH="$PATH" HOME="$HOME" .venv/Scripts/python.exe -c "import pygments, colorama, packaging, typing_extensions"`.
- **Reproduce before theorizing (first-class lesson, live 06.09).** I gave TWO wrong root-cause guesses for the `run_tests.sh` failure ("env -i hangs on Windows", "it discovers the full suite") before actually reproducing it. Both were wrong; the real cause (PYTHONPATH leak) only surfaced when I ran `env -i PATH="$PATH" HOME="$HOME" .venv/Scripts/python.exe -c "import pygments"` and watched it fail. Rule: when a test/runner fails, reproduce the EXACT failing invocation (same env, same flags) and read the actual error before stating a cause. A wrong diagnosis in a skill is worse than none — future sessions cite it and avoid a tool that actually works.
- **`scripts/package.json` `npm run test` only runs `test_workflow_immune.py` (WIS)** — it does NOT cover training scripts. Training-script changes need their own `test_*.py` files run via pytest (or `python test_x.py` directly).
- The repo `tests/` suite (openamer-agent core) references NONE of the training scripts — grep `tests/` for `world_model|memory_consolidation|active_learn|...` returns 0 hits. So the relevant evidence for training-script changes is the dedicated test files, not the core suite.

## Native OpenAmer integration (SOUL.md + skill registry)

The standalone `.py` scripts only become real when the MAIN agent (CLI + Desktop chat) knows about them. Three integration layers:

1. **`SOUL.md` in OPENAMER_HOME** (`C:/Users/damir/AppData/Local/openamer-laptop/SOUL.md`) — the primary identity file, loaded into EVERY session's system prompt via `load_soul_md()` in `agent/prompt_builder.py`. It documents Mini-OpenAmer capabilities with exact commands so the agent discovers and calls them unprompted. Verify: `load_soul_md()` returns non-None containing "Mini-OpenAmer".
2. **`skills/mini-openamer/SKILL.md`** — registers the capability set in the skill system (discoverable, tagged). Per the Footprint Ladder in AGENTS.md, this is a SKILL not a core tool — Mini-OpenAmer is user-specific, and core tools ship on every API call.
3. **Cron fleet** — 8 dedicated cron jobs (`online-learning-watchdog`, `active-learning-loop`, `internet-learner-247`, `self-improvement-loop`, `knowledge-to-action`, `self-model-evolution`, `swarm-intelligence-cycle`, `auto-skill-creation`) keep all loops running 24/7 inside the real OpenAmer fleet.
4. **Session-specific ASI modules** — `references/asi-modules-built-20260915.md` documents 5 new ASI capability modules (Domain Mastery Engine, Strategic Goal Engine, Tool Invention Engine, Continuous Benchmarking, Self-Directed Research) including their architecture, CLIs, cron patterns, and ASI-audit integration.





## Moved to references/ (same content, loaded on demand)

- `references/moved-to-references-same-content-loaded-on-deman.md` — Moved to references/ (same content, loaded on demand); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); …
- `references/inherited-trigger-from-autonomous-learning-loops.md` — Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); Inherited Trigger (from `autonomous-learning-loops`); …

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.

## Inherited Trigger (from `autonomous-learning-loops`)
Also handles topics previously covered by the absorbed skill `autonomous-learning-loops`.
