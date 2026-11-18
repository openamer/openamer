"""The chain decides when the work is done, so its pending count must be right.

Measured 2026-11-17: counting on `share` claimed all 185 locales were still
pending, because a locale can be 99.29 % "different from English" while having
zero real gaps (`el`: share 0.9929, real_gaps 0, share_real 1.0). Running eight
two-hour rounds against a wrong count means twelve hours of wasted work.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "i18n_backfill_chain.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("i18n_backfill_chain", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_state(tmp_path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"locales": rows}), encoding="utf-8")
    return p


def test_real_gap_counts_as_pending(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "STATE", write_state(tmp_path, [
        {"locale": "xx", "share": 0.99, "share_real": 0.99, "real_gaps": 3},
    ]))
    assert mod.pending_count() == 1


def test_el_case_is_not_pending(mod, tmp_path, monkeypatch):
    """share 0.9929 but no real gap: translated, just not character-identical."""
    monkeypatch.setattr(mod, "STATE", write_state(tmp_path, [
        {"locale": "el", "share": 0.9929, "share_real": 1.0, "real_gaps": 0},
    ]))
    assert mod.pending_count() == 0


def test_share_real_falls_back_to_share(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "STATE", write_state(tmp_path, [
        {"locale": "aa", "share": 0.5},
        {"locale": "bb", "share": 1.0},
    ]))
    assert mod.pending_count() == 1


def test_mixed_set_counts_only_the_unfinished(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "STATE", write_state(tmp_path, [
        {"locale": "el", "share": 0.99, "share_real": 1.0, "real_gaps": 0},
        {"locale": "ik", "share": 0.38, "share_real": 0.38, "real_gaps": 900},
        {"locale": "de", "share": 1.0, "share_real": 1.0, "real_gaps": 0},
    ]))
    assert mod.pending_count() == 1


def test_missing_state_file_gives_none(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "STATE", tmp_path / "absent.json")
    assert mod.pending_count() is None


def test_broken_state_file_gives_none(mod, tmp_path, monkeypatch):
    p = tmp_path / "state.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(mod, "STATE", p)
    assert mod.pending_count() is None
