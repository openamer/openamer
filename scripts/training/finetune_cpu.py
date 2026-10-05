#!/usr/bin/env python3
"""Mini-OpenAmer: LoRA SFT of the SERVED base (SmolLM2-360M-Instruct).

CPU-only. The adapter MUST be trained on the same base the tool_server loads:
scripts/training/tool_server.py reads `lora_out/adapter` and adopts its
base_model_name_or_path. Training a different base (this file used to train
Qwen2.5-1.5B and write lora_out_qwen25/) produced an adapter the server could
never load — so every nightly retrain was wasted and the loop never closed.
Output: lora_out/adapter (exactly where the hot-swap and the server expect it).

`--smoke` runs 3 steps into lora_out_smoke/ to verify the pipeline without
clobbering the production adapter.
"""
import json, math, os, sys, torch, pathlib
from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments, DataCollatorForSeq2Seq)
from peft import LoraConfig, get_peft_model

_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME", str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop")))
BASE = "HuggingFaceTB/SmolLM2-360M-Instruct"
DATA = os.path.join(_HOME, "scripts", "training", "sft_openamer.jsonl")
_SMOKE = "--smoke" in sys.argv
OUT = os.path.join(_HOME, "scripts", "training",
                   "lora_out_smoke" if _SMOKE else "lora_out")
MAXLEN = 1024

def _ram_ok(min_free_gb=6.0):
    """Guard: only train when the system has enough free RAM.

    Training loads the 2B model twice (frozen + gradients) ≈ 7-8 GB. When RAM
    is tight Windows swaps and training slows 10-50x (measured: 2 steps = 5 h
    instead of minutes). The tool_server also needs RAM — never starve it.
    """
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        free_gb = stat.ullAvailPhys / 1e9
        return free_gb >= min_free_gb, round(free_gb, 1)
    except Exception:
        return True, -1  # can't measure → allow (but log)


_ram_ok_val, _ram_free = _ram_ok()
if not _ram_ok_val:
    print(f"[finetune] ABORT: only {_ram_free} GB free RAM (need >= 6.0) — "
          f"Windows would swap and training would take 10-50x longer. "
          f"Retry when the tool_server is idle.", flush=True)
    sys.exit(0)
print(f"[finetune] RAM check OK: {_ram_free} GB free", flush=True)

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float32, low_cpu_mem_usage=True)
model.config.use_cache = False

lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                  task_type="CAUSAL_LM")
model = get_peft_model(model, lora)
model.print_trainable_parameters()

class SFT(Dataset):
    def __init__(self):
        self.rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, i):
        m = self.rows[i]["messages"]
        text = tok.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
        ids = tok(text, truncation=True, max_length=MAXLEN)["input_ids"]
        return {"input_ids": ids, "labels": ids[:]}

def collate(feats):
    maxlen = max(len(f["input_ids"]) for f in feats)
    pad = tok.pad_token_id or tok.eos_token_id
    out = {"input_ids": [], "attention_mask": [], "labels": []}
    for f in feats:
        ids = f["input_ids"]; lbl = f["labels"]
        d = maxlen - len(ids)
        out["input_ids"].append(ids + [pad] * d)
        out["attention_mask"].append([1] * len(ids) + [0] * d)
        out["labels"].append(list(lbl) + [-100] * d)  # mask padding only
    return {k: torch.tensor(v) for k, v in out.items()}

args = TrainingArguments(
    output_dir=OUT,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_train_epochs=3,
    max_steps=3 if _SMOKE else -1,
    learning_rate=2e-4,
    logging_steps=5,
    save_strategy="no",
    report_to=[],
    use_cpu=True,
)

trainer = Trainer(model=model, args=args, train_dataset=SFT(), data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "adapter"))
tok.save_pretrained(os.path.join(OUT, "adapter"))
print("ADAPTER_SAVED")
