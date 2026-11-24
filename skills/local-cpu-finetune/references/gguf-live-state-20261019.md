# GGUF live state — 2026-10-19 (tool_server GGUF migration)

The `local-cpu-finetune` GGUF compatibility matrix was wrong about the 2B. This
reference records the corrected, measured state so a future session does not
repeat the "2B GGUF does not load" conclusion.

## What is actually served today

`scripts/training/mini-openamer-2b-q4.gguf` — **1.27 GB**, 320 tensors,
`general.architecture = qwen35`, `general.basename = Qwen3.5`,
`general.name = Qwen3.5 2B Base`, 24 blocks, 2048 hidden, 262144 context,
file_type 15, tokenizer `gpt2` / pre `qwen35`, quantized by mradermacher on nico1.

Live on `:18080` via `llama-server.exe`:
- `GET /v1/models` → model id `mini-openamer-2b-q4.gguf`
- `POST /v1/chat/completions` → valid reply, 847 completion tokens, ~15% of the
  prompt survived into the answer, `finish_reason=stop`

## The name/size trap

Three files share the `mini-openamer` prefix and only one works:

| File | Size | Loads? |
|---|---|---|
| `mini-openamer-2b-q4.gguf` | **1.27 GB** | ✅ live on :18080 |
| `mini-openamer-q4.gguf` | 3.76 GB | ❌ `check_tensor_dims` fails at startup |
| `mini-openamer-f16.gguf` | 3.78 GB | ❌ `blk.24.attn_norm.weight not found` |

`merged/Merged-1.5B-*.gguf` (Qwen2.5, 28 blocks / 1536 hidden) are legacy
artifacts served by nothing — ignore them.

## tool_server.py after the GGUF migration (2026-10-19)

- No in-process model load anymore. `AutoTokenizer`/`AutoModelForCausalLM`/
  `PeftModel`/`model.generate` are gone; inference delegates to
  `from gguf_backend import chat as gguf_chat` → the running llama-server.
- `enable_thinking=False` is passed: Qwen3.5-2B-Base is a base model, so with
  thinking enabled it generates empty `content` and `finish_reason=length`.
- `/admin/swap` is a No-Op: `{"result": "noop: model is served by GGUF backend
  on :18080 (no in-process adapter to swap) [#1]"}`.
- Usage counters come from the GGUF response (`prompt_tokens`/`completion_tokens`).
- Idle timeout raised 30 min → 24 h (`IDLE_TIMEOUT = 86400`); the keepalive
  watchdog restarts it in ~5 s when it crashes.
- Verified live: `/health` `{"status":"alive","tools":9,"swaps":0}`, `/tools` 9
  tools, `POST /execute_tool` run_python → `"4"`, chat completion → tool_use.

## So the LoRA adapter is still not wired into the live model

`finetune_cpu.py` trains a LoRA; the live server serves a static GGUF. To close
the loop the adapter must be merged into the base and re-converted to GGUF. The
old `convert_to_gguf.py` is broken (wrong `GGUFWriter` API, hardcoded
`arch="qwen35"` constant that does not exist as a string — the enum member is
`gguf.constants.MODEL_ARCH.QWEN35`). `gguf-py` was installed into the venv
(`pip install gguf`, RC 0) to enable a corrected converter.

## Venv selection (again)

`finetune_cpu.py` must run with
`C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts/python.exe`
(has torch 2.14.0+cpu, transformers 5.17.0, peft 0.21.0). The agent's own
`sys.executable` has **no torch** → `ModuleNotFoundError`. Smoke test with that
explicit path and `OPENAMER_TRAIN_MIN_GB=6` passed: Qwen3.5-2B loaded, 1.47M
trainable params (0.078%), 3 steps in 2:03, `ADAPTER_SAVED` into
`lora_out_smoke/adapter`.