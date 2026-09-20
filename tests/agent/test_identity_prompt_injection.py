"""The measured identity block must reach the system prompt -- and must not be
able to break agent init when it is absent, empty, or poisoned.

SOUL.md is the operator's prose and is deliberately cache-stable. The identity
block is a different thing: it is RENDERED from measurements, so it changes
whenever the system does. Wiring it in is what lets the agent state its own
figures instead of being told them -- and the rule that comes with that is
"never state a number you have not just measured", so the block has to travel
with its provenance and be refreshable rather than frozen.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture()
def pb(monkeypatch, tmp_path):
    """Import prompt_builder with OPENAMER_HOME pointed at a scratch tree."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAMER_CONFIG_DIR", str(tmp_path))
    import openamer_cli.config as cfg

    monkeypatch.setattr(cfg, "get_openamer_home", lambda: tmp_path, raising=False)
    import agent.prompt_builder as mod

    importlib.reload(mod)
    monkeypatch.setattr(mod, "get_openamer_home", lambda: tmp_path, raising=False)
    return mod, tmp_path


def _write_identity(home: Path, body: str) -> Path:
    d = home / "memory" / "identity"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "identity.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_returns_none_when_the_identity_file_is_absent(pb):
    """A fresh install has no rendered identity; init must not fail on that."""
    mod, home = pb
    assert not (home / "memory" / "identity" / "identity.md").exists()
    assert mod.load_identity_md() is None


def test_returns_none_for_an_empty_file(pb):
    """An empty file is indistinguishable from 'nothing measured yet'."""
    mod, home = pb
    _write_identity(home, "   \n\n  ")
    assert mod.load_identity_md() is None


def test_returns_the_rendered_identity_when_present(pb):
    mod, home = pb
    _write_identity(home, "# OpenAmer -- Identity\n\nI am a system, not a model.\n")
    out = mod.load_identity_md()
    assert out is not None
    assert "I am a system, not a model." in out


def test_unreadable_file_degrades_to_none_instead_of_raising(pb):
    """The identity slot is best-effort: a read failure must never break init.

    The path exists but cannot be read as text -- represented by a directory,
    because chmod 0o000 does not make a file unreadable on Windows. Either way
    the reader raises OSError (IsADirectoryError here), and the loader must
    swallow it and report "no identity" rather than propagate.
    """
    mod, home = pb
    path = home / "memory" / "identity" / "identity.md"
    path.mkdir(parents=True, exist_ok=True)
    assert path.exists() and path.is_dir()
    assert mod.load_identity_md() is None


def test_context_files_prompt_includes_the_identity_block(pb):
    """The wiring itself: it must actually reach the assembled prompt."""
    mod, home = pb
    _write_identity(home, "# OpenAmer -- Identity\n\nborn 2026-09-01\n")
    prompt = mod.build_context_files_prompt(cwd=str(home), skip_soul=True)
    assert "born 2026-09-01" in prompt


def test_context_files_prompt_survives_a_missing_identity(pb):
    """Absent identity must leave the prompt usable, not empty or broken."""
    mod, home = pb
    (home / "AGENTS.md").write_text("project rules here", encoding="utf-8")
    prompt = mod.build_context_files_prompt(cwd=str(home), skip_soul=True)
    assert "project rules here" in prompt


def test_identity_is_not_folded_into_soul(pb):
    """They are separate slots on purpose.

    SOUL.md must stay byte-stable for prefix caching, so the volatile measured
    block is appended separately rather than rewritten into it.
    """
    mod, home = pb
    (home / "SOUL.md").write_text("operator prose", encoding="utf-8")
    _write_identity(home, "# OpenAmer -- Identity\n\nmeasured-marker\n")

    with_soul = mod.build_context_files_prompt(cwd=str(home), skip_soul=False)
    assert "operator prose" in with_soul
    assert "measured-marker" in with_soul

    without_soul = mod.build_context_files_prompt(cwd=str(home), skip_soul=True)
    assert "operator prose" not in without_soul
    assert "measured-marker" in without_soul
