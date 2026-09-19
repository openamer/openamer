#!/usr/bin/env python3
"""Regression test: a scratch OPENAMER_HOME must never be adopted as the install.

Bug (observed live 2026-09-19): the cron shell exported
``OPENAMER_HOME=/c/tmp/oa-home``. Native Windows Python read that MSYS form as
a RELATIVE path and expanded it to a phantom ``C:\\c\\tmp\\oa-home`` tree, which
merely EXISTED (an earlier run had created it). Every nightly script that
resolved ``OPENAMER_HOME`` without checking it was a real install then ran
against that empty directory:

* ``dream_cycle.py`` replayed **0 messages** from the phantom ``state.db`` and
  printed a clean "Clear night, no error motifs" report while the real
  ``state.db`` held hundreds of messages for the day (later: 866).
* ``memory_consolidation.py`` consolidated an empty episode store and reported
  a healthy "0 compressed" night while the real 50 MB store was never opened.
* ``session_diary.py`` wrote "no messages" for a day that had 400.

The same phantom dir is the one documented for darwin (see
``tests/test_darwin_phantom_home.py``); darwin was fixed by rejecting any
candidate that is not a real install root. These three nightly scripts had no
such guard.

Run:  pytest scripts/tests/test_nightly_phantom_home.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

TARGETS = (
    REPO / "scripts" / "training" / "memory_consolidation.py",
    REPO / "scripts" / "training" / "session_diary.py",
)


def _load(monkeypatch, path: Path, env_home: str | None):
    """Import *path* under a controlled OPENAMER_HOME.

    The modules resolve their home at import time, so the env must be set
    before the import — hence a fresh module object per case.
    """
    if env_home is None:
        monkeypatch.delenv("OPENAMER_HOME", raising=False)
    else:
        monkeypatch.setenv("OPENAMER_HOME", env_home)
    spec = importlib.util.spec_from_file_location(
        f"phantom_probe_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _home_of(mod) -> Path:
    for attr in ("_HOME", "HOME", "BASE"):
        val = getattr(mod, attr, None)
        if val is not None:
            return Path(val)
    raise AssertionError(f"{mod.__name__} exposes no home attribute")


REAL_HOME_NAME = "openamer-laptop"


@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.stem)
def test_msys_phantom_home_is_rejected(monkeypatch, target):
    """The live bug: MSYS-form scratch dir must not win over the real install."""
    mod = _load(monkeypatch, target, "/c/tmp/oa-home")
    home = _home_of(mod)
    assert home.name == REAL_HOME_NAME, (
        f"{target.name} adopted the scratch dir {home} instead of the real "
        f"install; a nightly run would report success against empty data"
    )
    assert home.is_absolute()


@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.stem)
def test_native_scratch_home_is_rejected(monkeypatch, target, tmp_path):
    """A scratch dir that EXISTS but is not an install must also be refused."""
    scratch = tmp_path / "scratch-home"
    scratch.mkdir()
    mod = _load(monkeypatch, target, str(scratch))
    home = _home_of(mod)
    assert home.name == REAL_HOME_NAME, (
        f"{target.name} adopted the bare scratch dir {home}"
    )
    assert home != scratch


@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.stem)
def test_no_env_falls_back_to_real_install(monkeypatch, target):
    mod = _load(monkeypatch, target, None)
    home = _home_of(mod)
    assert home.name == REAL_HOME_NAME
    assert home.is_absolute()


def test_msys_form_of_the_real_home_is_accepted(monkeypatch):
    """The guard must not be a blanket reject — the correct MSYS form works.

    A normalisation that refuses every ``/c/...`` input would pass the tests
    above while breaking a legitimate shell.
    """
    real = Path.home() / "AppData" / "Local" / REAL_HOME_NAME
    if not real.is_dir():
        pytest.skip(f"real install not present at {real}")
    msys = "/c/" + str(real)[3:].replace("\\", "/")
    mod = _load(monkeypatch, TARGETS[0], msys)
    home = _home_of(mod)
    assert home.name == REAL_HOME_NAME
    assert Path(home) == real
