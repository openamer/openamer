# Active Learn — Action Behavior (observed 07.09 & 08.09)

## Action → chat() dependency matrix

| Action | Needs `chat()` | Completes on CPU | Observed time (07.09) | Observed time (08.09) | Notes |
|--------|---------------|------------------|----------------------|----------------------|-------|
| `web_learn` | YES | YES (slow/empty) | ~30s | — | Returns "no insight extracted" — tool_server web_search returns nothing useful through 2B model |
| `self_test` | YES | YES | ~10-15s *(lock-starved artifact)* | **57.7s (GOOD)** | Produces meaningful self-critique. 07.09's ~15s timings were from a freshly-loaded model before lock starvation set in; **08.09 live session with a warm, healthy tool_server ran a full answer+critique cycle in 57.7s and returned GOOD**. The earlier fast numbers were accurate only for minimal/no-content replies, not meaningful cycles. |
| `world_explore` | NO | YES | ~5-7s | ~5-7s (inferred) | Fastest action — directly scans cron output, writes world_model edges. No model inference needed. |
| `skill_challenge` | Uses tool endpoint, not chat() | YES | ~10s | — | Calls execute_tool on tool_server for a random skill — PASS/FAIL |
| `cross_connect` | YES | **NO — HANGS** | >211s+ | — | Constructs long analogy prompt → 2B model on CPU never returns within reasonable time |

## Key findings (live 07.09)

- **No-args mode** ran 4/5 actions in ~211s; cross_connect was the one that didn't finish and had to be killed.
- Tool-server `/v1/chat/completions` with model `mini-openamer` responded to short prompts (self_test worked) but **returned empty body** to a curl test (`-d '{"model":"mini-openamer","messages":[{"role":"user","content":"hello"}],"max_tokens":10}'` → exit 0, no output). This confirms the endpoint is alive but unreliable.
- `web_learn` extracting "no insight" suggests the 2B model's text-generation output is being _consumed_ by the parser before any real content arrives — or the search results are empty because the tool_server web_search returns nothing useful at the 2B level.
- **Only `world_explore` is safe for cron** under the default tool_server on this laptop CPU. All others either produce empty results or hang.

## Update (live 07.09 evening — lock starvation, not inference slowness)

After discovering the tool_server had a hung model thread (PID 10220, 3.9 GB, 2:36h CPU), killing it and restarting revealed a completely different picture:

- **Freshly loaded tool_server ran ALL 5 actions in ~4 seconds.** Not 120s+. Not 211s. Four seconds.
- `web_learn` still returned "no insight extracted" (tool_server web_search → 2B model yields nothing useful), but `self_test`, `world_explore`, `skill_challenge`, and `cross_connect` all completed.
- This proves the earlier "2B model is too slow on CPU" diagnosis was WRONG. The **real bottleneck was the lock starvation** — one orphaned `model.generate()` call held the `threading.Lock`, and every subsequent request queued behind it forever.
- The 2B model on this laptop CPU is usable (~4s for 5 chat calls) — the earlier 120s+ timeouts were the lock, not the model.

**Revised conclusion**: the tool_server's model lock is the primary failure mode for cron jobs. A health check that also hits `/v1/chat/completions` (not just `/health` and `/execute_tool`) is the only reliable uptime signal. See the "Model lock starvation" pitfall in the main SKILL.md for the full diagnostic ladder and fix.

## Update (live 08.09 — normal operating point measured)

This session (08.09, tool_server healthy with 9 tools, 11 swaps confirmed via `/health` + curl `POST /v1/chat/completions` returning actual content in <30s):

- **self_test completed in 57.7s with GOOD** — the first empirically measured normal-state timing for a full 2-round (answer + critique) cycle.
- Tool_server was NOT freshly loaded (had been running long enough to accumulate 11 adapter swaps) — this is the **steady-state** operating point, not a cold-start artifact.
- The self_test question was *"What is the difference between correlation and causation in system diagnostics?"* — a moderately complex conceptual question.
- The critique phase confirmed [GOOD], meaning the model's answer was self-rated as accurate and complete.
- **Implication**: with a `timeout >= 120s` (ideally 300s), self_test is viable in cron on the laptop CPU even with a warm tool_server. The ~58s includes both generation rounds. Earlier claims that "self_test ~10-15s" were optimistic (only apply to generation-only with minimal tokens, not full answer+critique).

### Revised cron viability per action (08.09 steady-state)

| Action | Viable in cron? | Min timeout | Notes |
|--------|-----------------|-------------|-------|
| `world_explore` | ✅ YES | 30s | No chat() needed; fastest action |
| `self_test` | ✅ YES | **120s** (prefer 300s) | 58s measured for complete cycle; needs headroom for longer model generations |
| `skill_challenge` | ✅ YES | 60s | Uses execute_tool endpoint, not model inference |
| `web_learn` | ❌ NO | N/A | Returns "no insight extracted" — tool pipeline fails |
| `cross_connect` | ❌ NO | N/A | Constructs long analogy prompt → model never returns |

