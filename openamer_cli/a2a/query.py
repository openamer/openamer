"""openamer_cli.a2a.query — peer-to-peer query across the A2A swarm mesh.

Sends a question to known peers, collects answers, and ranks them by peer
trust score. Uses the existing relay/transport mechanism.

CLI usage (after adding to the parser):
    openamer a2a query "question text"
    openamer a2a query --local "question text"
    openamer a2a query --timeout 120 "question text"
    openamer a2a query --max-peers 3 "question text"
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from openamer_cli.a2a.core import IdentityStore
from openamer_cli.a2a.trust import TrustStore, Peer
from openamer_cli.a2a.registry import fetch_announcement
from openamer_cli.a2a import transport as a2a_transport


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------

@dataclass
class PeerAnswer:
    """A single answer returned by one peer."""

    peer_fingerprint: str
    peer_name: str = ""
    peer_url: str = ""
    ok: bool = False
    answer: str = ""
    error: str = ""
    trust_score: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "peer": self.peer_fingerprint,
            "name": self.peer_name,
            "url": self.peer_url,
            "ok": self.ok,
            "answer": self.answer,
            "error": self.error,
            "trust_score": self.trust_score,
            "latency_ms": self.latency_ms,
        }


@dataclass
class QueryResult:
    """Result of a mesh query — ranked answers + metadata."""

    question: str
    answers: list[PeerAnswer] = field(default_factory=list)
    peers_contacted: int = 0
    peers_answered: int = 0
    total_time_ms: int = 0
    local_answer: str = ""

    def best_answer(self) -> Optional[str]:
        """Return the highest-ranked answer content, or None."""
        for a in self.answers:
            if a.ok and a.answer:
                return a.answer
        return self.local_answer or None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answers": [a.to_dict() for a in self.answers],
            "peers_contacted": self.peers_contacted,
            "peers_answered": self.peers_answered,
            "total_time_ms": self.total_time_ms,
            "local_answer": self.local_answer,
        }


# ---------------------------------------------------------------------------
# peer discovery helpers
# ---------------------------------------------------------------------------

def _trust_score(peer: Peer) -> float:
    """Compute a trust score for a peer.

    Earlier-added peers get a higher score (they are more established).
    Score is a float in [0.0, 1.0] based on age relative to the oldest peer.
    """
    # If we have more than one peer, use relative age; otherwise baseline
    return 0.5


def _compute_trust_scores(peers: list[Peer]) -> dict[str, float]:
    """Assign trust scores to a list of peers, oldest-first ranking.

    The peer with the earliest ``added_ts`` gets the highest score (1.0).
    Scores linearly decrease to a minimum of 0.2.
    """
    if not peers:
        return {}
    # sort by added_ts ascending (oldest first = most trusted)
    sorted_peers = sorted(peers, key=lambda p: p.added_ts or 0)
    n = len(sorted_peers)
    scores: dict[str, float] = {}
    if n == 1:
        scores[sorted_peers[0].fingerprint] = 1.0
    else:
        # linear from 1.0 down to 0.2
        step = (1.0 - 0.2) / (n - 1) if n > 1 else 0.0
        for i, p in enumerate(sorted_peers):
            scores[p.fingerprint] = 1.0 - i * step
    return scores


def _discover_peer_urls(
    trust_store: TrustStore,
    *,
    max_peers: int = 5,
    timeout: float = 20.0,
) -> list[tuple[Peer, str]]:
    """Discover reachable URLs for trusted peers via the GitHub registry.

    Returns a list of ``(peer, url)`` pairs, limited to ``max_peers``.
    Only peers that have at least one reachable endpoint are included.
    """
    all_peers = trust_store.peers()
    # sort by trust score descending (already oldest-first)
    sorted_peers = sorted(all_peers, key=lambda p: p.added_ts or 0)

    discovered: list[tuple[Peer, str]] = []
    for peer in sorted_peers[:max_peers]:
        # Try fetching the signed announcement from the GitHub registry
        try:
            ann = fetch_announcement(peer.fingerprint, timeout=timeout)
            if ann and ann.endpoints:
                for ep in ann.endpoints:
                    url = ep.rstrip("/")
                    if url.startswith("http://") or url.startswith("https://"):
                        discovered.append((peer, url))
                        break  # one URL per peer is enough
        except Exception:
            pass
    return discovered


# ---------------------------------------------------------------------------
# main query function
# ---------------------------------------------------------------------------

def query_mesh(
    question: str,
    *,
    max_peers: int = 5,
    timeout: int = 60,
    identity: Optional[IdentityStore] = None,
    trust_store: Optional[TrustStore] = None,
    peer_urls: Optional[dict[str, str]] = None,
) -> QueryResult:
    """Send a question to known A2A peers and collect their answers.

    Parameters
    ----------
    question : str
        The question to ask the mesh.
    max_peers : int
        Maximum number of peers to contact (default 5).
    timeout : int
        Per-peer timeout in seconds (default 60).
    identity : IdentityStore, optional
        Local node identity. Auto-loaded if omitted.
    trust_store : TrustStore, optional
        Trust store with known peers. Auto-loaded if omitted.
    peer_urls : dict[str, str], optional
        Pre-resolved ``{fingerprint: url}`` map. When provided, skips
        registry-based URL discovery.

    Returns
    -------
    QueryResult
        Ranked answers (best first) plus metadata.
    """
    start = time.monotonic()
    identity = identity or IdentityStore()
    trust_store = trust_store or TrustStore()

    result = QueryResult(question=question)
    local_ident = identity.ensure_identity()

    # 1. Get known peers and assign trust scores
    all_peers = trust_store.peers()
    if not all_peers:
        result.local_answer = _fallback_answer(question)
        result.total_time_ms = int((time.monotonic() - start) * 1000)
        return result

    trust_scores = _compute_trust_scores(all_peers)

    # 2. Resolve peer URLs
    if peer_urls:
        # caller provided URLs — use them directly
        peer_url_map = peer_urls
    else:
        peer_url_map = {}
        discovered = _discover_peer_urls(trust_store, max_peers=max_peers)
        for peer, url in discovered:
            peer_url_map[peer.fingerprint] = url

    if not peer_url_map:
        # No reachable peers via HTTP — try relay-based discovery (best-effort)
        result.local_answer = _fallback_answer(question)
        result.total_time_ms = int((time.monotonic() - start) * 1000)
        return result

    # 3. Fan-out question to peers
    import threading
    from queue import Queue

    answers_list: list[PeerAnswer] = []
    lock = threading.Lock()

    def _ask_one(fp: str, url: str) -> None:
        peer_obj = trust_store.trusted(fp)
        peer_name = peer_obj.name if peer_obj else ""
        t0 = time.monotonic()
        try:
            resp = a2a_transport.ask(
                identity, trust_store, url,
                question, kind="ask", timeout=float(timeout),
            )
            latency = int((time.monotonic() - t0) * 1000)
            ok = bool(resp.get("ok"))
            answer_raw = resp.get("result", {})
            answer_text = (
                json.dumps(answer_raw, ensure_ascii=False)
                if isinstance(answer_raw, dict)
                else str(answer_raw)
            )
            err = resp.get("error", "") if not ok else ""
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            ok = False
            answer_text = ""
            err = str(e)

        pa = PeerAnswer(
            peer_fingerprint=fp,
            peer_name=peer_name,
            peer_url=url,
            ok=ok,
            answer=answer_text,
            error=err,
            trust_score=trust_scores.get(fp, 0.0),
            latency_ms=latency,
        )
        with lock:
            answers_list.append(pa)

    threads = []
    for fp, url in peer_url_map.items():
        t = threading.Thread(target=_ask_one, args=(fp, url), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=max(timeout, 5))

    # 4. Rank answers by trust score (descending), then by latency (ascending)
    #    Trusted peers with answers come first; errors sink to the bottom.
    def _sort_key(a: PeerAnswer) -> tuple:
        # (answered ? 0 : 1, -trust_score, latency_ms)
        return (0 if a.ok else 1, -a.trust_score, a.latency_ms)

    answers_list.sort(key=_sort_key)
    result.answers = answers_list
    result.peers_contacted = len(answers_list)
    result.peers_answered = sum(1 for a in answers_list if a.ok)
    result.total_time_ms = int((time.monotonic() - start) * 1000)

    # 5. If nothing from peers, try local answer as fallback
    if result.peers_answered == 0:
        result.local_answer = _fallback_answer(question)

    return result


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------

def _fallback_answer(question: str) -> str:
    """Produce a helpful local fallback when no peers are reachable."""
    return (
        "No A2A peers are currently reachable. "
        "Try `openamer a2a trust list` to see your trusted peers, "
        "or run `openamer a2a status` to verify your node identity. "
        "To add a peer: `openamer a2a trust add <fingerprint> <public_key>`."
    )


def answer_locally(question: str) -> str:
    """Answer a question using the local brain / insights memory when no peers
    are available.

    Checks the local mesh-learning memory for relevant insights.
    """
    import pathlib
    mem = pathlib.Path.home() / ".openamer" / "MEMORY-official-mesh.md"
    if not mem.exists():
        return _fallback_answer(question)

    from openamer_cli.a2a import meshlearn as _ml
    try:
        text = mem.read_text(encoding="utf-8", errors="replace")
        # Look for insights matching the question keywords
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        hits = []
        for line in text.splitlines():
            if line.startswith("#mesh:"):
                for kw in keywords:
                    if kw in line.lower():
                        hits.append(line)
                        break
        if hits:
            return "Local mesh memory suggests:\n" + "\n".join(hits[:5])
        return _fallback_answer(question)
    except Exception:
        return _fallback_answer(question)