"""Tests for openamer_cli.a2a.query — peer-to-peer mesh query."""

from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from openamer_cli.a2a.query import (
    PeerAnswer,
    QueryResult,
    query_mesh,
    answer_locally,
    _compute_trust_scores,
    _discover_peer_urls,
    _fallback_answer,
)
from openamer_cli.a2a.trust import TrustStore, Peer
from openamer_cli.a2a.core import IdentityStore, generate_identity


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    """Give each test its own home dir so trust/identity files don't collide."""
    return tmp_path / ".openamer"


@pytest.fixture
def identity(tmp_home: Path) -> IdentityStore:
    return IdentityStore(tmp_home)


@pytest.fixture
def trust_store(tmp_home: Path) -> TrustStore:
    return TrustStore(tmp_home)


@pytest.fixture
def peers(trust_store: TrustStore) -> list[Peer]:
    """Set up two trusted peers with different ages."""
    early = int(time.time()) - 86400 * 30  # 30 days ago
    recent = int(time.time()) - 3600       # 1 hour ago
    p1 = trust_store.add_peer(
        "aaaa1111aaaa1111", "a" * 64, name="old-friend",
    )
    # override added_ts for our test
    p1.added_ts = early
    trust_store._peers[p1.fingerprint] = p1
    p2 = trust_store.add_peer(
        "bbbb2222bbbb2222", "b" * 64, name="new-friend",
    )
    p2.added_ts = recent
    trust_store._peers[p2.fingerprint] = p2
    trust_store._save()
    return [p1, p2]


# ---------------------------------------------------------------------------
# data class tests
# ---------------------------------------------------------------------------

class TestPeerAnswer:
    def test_defaults(self) -> None:
        a = PeerAnswer(peer_fingerprint="fp1234")
        assert a.peer_fingerprint == "fp1234"
        assert a.ok is False
        assert a.trust_score == 0.0
        d = a.to_dict()
        assert d["peer"] == "fp1234"

    def test_to_dict(self) -> None:
        a = PeerAnswer(
            peer_fingerprint="fp1",
            peer_name="node1",
            peer_url="http://localhost:8080",
            ok=True,
            answer="some answer text",
            trust_score=0.9,
            latency_ms=42,
        )
        d = a.to_dict()
        assert d["ok"] is True
        assert d["answer"] == "some answer text"
        assert d["trust_score"] == 0.9
        assert d["latency_ms"] == 42


class TestQueryResult:
    def test_best_answer_with_peers(self) -> None:
        r = QueryResult(question="test")
        r.answers = [
            PeerAnswer(peer_fingerprint="fp1", ok=True, answer="answer1",
                       trust_score=0.8),
            PeerAnswer(peer_fingerprint="fp2", ok=False, error="timeout"),
        ]
        assert r.best_answer() == "answer1"

    def test_best_answer_fallback(self) -> None:
        r = QueryResult(question="test")
        r.local_answer = "local fallback"
        assert r.best_answer() == "local fallback"

    def test_best_answer_none(self) -> None:
        r = QueryResult(question="test")
        assert r.best_answer() is None

    def test_to_dict(self) -> None:
        r = QueryResult(question="what?", peers_contacted=2, peers_answered=1)
        r.answers = [PeerAnswer(peer_fingerprint="fp1", ok=True)]
        d = r.to_dict()
        assert d["question"] == "what?"
        assert d["peers_contacted"] == 2
        assert len(d["answers"]) == 1


# ---------------------------------------------------------------------------
# trust score computation
# ---------------------------------------------------------------------------

class TestTrustScores:
    def test_empty(self) -> None:
        assert _compute_trust_scores([]) == {}

    def test_single_peer(self) -> None:
        p = Peer(fingerprint="fp1", public_key="p" * 64, added_ts=1000)
        scores = _compute_trust_scores([p])
        assert scores["fp1"] == 1.0

    def test_two_peers_oldest_highest(self) -> None:
        p1 = Peer(fingerprint="old", public_key="a" * 64, added_ts=100)
        p2 = Peer(fingerprint="new", public_key="b" * 64, added_ts=200)
        scores = _compute_trust_scores([p1, p2])
        assert scores["old"] == 1.0
        assert scores["new"] == pytest.approx(0.2, abs=0.01)

    def test_three_peers_linear(self) -> None:
        peers = [
            Peer(fingerprint="a", public_key="x" * 64, added_ts=100),
            Peer(fingerprint="b", public_key="y" * 64, added_ts=200),
            Peer(fingerprint="c", public_key="z" * 64, added_ts=300),
        ]
        scores = _compute_trust_scores(peers)
        assert scores["a"] == pytest.approx(1.0, abs=0.01)
        assert scores["c"] == pytest.approx(0.2, abs=0.01)
        # b is in the middle
        assert scores["b"] < scores["a"]
        assert scores["b"] > scores["c"]


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------

