#!/usr/bin/env python3
"""Regression test: a DRY RUN must not write the world-model store.

Bug (observed live 2026-09-19): ``consolidate(dry_run=True)`` is documented as
"report only, no writes", and the tests do isolate the EPISODE side by
redirecting ``mc.EPISODES``/``mc.META_STATE`` to a temp dir. But the tail of
``consolidate()`` calls ``wm.prune()``/``wm.repair_store()``, which resolve their
own path from the ``OPENAMER_HOME`` module constant -- and ``prune()`` had no
``dry_run`` parameter at all. So a DRY RUN still pruned and rewrote the live
7.6 MB store.

Measured on a controlled fixture before the fix: 10 edges in, 9 edges out, sha
changed, ``result["world_model_pruned"] == {"removed": 1, "kept": 9}``. Every
test run of ``test_memory_consolidation.py`` was therefore touching production
data.

Run:  pytest scripts/training/test_world_model_dry_run.py
"""
import datetime
import hashlib
import json
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import memory_consolidation as mc
import world_model as wm


def _fixture(tmp):
    """10 edges, of which exactly 2 are near-duplicates (< 30% removal)."""
    edges = []
    for i in range(8):                      # mutually orthogonal -> all kept
        v = [0.0] * wm.DIM
        v[i] = 1.0
        edges.append({"ts": f"2026-01-0{i+1}T00:00:00", "schema_version": 2,
                      "kind": "fact", "cause": f"c{i}", "effect": f"e{i}",
                      "embedding": v, "embed_ok": True})
    base, twin = [0.1] * wm.DIM, [0.1] * wm.DIM
    twin[0] += 1e-7                         # cosine > 0.97 -> one duplicate
    edges.append({"ts": "2026-02-01T00:00:00", "schema_version": 2, "kind": "fact",
                  "cause": "dup1", "effect": "d1", "embedding": base, "embed_ok": True})
    edges.append({"ts": "2026-02-02T00:00:00", "schema_version": 2, "kind": "fact",
                  "cause": "dup2", "effect": "d2", "embedding": twin, "embed_ok": True})
    store = pathlib.Path(tmp) / "world_model.jsonl"
    store.write_text("\n".join(json.dumps(e) for e in edges) + "\n", encoding="utf-8")
    return store


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _redirect(monkeypatch, tmp, store):
    monkeypatch.setattr(wm, "WM", str(store))
    monkeypatch.setattr(mc, "EPISODES", str(pathlib.Path(tmp) / "e.jsonl"))
    monkeypatch.setattr(mc, "ARCHIVE", str(pathlib.Path(tmp) / "a.jsonl"))
    monkeypatch.setattr(mc, "META_STATE", str(pathlib.Path(tmp) / "m.json"))
    monkeypatch.setattr(mc, "HIERARCHY", str(pathlib.Path(tmp) / "h.json"))
    mc._save(mc.EPISODES, [{
        "ts": (datetime.datetime.now() - datetime.timedelta(days=45)).isoformat(),
        "kind": "brain_user", "text": "old", "meta": {},
    }])


def test_dry_run_does_not_write_the_store(monkeypatch, tmp_path):
    store = _fixture(tmp_path)
    _redirect(monkeypatch, tmp_path, store)
    before = _sha(store)

    result = mc.consolidate(dry_run=True)

    assert _sha(store) == before, (
        "consolidate(dry_run=True) rewrote the world-model store"
    )
    # The decision must still be REPORTED -- dry-run skips the write, not the work.
    assert result.get("world_model_pruned", {}).get("removed") == 1, (
        "dry run must still report what it WOULD prune"
    )


def test_real_run_still_prunes(monkeypatch, tmp_path):
    """The guard must not disable pruning itself (the fix is a narrowing)."""
    store = _fixture(tmp_path)
    _redirect(monkeypatch, tmp_path, store)
    before_lines = len(store.read_text(encoding="utf-8").strip().splitlines())

    mc.consolidate(dry_run=False)

    after_lines = len(store.read_text(encoding="utf-8").strip().splitlines())
    assert after_lines == before_lines - 1, (
        f"a real run must still prune the near-duplicate ({before_lines} -> {after_lines})"
    )


def test_prune_dry_run_matches_real_decision(monkeypatch, tmp_path):
    """dry_run=True and dry_run=False must agree on removed/kept counts."""
    store = _fixture(tmp_path)
    monkeypatch.setattr(wm, "WM", str(store))
    dry = wm.prune(dry_run=True)
    wet = wm.prune(dry_run=False)
    assert (dry["removed"], dry["kept"]) == (wet["removed"], wet["kept"])


def test_prune_decision_matches_per_pair_cosine(monkeypatch, tmp_path):
    """The normalise-once fast path must keep the exact >0.97 boundary.

    Guards the optimisation: cos(a,b) == dot(normalise(a), normalise(b)) is an
    identity, but an off-by-epsilon reimplementation would silently shift which
    edges count as duplicates.
    """
    store = _fixture(tmp_path)
    monkeypatch.setattr(wm, "WM", str(store))
    edges = wm._load()

    # Reference: the original per-pair algorithm, verbatim.
    kept, removed, seen = [], 0, []
    for e in edges:
        emb = e.get("embedding") or []
        if not emb or not e.get("embed_ok"):
            kept.append(e)
            continue
        if any(wm._cosine(emb, c[0]) > 0.97 for c in seen):
            removed += 1
        else:
            seen.append((emb, [e]))
            kept.append(e)

    got = wm.prune(dry_run=True)
    assert got["removed"] == removed and got["kept"] == len(kept)
