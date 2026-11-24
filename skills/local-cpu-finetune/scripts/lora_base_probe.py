#!/usr/bin/env python3
"""Prove which base a LoRA adapter belongs to WITHOUT downloading or loading it.

Two independent sources, compared against each other:

  1. DECLARED  -- ``adapter_config.json -> base_model_name_or_path``
  2. MEASURED  -- the safetensors header of ``adapter_model.safetensors``:
                  ``lora_A.weight`` has shape ``[r, hidden_in]``, so the second
                  dim IS the base model's hidden size. Read straight from the
                  file's JSON header; no torch, no transformers, no weights.

  3. EXPECTED  -- fetched from HF Hub: ``<base>/resolve/main/config.json``
                  (a few hundred bytes). Offline => reported as ``unmeasured``,
                  never guessed.

A DECLARED base that contradicts the MEASURED hidden size is the exact failure
that makes a retrain loop silently dead: the adapter can never attach
(`LoRA size mismatch at startup`).

Why this exists: on the no-GPU laptop the served adapter is SmolLM2-360M
(hidden 960), while ``scripts/training/tool_server.py`` on ``main`` still
hardcodes ``BASE = "Qwen/Qwen3.5-2B"`` (hidden 2048). Reading the header proves
the mismatch structurally instead of arguing from the model name.

Usage:
    python lora_base_probe.py <adapter_dir> [<adapter_dir> ...]

Exit codes: 0 = all consistent (or nothing measurable), 1 = a mismatch found,
2 = bad invocation.
"""
from __future__ import annotations

import json
import struct
import sys
import urllib.request
from pathlib import Path

_HF_CONFIG = "https://huggingface.co/{base}/resolve/main/config.json"


def _safetensors_header(path: Path) -> dict:
    """Parse the JSON header of a .safetensors file (8-byte LE length + JSON)."""
    with open(path, "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        return json.loads(fh.read(n))


def measure_hidden(path: Path) -> tuple[int | None, int | None]:
    """Return (hidden_in, r) measured from the lora_A weights, or (None, None).

    ``lora_A.weight`` is [r, hidden_in]; every layer agrees on hidden_in, so
    take the most common second dim. r is the most common first dim.
    """
    hdr = _safetensors_header(path)
    a_shapes = [tuple(v["shape"]) for k, v in hdr.items() if k.endswith("lora_A.weight")]
    if not a_shapes:
        return None, None
    hidden = max({s[1] for s in a_shapes}, key=lambda d: [s[1] for s in a_shapes].count(d))
    rank = max({s[0] for s in a_shapes}, key=lambda d: [s[0] for s in a_shapes].count(d))
    return hidden, rank


def expected_hidden(base: str) -> int | None:
    """Fetch the base's config.json from HF Hub and read hidden_size.

    Returns None (unmeasured) on any network/parse failure -- never a guess.
    """
    try:
        req = urllib.request.Request(_HF_CONFIG.format(base=base))
        with urllib.request.urlopen(req, timeout=20) as r:
            cfg = json.loads(r.read())
    except Exception:
        return None
    return cfg.get("hidden_size")


def probe(adapter_dir: Path) -> bool:
    """Print a verdict for one adapter dir. True == consistent."""
    cfg_p = adapter_dir / "adapter_config.json"
    st_p = adapter_dir / "adapter_model.safetensors"
    print(f"--- {adapter_dir}")
    if not cfg_p.exists():
        print("    adapter_config.json: MISSING -> unmeasured")
        return True
    declared = json.loads(cfg_p.read_text(encoding="utf-8")).get("base_model_name_or_path")
    print(f"    declared base : {declared or '(absent)'}")
    if not st_p.exists():
        print("    adapter_model.safetensors: MISSING -> hidden unmeasured")
        return True
    hidden, rank = measure_hidden(st_p)
    print(f"    measured hidden: {hidden}   (r={rank})   [from lora_A.weight shape]")
    if not declared or hidden is None:
        return True
    exp = expected_hidden(declared)
    if exp is None:
        print(f"    expected hidden: unmeasured (HF Hub unreachable for {declared})")
        return True
    ok = exp == hidden
    print(f"    expected hidden: {exp}   -> {'CONSISTENT' if ok else 'MISMATCH'}")
    if not ok:
        print(
            f"    !! {declared} has hidden_size {exp} but this adapter was trained at "
            f"{hidden}. These cannot attach: LoRA size mismatch at startup. The "
            f"serving BASE must be the base this adapter was trained on."
        )
    return ok


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    all_ok = True
    for raw in argv[1:]:
        d = Path(raw)
        if not d.is_dir():
            print(f"--- {raw}\n    not a directory -> skipped")
            continue
        all_ok &= probe(d)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
