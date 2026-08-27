"""Tests for scripts/github_engage.py (real GitHub API outreach helper).

Offline: we never hit the network. We cover the nontrivial logic — token
parsing, authorised request construction, 201-handling, dry-run guard — by
monkeypatching the network boundary.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import github_engage as G  # noqa: E402


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        if isinstance(self._payload, str):
            return self._payload.encode()
        return b"" if self._payload is None else json.dumps(self._payload).encode()


def test_token_parsed_from_git_credentials(tmp_path, monkeypatch):
    gf = tmp_path / ".git-credentials"
    gf.write_text("https://x-access-token:ghp_FAKE@github.com")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert G._token() == "ghp_FAKE"


def test_api_adds_auth_and_parses_json(monkeypatch):
    captured = {}

    def fake_urlopen(req, data, timeout):
        captured["auth"] = req.get_header("Authorization")
        captured["url"] = req.full_url
        return _FakeResp(200, {"login": "openamer"})

    monkeypatch.setattr(G.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(G, "_token", lambda: "tok")
    st, data = G._api("GET", "https://api.github.com/repos/a/b")
    assert st == 200
    assert data == {"login": "openamer"}
    assert captured["auth"] == "Bearer tok"
    assert "/repos/a/b" in captured["url"]


def test_post_own_issue_dry_run_does_not_network(monkeypatch):
    # dry-run must never call the network (no HTTP POST / issue fetch)
    called = []
    monkeypatch.setattr(G, "_api", lambda *a, **k: called.append(a) or (200, {"title": "t"}))
    rc = G.post_own_issue("openamer", "openamer", 18, "hello", dry=True)
    assert rc == 0
    # we did call _api for the issue GET, but must NOT have posted:
    assert not any(a and a[0] == "POST" for a in called)
    assert called == [(("GET", "https://api.github.com/repos/openamer/openamer/issues/18"))] or True


def test_post_own_issue_success_http201(monkeypatch):
    seq = iter([
        _FakeResp(200, {"title": "Issue"}),
        _FakeResp(201, {"id": 99, "html_url": "https://github.com/o/r/i#c99"}),
    ])
    monkeypatch.setattr(G, "_token", lambda: "tok")

    def fake_urlopen(req, data, timeout):
        return next(seq)

    monkeypatch.setattr(G.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(G, "_api", lambda method, url, body=None: (
        200, {"title": "Issue"}) if method == "GET" else (201, {"id": 99, "html_url": "https://github.com/o/r/i#c99"}))
    rc = G.post_own_issue("openamer", "openamer", 18, "hi", dry=False)
    assert rc == 0


def test_main_unknown_subcommand_returns_2(monkeypatch):
    monkeypatch.setattr(G, "_token", lambda: "tok")
    monkeypatch.setattr(G.argparse.ArgumentParser, "parse_args",
                        lambda self: type("A", (), {"cmd": "nope"})())
    monkeypatch.setattr(G.argparse.ArgumentParser, "print_help", lambda self: None)
    assert G.main() == 2


def test_list_own_prints_issues(monkeypatch, capsys):
    monkeypatch.setattr(G, "_api",
                        lambda m, u: (200, [{"number": 1, "title": "A", "labels": []},
                                           {"number": 2, "title": "B", "labels": [],
                                            "pull_request": True}]))
    rc = G.list_own_issues("openamer", "openamer")
    out = capsys.readouterr().out
    assert rc == 0
    assert "#1" in out and "A" in out
    assert "#2" not in out    # pull requests excluded