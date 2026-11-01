"""
OpenAmer Prototype — the CPU brain.

Byte-level (vocab 256) decoder-only transformer with two OpenAmer-specific
ingredients:

  * SpectralMix    — learned global mixing in the frequency domain (rFFT),
                     cheap on CPU and gives every token a full-sequence
                     receptive field at O(n log n) instead of O(n^2).
  * ConceptBottleneck — a narrow concept slot between blocks with a memory
                     gate that keeps activations from drifting (the
                     "memory-gate stabilization" the trainer relies on).

No GPU, no external deps beyond torch (CPU build). Everything is
deterministic given a seed, so checkpoints are reproducible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class OpenAmerConfig:
    vocab_size: int = 256
    max_seq_len: int = 256
    d_model: int = 256
    n_layers: int = 6
    n_heads: int = 4
    concept_dim: int = 64
    dropout: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OpenAmerConfig":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class SpectralMix(nn.Module):
    """Causal spectral mixing along the sequence axis.

    A learned FIR kernel per channel, applied as a convolution (i.e. a
    multiplication in the frequency domain) and evaluated with rFFT. The
    kernel is left-aligned, so output t depends only on inputs <= t — no
    future leak. The kernel starts as a delta (identity), so the layer is a
    no-op at init and learning is stable.

    Input (B, T, C) -> (B, T, C).
    """

    def __init__(self, max_seq_len: int, d_model: int, kernel_size: int = 32):
        super().__init__()
        self.kernel_size = kernel_size
        w = torch.zeros(kernel_size, d_model)
        w[0] = 1.0  # delta -> identity at init
        self.weight = nn.Parameter(w)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, cache: dict | None = None) -> torch.Tensor:
        B, T, C = x.shape
        K = self.kernel_size
        n = T + K - 1
        spec_x = torch.fft.rfft(x.transpose(1, 2), n=n, dim=-1)          # (B, C, F)
        spec_w = torch.fft.rfft(self.weight.t(), n=n, dim=-1)            # (C, F)
        out = torch.fft.irfft(spec_x * spec_w.unsqueeze(0), n=n, dim=-1)  # (B, C, n)
        out = out[..., :T].transpose(1, 2)                                # (B, T, C) causal
        if cache is not None:
            cache["buf"] = x[:, -(K - 1):]
        return self.norm(x + out)

    def step(self, x: torch.Tensor, cache: dict) -> torch.Tensor:
        """Single-position causal FIR using the cached recent inputs."""
        K = self.kernel_size
        buf = cache.get("buf")
        seq = x if buf is None or buf.shape[1] == 0 else torch.cat([buf, x], dim=1)
        cache["buf"] = seq[:, -(K - 1):]
        L = seq.shape[1]
        w = self.weight[:L]                       # w[k] pairs with x[t-k]
        y = (seq.flip(1) * w.unsqueeze(0)).sum(dim=1, keepdim=True)  # (B, 1, C)
        return self.norm(x + y)


class Attention(nn.Module):
    def __init__(self, cfg: OpenAmerConfig):
        super().__init__()
        assert cfg.d_model % cfg.n_heads == 0, "d_model must divide by n_heads"
        self.n_heads = cfg.n_heads
        self.head_dim = cfg.d_model // cfg.n_heads
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.dropout = cfg.dropout

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None,
                cache: dict | None = None) -> torch.Tensor:
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        if cache is not None:
            cache["k"], cache["v"] = k, v
        out = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=mask,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=mask is None,
        )
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(out)

    def step(self, x: torch.Tensor, cache: dict) -> torch.Tensor:
        """Single-position forward with a KV cache (used by generate)."""
        B, T, C = x.shape
        assert T == 1, "step() takes exactly one position"
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, 1, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, 1, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, 1, self.n_heads, self.head_dim).transpose(1, 2)
        if cache.get("k") is not None:
            k = torch.cat([cache["k"], k], dim=2)
            v = torch.cat([cache["v"], v], dim=2)
        cache["k"], cache["v"] = k, v
        out = F.scaled_dot_product_attention(q, k, v, attn_mask=None, is_causal=False)
        out = out.transpose(1, 2).contiguous().view(B, 1, C)
        return self.proj(out)


class ConceptBottleneck(nn.Module):
    """Narrow concept slot + memory gate.

    hidden -> concept_dim -> hidden, with a sigmoid gate produced from the
    concept vector. The gate is initialized near 0.5 and the residual is
    scaled by `gate_scale`, which is what keeps long runs from blowing up
    ("memory-gate stabilization").
    """

    def __init__(self, cfg: OpenAmerConfig):
        super().__init__()
        d, c = cfg.d_model, cfg.concept_dim
        self.down = nn.Linear(d, c, bias=False)
        self.up = nn.Linear(c, d, bias=False)
        self.gate = nn.Linear(c, d, bias=True)
        self.gate_scale = nn.Parameter(torch.tensor(0.5))
        self.norm = nn.LayerNorm(d)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        concept = F.gelu(self.down(x))
        g = torch.sigmoid(self.gate(concept))
        upd = self.up(concept) * g * torch.tanh(self.gate_scale)
        return self.norm(x + upd)


class Block(nn.Module):
    def __init__(self, cfg: OpenAmerConfig):
        super().__init__()
        self.norm1 = nn.LayerNorm(cfg.d_model)
        self.attn = Attention(cfg)
        self.norm2 = nn.LayerNorm(cfg.d_model)
        self.ff = nn.Sequential(
            nn.Linear(cfg.d_model, 4 * cfg.d_model),
            nn.GELU(),
            nn.Linear(4 * cfg.d_model, cfg.d_model),
        )

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None,
                cache: dict | None = None) -> torch.Tensor:
        x = x + self.attn(self.norm1(x), mask, cache)
        x = x + self.ff(self.norm2(x))
        return x

    def step(self, x: torch.Tensor, cache: dict) -> torch.Tensor:
        x = x + self.attn.step(self.norm1(x), cache)
        x = x + self.ff(self.norm2(x))
        return x


class OpenAmerNet(nn.Module):
    def __init__(self, cfg: OpenAmerConfig):
        super().__init__()
        self.cfg = cfg
        c = cfg.d_model
        self.tok_emb = nn.Embedding(cfg.vocab_size, c)
        self.pos_emb = nn.Embedding(cfg.max_seq_len, c)
        self.spectral = SpectralMix(cfg.max_seq_len, c)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layers)])
        self.concept = ConceptBottleneck(cfg)
        self.norm_f = nn.LayerNorm(c)
        self.head = nn.Linear(c, cfg.vocab_size, bias=False)
        self.head.weight = self.tok_emb.weight  # weight tying
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def _fit_len(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        """Crop to max_seq_len. Deliberately does NOT pad.

        SpectralMix builds its FFT length from the actual T, so padding buys
        nothing — and padding every decode step to 256 positions made
        generation ~12x slower than it needed to be.
        """
        T = x.shape[1]
        target = self.cfg.max_seq_len
        if T > target:
            x = x[:, -target:]
            T = target
        return x, T

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None,
                cache: dict | None = None):
        idx, orig = self._fit_len(idx)
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device).unsqueeze(0).expand(B, T)
        x = self.tok_emb(idx) + self.pos_emb(pos)
        x = self.spectral(x, None if cache is None else cache["spectral"])
        mask = None
        if cache is None:
            mask = torch.ones(T, T, dtype=torch.bool, device=idx.device).tril()
        for i, blk in enumerate(self.blocks):
            x = blk(x, mask, None if cache is None else cache["attn"][i])
        x = self.concept(x)
        logits = self.head(self.norm_f(x))

        loss = None
        if targets is not None:
            tgt = torch.full_like(idx, -100)
            tgt[:, :orig] = targets
            logits = logits[:, :orig]
            tgt = tgt[:, :orig]
            loss = F.cross_entropy(
                logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), ignore_index=-100
            )
        return logits, loss

    @torch.no_grad()
    def forward_step(self, tok: torch.Tensor, cache: dict) -> torch.Tensor:
        """One position, one step — attention and FIR read their state from cache."""
        B = tok.shape[0]
        pos = torch.full((B, 1), cache["pos"], dtype=torch.long, device=tok.device)
        x = self.tok_emb(tok) + self.pos_emb(pos)
        x = self.spectral.step(x, cache["spectral"])
        for i, blk in enumerate(self.blocks):
            x = blk.step(x, cache["attn"][i])
        x = self.concept(x)
        cache["pos"] += 1
        return self.head(self.norm_f(x))

    def new_cache(self) -> dict:
        return {"spectral": {}, "attn": [{} for _ in self.blocks], "pos": 0}

    def _sample(self, next_logits: torch.Tensor, temperature: float, top_p: float) -> torch.Tensor:
        next_logits = next_logits / max(temperature, 1e-6)
        if top_p < 1.0:
            sorted_logits, sorted_idx = torch.sort(next_logits, descending=True, dim=-1)
            probs = F.softmax(sorted_logits, dim=-1)
            cum = probs.cumsum(dim=-1)
            keep = cum - probs <= top_p
            keep[..., 0] = True
            filtered = torch.full_like(sorted_logits, float("-inf"))
            filtered[keep] = sorted_logits[keep]
            next_logits = torch.full_like(next_logits, float("-inf")).scatter(
                1, sorted_idx, filtered
            )
        return torch.multinomial(F.softmax(next_logits, dim=-1), 1)

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 40,
        temperature: float = 1.0,
        top_p: float = 1.0,
        use_cache: bool = True,
    ) -> torch.Tensor:
        self.eval()
        ids = input_ids[:, -self.cfg.max_seq_len:]
        cache = None
        next_logits = None

        if use_cache:
            cache = self.new_cache()
            cache["pos"] = ids.shape[1]
            logits, _ = self(ids, cache=cache)
            next_logits = logits[:, -1, :]

        for _ in range(max_new_tokens):
            if next_logits is None:
                ctx = ids[:, -self.cfg.max_seq_len:]
                logits, _ = self(ctx)
                next_logits = logits[:, -1, :]
            next_tok = self._sample(next_logits, temperature, top_p)
            ids = torch.cat([ids, next_tok], dim=1)
            if cache is not None and ids.shape[1] < self.cfg.max_seq_len:
                next_logits = self.forward_step(next_tok, cache)[:, -1, :]
            else:
                cache = None          # context full: fall back to full recompute
                next_logits = None
        return ids

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


def encode(text: str) -> list[int]:
    return list(text.encode("utf-8"))


def decode(ids) -> str:
    return bytes(int(i) % 256 for i in ids).decode("utf-8", errors="replace")


if __name__ == "__main__":
    torch.manual_seed(0)
    cfg = OpenAmerConfig()
    net = OpenAmerNet(cfg)
    x = torch.randint(0, 256, (2, 64))
    logits, loss = net(x, x)
    print(f"params: {net.n_params()/1e6:.2f}M  logits: {tuple(logits.shape)}  loss: {loss.item():.4f}")
    out = net.generate(torch.tensor([encode("OpenAmer ")]), max_new_tokens=16, top_p=0.9)
    print("sample:", decode(out[0].tolist()))