The `echo 2 > .learn_rotation` workaround (skip to world_explore) remains the safest cron invocation, but **self_test is now a viable second option** when the timeout is set to 300s.

## Safe cron invocation plan

For the `active-learning-loop` cron job, the recommended invocations in priority order:

1. **Default** (300s timeout): `python active_learn.py once` — runs the natural rotation, which includes self_test (~58s). If it times out, the rotation auto-skips to the next action.
2. **Safest** (low timeout): Write rotation to world_explore:
   ```bash
   echo 2 > /c/users/damir/appdata/local/openamer-laptop/scripts/training/.learn_rotation
   python active_learn.py once
   ```
   This runs world_explore only (~7s) — no chat() needed, no timeout risk.
3. **Never**: `python active_learn.py` (no args) — runs all 5 actions sequentially under the test/debug `else` branch, always times out.
4. **Never**: `python active_learn.py --once` (with leading dash) — arg parsing uses `lstrip("-")` internally so `--once` IS handled; but verify via `sys.argv[1] == "once"` which fails with `--once`. The script was NOT updated for this pattern — see the `--once` vs `once` pitfall in the main SKILL.md.

If the chat() dependency is fixed (e.g. routing to Ollama or a faster model), the cron can run ALL actions again. Track this in the cross_connect pitfall.

## Update (live 10.09) — tool-call JSON response from chat() on :8081

This session's `active_learn.py once` run revealed a NEW failure mode (distinct from lock starvation):

- **`web_learn` returned "no insight extracted"** — NOT because the model timed out, but because the tool_server responded with a **tool-call JSON array** (`[{"tool": "listen", "params": {...}}]`) instead of plain text containing `[INSIGHT]`.
- **`cross_connect` returned `[TOOL_RESULT:web_search] ...`** — the model decided to call `web_search` instead of producing a structural-connection insight.
- **Root cause**: the `chat()` helper in `active_learn.py` posts to `/v1/chat/completions` without setting any parameter to suppress tool calls. The Mini-OpenAmer model (loaded via `tool_server.py`) has tool definitions configured, so it can (and does, on certain prompts) choose to call a tool instead of answering with text. The `[INSIGHT]` parser in `web_learn` and the analogy query in `cross_connect` then find no text and return empty/malformed results.
- **Confirmed via curl**: `POST /v1/chat/completions {"model":"mini-openamer","messages":[{"role":"user","content":"hello"}],"max_tokens":20}` returned valid JSON with content being a tool-call array: `"[{\"tool\": \"listen\", \"params\": {\"action\": \"key\", \"target\": \"\"}}]"`
- **NOT lock starvation**: the tool_server was healthy (9 tools, 34 swaps, `/health` alive), the curl responded in <10s. This is a clean signal — the model *chose* to reply with a tool invocation because the prompt didn't force text-only output.
- **Fix in active_learn.py**: the `chat()` function should either (a) pass `\"tools\": []` or a `tool_choice: \"none\"` parameter to the chat completion request to suppress tool calls, or (b) post-process the response: if the content starts with `[` (JSON array), extract any text found or fall back to `SILENT`/`no insight extracted`. Option (a) is cleaner — the learning loop never needs tool orchestration from the model.

### Expanded action matrix (10.09 — tool-call noise mode)

| Action | chat() needed | Viable? | Observed behavior (10.09 healthy server) |
|--------|-------------|---------|------------------------------------------|
| `web_learn` | YES | ❌ NO — tool-call | Model returns tool-call JSON, parser finds no `[INSIGHT]` |
| `self_test` | YES | ⚠️ Partial | Model may answer or tool-call depending on prompt; needs tool_choice=none |
| `cross_connect` | YES | ❌ NO — tool-call | Model calls web_search instead of producing analogy |
| `skill_challenge` | NO (uses execute_tool) | ✅ YES | Completed in ~7s — PASS |
| `world_explore` | NO | ✅ YES | Fastest action, no chat() needed |

### Rotation observation
The `.learn_rotation` counter reached **64** (was ~8 on 07.09, ~50 actions in between). Each rotation cycles through 5 actions: web_learn → self_test → world_explore → skill_challenge → cross_connect → (repeat). Of 64 actions across all sessions, roughly:
- ~13 each of web_learn, self_test, cross_connect → mostly ineffective (tool-call or timeout)
- ~13 world_explore → productive (writes world-model edges)
- ~13 skill_challenge → productive (validates tool server skills)

**Effective actions ≈ 26/64 (40%)**. The other 60% are wasted on model-inference actions that return empty or tool-call artifacts. Fixing the tool_choice parameter in `chat()` would make ALL actions productive.

## Additional lesson (08.09) — cron job invocation matters

This session's cron job called `active_learn.py` (no args), which executes the `else` branch — all 5 actions in series, up to 5×60s = 300s+ — and timed out at the default 120s terminal timeout. The fix was re-invoking with the `once` arg via `timeout 300 python active_learn.py once`. The default (no-args) mode is a test/debug path, NOT a cron-suitable mode. **Always use `once` for cron**.