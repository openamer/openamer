"""The backup predicate must be judged on real names, not on clean ones.

Measured 2026-11-20 on this install: `$OPENAMER_HOME/scripts` holds **41 GB**, and
8.4 GB of it sat in files a last-suffix check lets through:

| file | size | last suffix | why a naive check missed it |
|---|---|---|---|
| `training/models/qwen2.5-1.5b-onnx-directml/model.onnx_data` | 7.1 GB | `.onnx_data` | not in the extension set at all |
| `training/mini-openamer-2b-q4.gguf.prev-1793395879` | 1.3 GB | `.prev-1793395879` | the weight suffix is not the last one |

The consequence was a 5.3 GB `scripts.zip` per day and 59 GB of backups on a
disk at 95%. `_keep()` therefore tests **every** suffix of the name.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import zipfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "auto-backup.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("auto_backup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("rel", [
    "training/models/qwen2.5-1.5b-onnx-directml/model.onnx_data",
    "training/mini-openamer-2b-q4.gguf.prev-1793395879",
    "training/mini-openamer-f16.gguf",
    "training/Mini_OpenAmer_2B/model.safetensors",
    "training/merged/model.safetensors",
    "training/lora_out/adapter_model.bin",
    "training/state.pt",
    "__pycache__/x.cpython-311.pyc",
    "training/scripts.tmp.zip",
])
def test_derived_bulk_is_not_backed_up(mod, tmp_path, rel):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")
    assert mod._keep(f) is False


@pytest.mark.parametrize("rel", [
    "training/online_buffer.jsonl",
    "cron-watchdog.py",
    "internet_learn_log.jsonl",
    "training/model_config.py",
])
def test_state_is_backed_up(mod, tmp_path, rel):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x", encoding="utf-8")
    assert mod._keep(f) is True


def test_zip_skips_the_weights(mod, tmp_path):
    """End to end through the real zipper: the bytes must not reach the archive."""
    src = tmp_path / "scripts"
    (src / "training").mkdir(parents=True)
    (src / "tool.py").write_text("print('state')\n", encoding="utf-8")
    (src / "training" / "online_buffer.jsonl").write_text("{}\n", encoding="utf-8")
    weights = src / "training" / "mini-openamer-f16.gguf"
    weights.write_bytes(b"W" * (2 * 1024 * 1024))
    rotated = src / "training" / "mini-openamer-2b-q4.gguf.prev-1793395879"
    rotated.write_bytes(b"V" * (2 * 1024 * 1024))
    onnx = src / "training" / "model.onnx_data"
    onnx.write_bytes(b"O" * (2 * 1024 * 1024))

    out = tmp_path / "scripts.zip"
    mod._zip_directory(src, out, encrypt=False, key=None)

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        total = sum(info.file_size for info in zf.infolist())

    assert names == {"tool.py", "training/online_buffer.jsonl"}
    assert total < 1024, f"archive carries derived bulk: {total} bytes"
