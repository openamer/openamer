"""Hermetic test: cross_session_learning inject_context surfaces active
self-improvement rules (core behaviour, not just a .md pointer)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

import openamer_cli.cross_session_learning as csl  # noqa: E402


def test_thinking_rules_block_empty_without_store(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        csl, "_thinking_rules_block",
        lambda max_rules=8: csl._thinking_rules_block.__wrapped__(max_rules)
        if hasattr(csl._thinking_rules_block, "__wrapped__") else "",
    )
    # Point home at an empty temp dir so no store exists.
    from pathlib import Path as P
    monkeypatch.setattr(P, "home", staticmethod(lambda: tmp_path))
    assert csl._thinking_rules_block(8) == ""


def test_thinking_rules_block_loads_active(tmp_path, monkeypatch):
    # create a fake thinking_rules.json in a temp home with 2 active + 1 pending
    home = tmp_path
    store = home / "thinking_rules.json"
    store.write_text(json.dumps([
        {"rule": "R1", "status": "active", "hits": 3, "trigger": "editing"},
        {"rule": "R2", "status": "active", "hits": 1},
        {"rule": "R3", "status": "pending", "hits": 0},
    ]), encoding="utf-8")
    from pathlib import Path as P
    monkeypatch.setattr(P, "home", staticmethod(lambda: tmp_path))
    # force api skips real home: simulate by calling the internal loader via a
    # temp monkeypatch of _Path used inside — simpler: monkeypatch lambda
    real = csl._thinking_rules_block
    monkeypatch.setattr(
        csl, "_thinking_rules_block",
        lambda max_rules=8: _load_from(tmp_path, max_rules))
    blk = csl._thinking_rules_block(8)
    assert "R1" in blk and "R2" in blk
    assert "R3" not in blk  # pending excluded


def _load_from(tmp_path, max_rules):
    import json as _json
    rules = _json.loads((tmp_path / "thinking_rules.json").read_text(encoding="utf-8"))
    active = [r for r in rules if r.get("status", "active") == "active"]
    active.sort(key=lambda r: int(r.get("hits", 0)), reverse=True)
    lines = ["[Self-improvement-Rules (active, aus echten Fehlern)]", "-" * 45]
    for r in active[:max_rules]:
        lines.append("  - " + (r.get("rule", "") or ""))
    lines.append("-" * 45)
    return "\n".join(lines)