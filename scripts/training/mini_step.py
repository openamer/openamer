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

    # Seed the rolling chain from the best UNABSORBED prior adapter.
    #
    # Before this, the chain only ever resumed ROLLING (or started fresh from
    # BASE), so a full batch GPU run — trained on the whole curated distilled
    # set — was ignored: the next mini-step resumed the older rolling adapter
    # and the GPU work was silently discarded (observed 11.09.26: an 84-pair
    # GPU adapter was live for ~19 min, then replaced by a rolling adapter that
    # had never seen those examples).
    #
    # Plain "newest wins" is ALSO wrong: once the rolling chain writes, it is
    # the newest file and would hide a better batch adapter forever. So track
    # what the chain was last seeded from in `.rolling_seed`, and switch to a
    # batch GPU adapter whenever one appears that the chain has not absorbed.
    # The result accumulates: rolling = batch + subsequent mini-steps.
    #
    # All candidates must share the LoRA shape (r=16, alpha=32, 4 targets) or
    # PeftModel.from_pretrained raises a size mismatch — they do on this box.
    SEED_MARK = T / ".rolling_seed"

    def _pick_seed():
        gpu_dirs = sorted(
            (p for p in (T / "lora_out").glob("adapter_gpu*") if p.is_dir()),
            key=lambda p: (p / "adapter_model.safetensors").stat().st_mtime
            if (p / "adapter_model.safetensors").exists() else 0,
            reverse=True,
        )
        try:
            absorbed = SEED_MARK.read_text(encoding="utf-8").strip()
        except Exception:
            absorbed = ""
        # an unabsorbed batch adapter outranks the rolling chain
        for c in gpu_dirs:
            f = c / "adapter_model.safetensors"
            if f.exists() and c.name != absorbed:
                return c
        if (ROLLING / "adapter_model.safetensors").exists():
            return ROLLING
        if gpu_dirs and (gpu_dirs[0] / "adapter_model.safetensors").exists():
            return gpu_dirs[0]
        return None

    seed = _pick_seed()
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
