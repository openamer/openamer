"""
OpenAmer Unified In-Process Service.

Binds the CPU brain directly into OpenAmer's surfaces:
  - `openamer asi think`      -> OpenAmerBrainService.think()
  - `openamer asi remember`   -> OpenAmerBrainService.remember()/recall()
  - `openamer brain stats`    -> heartbeat_tick() + corpus_stats()

The service is a singleton-ish object: construct it once per process, then
call think() per request. Lazy loading keeps process start cheap when the
brain is not used.

Usage:
    python openamer_unified.py            # self-test + heartbeat payload
    python openamer_unified.py "question" # one in-process thought
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # imported as openamer_brain.openamer_unified
    from .openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402
except ImportError:  # executed as a script
    from openamer_prototype import OpenAmerConfig, OpenAmerNet, decode, encode  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")


class OpenAmerBrainService:
    def __init__(self, checkpoint_path: str | os.PathLike | None = None, lazy: bool = False):
        self.ckpt_path = Path(checkpoint_path or HOME / "checkpoints" / "openamer_brain_latest.pt")
        self.device = "cpu"
        self.loaded = False
        self.model: OpenAmerNet | None = None
        self.cfg: OpenAmerConfig | None = None
        self.load_seconds = 0.0
        if not lazy:
            self._load_brain()

    def _load_brain(self) -> None:
        t0 = time.time()
        if self.ckpt_path.exists():
            ckpt = torch.load(self.ckpt_path, map_location="cpu", weights_only=True)
            cfg_raw = ckpt.get("config")
            self.cfg = (
                OpenAmerConfig.from_dict(cfg_raw) if isinstance(cfg_raw, dict) else cfg_raw
            )
            self.model = OpenAmerNet(self.cfg)
            self.model.load_state_dict(ckpt["model_state"])
            self.loaded = True
        else:
            self.cfg = OpenAmerConfig()
            self.model = OpenAmerNet(self.cfg)
            self.loaded = False
        self.model.eval()
        self.load_seconds = time.time() - t0

    def _ensure(self) -> OpenAmerNet:
        if self.model is None:
            self._load_brain()
        assert self.model is not None
        return self.model

    def think(self, query: str, max_tokens: int = 50, temperature: float = 0.6) -> str:
        """Called by `openamer asi think <q>`."""
        model = self._ensure()
        prompt = f"Think: {query} -> Solution: "
        ids = torch.tensor([encode(prompt)], dtype=torch.long)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=max_tokens, temperature=temperature, top_p=0.9)
        self.last_latency_ms = (time.time() - t0) * 1000
        return decode(out[0].tolist()[len(encode(prompt)):])

    def remember(self, text: str) -> dict:
        """Append a memory line to the brain corpus (raw text, anonymised later by the loop)."""
        store = HOME / "a2a" / "openamer-brain.jsonl"
        store.parent.mkdir(parents=True, exist_ok=True)
        rec = {"messages": [{"role": "assistant", "content": text}], "engine": "brain-service"}
        with open(store, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"stored": str(store), "chars": len(text)}

    def recall(self, query: str, limit: int = 3) -> list[str]:
        """Naive lexical recall over the brain corpus (no embeddings needed on CPU)."""
        store = HOME / "a2a" / "openamer-brain.jsonl"
        if not store.exists():
            return []
        q = {w for w in query.lower().split() if len(w) > 3}
        hits: list[tuple[int, str]] = []
        with open(store, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                low = line.lower()
                score = sum(1 for w in q if w in low)
                if score:
                    hits.append((score, line.strip()[:400]))
        hits.sort(key=lambda t: -t[0])
        return [h[1] for h in hits[:limit]]

    def heartbeat_tick(self) -> dict:
        """Payload for the 10-subsystem heartbeat."""
        model = self._ensure()
        assert self.cfg is not None
        return {
            "subsystem": "Brain",
            "status": "ONLINE" if self.loaded else "BOOTSTRAP",
            "device": "CPU",
            "threads": torch.get_num_threads(),
            "params": model.n_params(),
            "checkpoint": str(self.ckpt_path),
            "checkpoint_exists": self.ckpt_path.exists(),
            "load_ms": round(self.load_seconds * 1000, 1),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


if __name__ == "__main__":
    brain = OpenAmerBrainService()
    print("heartbeat:", json.dumps(brain.heartbeat_tick(), indent=2))
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"\nthink({q!r}):")
        print(brain.think(q))
    else:
        print("\nself-test thought:")
        print(repr(brain.think("optimize system load", max_tokens=24)))