class TestFallback:
    def test_fallback_answer(self) -> None:
        ans = _fallback_answer("How do I fix errors?")
        assert "No A2A peers are currently reachable" in ans
        assert "openamer a2a trust list" in ans

    @patch("openamer_cli.a2a.query.Path")
    def test_answer_locally_no_memory(self, mock_path) -> None:
        mock_path.home.return_value = Path(tempfile.mkdtemp())
        ans = answer_locally("test question")
        assert "No A2A peers" in ans


# ---------------------------------------------------------------------------
# integration: query_mesh with mocked transport
# ---------------------------------------------------------------------------

class TestQueryMesh:
    def test_no_peers(self, identity, trust_store) -> None:
        """When there are no peers, should return fallback."""
        result = query_mesh("test question", identity=identity,
                            trust_store=trust_store)
        assert result.peers_contacted == 0
        assert result.peers_answered == 0
        assert "No A2A peers" in result.local_answer

    @patch("openamer_cli.a2a.query.a2a_transport.ask")
    @patch("openamer_cli.a2a.query.fetch_announcement")
    def test_with_mocked_peers(
        self, mock_fetch, mock_ask, identity, trust_store, peers
    ) -> None:
        """Query should contact peers and collect answers."""
        # Mock registry to return an announcement with an endpoint
        ann = MagicMock()
        ann.endpoints = ["http://peer1.local:8080"]
        mock_fetch.return_value = ann

        # Mock ask() to return an answer
        mock_ask.return_value = {
            "ok": True,
            "kind": "ask",
            "result": {"text": "Here is the answer!"},
        }

        result = query_mesh(
            "how to fix X?",
            max_peers=2,
            timeout=30,
            identity=identity,
            trust_store=trust_store,
        )

        assert result.peers_contacted == 2
        assert result.peers_answered == 2
        assert result.answers[0].ok

        # First answer should be from the most-trusted peer (highest score)
        assert result.answers[0].trust_score >= result.answers[-1].trust_score

    @patch("openamer_cli.a2a.query.a2a_transport.ask")
    @patch("openamer_cli.a2a.query.fetch_announcement")
    def test_partial_answers(
        self, mock_fetch, mock_ask, identity, trust_store, peers
    ) -> None:
        """When some peers fail, surviving answers still show."""
        ann = MagicMock()
        ann.endpoints = ["http://peer.local:8080"]
        mock_fetch.return_value = ann

        # First call fails, second succeeds
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("connection refused")
            return {"ok": True, "result": {"text": "the answer"}}

        mock_ask.side_effect = _side_effect

        result = query_mesh(
            "question?",
            max_peers=2,
            timeout=10,
            identity=identity,
            trust_store=trust_store,
        )

        assert result.peers_answered == 1
        assert result.peers_contacted == 2
        ok_count = sum(1 for a in result.answers if a.ok)
        err_count = sum(1 for a in result.answers if not a.ok)
        assert ok_count == 1
        assert err_count == 1
        # OK answer sorts before errors
        assert result.answers[0].ok

    @patch("openamer_cli.a2a.query.a2a_transport.ask")
    @patch("openamer_cli.a2a.query.fetch_announcement")
    def test_all_fail_no_local(
        self, mock_fetch, mock_ask, identity, trust_store, peers
    ) -> None:
        """When all peers fail, falls back to local answer."""
        ann = MagicMock()
        ann.endpoints = ["http://peer.local:8080"]
        mock_fetch.return_value = ann
        mock_ask.side_effect = RuntimeError("timeout")

        result = query_mesh(
            "question?", max_peers=2, timeout=5,
            identity=identity, trust_store=trust_store,
        )
        assert result.peers_answered == 0
        assert result.peers_contacted == 2
        assert "No A2A peers" in result.local_answer

    @patch("openamer_cli.a2a.query.a2a_transport.ask")
    @patch("openamer_cli.a2a.query.fetch_announcement")
    def test_with_peer_urls_map(
        self, mock_fetch, mock_ask, identity, trust_store, peers
    ) -> None:
        """Using a pre-resolved peer_urls map skips registry discovery."""
        mock_ask.return_value = {
            "ok": True,
            "result": {"text": "answer via direct URL"},
        }

        result = query_mesh(
            "question?",
            max_peers=2,
            timeout=10,
            identity=identity,
            trust_store=trust_store,
            peer_urls={
                "aaaa1111aaaa1111": "http://p1.local:8080",
                "bbbb2222bbbb2222": "http://p2.local:8080",
            },
        )

        # Should NOT call fetch_announcement (skipped)
        mock_fetch.assert_not_called()
        assert result.peers_contacted == 2
        assert result.peers_answered == 2


