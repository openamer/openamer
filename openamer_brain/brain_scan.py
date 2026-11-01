"""
OpenAmer Brain Scan & Evaluation (CPU).

Loads the latest checkpoint (or a raw, untrained brain), measures real
generation latency, and prints memory/graph state of the corpus the brain
was trained on. This is what `openamer brain stats` should call.

Usage:
    python brain_scan.py [--checkpoint PATH] [--tokens 40] [--prompts N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # imported as openamer_brain.brain_scan
    from .openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402
except ImportError:  # executed as a script
    from openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
DEFAULT_CKPT = HOME / "checkpoints" / "openamer_brain_latest.pt"

PROMPTS = [
    "OpenAmer ASI Core: ",
    "openamer brain stats: ",
    "Self-improving agent: ",
]


def load_model(ckpt_path: Path) -> tuple[OpenAmerNet, bool]:
    if not ckpt_path.exists():
        cfg = OpenAmerConfig()
        return OpenAmerNet(cfg), False
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    cfg = OpenAmerConfig.from_dict(ckpt["config"]) if isinstance(ckpt.get("config"), dict) else ckpt["config"]
    model = OpenAmerNet(cfg)
    model.load_state_dict(ckpt["model_state"])
    return model, True


def corpus_stats() -> dict:
    out = {}
    for rel in ("a2a/openamer-brain.jsonl", "scripts/training/sft_openamer.jsonl"):
        p = HOME / rel
        if p.exists():
            with open(p, "rb") as f:
                lines = sum(1 for _ in f)
            out[rel] = {"lines": lines, "bytes": p.stat().st_size}
    return out


def scan(ckpt_path: Path, max_new_tokens: int) -> int:
    print("=" * 45)
    print("       OPENAMER BRAIN SCANNER (CPU)")
    print("=" * 45)

    model, trained = load_model(ckpt_path)
    if trained:
        print(f"[OK] Loaded checkpoint: {ckpt_path}")
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        print(f"     trained step: {ckpt.get('step')}  loss: {ckpt.get('loss')}")
    else:
        print(f"[!] No checkpoint at {ckpt_path} — using a raw, untrained brain.")

    print(f"     params: {model.n_params()/1e6:.2f}M  device: cpu  threads: {torch.get_num_threads()}")
    cs = corpus_stats()
    for k, v in cs.items():
        print(f"     corpus {k}: {v['lines']:,} lines / {v['bytes']/1e6:.2f} MB")
    if not cs:
        print("     corpus: none found")

    model.eval()
    lat = []
    print("\n--- live generation (untrained output is noise, latency is real) ---")
    for prompt in PROMPTS:
        ids = torch.tensor([encode(prompt)], dtype=torch.long)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=max_new_tokens, temperature=0.7, top_p=0.85)
        dt = time.time() - t0
        lat.append(dt)
        text = decode(out[0].tolist()[len(encode(prompt)):])
        printable = "".join(ch if ch.isprintable() or ch == "\n" else "·" for ch in text)
        print(f"\n[prompt] {prompt!r}")
        print(f"[answer] {printable[:200]!r}")
        print(f"[latency] {dt*1000:.1f} ms for {max_new_tokens} tokens "
              f"({max_new_tokens/max(dt,1e-9):.1f} tok/s)")

    mean = sum(lat) / len(lat)
    print(f"\n[summary] mean {mean*1000:.1f} ms/prompt — {max_new_tokens/max(mean,1e-9):.1f} tok/s on CPU")
    print(json.dumps({
        "checkpoint": str(ckpt_path),
        "trained": trained,
        "params": model.n_params(),
        "threads": torch.get_num_threads(),
        "mean_latency_ms": round(mean * 1000, 1),
        "tokens_per_sec": round(max_new_tokens / max(mean, 1e-9), 1),
    }))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=str(DEFAULT_CKPT))
    ap.add_argument("--tokens", type=int, default=40)
    args = ap.parse_args()
    return scan(Path(args.checkpoint), args.tokens)


if __name__ == "__main__":
    raise SystemExit(main())
