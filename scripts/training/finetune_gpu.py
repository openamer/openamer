#!/usr/bin/env python3
"""GPU finetune — optimized for 8GB VRAM (RTX 3060 Ti).

Key optimizations for 8GB:
  - fp16 instead of bf16 (less VRAM)
  - gradient checkpointing (massive VRAM savings)
  - batch_size=1 with grad_accumulation=4
  - maxlen=512 (reduced context)
  - expandable_segments alloc conf
"""
import json, os, sys, torch

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments)
from peft import LoraConfig, get_peft_model

BASE = "Qwen/Qwen3.5-2B"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sft_openamer.jsonl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_out_gpu")
MAXLEN = 512

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(
    BASE, torch_dtype=torch.float16, low_cpu_mem_usage=True).cuda()
model.gradient_checkpointing_enable()
model.config.use_cache = False

lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                  target_modules=["o_proj", "q_proj", "k_proj", "v_proj"],
                  task_type="CAUSAL_LM")
model = get_peft_model(model, lora)
model.print_trainable_parameters()

class SFT(Dataset):
    def __init__(self):
        self.rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    def __len__(self): return len(self.rows)
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
        out["labels"].append(list(lbl) + [-100] * d)
    return {k: torch.tensor(v) for k, v in out.items()}

args = TrainingArguments(
    output_dir=OUT, per_device_train_batch_size=1,
    gradient_accumulation_steps=4, num_train_epochs=3,
    learning_rate=2e-4, logging_steps=5, save_strategy="no",
    report_to=[], fp16=True,
)
trainer = Trainer(model=model, args=args, train_dataset=SFT(), data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "adapter"))
tok.save_pretrained(os.path.join(OUT, "adapter"))
print("GPU_TRAINING_DONE")
