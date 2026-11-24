# Qwen3.5-2B → GGUF → served (worked transcript, 2026-10-30)

The self-training loop looked healthy for weeks while the served model was the
untouched upstream base. This is the full repair, with the exact error texts, so a
future session does not re-derive it.

## 0. The finding that started it

```python
head = (T/"mini-openamer-2b-q4.gguf").open("rb").read(200_000).decode("latin-1", "replace")
# general.architecture: qwen35
# general.name:         Qwen3.5 2B Base      <-- upstream, not OpenAmer
# general.basename:     Qwen3.5
# general.finetune:     Base
# general.license:      https://huggingface.co/Qwen/Qwen3.5-2B-Base/...
```

Meanwhile: cron green, adapter mtimes advancing, `RETRAIN_OK` in the log,
`lora_out/adapter_rolling` present. Every proxy said "learning works"; the artifact
said "never reached production".

## 1. Four names for one artifact

| Stage | File | Value before |
|---|---|---|
| train | `finetune_cpu.py` | `BASE = Qwen/Qwen3.5-2B`, `OUT = lora_out` (adapter → `lora_out/adapter`) |
| merge | `merge_and_export.py` | `BASE = Qwen/Qwen2.5-1.5B`, `ADAPTER = lora_out_qwen25/adapter` |
| convert | `convert_to_gguf.py` | `OUT = mini-openamer-q4.gguf` |
| serve | `gguf_backend.py` | `MODEL = mini-openamer-2b-q4.gguf` |

The merge read an adapter the trainer never wrote, onto a base the trainer never
used; the converter wrote a name the backend never reads; and the last step POSTed a
PEFT adapter to a llama-server that cannot load one.

## 2. Vendoring the real converter

Nothing usable locally — `C:\Users\damir\llamacpp` and
`C:\Users\damir\.emilija\workspace\llama.cpp` carry `llama-server.exe` and
`llama-quantize.exe`, but no `convert_hf_to_gguf.py`.

The file on `raw.githubusercontent.com` is only ~14 KB because it imports a package:

```python
from conversion import (...)
sys.path.insert(1, str(Path(__file__).parent / 'gguf-py'))
```

so:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/ggml-org/llama.cpp scripts/training/tools/llama-convert
git -C scripts/training/tools/llama-convert sparse-checkout set --no-cone \
  /conversion/ /convert_hf_to_gguf.py /gguf-py/
```

First attempt without `--no-cone`:

```
fatal: 'convert_hf_to_gguf.py' is not a directory; to treat it as a directory anyway, rerun with --skip-checks
```

Result: 3.4 MB, 111 modules, `conversion/qwen.py` contains `qwen35`.

## 3. Three failures in a row, each with its exact text

### (a) hand-rolled writer — silently unloadable

The old `convert_to_gguf.py` used `gguf.GGUFWriter` with
`name.replace(".", "_")` and arch `qwen3_5`. Produced a file; llama.cpp rejected it.
Never diagnose this from the code — compare tensor names of a known-good file and the
new one with `GGUFReader`; here they matched, which redirected the search to the
metadata.

### (b) MTP block — converts cleanly, refuses to load

```
E llama_model_load: error loading model: check_tensor_dims: tensor 'blk.24.attn_norm.weight' not found
E llama_model_load_from_file_impl: failed to load model
```

Cause: `config.json` of the merged model says `num_hidden_layers: 24` and
`mtp_num_hidden_layers: 1`; the file holds 24 blocks (320 tensors). Upstream's
`conversion/qwen.py` does:

```python
self.block_count = self.hparams["num_hidden_layers"]
if not self.no_mtp:
    n_mtp = self.hparams.get("mtp_num_hidden_layers", 0)
    if n_mtp == 0:
        assert self.opt_num_mtp_layers != 0
        n_mtp = self.opt_num_mtp_layers
    self.block_count += n_mtp        # -> 25
```

and `no_mtp` is set True only for `Qwen3_5TextModel`:

```python
if get_model_architecture(hparams, ModelType.TEXT) == "Qwen3_5TextModel":
    self.no_mtp = True
```

### (c) the tempting wrong fix — converter asserts

Setting only `mtp_num_hidden_layers: 0` while keeping
`architectures: ["Qwen3_5ForCausalLM"]`:

```
File "conversion/qwen.py", line 322, in __init__
    assert self.opt_num_mtp_layers != 0
AssertionError
```

The **architecture name** is the switch, not the count.

## 4. `normalize_config()` — derive the config from the weights

In `merge_and_export.py`, after `save_pretrained`:

```python
def _weight_names(model_dir: Path) -> list[str]:
    index = model_dir / "model.safetensors.index.json"
    if index.exists():
        return list(json.loads(index.read_text(encoding="utf-8")).get("weight_map", {}))
    names = []
    for st in model_dir.glob("*.safetensors"):
        with st.open("rb") as fh:
            n = int.from_bytes(fh.read(8), "little")
            header = json.loads(fh.read(n))
        names += [k for k in header if k != "__metadata__"]
    return names

def _layer_count_from_weights(model_dir) -> int:
    layers = {int(m.group(1)) for n in _weight_names(model_dir)
              if (m := re.search(r"layers\.(\d+)\.", n))}
    return max(layers) + 1 if layers else 0

