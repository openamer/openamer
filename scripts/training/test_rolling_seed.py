#!/usr/bin/env python3
"""Guard: the rolling chain must not discard batch (GPU) training.

Regression target (observed live 2026-09-11): `mini_step.py` only ever resumed
`lora_out/adapter_rolling` (or started fresh from BASE). A full batch GPU run
over the whole curated distilled set — `lora_out/adapter_gpu_<date>` — was
therefore invisible to the chain: the very next mini-step resumed the older
rolling adapter and the GPU work was gone. The 84-pair GPU adapter was live for
about 19 minutes, then silently replaced.

The fix seeds the chain from the best UNABSORBED adapter, tracking what it last
absorbed in `.rolling_seed`. Plain "newest file wins" is NOT enough — once the
rolling chain writes, it becomes the newest file and would hide a better batch
adapter forever. These tests pin both halves.
"""
import json
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).parent / "mini_step.py"


def _source():
    return SRC.read_text(encoding="utf-8")


def test_seed_tracking_exists():
    """The chain must record what it was last seeded from."""
    src = _source()
    assert "SEED_MARK" in src, "no seed marker — batch adapters can be re-absorbed forever"
    assert ".rolling_seed" in src, "seed marker file name missing"


def test_seed_prefers_unabsorbed_batch_adapter():
    """An unabsorbed adapter_gpu* dir must outrank the rolling chain."""
    src = _source()
    assert "adapter_gpu*" in src, "batch adapter dirs are not considered at all"
    # the comparison against the absorbed name must be present
    assert re.search(r"c\.name\s*!=\s*absorbed", src), \
        "no check against the absorbed name — newest-wins would hide batch runs"


def test_rolling_still_used_when_nothing_new():
    """With no unabsorbed batch adapter, the chain resumes ROLLING."""
    src = _source()
    assert "return ROLLING" in src


def test_seed_shape_matches_rolling_config():
    """A seed adapter with a different LoRA shape would crash the load.

    All adapters on this box must be r=16, alpha=32 over the same 4 targets.
    If a future training run changes the shape, the seed logic must not pick it
    blindly — this test documents the invariant that keeps the swap safe.
    """
    root = pathlib.Path(__file__).parent / "lora_out"
    if not root.exists():
        return  # nothing on disk in a bare checkout
    shapes = {}
    for cfg in root.glob("adapter*/adapter_config.json"):
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        shapes[cfg.parent.name] = (
            d.get("r"), d.get("lora_alpha"),
            tuple(sorted(d.get("target_modules") or [])),
        )
    if not shapes:
        return
    distinct = set(shapes.values())
    assert len(distinct) == 1, (
        f"adapters have mismatched LoRA shapes — a seed swap would crash: {shapes}")


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  [PASS] {name}")
            except Exception as e:
                fails += 1
                print(f"  [FAIL] {name}: {e}")
    print(f"\n{'FAILED' if fails else 'OK'}: {fails} failure(s)")
    sys.exit(1 if fails else 0)
