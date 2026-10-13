"""Tests for openamer_cli/a2a/ard_client.py (ARD discovery client).

Hermetic: the network call is not exercised; we cover the request-building and
response-parsing logic + CLI wiring by monkeypatching urllib. The live registry
query is validated separately via a manual run (real results returned).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import ard_client  # noqa: E402


class _FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._payload


def test_search_builds_correct_request(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["method"] = req.get_method()
        return _FakeResp({"results": [], "referrals": []})

    monkeypatch.setattr(ard_client.urllib.request, "urlopen", fake_urlopen)
    ard_client.search("find an MCP server", page_size=7)
    assert captured["method"] == "POST"
    assert captured["body"] == {"query": {"text": "find an MCP server"}, "pageSize": 7}
    assert "huggingface-hf-discover.hf.space/search" in captured["url"]


def test_search_results_returns_empty_on_failure(monkeypatch):
    monkeypatch.setattr(ard_client.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("offline")))
    assert ard_client.search_results("any") == []


def test_search_results_parses(monkeypatch):
    payload = {"results": [{"displayName": "X", "type": "application/ai-skill",
                            "description": "desc", "url": None}],
               "referrals": []}
    monkeypatch.setattr(ard_client.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    res = ard_client.search_results("x")
    assert len(res) == 1
    assert res[0]["displayName"] == "X"


def test_format_result():
    r = {"displayName": "MyAgent", "type": "application/agent",
         "description": "does things", "url": "https://x"}
    s = ard_client.format_result(r)
    assert "MyAgent" in s and "does things" in s


def test_format_result_tolerates_missing_fields():
    s = ard_client.format_result({})
    assert "?" in s