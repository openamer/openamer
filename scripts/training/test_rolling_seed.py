#!/usr/bin/env python3
"""Guard: the rolling chain must not discard batch (GPU) training.

Regression (observed live 2026-09-11): `mini_step.py` only ever resumed
`lora_out/adapter_rolling` (or started fresh from BASE), so a batch GPU run over
the whole curated distilled set was invisible to the chain — the next mini-step
resumed the older rolling adapter and the GPU work was gone. The 84-pair GPU
adapter was live ~19 min, then silently replaced.

The fix seeds from the best UNABSORBED adapter, tracking what it last absorbed
in `.rolling_seed`. Plain "newest wins" is also wrong: once the chain writes it
becomes the newest file and would hide a batch adapter forever.

These tests exercise `pick_seed()` behaviour directly on a synthetic tree —
no model loading, no dependency on the live `lora_out`.
"""
import ast
import importlib.util
import json
import pathlib
import sys
import tempfile

SRC = pathlib.Path(__file__).parent / "mini_step.py"


_HEAVY = {"torch", "transformers", "peft"}


def _load_pick_seed():
    """Extract ONLY the seed helpers — importing the module pulls in torch,
    which the repo venv lacks (training deps live in a separate venv)."""
    ns = {"__name__": "mini_step_seed", "os": __import__("os"),
          "pathlib": pathlib, "Path": pathlib.Path}
    for node in ast.parse(SRC.read_text(encoding="utf-8")).body:
        heavy = isinstance(node, ast.Import) and any(a.name in _HEAVY for a in node.names)
        heavy |= isinstance(node, ast.ImportFrom) and node.module in _HEAVY
        if heavy:
            continue
        wanted = isinstance(node, ast.FunctionDef) and node.name in ("pick_seed", "_adapter_mtime")
        wanted |= isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") in ("T", "ROLLING", "SEED_MARK") for t in node.targets)
        if wanted:
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(SRC), "exec"), ns)
    return ns["pick_seed"]


pick_seed = _load_pick_seed()


def _tree(tmp):
    """Build a fake lora_out with one batch adapter and a rolling chain."""
    lora = pathlib.Path(tmp) / "lora_out"
    batch = lora / "adapter_gpu_20260101"
    rolling = lora / "adapter_rolling"
    for d, ts in ((batch, 1000), (rolling, 2000)):
        d.mkdir(parents=True)
        (d / "adapter_model.safetensors").write_bytes(b"x")
        import os
        os.utime(d / "adapter_model.safetensors", (ts, ts))
    mark = pathlib.Path(tmp) / ".rolling_seed"
    return lora, batch, rolling, mark


def test_unabsorbed_batch_outranks_the_rolling_chain():
    """The whole point: fresh GPU work must be picked up, even though the
    rolling file has a NEWER mtime."""
    with tempfile.TemporaryDirectory() as tmp:
        lora, batch, rolling, mark = _tree(tmp)
        got = pick_seed(lora_dir=lora, rolling=rolling, mark=mark)
        assert got == batch, f"expected the batch adapter, got {got}"


def test_absorbed_batch_falls_back_to_rolling():
    """Once absorbed, the chain continues from its own newest state."""
    with tempfile.TemporaryDirectory() as tmp:
        lora, batch, rolling, mark = _tree(tmp)
        mark.write_text(batch.name, encoding="utf-8")
        got = pick_seed(lora_dir=lora, rolling=rolling, mark=mark)
        assert got == rolling, f"expected the rolling chain, got {got}"


def test_a_newer_batch_after_absorption_is_picked_up():
    """A second GPU run must not be blocked by the first one's marker."""
    with tempfile.TemporaryDirectory() as tmp:
        lora, batch, rolling, mark = _tree(tmp)
        mark.write_text(batch.name, encoding="utf-8")
        newer = lora / "adapter_gpu_20260202"
        newer.mkdir()
        (newer / "adapter_model.safetensors").write_bytes(b"y")
        import os
        os.utime(newer / "adapter_model.safetensors", (3000, 3000))
        got = pick_seed(lora_dir=lora, rolling=rolling, mark=mark)
        assert got == newer, f"expected the newer batch adapter, got {got}"


def test_seedless_dir_is_never_chosen():
    """A dir without weights must not be offered as a seed (it would crash)."""
    with tempfile.TemporaryDirectory() as tmp:
        lora, batch, rolling, mark = _tree(tmp)
        (batch / "adapter_model.safetensors").unlink()   # batch is now unusable
        got = pick_seed(lora_dir=lora, rolling=rolling, mark=mark)
        assert got == rolling, f"expected to skip the weightless dir, got {got}"


def test_no_candidates_returns_none():
    """Empty tree -> None, so the caller trains a fresh LoRA."""
    with tempfile.TemporaryDirectory() as tmp:
        lora = pathlib.Path(tmp) / "lora_out"
        lora.mkdir()
        assert pick_seed(lora_dir=lora, rolling=lora / "nope",
                            mark=pathlib.Path(tmp) / ".rolling_seed") is None


def test_live_adapters_share_one_lora_shape():
    """A seed with a different shape would crash PeftModel.from_pretrained."""
    root = pathlib.Path(__file__).parent / "lora_out"
    shapes = {}
    for cfg in root.glob("adapter*/adapter_config.json"):
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        shapes[cfg.parent.name] = (d.get("r"), d.get("lora_alpha"),
                                   tuple(sorted(d.get("target_modules") or [])))
    if shapes:
        assert len(set(shapes.values())) == 1, f"mismatched LoRA shapes: {shapes}"


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
