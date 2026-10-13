#!/usr/bin/env python3
"""Single mini training step for online learning (isolated process).

Trains 1 step on up to 2 newest buffer examples, saves as the ROLLING
adapter (separate from the night-batch 'adapter'). CPU-only, ~5s.

Output: last stdout line = JSON result for the parent loop.
"""
import os
import json, os, sys, torch, pathlib
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model

BASE = "Qwen/Qwen3.5-2B"
T = pathlib.Path(os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "scripts", "training"))
BUFFER = T / "online_buffer.jsonl"
ROLLING = T / "lora_out" / "adapter_rolling"
SEED_MARK = T / ".rolling_seed"
MAXLEN = 512


def _adapter_mtime(d):
    """mtime of a dir's adapter weights, or 0 when it has none (unusable seed)."""
    f = d / "adapter_model.safetensors"
    return f.stat().st_mtime if f.exists() else 0


def pick_seed(lora_dir=None, rolling=None, mark=None):
    """Best adapter to continue training from — see the note in `main`.

    The chain used to resume only ROLLING (or start fresh from BASE), so a
    batch GPU run over the curated distilled set was invisible and got
    discarded by the next mini-step. Plain "newest wins" is also wrong: once
    the chain writes, it is the newest file and hides batch runs forever.
    Hence the `.rolling_seed` marker — rolling = batch + later mini-steps.

    Seeds must share the LoRA shape (r=16, alpha=32, 4 targets) or
    PeftModel.from_pretrained raises a size mismatch; see test_rolling_seed.
    """
    lora_dir = pathlib.Path(lora_dir or (T / "lora_out"))
    rolling = pathlib.Path(rolling or ROLLING)
    mark = pathlib.Path(mark or SEED_MARK)
    batches = sorted(lora_dir.glob("adapter_gpu*"), key=_adapter_mtime, reverse=True)
    absorbed = mark.read_text(encoding="utf-8").strip() if mark.exists() else ""
    for d in batches:                                   # unabsorbed batch wins
        if _adapter_mtime(d) and d.name != absorbed:
            return d
    if _adapter_mtime(rolling):
        return rolling
    return next((d for d in batches if _adapter_mtime(d)), None)


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

    seed = pick_seed()
    if seed is not None:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, seed, is_trainable=True)
        fresh = False
        try:
            SEED_MARK.write_text(seed.name, encoding="utf-8")
        except Exception:
            pass
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
