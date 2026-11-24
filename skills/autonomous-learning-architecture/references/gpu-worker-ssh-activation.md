# GPU Worker activation over SSH (live 11.09)

Durable recipe for bringing the RTX 3060 Ti worker (:8082, `frontier_server.py`)
online from the laptop over SSH — and the trap that kept it dead for weeks.

## The setup trap

Memory said "GPU-PC offline (SSH timeout)". It was **reachable the whole time** —
the worker just never started because the frontier server crashed. Do not trust
"offline" notes; probe `ssh -o BatchMode=yes -o ConnectTimeout=8 user@host` first.

## Symptom chain that reveals the real bug

```
[frontier-server] loading model...
...97% weights loaded...
AssertionError: Torch not compiled with CUDA enabled
```
The PC had an RTX 3060 Ti but `torch 2.12.1+cpu`. The server loaded fine then
died the moment it called `.cuda()` — so `:8082` never answered and memory
recorded "offline". **Never conclude "PC offline" from a dead worker; check the
worker's own crash log.**

## Fix sequence (from the laptop)

1. **Probe** `nvidia-smi --query-gpu=name --format=csv,noheader` → `RTX 3060 Ti`,
   `python --version` → 3.11.11, and confirm the repo exists on the PC.
2. **Install CUDA PyTorch into the uv-managed python** (it is externally managed):
   ```
   ssh ... "python -m pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121 --break-system-packages"
   ```
   `--break-system-packages` is required (uv python → PEP 668). Plain `pip install`
   says "already satisfied" and keeps the CPU build. Force-reinstall or the index
   URL won't take. Install `peft accelerate` the same way if missing.
3. **Verify**: `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → `2.5.1+cu121 True NVIDIA GeForce RTX 3060 Ti`.
4. **Start persistently** — a plain `start /b` or `Start-Process` under SSH DIES
   when the SSH session ends (Windows kills child processes of the session). The
   reliable way is a scheduled task:
   ```
   schtasks /create /tn OpenAmerFrontier \
     /tr "<python-exe> <path>\frontier_server.py" /sc once /st 00:00 /f
   schtasks /run /tn OpenAmerFrontier
   ```
   Task-owned processes survive the SSH disconnect. Add a `>> log 2>&1` wrapper
   `.bat` if you need output capture (a bare task has no redirect).
5. **LAN firewall**: the server binds `0.0.0.0` but Windows Firewall still drops
   the laptop's direct connection; `curl localhost:8082/health` ON the PC works
   while `curl http://<pc-ip>:8082/health` from the laptop hangs. Add:
   ```
   netsh advfirewall firewall add rule name="OpenAmerFrontier8082" dir=in action=allow protocol=TCP localport=8082
   ```
   Then verify from the laptop IP.
6. **Model VRAM note**: Qwen3.5-4B fills all 8 GB VRAM; a second CUDA workload
   (e.g. GPU finetune) will OOM. For training, stop the frontier server first
   (`taskkill /f /pid <pid>`), run the trainer, then restart the task.

## GPU finetune (same session)

`finetune_gpu.py` (fp16 + gradient_checkpointing + batch=1 + maxlen=512 for 8 GB)
takes ~9–10 min for 72 steps. **Do not run it through a foreground SSH with a
60 s `timeout`** — it gets killed at 90%. Run it detached via its own `schtasks`
entry with a wrapper that `>> train.log 2>&1` and echoes `EXIT_CODE=%ERRORLEVEL%`,
then poll the log for `GPU_TRAINING_DONE`. Transfer the trained LoRA back to the
laptop with `scp` and hot-swap it into the tool_server (:8081) via the
`/admin/swap` endpoint — the fresh weights become live without restarting.
