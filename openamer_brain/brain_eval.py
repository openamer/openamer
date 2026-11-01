"""What can the local brain actually do? Measured, not assumed.

Loss tells you how well a model predicts bytes; it does not tell you whether it
can answer anything. This evaluates four things a usable brain needs:

  1. next-token accuracy  — top-1 / top-5 hit rate on held-out bytes
  2. dialogue format      — given "<|user|> ...", does it open with
                            "<|assistant|>"? (format, not knowledge)
  3. answer loss          — loss on the assistant turn only, i.e. how well it
                            models the part that matters
  4. greedy completion    — what it actually writes for a few prompts

Nothing here needs a GPU or the network.

    python brain_eval.py [--checkpoint PATH] [--samples 40]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # imported as openamer_brain.brain_eval
    from .openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402
    from .corpus import curate_message_stream, default_sources  # noqa: E402
except ImportError:  # executed as a script
    from openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402
    from corpus import curate_message_stream, default_sources  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
DEFAULT_CKPT = HOME / "checkpoints" / "openamer_brain_latest.pt"

ASSISTANT_MARKER = "<|assistant|>"
FORMAT_PROMPTS = [
    "<|user|> wie viele cron jobs laufen gerade?",
    "<|user|> was ist ein agent?",
    "<|user|> baue das projekt",
    "<|user|> erklaere mir den tool server",
]


def load_model(path: Path, seq_len: int = 256) -> tuple[OpenAmerNet, bool]:
    if not path.exists():
        return OpenAmerNet(OpenAmerConfig(max_seq_len=seq_len)), False
    blob = torch.load(path, map_location="cpu", weights_only=True)
    cfg_raw = blob.get("config")
    cfg = OpenAmerConfig.from_dict(cfg_raw) if isinstance(cfg_raw, dict) else cfg_raw
    cfg.max_seq_len = seq_len
    model = OpenAmerNet(cfg)
    model.load_state_dict(blob["model_state"])
    model.eval()
    return model, True


def heldout_tokens(val_ratio: float = 0.01) -> torch.Tensor:
    text, _ = curate_message_stream(
        default_sources(HOME, Path(os.environ.get("OPENAMER_BRAIN_DATA")
                                  or Path.home() / ".openamer" / "brain_data")),
        max_msg_chars=1200,
        drop_roles=(),
        dedupe=True,
    )
    tokens = torch.tensor(list(text.encode("utf-8")), dtype=torch.long)
    n = max(4096, int(len(tokens) * val_ratio))
    return tokens[-n:]


def next_token_accuracy(model: OpenAmerNet, tokens: torch.Tensor, samples: int) -> dict:
    """Top-1 / top-5 hit rate on positions drawn from the holdout."""
    seq = model.cfg.max_seq_len
    span = max(1, len(tokens) - seq - 1)
    top1 = top5 = total = 0
    with torch.no_grad():
        for i in range(samples):
            start = int(span * (i + 1) / (samples + 1))
            chunk = tokens[start : start + seq + 1]
            if len(chunk) < seq + 1:
                continue
            logits, _ = model(chunk[:-1].unsqueeze(0))
            target = chunk[1:]
            preds = logits[0].argmax(dim=-1)
            top5_idx = logits[0].topk(5, dim=-1).indices
            top1 += int((preds == target).sum())
            top5 += int((top5_idx == target.unsqueeze(-1)).any(dim=-1).sum())
            total += int(target.numel())
    return {"top1": top1 / total if total else 0.0,
            "top5": top5 / total if total else 0.0,
            "positions": total}


def format_hit_rate(model: OpenAmerNet) -> dict:
    """Does a user prompt make it emit the assistant marker?"""
    hits = []
    for prompt in FORMAT_PROMPTS:
        ids = torch.tensor([encode(prompt)], dtype=torch.long)
        with torch.no_grad():
            # Byte-level: 6 tokens would be 6 CHARACTERS, and the marker
            # "<|assistant|>" alone is 13 — give it room to actually say it.
            out = model.generate(ids, max_new_tokens=len(ASSISTANT_MARKER) + 8,
                                 temperature=1e-4, top_p=1.0, use_cache=True)
        text = decode(out[0].tolist()[len(encode(prompt)):])
        hits.append(text.lstrip().startswith(ASSISTANT_MARKER))
    return {"rate": sum(hits) / len(hits), "hits": hits}


def answer_loss(model: OpenAmerNet, tokens: torch.Tensor, samples: int = 12) -> float | None:
    """Loss on assistant continuations only (mask everything else)."""
    seq = model.cfg.max_seq_len
    text = bytes(tokens.tolist()).decode("utf-8", errors="replace")
    marker = "<|assistant|>"
    losses = []
    pos = 0
    while len(losses) < samples:
        idx = text.find(marker, pos)
        if idx < 0:
            break
        start = max(0, idx - 64)
        piece = text[start : idx + 96]
        pos = idx + len(marker)
        ids = torch.tensor([encode(piece)], dtype=torch.long)
        if ids.shape[1] < 8 or ids.shape[1] > seq:
            continue
        target = ids.clone()
        cut = len(encode(piece[: idx - start + len(marker)]))
        target[:, :max(0, cut - 1)] = -100
        with torch.no_grad():
            _, loss = model(ids[:, :-1], target[:, 1:])
        if loss is not None and loss == loss:
            losses.append(float(loss))
    return sum(losses) / len(losses) if losses else None


def greedy_samples(model: OpenAmerNet, n: int = 4) -> list[dict]:
    out = []
    for prompt in FORMAT_PROMPTS[:n]:
        ids = torch.tensor([encode(prompt)], dtype=torch.long)
        with torch.no_grad():
            gen = model.generate(ids, max_new_tokens=120, temperature=1e-4, top_p=1.0,
                                 use_cache=True)
        text = decode(gen[0].tolist()[len(encode(prompt)):])
        out.append({"prompt": prompt, "completion": text})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=str(DEFAULT_CKPT))
    ap.add_argument("--samples", type=int, default=40)
    args = ap.parse_args()

    model, trained = load_model(Path(args.checkpoint))
    print(f"checkpoint : {args.checkpoint} ({'trained' if trained else 'untrained'})")
    print(f"params     : {model.n_params()/1e6:.2f}M")

    tokens = heldout_tokens()
    acc = next_token_accuracy(model, tokens, args.samples)
    print(f"holdout    : {len(tokens):,} bytes")
    print(f"top-1      : {acc['top1']*100:.2f}%  (random = {100/256:.2f}%)")
    print(f"top-5      : {acc['top5']*100:.2f}%")

    fmt = format_hit_rate(model)
    print(f"format     : {fmt['rate']*100:.0f}% of prompts open with <|assistant|>")

    aloss = answer_loss(model, tokens)
    print(f"answer loss: {'n/a' if aloss is None else f'{aloss:.4f}'}")

    print("\ngreedy completions:")
    for row in greedy_samples(model):
        shown = "".join(ch if ch.isprintable() or ch == "\n" else "·"
                        for ch in row["completion"])[:160]
        print(f"  {row['prompt'][:52]!r}\n    -> {shown!r}")

    print()
    print(json.dumps({
        "checkpoint": str(args.checkpoint),
        "params": model.n_params(),
        "top1": round(acc["top1"], 5),
        "top5": round(acc["top5"], 5),
        "format_rate": round(fmt["rate"], 3),
        "answer_loss": None if aloss is None else round(aloss, 4),
        "positions": acc["positions"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
