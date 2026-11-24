# GGUF runtime compatibility measurement — 2026-10-19

Host: Windows 10, 22 GB RAM, no GPU. Engine:
`C:\Users\damir\llamacpp\llama-server.exe`, `--n-gpu-layers 0 --threads 4`.

All four Qwen3.5-family GGUFs on this host were tested with the same harness:

```python
def run_server(model, port, threads=4):
    cmd=[r'C:\Users\damir\llamacpp\llama-server.exe','--model',model,
         '--port',str(port),'--host','127.0.0.1','--n-gpu-layers','0',
         '--threads',str(threads),'--ctx-size','8192']
    # wait for /health, then POST /v1/chat/completions
```

Prompt used for the accuracy test: `"Was ist 7 mal 8? Antworte knapp."`

## Results

| Model | Path | Result |
|---|---|---|
| **Qwen3.5-4B-Q4_K_M** | `.emilija/workspace/models/Qwen3.5-4B-Q4_K_M.gguf` | ✅ 13.1 s, 10.7 tok/s, 355 reasoning tokens, content = `56` |
| Qwen3.5-0.8B-Q4_K_M | `.emilija/workspace/models/Qwen3.5-0.8B-Q4_K_M.gguf` | ❌ 93.7 s, 43.7 tok/s, **11,518 reasoning tokens, content = `""`** |
| mini-openamer-q4.gguf | `scripts/training/mini-openamer-q4.gguf` | ❌ server never reaches /health |
| mini-openamer-f16.gguf | `scripts/training/mini-openamer-f16.gguf` | ❌ `blk.24.attn_norm.weight not found` |

## The 0.8B trap — detail

Qwen3.5 emits `reasoning_content` before `content`. The 0.8B's reasoning for a
trivial question ran to 11,518 tokens and never produced an answer:

```
4B:  zeit=13.1s tok/s=10.7 reasoning=355 content="56"
0.8B: zeit=93.7s tok/s=43.7 reasoning=11518 content=""
```

`max_tokens` controls *content*, not reasoning. With `max_tokens=512` the 0.8B
produced 1,416 reasoning tokens and no content; at 4,096 it produced 11,518 and
still no content. The cap silently truncates the answer away.

## The 2B GGUFs — detail

Both `mini-openamer-q4.gguf` and `mini-openamer-f16.gguf` are Qwen3.5-2B
conversions (3.7 GB, 320 tensors, `general.architecture = qwen35`). Neither
loads:

- f16: `check_tensor_dims: tensor 'blk.24.attn_norm.weight' not found`
- q4: silent startup failure, /health never responds

The 2B safetensors path (transformers + LoRA) still works — that is the
SmolLM2-360M adapter served on `:8081` — but it is not a 2B base.

## Conclusion

`Qwen3.5-4B-Q4_K_M.gguf` is the only GGUF on this host that loads and answers.
10–13 s per question in a background brain is acceptable. The 0.8B is faster on
tok/s but never finishes; the 2B GGUFs do not load at all.