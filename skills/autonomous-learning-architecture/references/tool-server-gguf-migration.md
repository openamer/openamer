# tool_server.py → GGUF backend migration (live 18.10.26)

## What was broken

`scripts/training/tool_server.py` (the canonical Mini-OpenAmer server on `:8081`) loaded
the 2B model **in-process** via transformers + PEFT:

```python
BASE = "Qwen/Qwen3.5-2B"
ADAPTER = .../lora_out/adapter
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, ADAPTER)
```

Two defects, both verified live:

1. **Wrong base model.** The LoRA adapter's `adapter_config.json` declares its training
   base as `SmolLM2-360M`, not Qwen3.5-2B. So the in-process path silently loaded a
   360M model with a Qwen3.5 tokenizer — wrong answers, wrong tool behaviour, and on the
   CPU laptop (22 GB RAM) the combined load crashed the server on **every** start. The
   code comments claimed Qwen3.5-2B; the actual loaded model was SmolLM2-360M.
2. **No working inference path survived.** The server never reached `TOOL_SERVER_READY`,
   so `:8081` was unreachable and every consumer (cron, probes, `internet_learner`) saw
   connection refused.

## The fix

The model is served by `gguf_backend.py`, which starts `llama-server` on
`127.0.0.1:18080` with `mini-openamer-2b-q4.gguf` (Qwen3.5-2B-Base, Q4_K_M, 1.2 GB,
256k ctx, 4 threads). `tool_server.py` became a pure orchestrator:

| Change | Before | After |
|---|---|---|
| Model load | `AutoTokenizer` + `AutoModelForCausalLM` + `PeftModel` block | `from gguf_backend import chat as gguf_chat` |
| Inference | `tok.apply_chat_template` → `model.generate(...)` → `tok.decode` | `gguf_chat(msgs, max_tokens, temperature, enable_thinking=False)` |
| `/admin/swap` | `model.load_adapter(...)` + `set_adapter(...)` via `.swap_request` file | **No-op** — no in-process PEFT model exists; still returns 200 |
| Usage | `ids["input_ids"].shape[1]` / `max_new` | `res["prompt_tokens"]` / `res["completion_tokens"]` from the GGUF response |
| Imports | `import torch`, `from transformers import ...`, `from peft import ...` | removed; added `import traceback as _tb` for the 503 error path |

`_strip_thinking()` is kept unchanged — it still strips Qwen3.5 `` traces.

## Critical detail: `enable_thinking=False` is mandatory

Qwen3.5-2B-**Base** is a base model, not an instruct model. Measured on the running
server: with thinking enabled the model emits reasoning tokens but **no content**
(`finish_reason: "length"`, `content: ""`). With `enable_thinking=False` it answers
directly. `gguf_backend.chat()` already sends this flag; do not override it.

## Verification (all live, real tool output)

```
GET  http://localhost:8081/health          -> {"status":"alive","tools":9,"swaps":0}
GET  http://localhost:8081/tools           -> 9 tools, names match the TOOLS table
POST http://localhost:8081/execute_tool    -> run_python print(2+2) -> "4", security gate ran
POST http://localhost:8081/v1/chat/completions
  "What is 15% of 847?" -> [TOOL_RESULT:run_python] {"stdout":"127.05"}, finish_reason=tool_use
  ~6.7 s wall clock, 28-30 tok/s
GET  http://localhost:18080/health         -> {"status":"ok"}
```

Plus a new E2E suite `scripts/training/test_tool_server_gguf.py` (6 steps, incl. a
static check that no in-process model code survived) → **`ALL TESTS PASSED`**, rc 0.

## Pitfalls hit while doing this

- **`/admin/swap` crashed with `NameError: name 'ADAPTER' is not defined`** after the
  model block was removed — the swap handler still referenced the deleted constant.
  The fix is a no-op response, not a re-import.
- **The lazy `.swap_request` mechanism also referenced `model`** and had to be removed
  entirely, not just neutered.
- **`tool_server.start.log` is opened by the running server** — `os.remove()` on it
  from another process raises `PermissionError`. Don't clean up files the live process
  holds.
- **Port ownership**: three `llama-server.exe` instances were running on `:18080`
  (legacy spawns). `:18080` health was still `ok` because one of them answered, but
  always check the actual model path in `/v1/models` before trusting a health response.

## Related

- `mini-openamer` skill (user-owned, `created_by=None`) documents the canonical server
  and the `:8081`-squatter rule, but still describes the **old** in-process model path
  and the hot-swap mechanism. It is **not** curator-managed — `skill_manage` refuses to
  patch it. Recommend `openamer curator adopt mini-openamer` so the migration lands
  there too; until then this file is the authoritative record.
- `autonomous-learning-architecture` SKILL.md carries the condensed version of this
  entry under the `tool_server.py` architecture change bullet.