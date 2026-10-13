"""Tests for the episodic store (scripts/longterm_memory.py).

The store is the organ that records every experience. It had written nothing for
17 days, and two defects let that happen while every status stayed green:

  * the module could not even be imported (`Path` used, never imported), and
  * `_save()` wrote back only what `_load()` returned, so it DELETED every record
    `_load()` had skipped - 2898 of 3065 live records.

Both are pinned here, because both failed silently.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MODULE = REPO / "scripts" / "longterm_memory.py"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """The module, pointed at a throwaway store. Never the real one."""
    spec = importlib.util.spec_from_file_location("longterm_memory", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # a NameError here is the import bug returning
    target = tmp_path / "longterm_episodes.jsonl"
    monkeypatch.setattr(mod, "STORE", str(target))
    return mod, target


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )


def _read(path: Path) -> list[dict]:
    """Parsed records only - same tolerance as the module under test."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def test_the_module_imports(store):
    """Regression: `Path.home()` was called with no `pathlib` import.

    That raised NameError at import time, so the repo copy of this module was
    dead - every invocation crashed on line 20 before doing anything.
    """
    mod, _ = store
    assert mod.STORE


def test_load_skips_records_without_text_and_embedding(store):
    """A foreign/heartbeat line must never reach index/query/stats."""
    mod, target = store
    _write(target, [
        {"ts": "x", "kind": "compressed", "text": "no embedding here"},
        {"ts": "x", "kind": "brain_user", "text": "real", "embedding": [0.1, 0.2]},
        {"ts": "x", "kind": "heartbeat"},
    ])

    loaded = mod._load()

    assert [e["text"] for e in loaded] == ["real"]


def test_save_does_not_delete_records_load_skipped(store):
    """THE data-loss bug: saving what `_load()` returned erased everything else.

    Measured before the fix: 2898 of 3065 records were kind="compressed" with no
    embedding, so one `index` run would have wiped 3 MB of real episodes.
    """
    mod, target = store
    _write(target, [
        {"ts": "x", "kind": "compressed", "text": "keep-1"},
        {"ts": "x", "kind": "brain_user", "text": "real", "embedding": [0.1]},
        {"ts": "x", "kind": "compressed", "text": "keep-2"},
    ])

    mod._save(mod._load())

    after = _read(target)
    assert len(after) == 3, "a save must round-trip the whole file"
    assert sum(1 for r in after if r.get("kind") == "compressed") == 2


def test_save_is_idempotent(store):
    """Two round-trips must not grow the file - a duplicate is also a corruption."""
    mod, target = store
    _write(target, [
        {"ts": "x", "kind": "compressed", "text": "keep"},
        {"ts": "x", "kind": "brain_user", "text": "real", "embedding": [0.1]},
    ])

    mod._save(mod._load())
    first = _read(target)
    mod._save(mod._load())

    assert _read(target) == first


def test_an_unparseable_line_is_preserved(store):
    """A corrupt line is data too: repairing the store must not drop it silently."""
    mod, target = store
    _write(target, [
        {"ts": "x", "kind": "brain_user", "text": "real", "embedding": [0.1]},
    ])
    with target.open("a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")

    mod._save(mod._load())

    assert "{not json at all" in target.read_text(encoding="utf-8")
    assert len(_read(target)) == 1
