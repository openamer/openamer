# Worked case: the retrain fix is live but not on `main` (2026-10-06)

Found while assembling a factual GitHub issue update on our own repo. The loop
was declared fixed on 2026-10-05 (`6922c42ca`). Measured this run: **two halves
of that fix travelled differently**, and one never reached `main` at all.

## Commands actually run, and what they returned

```bash
# 1. Does the tree the contributor installs still carry the bug?
cd /c/Users/damir/openamer-repo && grep -n 'BASE = ' scripts/training/tool_server.py
# 377:BASE = "Qwen/Qwen3.5-2B"
grep -n 'ADAPTER = ' scripts/training/tool_server.py
# 378:... os.environ.get("OPENAMER_HOME", str(Path.home()/"AppData"/"Local"/"openamer")) , "scripts","training","lora_out","adapter")

# 2. Byte-compare live vs repo (three copies exist: live / openamer-repo / repo-tmp)
for f in scripts/training/finetune_cpu.py scripts/training/auto_retrain.py scripts/training/tool_server.py; do
  a=$(md5sum "$H/$f" | cut -d' ' -f1); b=$(md5sum "$R/$f" | cut -d' ' -f1)
  echo "$f live=$a repo=$b $([ "$a" = "$b" ] && echo SAME || echo DIFF)"
done
# finetune_cpu.py   SAME   (2b8b60cd758214ecdb83cc0e2aa90551)
# auto_retrain.py   SAME   (86c3e8e6cf0c37b177d8579075e7769b)   <- this half shipped
# tool_server.py    DIFF   live 7037e7bef35a733dc61ed06b7c38b1bb / repo ce485460e9e7d099df42c94a667d56d3
```

`main` is missing ONLY the serving-side half: `_base_for_adapter()` (resolve BASE
from `adapter_config.json`, fallback `HuggingFaceTB/SmolLM2-360M-Instruct`) and
the corrected `OPENAMER_HOME` default (`openamer-laptop`, not `openamer`).

## The structural proof of the mismatch

Read the safetensors header — no torch, no weights, no download:

```python
import struct, json
p = "$H/scripts/training/lora_out/adapter/adapter_model.safetensors"
with open(p, "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    hdr = json.loads(f.read(n))
hdr["base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight"]["shape"]
```

```
[16, 960]     # r=16, hidden_in=960  -> SmolLM2-360M-Instruct
```

`Qwen/Qwen3.5-2B` is hidden 2048. The `main` pair (`BASE = Qwen3.5-2B` +
SmolLM2 LoRA) is therefore a guaranteed startup failure, not a suspicion. This is
stronger than quoting `adapter_config.json` alone, because it measures the actual
tensor, so a stale/mistyped `base_model_name_or_path` cannot hide it.

Re-runnable: `scripts/lora_base_probe.py` (compares declared vs measured vs the
base's `config.json` fetched from HF Hub; offline => *unmeasured*).

## The data-path half (this one IS on `main`)

```
$HOME/.openamer/a2a/openamer-brain.jsonl           57,522,301 B   mtime 2026-09-24 12:38  <- stale
$OPENAMER_HOME/a2a/openamer-brain.jsonl  7,544 rec 144,760,807 B  mtime live             <- real
```

`brain_collect` regenerates rather than appends, so `count - last_count` is not a
usable "new data" signal (it goes negative when the dataset shrinks). The fix
gates on `BRAIN.stat().st_mtime > MARKER.stat().st_mtime` plus `>= MIN_NEW_PAIRS`.

## Green evidence gathered the same run

```bash
python3 -m pytest scripts/tests/test_retrain_alignment.py -q
# 4 passed in 0.04s
```

The suite asserts against the **served** adapter's own `adapter_config.json`
(trainer `BASE` == served base, `OUT` == the path the hot-swap reads, backup
precedes training) — a behaviour contract, not a snapshot. Note the
"canonical test venv" caveat: a bare `python -m pytest` resolved to a venv with
no pytest; `python3` (the standalone interpreter) carried 9.1.1.

Adapter actually landed: `lora_out/adapter/adapter_model.safetensors`,
13,141,032 B, mtime `2026-10-05 23:03`; `adapter_backup/` and
`lora_out/adapter_pre_retrain_20261005-2205/` both present (rollback exists).

## Traps hit in this run

- **`diff <(sort a) <(sort b)` is the WRONG way to compare two source copies.**
  Sorting destroys position, so the live file's *added* functions report as
  deletions of the repo's (`< return "HuggingFaceTB/SmolLM2-360M-Instruct"`).
  It looks like the live file is *missing* the fix. Diff line-by-line, or compare
  the specific constants.
- **`find ... -maxdepth 3 -name a -o -maxdepth 3 -name b`** re-applies `-maxdepth`
  per branch and silently scans less than you think. One `-maxdepth` before the
  expression.
- **A python one-liner mixing MSYS `r'/c/...'` with `Path.home()`** produced
  `C:\Users\damir\AppData\AppData\Local\...`. Use native `C:/...` literal paths
  in the same script, or resolve everything from one root.

## Publishing rule that came out of it

State *which tree* a fix is in. "The loop is fixed" was true of the live tree and
false of `main` — the published comment had to say so explicitly, and name the
one-line change (`BASE = _base_for_adapter()`) rather than implying it shipped.
