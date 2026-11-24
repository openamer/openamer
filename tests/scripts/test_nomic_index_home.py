"""Tests for scripts/bench/nomic_index.py — install-home resolution.

The script used to derive its data root from `Path(__file__).parents[2]`, which
is the install home only while the file sits in `<home>/scripts/bench/`. As soon
as it was published to a checkout, that expression resolved to the repository
root and the store, the index and the delta all pointed at paths that do not
exist there. Nothing would have failed loudly at import time — the builder would
simply have reported an empty store and rebuilt an index from nothing.

These tests pin the resolution order (OPENAMER_HOME wins, then the platform
default) and, most importantly, that the data root is not the checkout.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bench" / "nomic_index.py"


def load(home: Path):
    spec = importlib.util.spec_from_file_location("nomic_index_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # module level holds only paths: no I/O
    return module


@pytest.fixture()
def home(tmp_path, monkeypatch):
    directory = tmp_path / "install-home"
    (directory / "memory").mkdir(parents=True)
    monkeypatch.setenv("OPENAMER_HOME", str(directory))
    return directory


def test_base_follows_openamer_home(home):
    module = load(home)

    assert module.BASE == home.resolve()


def test_data_root_is_not_the_checkout(home):
    """The regression: parents[2] is the repo root for the published copy."""
    module = load(home)

    assert module.BASE != SCRIPT.parents[2]


def test_store_index_and_delta_all_live_under_the_same_root(home):
    module = load(home)
    root = home.resolve()

    assert module.STORE == root / "memory" / "longterm_episodes.jsonl"
    assert module.INDEX == root / "memory" / "embeddings-nomic.npz"
    assert module.DELTA == root / "memory" / "embeddings-nomic-delta.jsonl"


def test_without_the_env_var_the_platform_default_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAMER_HOME", raising=False)

    module = load(tmp_path)

    default = (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
    assert module.BASE == default
    assert module.BASE != SCRIPT.parents[2]
