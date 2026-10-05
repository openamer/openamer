"""Regression: the retrain loop must train the SERVED base and land in the served path.

Two bugs broke the nightly self-training loop (found 2026-10-05):

1. BASE MISMATCH — finetune_cpu.py trained Qwen2.5-1.5B, but tool_server.py
   serves SmolLM2-360M + lora_out/adapter. An adapter for a different base can
   never load, so every retrain was wasted and the loop never closed.
2. WRONG OUTPUT DIR — it wrote lora_out_qwen25/, while the hot-swap copies
   lora_out/adapter — so the swap moved an unchanged directory.

Values are read as source (regex/JSON), NOT imported: finetune_cpu.py imports
torch, which the canonical test venv (openamer-agent/.venv) does not carry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
T = HOME / "scripts" / "training"
FINETUNE_SRC = (T / "finetune_cpu.py").read_text(encoding="utf-8")
RETRAIN_SRC = (T / "auto_retrain.py").read_text(encoding="utf-8")
ADAPTER_CFG = json.loads((T / "lora_out" / "adapter" / "adapter_config.json").read_text(encoding="utf-8"))


def _const(name: str) -> str:
    m = re.search(rf'^{name}\s*=\s*"([^"]+)"', FINETUNE_SRC, re.M)
    assert m, f"{name} not found in finetune_cpu.py"
    return m.group(1)


def test_trainer_base_matches_served_adapter():
    """The single invariant that makes the whole loop work."""
    served = ADAPTER_CFG["base_model_name_or_path"]
    assert _const("BASE") == served, f"trainer base {_const('BASE')!r} != served base {served!r}"


def test_trainer_output_is_the_served_path():
    """lora_out (not lora_out_qwen25) — where the hot-swap and server look.
    Note: the docstring mentions lora_out_qwen25 (it documents the old bug),
    so assert on the OUT assignment, not on the whole file."""
    assert 'else "lora_out")' in FINETUNE_SRC          # non-smoke target
    assert '"lora_out_smoke" if _SMOKE' in FINETUNE_SRC
    # the served directory must be the one the hot-swap reads
    assert 'T / "lora_out" / "adapter"' in RETRAIN_SRC


def test_retrain_backs_up_before_training():
    """A backup taken AFTER finetune copies the NEW adapter — no rollback.
    The copytree must appear before the finetune call in source order."""
    backup_at = RETRAIN_SRC.index("copytree(adapter, backup)")
    train_at = RETRAIN_SRC.index('"finetune_cpu.py"')
    assert backup_at < train_at, "adapter backup must precede training (rollback safety)"


def test_smoke_mode_writes_a_throwaway_dir():
    """--smoke must never clobber the production adapter."""
    assert "lora_out_smoke" in FINETUNE_SRC and '"--smoke"' in FINETUNE_SRC
