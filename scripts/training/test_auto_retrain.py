#!/usr/bin/env python3
"""Regression guard: auto_retrain must run its training children under the
TRAINING venv, never under the interpreter that happens to launch the cron.

Live bug (12.09): the cron wrapper runs under openamer-agent/venv (agent env,
huggingface-hub 1.2.3). auto_retrain used ``sys.executable`` for distill_sft /
finetune_cpu, so the training subprocess resolved transformers' requirement
(huggingface-hub>=1.5.0) against the AGENT venv and died instantly:

    ImportError: huggingface-hub>=1.5.0,<2.0 is required ... found 1.2.3

The fix: ``_train_python()`` picks the dedicated training venv and ``sh()``
strips PYTHONPATH from the child env (the agent shell exports a PYTHONPATH that
shadows the training venv's site-packages).

These tests are hermetic: no training runs, no venv is required on disk.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auto_retrain as ar


def test_no_bare_sys_executable_for_training_children():
    """The training children must be launched with PY, not sys.executable."""
    src = (Path(ar.__file__)).read_text(encoding="utf-8")
    assert "sh([sys.executable" not in src, (
        "auto_retrain still launches a training child with sys.executable — "
        "it resolves transformers against the AGENT venv and dies with "
        "ImportError huggingface-hub>=1.5.0"
    )
    assert src.count("sh([PY,") == 2, "both distill_sft and finetune_cpu must use PY"


def test_train_python_prefers_env_override(monkeypatch):
    """OPENAMER_TRAIN_PYTHON wins when it points at a real file."""
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as fh:
        fake = fh.name
    try:
        monkeypatch.setenv("OPENAMER_TRAIN_PYTHON", fake)
        assert ar._train_python() == fake
    finally:
        os.unlink(fake)


def test_train_python_falls_back_to_sys_executable(monkeypatch, tmp_path):
    """With no env override and no venv anywhere, fall back to sys.executable."""
    monkeypatch.delenv("OPENAMER_TRAIN_PYTHON", raising=False)
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "empty"))  # no venv here
    monkeypatch.setattr(ar, "T", tmp_path / "scripts" / "training")  # no venv here
    assert ar._train_python() == sys.executable


def test_train_python_finds_home_venv(monkeypatch, tmp_path):
    """The training venv lives at $OPENAMER_HOME/venv (next to the scripts tree)."""
    monkeypatch.delenv("OPENAMER_TRAIN_PYTHON", raising=False)
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    py = tmp_path / "venv" / "Scripts" / "python.exe"
    py.parent.mkdir(parents=True)
    py.write_text("")
    monkeypatch.setattr(ar, "T", tmp_path / "somewhere" / "training")  # no venv here
    assert Path(ar._train_python()).resolve() == py.resolve()


def test_train_python_finds_venv_beside_training_dir(monkeypatch, tmp_path):
    """Fallback: a venv sitting beside the training dir is still found."""
    monkeypatch.delenv("OPENAMER_TRAIN_PYTHON", raising=False)
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "empty-home"))  # no venv there
    train_dir = tmp_path / "scripts" / "training"
    train_dir.mkdir(parents=True)
    py = tmp_path / "scripts" / "venv" / "Scripts" / "python.exe"
    py.parent.mkdir(parents=True)
    py.write_text("")
    monkeypatch.setattr(ar, "T", train_dir)
    assert Path(ar._train_python()).resolve() == py.resolve()


def test_sh_strips_pythonpath(monkeypatch, tmp_path):
    """sh() must not leak the agent shell's PYTHONPATH into training children.

    This is the second half of the same bug class: a PYTHONPATH pointing at the
    agent venv's site-packages is searched BEFORE the training venv's own, so
    the wrong huggingface_hub wins again even with the right interpreter.
    """
    monkeypatch.setenv("PYTHONPATH", "C:/definitely/should/not/leak")
    if os.name == "nt":
        out = ar.sh([sys.executable, "-c",
                     "import os; print(os.environ.get('PYTHONPATH', '<unset>'))"],
                    timeout=60)
    else:
        out = ar.sh([sys.executable, "-c",
                     "import os; print(os.environ.get('PYTHONPATH', '<unset>'))"],
                    timeout=60)
    assert out.strip() == "<unset>", f"PYTHONPATH leaked into child: {out!r}"


def test_sh_raises_on_nonzero_exit():
    """A failing child must surface as RuntimeError with its captured output."""
    with pytest.raises(RuntimeError) as exc:
        ar.sh([sys.executable, "-c",
               "import sys; sys.stderr.write('boom'); sys.exit(3)"], timeout=60)
    assert "boom" in str(exc.value)
