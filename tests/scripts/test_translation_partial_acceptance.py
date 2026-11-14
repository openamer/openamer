"""Contract: one rejected string must not discard the rest of its chunk.

The measured bug: `translate_chunk` was all-or-nothing. A single item the
validator rejects (an unchanged English label, a placeholder slip) threw away
the other nineteen and re-sent the whole batch. Large languages passed often
enough to hide it; Xhosa reported `0/2219 validated literals` across 111 chunks
and stayed at 0% for hours.

These tests pin the fix: accepted items survive, a later lane only fills what is
still missing, and a fully rejected chunk still returns what other items earned.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def fill(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "fill_partial", REPO / "scripts" / "fill_desktop_locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "backend_chain",
                        lambda env: [("lane-a", "u", "-", "m"), ("lane-b", "u", "-", "m")])
    return module


def reply(mapping: dict) -> str:
    return json.dumps(mapping)


def test_rejected_item_does_not_discard_its_chunk(fill, monkeypatch):
    # Lane A: index 0 comes back as unchanged English (rejected), 1 and 2 translated.
    replies = iter([reply({"0": "Error", "1": "Yandisa", "2": "Kwehlulekile"}),
                    reply({"0": "Kwenzeke into engalunganga"})])
    monkeypatch.setattr(fill, "call_model", lambda *a, **k: next(replies))
    items = [("common.error", "Error"),
             ("common.expand", "Expand"),
             ("common.failed", "Failed")]
    out = fill.translate_chunk(items, "Xhosa", {})
    assert out == {"common.expand": "Yandisa",
                   "common.failed": "Kwehlulekile",
                   "common.error": "Kwenzeke into engalunganga"}


def test_second_lane_only_sees_what_is_missing(fill, monkeypatch):
    seen: list[str] = []

    def fake_call(url, model, key, prompt, timeout=240):
        seen.append(prompt)
        if len(seen) == 1:
            return reply({"0": "Yandisa"})          # only index 0 answered
        return reply({"0": "Kwehlulekile"})          # index 0 of the NEW batch

    monkeypatch.setattr(fill, "call_model", fake_call)
    out = fill.translate_chunk([("a", "Expand"), ("b", "Failed")], "Xhosa", {})
    assert out == {"a": "Yandisa", "b": "Kwehlulekile"}
    # The second prompt must not contain the already-translated string again.
    assert "Expand" not in seen[1]


def test_a_lane_that_returns_nothing_keeps_the_others_work(fill, monkeypatch):
    replies = iter(["not json at all", reply({"0": "Yandisa", "1": "Kwehlulekile"})])
    monkeypatch.setattr(fill, "call_model", lambda *a, **k: next(replies))
    out = fill.translate_chunk([("a", "Expand"), ("b", "Failed")], "Xhosa", {})
    assert out == {"a": "Yandisa", "b": "Kwehlulekile"}


def test_all_rejected_returns_empty_not_a_fake_success(fill, monkeypatch):
    monkeypatch.setattr(fill, "call_model",
                        lambda *a, **k: reply({"0": "Expand", "1": "Failed"}))
    assert fill.translate_chunk([("a", "Expand"), ("b", "Failed")], "Xhosa", {}) == {}
