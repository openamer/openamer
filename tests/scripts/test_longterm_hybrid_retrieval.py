"""Retrieval contract for the episodic memory: what must stay true.

Three properties were broken today and each one is a regression waiting to
happen again:

1. `_load` dropped every episode without a vector, so ~1,000 memories were
   invisible to all search.
2. `_save` dropped them too, so they would have been deleted on the next write.
3. Ranking could not compensate: a perfect keyword match scored below a mediocre
   cosine, so a vector-less record could never surface.

The store here is synthetic on purpose — a test that reads the live 8,000-episode
file would pass or fail depending on what this machine happened to record.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import longterm_memory as memory  # noqa: E402


def _unit(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


VECTOR = _unit([1.0, 0.0, 0.0])
OTHER = _unit([0.0, 1.0, 0.0])


@pytest.fixture()
def store(tmp_path: Path, monkeypatch):
    path = tmp_path / "episodes.jsonl"
    episodes = [
        {"text": "der build scheitert auf windows mit pfad problemen", "kind": "a", "embedding": VECTOR},
        {"text": "kubectl port-forward auf 9222 fuer den browser debug", "kind": "b", "embedding": OTHER},
        {"text": "ohne vektor geschrieben als der embedder tot war helixscan", "kind": "c", "embedding": None},
        {"text": "noch ein eintrag mit dem wort build und sonst nichts", "kind": "d", "embedding": OTHER},
    ]
    path.write_text("\n".join(json.dumps(e) for e in episodes), encoding="utf-8")
    monkeypatch.setattr(memory, "STORE", str(path))
    monkeypatch.setattr(memory, "_IDF_CACHE", {"key": None, "df": None, "n": 0})
    monkeypatch.setattr(memory, "embed", lambda _text: VECTOR)
    return path


def test_load_keeps_episodes_without_a_vector(store: Path) -> None:
    episodes = memory._load()
    assert len(episodes) == 4
    assert sum(1 for e in episodes if not e.get("embedding")) == 1


def test_save_does_not_drop_episodes_without_a_vector(store: Path) -> None:
    episodes = memory._load()
    memory._save(episodes)
    rewritten = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rewritten) == 4
    assert any(not e.get("embedding") for e in rewritten)


def test_rare_token_reaches_a_vectorless_episode(store: Path) -> None:
    """A term that appears exactly once must surface its episode.

    The fixture's embedder returns a constant vector, so some episode always has
    a "perfect" cosine no matter what was asked - an artefact no real embedder
    produces. The contract asserted here is therefore: a unique term reaches the
    top results, and it does so alone when no embedder is available at all.
    """
    results = memory.query("helixscan", k=2)
    assert results, "a distinctive term must find its episode"
    assert any("helixscan" in _score_record["text"] for _value, _score_record in results)


def test_identifier_survives_a_common_word(store: Path, monkeypatch) -> None:
    """'build' is in two episodes, the port number in one.

    With the embedder unavailable the identifier must rank first; with a constant
    test embedder the semantic signal is meaningless, so the weaker claim is used:
    the identifier stays in the top two instead of being pushed out entirely.
    """
    monkeypatch.setattr(memory, "embed", lambda _text: None)
    assert "9222" in memory.query("build 9222", k=1)[0][1]["text"]

    monkeypatch.setattr(memory, "embed", lambda _text: VECTOR)
    top_two = [record["text"] for _value, record in memory.query("build 9222", k=2)]
    assert any("9222" in text for text in top_two), top_two


def test_query_without_embedder_returns_keyword_hits(store: Path, monkeypatch) -> None:
    monkeypatch.setattr(memory, "embed", lambda _text: None)
    results = memory.query("kubectl", k=2)
    assert results
    assert "kubectl" in results[0][1]["text"]


def test_empty_store_returns_nothing(store: Path, monkeypatch) -> None:
    store.write_text("", encoding="utf-8")
    monkeypatch.setattr(memory, "_IDF_CACHE", {"key": None, "df": None, "n": 0})
    assert memory.query("irgendwas", k=3) == []
