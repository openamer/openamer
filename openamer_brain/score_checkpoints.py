"""Score checkpoints on one identical held-out slice.

Two checkpoints trained on different corpora are not comparable through
their own training logs — the text differs. This evaluates both against the
same curated holdout, which is the only honest comparison.

    python score_checkpoints.py ckpt_a.pt ckpt_b.pt [--val-ratio 0.01]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # imported as openamer_brain.score_checkpoints
    from .openamer_prototype import OpenAmerConfig, OpenAmerNet  # noqa: E402
    from .corpus import curate_message_stream, default_sources  # noqa: E402
except ImportError:  # executed as a script
    from openamer_prototype import OpenAmerConfig, OpenAmerNet  # noqa: E402
    from corpus import curate_message_stream, default_sources  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
CHUNKS = 12


def load_holdout(seq_len: int, val_ratio: float, max_msg_chars: int) -> torch.Tensor:
    data_dir = Path(os.environ.get("OPENAMER_BRAIN_DATA") or (Path.home() / ".openamer" / "brain_data"))
    text, _stats = curate_message_stream(
        default_sources(HOME, data_dir),
        max_msg_chars=max_msg_chars,
        drop_roles=(),
        dedupe=True,
    )
    tokens = torch.tensor(list(text.encode("utf-8")), dtype=torch.long)
    n_val = max(seq_len * CHUNKS + 8, int(len(tokens) * val_ratio))
    return tokens[-n_val:]


def score(ckpt_path: Path, holdout: torch.Tensor, seq_len: int) -> dict:
    blob = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    cfg_raw = blob.get("config")
    cfg = OpenAmerConfig.from_dict(cfg_raw) if isinstance(cfg_raw, dict) else cfg_raw
    cfg.max_seq_len = seq_len
    model = OpenAmerNet(cfg)
    model.load_state_dict(blob["model_state"])
    model.eval()

    span = len(holdout) - seq_len - 1
    losses = []
    with torch.no_grad():
        for i in range(CHUNKS):
            start = int(span * i / CHUNKS)
            chunk = holdout[start : start + seq_len + 1].unsqueeze(0)
            _, loss = model(chunk[:, :-1], chunk[:, 1:])
            losses.append(float(loss))
    mean = sum(losses) / len(losses)
    return {
        "checkpoint": str(ckpt_path),
        "step": blob.get("step"),
        "train_loss_recorded": None if blob.get("loss") is None else round(float(blob["loss"]), 4),
        "holdout_loss": round(mean, 4),
        "holdout_perplexity": round(pow(2.718281828, mean), 2),
        "params": model.n_params(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoints", nargs="+")
    ap.add_argument("--seq", type=int, default=256)
    ap.add_argument("--val-ratio", type=float, default=0.01)
    ap.add_argument("--max-msg-chars", type=int, default=800)
    args = ap.parse_args()

    holdout = load_holdout(args.seq, args.val_ratio, args.max_msg_chars)
    print(f"[holdout] {len(holdout):,} bytes from the tail of the curated corpus "
          f"(max_msg_chars={args.max_msg_chars}, dedupe on)")

    rows = []
    for ck in args.checkpoints:
        path = Path(ck)
        if not path.exists():
            print(f"  ! missing {path}")
            continue
        rows.append(score(path, holdout, args.seq))

    print()
    print(f"{'checkpoint':34s} {'step':>6s} {'recorded':>9s} {'holdout':>8s} {'ppl':>7s}")
    for r in rows:
        print(f"{Path(r['checkpoint']).name:34s} {str(r['step']):>6s} "
              f"{str(r['train_loss_recorded']):>9s} {r['holdout_loss']:>8.4f} {r['holdout_perplexity']:>7.2f}")
    print()
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
