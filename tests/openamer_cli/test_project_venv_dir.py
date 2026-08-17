"""Tests for ``_project_venv_dir()`` (dev ``.venv`` vs managed ``venv``).

Regresses the ``openamer update`` failure "Failed to inspect Python interpreter
from active virtual environment at venv\\Scripts\\python.exe" seen in a dev
checkout whose virtualenv lives under ``.venv`` (VS Code / uv / an
original-development clone), while managed installs keep the plain ``venv``.
"""

from __future__ import annotations

import openamer_cli.main as m


def _make_dir(p) -> None:
    p.mkdir(parents=True, exist_ok=True)


def test_prefers_dot_venv_when_plain_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _make_dir(tmp_path / ".venv")
    assert m._project_venv_dir() == tmp_path / ".venv"


def test_prefers_plain_venv_when_dot_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _make_dir(tmp_path / "venv")
    assert m._project_venv_dir() == tmp_path / "venv"


def test_keeps_plain_venv_when_both_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _make_dir(tmp_path / "venv")
    _make_dir(tmp_path / ".venv")
    # Managed norm wins when both are present — never second-guess a provisioned
    # install just because a stray .venv happened to be created alongside it.
    assert m._project_venv_dir() == tmp_path / "venv"


def test_falls_back_to_plain_venv_when_neither_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    # No venv at all: report the plain path (matches historical behaviour).
    assert m._project_venv_dir() == tmp_path / "venv"