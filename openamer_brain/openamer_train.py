"""
OpenAmer Brain Training Loop (CPU-optimized).

Reads the data OpenAmer actually collects on this machine:
  * $OPENAMER_HOME/a2a/openamer-brain.jsonl        (openamer a2a brain collect)
  * $OPENAMER_HOME/scripts/training/sft_openamer.jsonl
  * $OPENAMER_HOME/scripts/training/online_buffer.jsonl
  * ~/.openamer/brain_data/*.{txt,jsonl,md}        (drop-in extra corpus)

Records are chat-shaped ({"messages": [...]}); plain {"text": ...} and raw
lines are accepted too. If nothing is found we fall back to bootstrap
patterns so the loop never dies on an empty corpus.

Usage:
    python openamer_train.py [--steps 200] [--epochs 5] [--lr 3e-4]
                             [--batch 4] [--seq 256] [--resume] [--val-ratio 0.02]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # imported as openamer_brain.openamer_train
    from .openamer_prototype import OpenAmerConfig, OpenAmerNet  # noqa: E402
except ImportError:  # executed as a script
    from openamer_prototype import OpenAmerConfig, OpenAmerNet  # noqa: E402

THREADS = os.cpu_count() or 4
torch.set_num_threads(THREADS)

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
DATA_DIR = Path(os.environ.get("OPENAMER_BRAIN_DATA") or (Path.home() / ".openamer" / "brain_data"))
CHECKPOINT_DIR = HOME / "checkpoints"
LOG_PATH = CHECKPOINT_DIR / "train_log.jsonl"

SOURCES = [
    HOME / "a2a" / "openamer-brain.jsonl",
    HOME / "scripts" / "training" / "sft_openamer.jsonl",
    HOME / "scripts" / "training" / "online_buffer.jsonl",
]

BOOTSTRAP = (
    "OpenAmer ASI Core: 5 native tools, 10 subsystem heartbeat. "
    "Self-improving AI agent for Windows. Runs local, CPU-only, 0 EUR per day. "
    "openamer brain stats: memory graph optimal. "
) * 100


def _render_record(obj) -> str:
    """Turn one JSONL record into plain training text."""
    if not isinstance(obj, dict):
        return ""
    if "messages" in obj and isinstance(obj["messages"], list):
        parts = []
        for m in obj["messages"]:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user")
            content = m.get("content") or ""
            if isinstance(content, list):  # multimodal / content blocks
                content = " ".join(
                    str(c.get("text", "")) for c in content if isinstance(c, dict)
                )
            calls = m.get("tool_calls")
            if calls:
                content = f"{content} {json.dumps(calls, ensure_ascii=False)}".strip()
            if content:
                parts.append(f"<|{role}|> {content}")
        return "\n".join(parts)
    for key in ("text", "content", "prompt", "output", "answer"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # online_buffer.jsonl shape: {"u": question, "a": answer}
    u, a = obj.get("u"), obj.get("a")
    if isinstance(u, str) and isinstance(a, str) and (u.strip() or a.strip()):
        return f"<|user|> {u.strip()}\n<|assistant|> {a.strip()}"
    if isinstance(u, str) and u.strip():
        return u
    if isinstance(a, str) and a.strip():
        return a
    return ""


def collect_text(data_dir: Path, sources: list[Path]) -> tuple[str, dict]:
    chunks: list[str] = []
    stats: dict[str, dict] = {}

    files = list(sources)
    if data_dir.exists():
        files += [Path(p) for p in sorted(
            glob.glob(str(data_dir / "*.txt"))
            + glob.glob(str(data_dir / "*.jsonl"))
            + glob.glob(str(data_dir / "*.md"))
        )]

    for fpath in files:
        if not fpath.exists() or not fpath.is_file():
            continue
        recs = kept = 0
        buf: list[str] = []
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                if fpath.suffix == ".jsonl":
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        recs += 1
                        try:
                            txt = _render_record(json.loads(line))
                        except Exception:
                            txt = line  # keep raw line rather than drop data
                        if txt.strip():
                            buf.append(txt)
                            kept += 1
                else:
                    raw = f.read()
                    recs = kept = 1
                    buf.append(raw)
        except OSError as exc:
            stats[str(fpath)] = {"error": str(exc)}
            continue
        joined = "\n".join(buf)
        chunks.append(joined)
        stats[str(fpath)] = {"records": recs, "kept": kept, "chars": len(joined)}

    text = "\n\n".join(chunks)
    if not text.strip():
        print(f"[!] No corpus found in {data_dir} or the known brain sources. Using bootstrap patterns.")
        text = BOOTSTRAP
        stats["__bootstrap__"] = {"records": 0, "chars": len(text)}
    return text, stats


class OpenAmerTextDataset(Dataset):
    """Byte-level next-token chunks with a fixed stride (one chunk per stride/2)."""

    def __init__(self, tokens: torch.Tensor, seq_len: int, limit: int | None = None):
        self.seq_len = seq_len
        self.tokens = tokens
        self.stride = max(1, seq_len // 2)
        n = max(1, (len(tokens) - seq_len - 1) // self.stride)
        self.n = min(n, limit) if limit else n

    def __len__(self) -> int:
        return self.n

    def __getitem__(self, idx: int):
        start = idx * self.stride
        chunk = self.tokens[start : start + self.seq_len + 1]
        if len(chunk) < self.seq_len + 1:
            pad = torch.zeros(self.seq_len + 1 - len(chunk), dtype=torch.long)
            chunk = torch.cat([chunk, pad])
        return chunk[:-1], chunk[1:]


def save_checkpoint(model: OpenAmerNet, path: Path, step: int, loss: float,
                    optimizer: torch.optim.Optimizer | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep one generation of history: a short smoke run (`--steps 3`) must not
    # silently destroy a long-trained checkpoint.
    if path.exists():
        prev = path.with_name(path.stem + ".prev" + path.suffix)
        try:
            shutil.copy2(path, prev)
        except OSError:
            pass
    blob = {
        "model_state": model.state_dict(),
        "config": model.cfg.to_dict(),
        "step": step,
        "loss": loss,
    }
    if optimizer is not None:
        blob["optimizer"] = optimizer.state_dict()
    torch.save(blob, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--seq", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--val-ratio", type=float, default=0.02)
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--n-layers", type=int, default=6)
    ap.add_argument("--ckpt-every", type=int, default=50)
    ap.add_argument("--threads", type=int, default=0,
                    help="torch CPU threads (0 = auto: min(8, cores))")
    args = ap.parse_args()

    if args.threads:
        torch.set_num_threads(args.threads)
    elif THREADS > 8:
        # 16 torch threads on a 16-core box that also runs the agent, Defender
        # and cron oversubscribes and throughput collapses. 8 is the sweet spot.
        torch.set_num_threads(8)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] OpenAMER CPU Trainer — threads: {THREADS} — home: {HOME}")

    text, stats = collect_text(DATA_DIR, SOURCES)
    for src, st in stats.items():
        print(f"    {src}: {st}")

    tokens = torch.tensor(list(text.encode("utf-8")), dtype=torch.long)
    print(f"[*] Corpus: {len(tokens):,} byte tokens ({len(text):,} chars)")

    cfg = OpenAmerConfig(
        vocab_size=256,
        max_seq_len=args.seq,
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=4,
        concept_dim=64,
    )

    n_val = int(len(tokens) * args.val_ratio)
    train_tokens = tokens[: len(tokens) - n_val] if n_val > 64 else tokens
    val_tokens = tokens[len(tokens) - n_val :] if n_val > 64 else None

    ds = OpenAmerTextDataset(train_tokens, cfg.max_seq_len)
    loader = DataLoader(ds, batch_size=args.batch, shuffle=True, drop_last=True)

    model = OpenAmerNet(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    start_step = 0

    latest = CHECKPOINT_DIR / "openamer_brain_latest.pt"
    if args.resume and latest.exists():
        ckpt = torch.load(latest, map_location="cpu", weights_only=True)
        model.load_state_dict(ckpt["model_state"])
        if "optimizer" in ckpt:
            optimizer.load_state_dict(ckpt["optimizer"])
        else:
            print("[!] checkpoint has no optimizer state — optimizer restarts fresh")
        start_step = int(ckpt.get("step", 0))
        print(f"[*] Resumed from {latest} at step {start_step}")

    model.train()
    print(f"[*] Model: {model.n_params()/1e6:.2f}M params — {args.steps} steps, batch {args.batch}, seq {cfg.max_seq_len}")

    step = start_step
    t_start = time.time()
    last_loss = float("nan")
    running: list[float] = []

    def evaluate() -> float | None:
        """Mean loss over several held-out chunks.

        A single chunk is far too noisy to compare runs (it swung 2.13 vs 2.58
        at identical train loss), so average a handful of fixed offsets.
        """
        if val_tokens is None or len(val_tokens) <= cfg.max_seq_len + 1:
            return None
        model.eval()
        span = len(val_tokens) - cfg.max_seq_len - 1
        losses = []
        with torch.no_grad():
            for i in range(8):
                start = int(span * i / 8)
                chunk = val_tokens[start : start + cfg.max_seq_len + 1].unsqueeze(0)
                _, vloss = model(chunk[:, :-1], chunk[:, 1:])
                losses.append(float(vloss))
        model.train()
        return sum(losses) / len(losses)

    done = False
    for epoch in range(args.epochs):
        for x, y in loader:
            optimizer.zero_grad(set_to_none=True)
            _, loss = model(x, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            step += 1
            last_loss = float(loss.item())
            running.append(last_loss)

            if step % 10 == 0:
                elapsed = time.time() - t_start
                tok_per_sec = (10 * args.batch * cfg.max_seq_len) / max(elapsed, 1e-9)
                gate = float(torch.tanh(model.concept.gate_scale).item())
                print(
                    f"[Step {step:04d}] loss {last_loss:.4f} | {tok_per_sec:7.1f} tok/s | "
                    f"concept-gate {gate:+.3f}"
                )
                t_start = time.time()

            if step % args.ckpt_every == 0:
                save_checkpoint(model, latest, step, last_loss, optimizer)
                vloss = evaluate()
                rec = {
                    "step": step,
                    "loss": round(last_loss, 4),
                    "val_loss": None if vloss is None else round(vloss, 4),
                    "tok_per_s": round(tok_per_sec, 1),
                    "params": model.n_params(),
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as lf:
                    lf.write(json.dumps(rec) + "\n")
                print(f"[OK] checkpoint -> {latest} (step {step}, val {rec['val_loss']})")

            if step >= args.steps:
                done = True
                break
        if done:
            break

    save_checkpoint(model, latest, step, last_loss)
    mean_loss = sum(running[-50:]) / max(1, len(running[-50:]))
    print(f"[OK] training cycle finished — steps {step}, last-50 mean loss {mean_loss:.4f}")
    print(f"[OK] checkpoint: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
