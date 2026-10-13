"""Tests für den Vector Memory Store."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from openamer_cli.vector_memory import (
    MemoryEntry,
    VectorMemoryStore,
    cosine_similarity,
    _tokenize,
    _idf,
    _tfidf_vector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """VectorMemoryStore mit temporärem Verzeichnis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        s = VectorMemoryStore(vector_dir=Path(tmpdir))
        yield s


# ---------------------------------------------------------------------------
# TF-IDF Core Tests
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_simple_text(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_german_text(self):
        tokens = _tokenize("Überraschung! Das ist ein Test.")
        assert "überraschung" in tokens
        assert "test" in tokens

    def test_empty_text(self):
        assert _tokenize("") == []

    def test_special_chars(self):
        tokens = _tokenize("foo.bar, baz_qux! @#$")
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz_qux" in tokens


class TestIDF:
    def test_single_doc(self):
        corpus = [["hello", "world"]]
        idf = _idf(corpus)
        assert "hello" in idf
        assert idf["hello"] > 0

    def test_multi_doc(self):
        corpus = [["hello", "world"], ["hello", "foo"]]
        idf = _idf(corpus)
        assert idf["hello"] < idf["world"]  # hello is more common → lower IDF

    def test_empty_corpus(self):
        assert _idf([]) == {}


class TestTFIDFVector:
    def test_vector_shape(self):
        idf = {"hello": 2.0, "world": 3.0}
        vec = _tfidf_vector(["hello"], idf)
        assert vec.shape == (2,)
        assert vec[0] > 0  # hello has TF > 0
        assert vec[1] == 0.0  # world has TF = 0

    def test_empty_tokens(self):
        idf = {"hello": 2.0}
        vec = _tfidf_vector([], idf)
        assert np.all(vec == 0.0)


class TestCosineSimilarity:
    def test_identical(self):
        a = np.array([1.0, 0.0, 1.0])
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_zero_vector(self):
        a = np.array([1.0, 0.0])
        z = np.zeros(2)
        assert cosine_similarity(a, z) == 0.0


# ---------------------------------------------------------------------------
# VectorMemoryStore Tests
# ---------------------------------------------------------------------------


class TestVectorMemoryStore:
    def test_store_and_search(self, store):
        store.store("t1", "Python ist eine großartige Programmiersprache")
        store.store("t2", "Der Himmel ist blau und die Sonne scheint")
        store.store("t3", "TypeScript ist auch eine gute Sprache für Webentwicklung")

        results = store.search("Python Programmierung", top_k=2)
        assert len(results) == 2
        assert results[0][0].key == "t1"  # Python most relevant

    def test_store_persists(self, store):
        store.store("p1", "Persistenz Test Content")
        store_path = store.vector_dir
        assert (store_path / "index.json").exists()
        assert (store_path / "vectors.npy").exists()
        assert (store_path / "documents.json").exists()

    def test_reload(self, store):
        store.store("r1", "Reload Test")
        # Neuen Store mit gleichem Pfad erstellen
        store2 = VectorMemoryStore(vector_dir=store.vector_dir)
        results = store2.search("reload", top_k=5)
        assert len(results) >= 1

    def test_get_stats(self, store):
        stats = store.get_stats()
        assert "total_entries" in stats
        assert stats["total_entries"] == 0

        store.store("s1", "Stats Test")
        stats = store.get_stats()
        assert stats["total_entries"] == 1
        assert stats["vector_dimensions"] > 0

    def test_delete_entry(self, store):
        entry = store.store("d1", "Delete Test")
        assert len(store.get_all_entries()) == 1
        assert store.delete_entry(entry.id) is True
        assert len(store.get_all_entries()) == 0

    def test_delete_nonexistent(self, store):
        assert store.delete_entry("nonexistent") is False

    def test_search_empty_store(self, store):
        results = store.search("anything")
        assert results == []

    def test_compress(self, store):
        for i in range(5):
            store.store(f"c{i}", f"Content number {i} for testing")
        assert len(store.get_all_entries()) == 5
        removed = store.compress(max_entries=3)
        assert removed == 2
        assert len(store.get_all_entries()) == 3

    def test_store_with_metadata(self, store):
        meta = {"source": "test", "tags": ["python", "vector"]}
        entry = store.store("meta1", "Metadata test", metadata=meta)
        assert entry.metadata == meta

    def test_search_semantic_similarity(self, store):
        # Ähnliche Konzepte sollten höhere Scores haben
        store.store("prog1", "Python is a programming language")
        store.store("prog2", "JavaScript is used for web development")
        store.store("weather", "It is sunny and warm today")

        results = store.search("coding software development", top_k=3)
        # Die Programmierung-Einträge sollten vor dem Wetter-Eintrag kommen
        top_keys = [r[0].key for r in results]
        assert top_keys[0] in ("prog1", "prog2")

    def test_multiple_search_calls(self, store):
        store.store("m1", "First memory entry")
        store.store("m2", "Second memory entry")
        store.store("m3", "Third memory entry about something else")

        # Erster Search
        r1 = store.search("memory entry", top_k=2)
        assert len(r1) == 2

        # Zweiter Search sollte auch funktionieren (nicht corrupt)
        r2 = store.search("something else", top_k=1)
        assert len(r2) == 1
        assert r2[0][0].key == "m3"