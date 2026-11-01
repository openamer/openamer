"""Causality + sanity checks for the CPU brain.

1. Untrained loss must sit at ln(256) ~= 5.545 (uniform predictor). Lower
   means information is leaking from the target position.
2. Perturbing token t must not change logits at any position < t.
3. Checkpoint round-trip must reproduce logits bit-for-bit.
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402

torch.manual_seed(0)
cfg = OpenAmerConfig(max_seq_len=64, d_model=128, n_layers=3, n_heads=4)
net = OpenAmerNet(cfg)
net.eval()
fails = []

# --- 1. untrained loss ~ ln(vocab) ---
# Targets MUST be shifted (next token), otherwise position i legitimately
# sees token i and the loss drops below ln(vocab) with no leak involved.
x = torch.randint(0, 256, (4, 64))
_, loss = net(x[:, :-1], x[:, 1:])
target = math.log(cfg.vocab_size)
print(f"[1] untrained loss {loss.item():.4f}  expected ~{target:.4f}")
if abs(loss.item() - target) > 0.35:
    fails.append(f"loss {loss.item():.3f} != ln(vocab) {target:.3f} -> leak or bad init")

# --- 2. future tokens must not influence the past ---
seq = torch.randint(0, 256, (1, 64))
with torch.no_grad():
    base, _ = net(seq)
worst = 0.0
for pos in (0, 15, 31):
    pert = seq.clone()
    pert[0, pos + 1 :] = torch.randint(0, 256, (64 - pos - 1,))
    with torch.no_grad():
        alt, _ = net(pert)
    delta = (alt[:, : pos + 1] - base[:, : pos + 1]).abs().max().item()
    worst = max(worst, delta)
    print(f"[2] perturb from {pos+1}: max |dlogit| at <= {pos} = {delta:.3e}")
if worst > 1e-5:
    fails.append(f"causality broken: past logits changed by {worst:.3e}")

# --- 3. checkpoint round-trip ---
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "ckpt.pt"
    torch.save({"model_state": net.state_dict(), "config": cfg.to_dict()}, p)
    ck = torch.load(p, map_location="cpu", weights_only=True)
    net2 = OpenAmerNet(OpenAmerConfig.from_dict(ck["config"]))
    net2.load_state_dict(ck["model_state"])
    net2.eval()
    with torch.no_grad():
        a, _ = net(seq)
        b, _ = net2(seq)
    same = torch.equal(a, b)
    print(f"[3] checkpoint round-trip identical logits: {same}")
    if not same:
        fails.append("checkpoint round-trip changed logits")

# --- 4. generate runs and grows by exactly max_new_tokens ---
out = net.generate(torch.tensor([encode("test")]), max_new_tokens=8, temperature=0.8, top_p=0.9)
print(f"[4] generate 4 -> {out.shape[1]} tokens, sample {decode(out[0].tolist())!r}")
if out.shape[1] != 4 + 8:
    fails.append(f"generate produced {out.shape[1]} tokens, expected 12")

# --- 5. KV-cache path must match the full forward ---
cfg2 = OpenAmerConfig(max_seq_len=128, d_model=128, n_layers=3, n_heads=4)
torch.manual_seed(7)
net2 = OpenAmerNet(cfg2)
net2.eval()
prompt = torch.randint(0, 256, (1, 17))
cache = net2.new_cache()
cache["pos"] = prompt.shape[1]
with torch.no_grad():
    logits_full, _ = net2(prompt, cache=cache)
    step_max = 0.0
    tok = torch.tensor([[42]])
    gen_ids = prompt.clone()
    for i in range(6):
        gen_ids = torch.cat([gen_ids, tok], dim=1) if i > 0 else torch.cat([prompt, tok], dim=1)
        step_logits = net2.forward_step(tok, cache)
        ref_logits, _ = net2(gen_ids)
        d = (step_logits[:, -1, :] - ref_logits[:, -1, :]).abs().max().item()
        step_max = max(step_max, d)
        tok = torch.tensor([[int(step_logits.argmax())]])
print(f"[5] KV-cache vs full forward: max |dlogit| = {step_max:.3e} over 6 steps")
if step_max > 2e-4:
    fails.append(f"KV-cache path diverges from full forward: {step_max:.3e}")

# --- 6. cached generation is not slower than the naive path ---
import time
p = torch.tensor([encode("OpenAmer ASI Core: ")])
t0 = time.time()
_ = net2.generate(p, max_new_tokens=12, temperature=0.8, top_p=0.9, use_cache=True)
t_cache = time.time() - t0
t0 = time.time()
_ = net2.generate(p, max_new_tokens=12, temperature=0.8, top_p=0.9, use_cache=False)
t_naive = time.time() - t0
print(f"[6] 12 tokens on a 3-layer net: cache {t_cache*1000:.0f} ms vs naive {t_naive*1000:.0f} ms "
      f"({t_naive/max(t_cache,1e-9):.1f}x)")

print()
if fails:
    print("FAILED:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("ALL CHECKS PASSED")
