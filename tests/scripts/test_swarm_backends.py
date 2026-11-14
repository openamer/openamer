"""Contract: swarm lanes come from a live spec, and a pin really pins.

The translation fleet shards by (provider, model) because a free tier's rate
limit is per model. Two things must therefore hold, and both are cheap to break
without noticing:

* a model discovered from the provider catalog reaches `backend_chain()`;
* `OPENAMER_I18N_BACKEND` narrows the chain to exactly that lane, otherwise every
  worker races every provider again and a single 429 stalls the fleet.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def fill(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "fill_swarm", REPO / "scripts" / "fill_desktop_locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "EXTRA_BACKENDS_FILE", tmp_path / "swarm-backends.json")
    monkeypatch.setattr(module, "PINNED_BACKEND", "")
    return module


def write_spec(path: Path, rows) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_discovered_lane_reaches_the_chain(fill):
    write_spec(fill.EXTRA_BACKENDS_FILE, [
        {"name": "or-gemma", "url": "https://openrouter.ai/api/v1/chat/completions",
         "key_env": "OPENROUTER_API_KEY", "model": "google/gemma-4-31b-it:free"},
    ])
    chain = fill.backend_chain({"OPENROUTER_API_KEY": "k"})
    assert ("or-gemma", "https://openrouter.ai/api/v1/chat/completions",
            "OPENROUTER_API_KEY", "google/gemma-4-31b-it:free") in chain


def test_spec_lane_without_key_is_dropped(fill):
    write_spec(fill.EXTRA_BACKENDS_FILE, [
        {"name": "or-gemma", "url": "https://x/v1", "key_env": "OPENROUTER_API_KEY",
         "model": "m"},
    ])
    assert all(cand[0] != "or-gemma" for cand in fill.backend_chain({}))


def test_keyless_lane_survives_an_empty_env(fill):
    write_spec(fill.EXTRA_BACKENDS_FILE, [
        {"name": "pollinations", "url": "https://text.pollinations.ai/openai",
         "key_env": "-", "model": "openai-fast"},
    ])
    assert any(cand[0] == "pollinations" for cand in fill.backend_chain({}))


def test_pin_narrows_the_chain_to_one_lane(fill, monkeypatch):
    write_spec(fill.EXTRA_BACKENDS_FILE, [
        {"name": "lane-a", "url": "https://a/v1", "key_env": "K", "model": "ma"},
        {"name": "lane-b", "url": "https://b/v1", "key_env": "K", "model": "mb"},
    ])
    monkeypatch.setattr(fill, "PINNED_BACKEND", "lane-b")
    names = [cand[0] for cand in fill.backend_chain({"K": "k"})]
    assert names == ["lane-b"], names


def test_malformed_spec_rows_are_ignored_not_fatal(fill):
    write_spec(fill.EXTRA_BACKENDS_FILE, [
        {"name": "ok", "url": "https://ok/v1", "key_env": "-", "model": "m"},
        {"name": "", "url": "https://no/v1", "model": "m"},
        {"url": "https://nameless/v1", "model": "m"},
        "not-a-dict",
    ])
    names = [cand[0] for cand in fill.backend_chain({})]
    assert "ok" in names
    assert all(isinstance(name, str) and name for name in names)


def test_unreadable_spec_keeps_the_builtin_chain(fill):
    fill.EXTRA_BACKENDS_FILE.write_text("{ not json", encoding="utf-8")
    names = [cand[0] for cand in fill.backend_chain({"OLLAMA_API_KEY": "k"})]
    assert "ollama-deepseek" in names


def test_untranslated_locales_are_the_empty_ones(tmp_path, monkeypatch):
    """--only-empty must spend lanes on the gap, not on finished work."""
    spec = importlib.util.spec_from_file_location(
        "swarm_launcher", REPO / "scripts" / "start_translation_swarm.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher, "HOME", tmp_path)
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "desktop_aa.json").write_text('{"a.b": "Galtó"}', encoding="utf-8")
    (tmp_path / "tmp" / "desktop_ab.json").write_text('{"a.b": ""}', encoding="utf-8")
    empty = launcher.untranslated_locales()
    assert "aa" not in empty, "a locale with content must not consume a lane"
    assert "ab" in empty, "an empty cache must be scheduled"