def normalize_config(model_dir) -> None:
    cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    names = _weight_names(model_dir)
    has_mtp = any(n.startswith("mtp.") or ".mtp." in n for n in names)
    present = _layer_count_from_weights(model_dir)
    target = cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else cfg
    if present and target.get("num_hidden_layers") != present:
        target["num_hidden_layers"] = present
    if not has_mtp:
        target["mtp_num_hidden_layers"] = 0
        if any(str(a).startswith("Qwen3_5For") for a in cfg.get("architectures", [])):
            cfg["architectures"] = ["Qwen3_5TextModel"]
    (model_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
```

Live output: `WARN config declares 24+1 blocks, weights hold 24` →
`CONFIG_NORMALIZED: blocks=24 arch=['Qwen3_5TextModel'] mtp=0`.

## 5. Convert + quantize + atomic swap

`convert_to_gguf.py` takes every path from `pipeline_paths.py`
(`SERVED_GGUF`, `F16_GGUF`, `llama_convert_script()`, `llama_quantize()`):

```python
_run([sys.executable, str(converter), str(src), "--outfile", str(f16), "--outtype", "f16"], 7200, "convert")
_run([str(quant), str(f16), str(tmp_q), args.quant], 3600, "quantize")     # tmp_q = out + ".new"
if produced.stat().st_size < 100 * 1024 * 1024:
    raise SystemExit(f"FAIL produced file looks wrong: {produced}")
backup = out.with_name(out.name + f".prev-{int(time.time())}")
if out.exists():
    shutil.copy2(out, backup)
shutil.move(str(produced), str(out))
```

Both stages ran in about a minute end to end and printed
`GGUF_SAVED … (1.27 GB)` + `GGUF_BACKUP …`.

## 6. Prove it loads, then A/B it

```python
proc = subprocess.Popen([LLAMA, "--model", str(new), "--host", "127.0.0.1",
                         "--port", str(port), "--ctx-size", "4096",
                         "--threads", "4", "--n-gpu-layers", "0"])
# poll /health, then POST /v1/chat/completions with
#   "chat_template_kwargs": {"enable_thinking": False}
```

Measured:

| prompt | base (served before) | merged (adapter_rolling) |
|---|---|---|
| Hauptstadt von Frankreich? | `Paris` | `Paris` |
| 17 * 3? | `49` ✗ | `51` ✓ |
| Liste sortieren | `xs.sort()` | `xs.sort()` |

Identity after the swap: `general.name = Mini_OpenAmer_2B`, `block_count = 24`,
320 tensors, **30.1 tok/s**.

## 7. Reload semantics

`gguf_backend._start()` is lazy: it spawns `llama-server` only when `/health` fails.
So replacing the file is not enough — the running server keeps the old weights in
RAM. Stop the listener on `:18080`, then the next `gguf_backend.chat()` loads the new
file:

```python
Stop-Process -Id (Get-NetTCPConnection -LocalPort 18080 -State Listen).OwningProcess -Force
# verify: gguf_backend.chat([...]) -> "Bereit", 30.1 tok/s, model = the new path
```

## 8. Regression test that pins the chain

`scripts/tests/test_retrain_alignment.py` reads the scripts as **source** (regex/JSON,
no import — `finetune_cpu.py` needs torch which the agent venv lacks):

- trainer `BASE` == the served base
- `finetune_cpu.py` saves to `OUT/adapter`, and `OUT` is under `scripts/training`
- `gguf_backend.MODEL` == the file `pipeline_paths.SERVED_GGUF` names
- no `GGUFWriter(` in the converter; `llama_convert_script` used; `llama_quantize` used
- `merge_and_export` still guards `base mismatch`
- `auto_retrain` calls merge + convert, has no `admin/swap`, and writes the 24 h
  marker **after** the convert call
- merged `config.json`: 24 layers, no MTP, `architectures == ["Qwen3_5TextModel"]`
- served GGUF header contains `openamer`

### Pitfall in that test: prose is not the defect

Two assertions failed on their own explanatory comments — `"GGUFWriter" not in src`
tripped on the docstring line *"the old hand-rolled GGUFWriter produced a file…"*, and
`"admin/swap" not in src` tripped on the comment describing the removed POST. Strip
prose before asserting:

```python
def _code_only(src: str) -> str:
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub("\x27" * 3 + r".*?" + "\x27" * 3, "", src, flags=re.S)
    return "\n".join(line.split("#", 1)[0] for line in src.splitlines())
```

## 9. `npm run test` was red for unrelated reasons — classify before fixing

`bash scripts/run_research_tests.sh --fast` → `85 passed, 4 failed`, none in the
pipeline files. Two were real and got fixed (the `group_state` tool was never wired
into `tool_server.py`; a test asserted a mathematically false claim that
`score_answer("0.375", "3/8")` must be False — 3/8 *is* 0.375, so the scorer was
right and the test was corrected, with `0.37` vs `3/8` added as the real near-miss
control). Final: `89 passed, 0 failed`, and the slow head-line stage
(`final_comparison.py --epochs 400 --warmup 250 --seeds 2`, ~23 min on this CPU)
was run explicitly instead of leaving it as `SKIPPED (--fast)`.

## 10. Disk hygiene

Intermediates cost real space: `merged_verify/` 3.78 GB, one F16 GGUF 2.5 GB, two
`.prev-*` copies 1.27 GB each. Keep exactly one backup
(`mini-openamer-2b-q4.gguf.prev-<ts>`), delete verify dirs and F16 after a successful
swap, and report the free-space delta (here 334 GB → 340 GB).
