"""Tests for ``openamer plugins search`` (GitHub plugin discovery)."""

from __future__ import annotations

from unittest import mock

from openamer_cli import plugins_cmd


def _fake_urlopen(topic_items, name_items):
    """Return a urlopen mock that serves topic results then name results."""

    class _Resp:
        def __init__(self, items):
            self._items = items

        def read(self):
            import json

            return json.dumps({"total_count": len(self._items), "items": self._items}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=15):
        url = req.full_url
        # The query is URL-encoded, so "topic:openamer-plugin" becomes
        # "topic%3Aopenamer-plugin".
        if "topic%3Aopenamer-plugin" in url:
            return _Resp(topic_items)
        return _Resp(name_items)

    return _urlopen


def test_search_returns_topic_results():
    items = [
        {
            "full_name": "acme/openamer-plugin-foo",
            "description": "A foo plugin",
            "stargazers_count": 12,
            "html_url": "https://github.com/acme/openamer-plugin-foo",
        }
    ]
    with mock.patch("urllib.request.urlopen", _fake_urlopen(items, [])):
        results = plugins_cmd._github_plugin_search("", 10)
    assert len(results) == 1
    assert results[0]["full_name"] == "acme/openamer-plugin-foo"
    assert results[0]["stargazers_count"] == 12


def test_search_falls_back_to_name_when_topic_empty():
    items = [
        {
            "full_name": "acme/openamer-plugin-bar",
            "description": "A bar plugin",
            "stargazers_count": 3,
            "html_url": "https://github.com/acme/openamer-plugin-bar",
        }
    ]
    with mock.patch("urllib.request.urlopen", _fake_urlopen([], items)):
        results = plugins_cmd._github_plugin_search("", 10)
    assert len(results) == 1
    assert results[0]["full_name"] == "acme/openamer-plugin-bar"


def test_search_returns_empty_on_network_error():
    def _boom(req, timeout=15):
        raise OSError("network down")

    with mock.patch("urllib.request.urlopen", _boom):
        results = plugins_cmd._github_plugin_search("", 10)
    assert results == []
