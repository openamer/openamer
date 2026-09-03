#!/usr/bin/env python3
"""Single mini training step for online learning (isolated process).

Trains 1 step on up to 2 newest buffer examples, saves as the ROLLING
adapter (separate from the night-batch 'adapter'). CPU-only, ~5s.

Output: last stdout line = JSON result for the parent loop.
"""
import json, os, sys, torch, pathlib
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

BASE = "Qwen/Qwen3.5-2B"
T = pathlib.Path(r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training")
BUFFER = T / "online_buffer.jsonl"
ROLLING = T / "lora_out" / "adapter_rolling"
MAXLEN = 512

def main():
    if not BUFFER.exists():
        print(json.dumps({"skipped": "empty buffer"})); return

    lines = open(BUFFER, encoding="utf-8").readlines()
    batch = [json.loads(l) for l in lines[-2:]]   # newest 2 examples
    if not batch:
        print(json.dumps({"skipped": "no examples"})); return

    tok = AutoTokenizer.from_pretrained(BASE)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True)

    # resume rolling adapter if it exists (continual learning!), else fresh LoRA
    if (ROLLING / "adapter_model.safetensors").exists():
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, ROLLING, is_trainable=True)
        fresh = False
    else:
        lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                          target_modules=["o_proj", "q_proj", "k_proj", "v_proj"], task_type="CAUSAL_LM")
        model = get_peft_model(model, lora)
        fresh = True

    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)

    total_loss = 0.0
    for ex in batch:
        text = tok.apply_chat_template(
            [{"role": "system", "content": "Du bist OpenAmer Agent."},
             {"role": "user", "content": ex["u"]},
             {"role": "assistant", "content": ex["a"]}],
            tokenize=False)
        ids = tok(text, truncation=True, max_length=MAXLEN, return_tensors="pt")
        out = model(**ids, labels=ids["input_ids"])
        loss = out.loss
        loss.backward()
        opt.step()
        opt.zero_grad()
        total_loss += loss.item()

    model.save_pretrained(ROLLING)
    print(json.dumps({"ok": True, "examples": len(batch),
                      "avg_loss": round(total_loss / len(batch), 3),
                      "fresh_adapter": fresh}))

if __name__ == "__main__":
    main()
