# Model Training Pipeline: Qwen2.5-1.5B for Ollama Deploy

## Why Qwen2.5, not Qwen3.5

Qwen3.5-2B (Hybrid Arch: linear attention + mrope) is **too new for tooling**:
- `llama.cpp` / Ollama GGUF converter produces files that **fail to load** with
  `check_tensor_dims: tensor 'blk.24.attn_norm.weight' not found`
- `gguf-py` (`GGUFWriter`) API is unstable across versions — `open_output_file()`
  must be called AFTER `add_tensor` (while state = NO_FILE), and
  `write_tensors_to_file()` internally calls `write_ti_data_to_file()`, so DO NOT
  call it manually.
- Ollama 0.34.0 does NOT support qwen3_5 architecture for `ollama create`

Qwen2.5-1.5B is widely supported: Ollama has it as `qwen2.5:1.5b`, GGUF works
out-of-the-box, and the base model is available at `Qwen/Qwen2.5-1.5B` on HF.

## Complete Pipeline (6 steps)

### 1. Distil SFT data from brain
```
python distill_sft.py
# Output: sft_openamer.jsonl (148 pairs in current set)
```
Gate with `_answer_is_safe()` — rejects invented metrics, CoT leaks, self-praise.

### 2. LoRA training on CPU
```
# Script: scripts/training/finetune_cpu.py
# BASE: Qwen/Qwen2.5-1.5B
# OUT: lora_out_qwen25/adapter/
Hyperparams: r=16, 4 target modules, maxlen=1024, batch=1, grad_accum=4
Training time: ~30 min on CPU (vs 45 min for Qwen3.5-2B)
Expected loss: 2.3 → 1.7 over 48 steps
```
**RAM guard**: checks for ≥6 GB free before starting. Training uses ~7-8 GB.

### 3. Merge LoRA into base model
```
# Script: scripts/training/merge_and_export.py
# BASE: Qwen/Qwen2.5-1.5B
# ADAPTER: lora_out_qwen25/adapter/
# Output: merged/ (safetensors, ~3.6 GB in f16)
```
Uses `PeftModel.from_pretrained(model, ADAPTER).merge_and_unload()`.
Merge time: ~7 min on CPU.

### 4. GGUF conversion via llama.cpp (NOT gguf-py directly)
```
# From /tmp/llama.cpp/convert_hf_to_gguf.py
python convert_hf_to_gguf.py --outtype f16 /path/to/merged
# Output: merged/Merged-1.5B-F16.gguf (~3.76 GB)
```
**CRITICAL**: use `convert_hf_to_gguf.py` from the official llama.cpp repo, NOT
`gguf-py` directly. The gguf-py `GGUFWriter` API:
- `add_tensor()` must be called BEFORE `open_output_file()` (state = NO_FILE)
- `write_tensors_to_file()` internally calls `write_ti_data_to_file()` — do NOT
  call `write_ti_data_to_file()` separately
- `write_kv_data_to_file()` must precede `write_tensors_to_file()`
- The resulting GGUF has structural issues (missing metadata, wrong architecture)

The llama.cpp converter produces a VALID GGUF with all required metadata.

### 5. Ollama create (with quantization)
```
ollama create openamer/openamer-mini --quantize q4_K_M -f Modelfile
```
**Modelfile content** (reference in `scripts/training/Modelfile`):
```
FROM ./merged/Merged-1.5B-F16.gguf
TEMPLATE """...""
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 8192
LICENSE Apache-2.0
```
Q4_K_M reduces size from ~3.76 GB to ~1.3 GB.

### 6. Push to ollama.com
```
ollama login   # opens browser — user must do this
ollama push openamer/openamer-mini
# Live at: https://ollama.com/openamer/openamer-mini
```

## MSYS Path Translation Bug (critical for Windows)

In MSYS/Git-Bash, paths like `/c/Users/damir/...` get DOUBLE-TRANSLATED when
passed as arguments to `python.exe`: `/c/Users/...` → `C:\c\Users\...` (the `/c/`
is expanded to `C:\` AND the forward slashes stay).

**Fix**: write a `.bat` wrapper that uses bare Windows paths:
```bat
@echo off
set PYTHON=C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe
set SCRIPT=C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\script.py
"%PYTHON%" "%SCRIPT%"
```
Run via `cmd.exe /c "C:\path\to\wrapper.bat"` from MSYS.
Also works: use `workdir` parameter in terminal() calls pointing to the training dir.

## Windows background process patterns
- Use `notify_on_complete=true` for bounded tasks (training, merge)
- Use `notify_on_complete=false` for silent retries of known-fragile scripts
- Always use the `openamer-laptop` venv (`venv/Scripts/python.exe`), NOT PATH python
  (which resolves to `openamer-agent/venv` — no torch/transformers/gguf there)

## Benchmark comparison
- OpenRouter (deepseek-v4-flash): 70.4% on MMLU-style 40 questions
- Mini-model (local Ollama): expected 50-65% (smaller model, less training data)
- Run via: `python scripts/mini_benchmark.py`

## What NOT to do
- Do NOT use `gguf-py`'s `GGUFWriter` to create a GGUF from scratch — the API is
  unstable, the resulting file has structural issues, and Ollama rejects it
- Do NOT use Qwen3.5 for GGUF export — the architecture is too new for tooling
- Do NOT `ollama create` without `--quantize q4_K_M` — the f16 GGUF is 3.76 GB
  and q4_K_M reduces it to 1.3 GB while preserving quality
- Do NOT call `write_ti_data_to_file()` manually — `write_tensors_to_file()` does it
- Do NOT call `add_tensor()` after `open_output_file()` — state must be NO_FILE