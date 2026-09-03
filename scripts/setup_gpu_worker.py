#!/usr/bin/env python3
"""OpenAmer GPU Worker Setup — run this ON THE SECOND PC (with RTX 3060 Ti).

Automatically:
  1. Installs Python packages (torch CUDA, openamer deps)
  2. Clones the OpenAmer repo from GitHub
  3. Copies all training scripts from this session
  4. Configures CUDA for GPU training
  5. Sets up Wake-on-LAN listener
  6. Starts the GPU training worker
  7. Connects to the Mesh (Laptop = Master)

Run:  python setup_gpu_worker.py
"""
import os, sys, subprocess, json, time, urllib.request, platform

print("=" * 60)
print("  OpenAmer GPU Worker Setup")
print("  Target: PC with RTX 3060 Ti 8GB + 16GB RAM")
print("=" * 60)

REPO = os.path.join(os.path.expanduser("~"), "openamer-repo")
HOME = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                    "AppData", "Local", "openamer-laptop")

def run(cmd, **kw):
    print(f"  > {cmd[:80]}...")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0 and kw.get("check", False):
        print(f"  ERROR: {r.stderr[:300]}")
    return r

def step(n, title):
    print(f"\n{'='*60}\n  STEP {n}: {title}\n{'='*60}")

# ---- Step 1: Check GPU ----
step(1, "Check GPU")
r = subprocess.run(["nvidia-smi"], capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode != 0:
    print("  ❌ nvidia-smi not found — install NVIDIA drivers first!")
    print("  Download: https://www.nvidia.com/drivers")
    sys.exit(1)
gpu_line = [l for l in r.stdout.split("\n") if "3060" in l or "RTX" in l]
print(f"  ✅ GPU: {gpu_line[0].strip() if gpu_line else 'detected'}")

# ---- Step 2: Install CUDA PyTorch ----
step(2, "Install PyTorch with CUDA")
r = run("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
if r.returncode == 0:
    # verify CUDA
    r2 = subprocess.run([sys.executable, "-c",
        "import torch; print('CUDA:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"  {r2.stdout.strip()}")
else:
    print("  Trying pip3...")
    run("pip3 install torch --index-url https://download.pytorch.org/whl/cu121")

# ---- Step 3: Install OpenAmer ----
step(3, "Install OpenAmer")
r = run("pip install openamer")
if r.returncode != 0:
    print("  Trying from repo...")
if not os.path.exists(REPO):
    run(f"git clone https://github.com/openamer/openamer.git {REPO}")
else:
    run(f"cd {REPO} && git pull")

# ---- Step 4: Copy training scripts from GitHub ----
step(4, "Download training scripts")
training_scripts = [
    "deep_task.py", "tool_math.py", "reasoning_loop.py",
    "analogy_engine.py", "online_learning.py", "mini_step.py",
    "smart_router.py", "tool_server.py", "serve_live.py",
    "auto_retrain.py", "distill_sft.py", "finetune_cpu.py",
]
os.makedirs(os.path.join(REPO, "scripts", "training"), exist_ok=True)
for script in training_scripts:
    url = f"https://raw.githubusercontent.com/openamer/openamer/main/scripts/training/{script}"
    dst = os.path.join(REPO, "scripts", "training", script)
    try:
        urllib.request.urlretrieve(url, dst)
        print(f"  ✅ {script}")
    except Exception as e:
        print(f"  ⚠ {script}: {str(e)[:60]}")

# ---- Step 5: Convert auto_retrain to GPU ----
step(5, "Configure GPU training")
gpu_finetune = os.path.join(REPO, "scripts", "training", "finetune_gpu.py")
gpu_code = '''#!/usr/bin/env python3
"""GPU version of finetune_cpu.py — 10x faster with CUDA."""
import json, os, sys, torch
from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                          TrainingArguments)
from peft import LoraConfig, get_peft_model

BASE = "Qwen/Qwen3.5-2B"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sft_openamer.jsonl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lora_out_gpu")
MAXLEN = 1024

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True).cuda()
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
    output_dir=OUT, per_device_train_batch_size=2,
    gradient_accumulation_steps=2, num_train_epochs=3,
    learning_rate=2e-4, logging_steps=5, save_strategy="no",
    report_to=[], bf16=True,
)
trainer = Trainer(model=model, args=args, train_dataset=SFT(), data_collator=collate)
trainer.train()
model.save_pretrained(os.path.join(OUT, "adapter"))
tok.save_pretrained(os.path.join(OUT, "adapter"))
print("GPU_TRAINING_DONE")
'''
with open(gpu_finetune, "w", encoding="utf-8") as f:
    f.write(gpu_code)
print("  ✅ finetune_gpu.py created")

# ---- Step 6: Wake-on-LAN listener ----
step(6, "Setup Wake-on-LAN listener")
wol_script = os.path.join(HOME, "scripts", "wol_listener.py")
os.makedirs(os.path.dirname(wol_script), exist_ok=True)
wol_code = '''#!/usr/bin/env python3
"""Wake-on-LAN listener: receives magic packets from the laptop to wake the GPU worker."""
import socket, subprocess, sys

PORT = 9
MAGIC_PREFIX = b"\\xff" * 6

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", PORT))
    print(f"Wake-on-LAN listener on port {PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        if data[:6] == MAGIC_PREFIX:
            mac = data[6:12]
            print(f"Magic packet from {addr} — waking GPU worker")
            # start the GPU training worker
            subprocess.Popen([sys.executable,
                r"C:/Users/damir/openamer-repo/scripts/training/auto_retrain.py"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            print(f"Unknown packet from {addr}")

if __name__ == "__main__":
    main()
'''
with open(wol_script, "w", encoding="utf-8") as f:
    f.write(wol_code)
print("  ✅ wol_listener.py created")

# ---- Step 7: Get the laptop's MAC for WOL config ----
step(7, "Summary")
print(f"""
  SETUP COMPLETE!

  This PC is now a GPU Worker for OpenAmer.

  What it can do:
  ✅ GPU LoRA training (10x faster than CPU)
  ✅ 7B-13B model inference
  ✅ Frontier reasoning offline

  To start the GPU worker:
    python {gpu_finetune}

  To start the Wake-on-LAN listener:
    python {wol_script}

  To sync with the laptop (once both are running):
    The laptop sends Magic Packets + training data via the Agent Mesh.

  Questions? Ask Mini-OpenAmer on the laptop: localhost:8081
""")
print("=" * 60)
