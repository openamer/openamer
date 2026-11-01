"""Environment leakage must not hide missing packages in a repair target."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import openamer_cli.main as main


@pytest.fixture
def empty_python(tmp_path):
    """Use a real empty venv, not the developer interpreter's dependencies."""
    target = tmp_path / "target"
    subprocess.run(
        [sys.executable, "-I", "-m", "venv", "--without-pip", str(target)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@pytest.mark.parametrize("leak_source", ["pythonpath", "working_directory"])
def test_foreign_package_cannot_make_empty_target_look_healthy(
    tmp_path, monkeypatch, empty_python, leak_source
):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "yaml.py").write_text("SafeDumper = object()\n", encoding="utf-8")
    monkeypatch.delenv("PYTHONHOME", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    if leak_source == "pythonpath":
        monkeypatch.setenv("PYTHONPATH", str(foreign))
    else:
        monkeypatch.chdir(foreign)

    monkeypatch.setattr(main, "_resolve_install_target_python", lambda *a: empty_python)
    monkeypatch.setattr(main, "_LAZY_REFRESH_IMPORT_PROBES", (("yaml", "SafeDumper"),))

    # The target has no PyYAML. A foreign yaml.py must never satisfy its probe.
    assert main._detect_broken_lazy_refresh_imports(
        [str(empty_python), "-m", "pip"], env=dict(os.environ)
    ) == ["PyYAML"]
