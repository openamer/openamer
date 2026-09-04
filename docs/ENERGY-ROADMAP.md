# Energy Roadmap: From 75 W to 20 W

The goal: Mini-OpenAmer's cognition at biological brain level (20 W).

## Current state (measured 2026-09-04)

| Component | Power |
|---|---|
| Laptop (2B + 7 learning loops) | ~25 W |
| PC (4B warm on GPU) | ~35-50 W |
| **Total** | **~60-75 W** |
| Human brain (reference) | 20 W |

## The 4-Step Path to 20 W

### Step 1: Quantization (DONE — scripts exist)
- Laptop: `torch.ao.quantization` dynamic int8 (CPU, no CUDA needed)
  - `quantized_server.py` — int8 inference, ~40% energy saving
  - Trade-off: CPU int8 inference is slower in current torch version
- PC: bitsandbytes 4-bit (CUDA) — `quantized_server.py` auto-detects
  - 4B model in 4-bit ≈ 2.5 GB VRAM (vs 7.9 GB fp16) → room for more models

### Step 2: Distillation (READY — server script exists)
- `mini_distilled_server.py`: Qwen3.5-0.8B trained on the SAME SFT data
  the 2B learned from (same behavior, 1/5 the size)
- 0.8B fp16 ≈ 1.6 GB RAM, ~10 W inference (vs ~25 W for 2B)
- **-60% energy for local inference**

### Step 3: Sparsity (PARTIALLY DONE — architecture-level)
- Qwen3.5's Hybrid Mamba IS sparse-by-design (18 linear + 6 full attention)
  — linear attention = O(n) compute, not O(n²)
- Further optimization: early-exit for simple queries (stop in early layers)
- Future: MoE-style activation (only relevant experts fire)

### Step 4: Neuromorphic Hardware (~500 €, 1-2 years)
- BrainChip Akida (USB stick, ~500 €): 1-5 W for agent-level inference
- Intel Loihi 2: research-grade spiking neural networks
- OpenAmer's architecture (events, sparsity, state-space) maps well to SNN

## Full Energy Projection

| Stage | Inference Power | Year |
|---|---|---|
| Now (2B + 4B hybrid) | 60-75 W | 2026 |
| After quantization | 40-50 W | 2026 |
| After distillation (0.8B local) | 35-45 W | 2026 |
| + Sparsity optimizations | 25-35 W | 2027 |
| + Neuromorphic Akida | 5-10 W | 2027-2028 |
| **Target: brain-level** | **~20 W** | **2028** |

The comparison: 20 W brain vs 50 GW datacenter = 14 BILLION times.
We are at 3-4x. The path is short and concrete.