# ---------------------------------------------------------------------------
# discover_peer_urls (unit)
# ---------------------------------------------------------------------------

class TestDiscoverPeerUrls:
    def test_no_peers(self, trust_store) -> None:
        urls = _discover_peer_urls(trust_store, max_peers=5)
        assert urls == []

    @patch("openamer_cli.a2a.query.fetch_announcement")
    def test_discovery_calls_registry(
        self, mock_fetch, trust_store, peers
    ) -> None:
        ann = MagicMock()
        ann.endpoints = ["http://node1.openamer:9090/card"]
        mock_fetch.return_value = ann

        urls = _discover_peer_urls(trust_store, max_peers=5)
        assert len(urls) >= 1
        assert urls[0][1] == "http://node1.openamer:9090/card"


# ---------------------------------------------------------------------------
# CLI integration (via sys.argv)
# ---------------------------------------------------------------------------

class TestCliParser:
    def test_query_parser_args(self) -> None:
        """Verify argparse produces the right namespace for query."""
        import argparse
        from openamer_cli.subcommands.a2a import build_a2a_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        build_a2a_parser(sub)

        # Test basic query
        ns = parser.parse_args(["a2a", "query", "how to fix it?"])
        assert ns.a2a_cmd == "query"
        assert ns.question == "how to fix it?"
        assert ns.local is False
        assert ns.timeout == 60
        assert ns.max_peers == 5

        # Test with --local
        ns = parser.parse_args(["a2a", "query", "--local", "question?"])
        assert ns.local is True

        # Test with --timeout 120
        ns = parser.parse_args(["a2a", "query", "--timeout", "120", "question?"])
        assert ns.timeout == 120
        assert ns.max_peers == 5

        # Test with --max-peers 3
        ns = parser.parse_args(["a2a", "query", "--max-peers", "3", "question?"])
        assert ns.max_peers == 3

        # Test all flags together
        ns = parser.parse_args(
            ["a2a", "query", "--local", "--timeout", "30", "--max-peers", "10",
             "big question?"]
        )
        assert ns.local is True
        assert ns.timeout == 30
        assert ns.max_peers == 10
        assert ns.question == "big question?"


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------

class TestRanking:
    def test_sort_key_answered_before_errors(self) -> None:
        """OK answers sort before errors regardless of trust score."""
        answers = [
            PeerAnswer(peer_fingerprint="high-err", ok=False,
                       error="timeout", trust_score=0.9),
            PeerAnswer(peer_fingerprint="low-ok", ok=True,
                       answer="works", trust_score=0.3),
        ]
        answers.sort(key=lambda a: (0 if a.ok else 1, -a.trust_score, a.latency_ms))
        assert answers[0].ok is True
        assert answers[1].ok is False

    def test_same_status_trust_desc(self) -> None:
        """Within same status, higher trust score comes first."""
        answers = [
            PeerAnswer(peer_fingerprint="low-trust", ok=True, answer="b", trust_score=0.4),
            PeerAnswer(peer_fingerprint="high-trust", ok=True, answer="a", trust_score=0.9),
        ]
        answers.sort(key=lambda a: (0 if a.ok else 1, -a.trust_score, a.latency_ms))
        assert answers[0].peer_fingerprint == "high-trust"

    def test_no_answers_returns_none_via_best_answer(self) -> None:
        r = QueryResult(question="anything")
        assert r.best_answer() is None

    def test_peer_answer_error_empty_answer(self) -> None:
        """A failed peer has empty answer, but error text."""
        a = PeerAnswer(peer_fingerprint="fp", ok=False, error="connection failed")
        assert not a.answer
        assert a.error == "connection failed"